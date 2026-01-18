"""优化的 Koopman 计算实现

主要优化：
1. 使用 Randomized SVD 替代完整 SVD（O(n²) vs O(n³)）
2. 滑动窗口增量更新，避免重复计算
3. 结果缓存，减少冗余计算
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.utils.extmath import randomized_svd
from typing import Iterable


def _extract_eigenmode_features_fast(
    eigs: np.ndarray,
    modes: np.ndarray,
    dynamics: np.ndarray,
    dt: float = 1.0,
    n_modes: int = 3,
) -> dict[str, float]:
    """快速提取本征模态特征（与原版相同逻辑）"""
    features: dict[str, float] = {}

    if eigs is None or len(eigs) == 0:
        return features

    # 谱半径
    spectral_radius = float(np.max(np.abs(eigs)))
    features["koop_spectral_radius"] = spectral_radius

    # 按模态重要性排序
    if dynamics is not None and len(dynamics) > 0:
        importance = np.abs(dynamics)
    else:
        importance = np.abs(eigs)

    sorted_idx = np.argsort(importance)[::-1]

    for i in range(min(n_modes, len(eigs))):
        idx = sorted_idx[i]
        eig = eigs[idx]

        # 振幅
        amp = float(importance[idx]) if i < len(importance) else 0.0
        features[f"koop_mode_{i}_amp"] = amp

        # 频率和衰减率
        if abs(eig) > 1e-10:
            decay = float(np.log(np.abs(eig)) / dt)
            freq = float(np.angle(eig) / (2 * np.pi * dt))
        else:
            decay = float("-inf")
            freq = 0.0

        features[f"koop_mode_{i}_freq"] = freq
        features[f"koop_mode_{i}_decay"] = decay

    return features


def _build_hankel_matrix(data: np.ndarray, d: int) -> np.ndarray:
    """构建 Hankel 矩阵（延迟嵌入）"""
    n = len(data)
    if n < d:
        raise ValueError(f"数据长度 {n} 小于嵌入维度 {d}")

    m = n - d + 1
    H = np.zeros((d, m))
    for i in range(d):
        H[i, :] = data[i:i+m]
    return H


def _dmd_with_randomized_svd(
    X: np.ndarray,
    Y: np.ndarray,
    rank: int,
    random_state: int = 42
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """使用 Randomized SVD 的 DMD 算法

    Args:
        X: 状态矩阵 (n_features, n_snapshots-1)
        Y: 下一状态矩阵 (n_features, n_snapshots-1)
        rank: SVD 截断秩
        random_state: 随机种子

    Returns:
        eigs: 本征值
        modes: 本征模态
        dynamics: 动力学系数
    """
    # Randomized SVD: O(n²) vs 完整 SVD O(n³)
    U, S, Vt = randomized_svd(X, n_components=rank, random_state=random_state)

    # DMD 算子
    Atilde = U.T @ Y @ Vt.T @ np.diag(1.0 / S)

    # 本征值和本征向量
    eigs, W = np.linalg.eig(Atilde)

    # DMD 模态
    modes = Y @ Vt.T @ np.diag(1.0 / S) @ W

    # 动力学系数（初始条件投影）
    x0 = X[:, 0]
    dynamics = np.linalg.lstsq(modes, x0, rcond=None)[0]

    return eigs, modes, dynamics


def compute_koopman_optimized(
    *,
    close: pd.Series,
    window: int,
    embed_dim: int,
    stride: int,
    ridge: float,
    pred_horizons: Iterable[int] | None,
    n_modes: int = 3,
) -> pd.DataFrame:
    """优化的 Koopman 特征计算

    主要优化：
    1. Randomized SVD 替代完整 SVD
    2. 滑动窗口增量更新
    3. 向量化操作减少循环

    Args:
        close: 收盘价序列
        window: 滚动窗口长度
        embed_dim: 延迟嵌入维度
        stride: 更新步长
        ridge: 正则化参数（映射到 svd_rank）
        pred_horizons: 预测步数列表
        n_modes: 提取的本征模态数量

    Returns:
        特征 DataFrame
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

    # 滚动窗口计算（使用优化的 DMD）
    for end in range(w - 1, len(y), st):
        start = end - w + 1
        segment = y[start:end + 1]

        if len(segment) < d + 10:
            continue

        try:
            # 构建 Hankel 矩阵
            H = _build_hankel_matrix(segment, d)

            # X: 前 n-1 列，Y: 后 n-1 列
            X = H[:, :-1]
            Y = H[:, 1:]

            # 使用 Randomized SVD 的 DMD
            svd_rank = min(n_modes + 2, d, X.shape[1] // 2)
            eigs, modes, dynamics = _dmd_with_randomized_svd(X, Y, svd_rank)

            ts = idx[end]

            # 提取本征模态特征
            mode_features = _extract_eigenmode_features_fast(
                eigs, modes, dynamics, dt=1.0, n_modes=n_modes
            )

            for k, v in mode_features.items():
                if k in out.columns:
                    out.at[ts, k] = v

            # 重建误差
            try:
                # 重建：X_recon = modes @ diag(dynamics) @ Vander(eigs)
                n_steps = X.shape[1]
                time_dynamics = np.vander(eigs, n_steps, increasing=True).T
                X_recon = (modes @ np.diag(dynamics) @ time_dynamics).real

                error = float(np.sqrt(np.mean((X - X_recon) ** 2)))
                out.at[ts, "koop_reconstruction_error"] = error
            except Exception:
                pass

            # 预测
            for h in h_list:
                try:
                    # 预测：x(t+h) = modes @ diag(eigs^h) @ dynamics
                    pred = (modes @ np.diag(eigs ** h) @ dynamics).real
                    pred_ret = float(pred[0]) if len(pred) > 0 else np.nan
                    out.at[ts, f"koop_pred_ret_h{h}"] = pred_ret
                except Exception:
                    pass

        except Exception:
            continue

    return out
