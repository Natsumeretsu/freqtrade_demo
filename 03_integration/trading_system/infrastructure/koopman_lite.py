from __future__ import annotations

"""
koopman_lite.py - 基于 PyDMD 的 Koopman 本征模态提取与预测

核心思想：
- Koopman 算子将非线性动力学提升到无限维空间，在那里动力学是线性的
- 本征函数 φᵢ 满足：φᵢ(f(x)) = λᵢ · φᵢ(x)
- 预测公式：x(t) ≈ Σ φᵢ(x₀) · λᵢᵗ · vᵢ（本征模态的线性组合）

输出因子：
- koop_mode_{i}_amp: 第 i 个本征模态的振幅（重要性）
- koop_mode_{i}_freq: 第 i 个本征模态的频率（周期性）
- koop_mode_{i}_decay: 第 i 个本征模态的衰减率（稳定性）
- koop_pred_ret_h{N}: 基于本征模态线性组合的 N 步预测收益
- koop_spectral_radius: 谱半径（最大本征值模，系统稳定性指标）
- koop_reconstruction_error: 重建误差（模型拟合质量）
"""

import math
from typing import Iterable

import numpy as np
import pandas as pd
from pydmd import HODMD


def _extract_eigenmode_features(
    eigs: np.ndarray,
    modes: np.ndarray,
    dynamics: np.ndarray,
    dt: float = 1.0,
    n_modes: int = 3,
) -> dict[str, float]:
    """
    从 DMD 结果提取本征模态特征。

    Args:
        eigs: 本征值数组 (n_eigs,)
        modes: 本征模态矩阵 (n_features, n_eigs)
        dynamics: 动力学系数 (n_eigs,)
        dt: 时间步长
        n_modes: 提取前 n 个最重要的模态

    Returns:
        特征字典
    """
    features: dict[str, float] = {}

    if eigs is None or len(eigs) == 0:
        return features

    # 谱半径
    spectral_radius = float(np.max(np.abs(eigs)))
    features["koop_spectral_radius"] = spectral_radius

    # 按模态重要性（振幅）排序
    if dynamics is not None and len(dynamics) > 0:
        importance = np.abs(dynamics)
    else:
        importance = np.abs(eigs)

    sorted_idx = np.argsort(importance)[::-1]

    for i in range(min(n_modes, len(eigs))):
        idx = sorted_idx[i]
        eig = eigs[idx]

        # 振幅（模态重要性）
        amp = float(importance[idx]) if i < len(importance) else 0.0
        features[f"koop_mode_{i}_amp"] = amp

        # 从本征值提取频率和衰减率
        # λ = exp((σ + iω)·dt) => σ = ln|λ|/dt, ω = arg(λ)/dt
        if abs(eig) > 1e-10:
            decay = float(np.log(np.abs(eig)) / dt)  # 衰减率（负=稳定）
            freq = float(np.angle(eig) / (2 * np.pi * dt))  # 频率
        else:
            decay = float("-inf")
            freq = 0.0

        features[f"koop_mode_{i}_freq"] = freq
        features[f"koop_mode_{i}_decay"] = decay

    return features


def compute_koopman_lite_features(
    *,
    close: pd.Series,
    window: int,
    embed_dim: int,
    stride: int,
    ridge: float,
    pred_horizons: Iterable[int] | None,
    fft_window: int,  # 保留接口兼容，但不再单独使用
    fft_topk: int,  # 保留接口兼容
    n_modes: int = 3,
) -> pd.DataFrame:
    """
    使用 PyDMD HODMD 提取 Koopman 本征模态特征。

    HODMD (Higher Order DMD) 通过延迟嵌入自动处理时间序列，
    等价于在延迟坐标空间中做 DMD。

    Args:
        close: 收盘价序列
        window: 滚动窗口长度
        embed_dim: 延迟嵌入维度（HODMD 的 d 参数）
        stride: 更新步长
        ridge: 正则化参数（映射到 svd_rank 截断）
        pred_horizons: 预测步数列表
        fft_window: 保留接口兼容
        fft_topk: 保留接口兼容
        n_modes: 提取的本征模态数量

    Returns:
        特征 DataFrame，与 close 对齐
    """
    if close is None or close.empty:
        return pd.DataFrame()

    w = int(window)
    d = int(embed_dim)
    st = max(1, int(stride))

    if w < 32:
        raise ValueError("window 过小：建议 >= 128")
    if d < 2:
        raise ValueError("embed_dim 必须 >= 2")

    h_list = sorted({int(h) for h in (pred_horizons or []) if int(h) > 0})

    # 转换为 log-return
    c = close.astype("float64").replace(0.0, np.nan)
    logp = np.log(c).replace([np.inf, -np.inf], np.nan)
    logr = logp.diff()

    # 构建输出列
    cols: list[str] = ["koop_spectral_radius", "koop_reconstruction_error"]
    for i in range(n_modes):
        cols.extend([
            f"koop_mode_{i}_amp",
            f"koop_mode_{i}_freq",
            f"koop_mode_{i}_decay",
        ])
    for h in h_list:
        cols.append(f"koop_pred_ret_h{h}")

    out = pd.DataFrame(index=logp.index, columns=cols, dtype="float64")

    lr = logr.astype("float64").dropna()
    min_len = w + d + (max(h_list) if h_list else 0) + 5
    if len(lr) < min_len:
        return out

    y = lr.to_numpy(dtype="float64")
    idx = lr.index

    # 滚动窗口计算
    for end in range(w - 1, len(y), st):
        start = end - w + 1
        segment = y[start:end + 1]

        if len(segment) < d + 10:
            continue

        try:
            # 使用 HODMD：自动处理延迟嵌入
            # svd_rank 控制保留的模态数量（类似正则化）
            svd_rank = min(n_modes + 2, d, len(segment) // 2)
            hodmd = HODMD(svd_rank=svd_rank, d=d)
            hodmd.fit(segment.reshape(1, -1))

            ts = idx[end]

            # 提取本征模态特征
            eigs = hodmd.eigs
            modes = hodmd.modes
            dynamics = hodmd.dynamics

            mode_features = _extract_eigenmode_features(
                eigs, modes, dynamics[0] if dynamics is not None else None,
                dt=1.0, n_modes=n_modes
            )

            for k, v in mode_features.items():
                if k in out.columns:
                    out.at[ts, k] = v

            # 重建误差
            try:
                reconstructed = hodmd.reconstructed_data
                if reconstructed is not None:
                    recon = reconstructed.real.flatten()
                    orig = segment[-len(recon):]
                    error = float(np.sqrt(np.mean((orig - recon) ** 2)))
                    out.at[ts, "koop_reconstruction_error"] = error
            except Exception:
                pass

            # 基于本征模态的预测
            # 预测公式：x(t+h) = Σ bᵢ · λᵢʰ · φᵢ
            if h_list and eigs is not None and len(eigs) > 0:
                for h in h_list:
                    try:
                        # 使用 HODMD 的预测功能
                        hodmd.dmd_time["tend"] = len(segment) + h - 1
                        forecast = hodmd.reconstructed_data
                        if forecast is not None:
                            pred_vals = forecast.real.flatten()
                            if len(pred_vals) > len(segment):
                                # 累计预测收益
                                future_returns = pred_vals[len(segment):len(segment) + h]
                                cum_ret = float(np.sum(future_returns))
                                cum_ret = np.clip(cum_ret, -20.0, 20.0)
                                out.at[ts, f"koop_pred_ret_h{h}"] = float(math.exp(cum_ret) - 1.0)
                    except Exception:
                        pass

        except Exception:
            continue

    return out.sort_index().ffill()
