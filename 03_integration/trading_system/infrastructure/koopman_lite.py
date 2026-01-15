from __future__ import annotations

"""
koopman_lite.py - Koopa/Koopman 思路的轻量实现（无 torch 依赖）

本模块是“研究脚本”与“策略/服务侧在线计算”的共享实现，用于保证口径一致：
- scripts/qlib/koopman_lite.py：离线批量生成额外因子
- trading_system.infrastructure.factor_engines.*：策略侧按需在线计算同名因子

实现目标：
- 在滚动窗口上估计局部线性算子（DMD/eDMD 的 ridge 版本），输出：
  - Koopman 算子谱半径（稳定性/体制）
  - one-step 拟合误差（可拟合性/噪声强度）
  - 多步预测的累计收益（可选）
- 用 FFT 做“时不变/时变”拆分的近似，输出：
  - 低通趋势斜率
  - 高通残差
  - 低通能量占比

注意：
- 为控制计算量，默认按 stride 频率更新算子/FFT，并对输出做 ffill，保持“在线可用”。
- 该实现只依赖 close 序列；如果未来要扩展到多维观测（订单簿/成交量等），再升级到 EDMD 字典即可。
"""

import math
from typing import Iterable

import numpy as np
import pandas as pd


def _fft_lowpass_stats(x: np.ndarray, *, topk: int) -> tuple[float, float, float, float]:
    """
    在窗口 x 上做简单 FFT 低通重建，返回：
    - low_last: 低通重建值（最后一个点）
    - high_last: 高通残差（x_last - low_last）
    - low_slope: 低通斜率（low_last - low_prev）
    - energy_ratio: 低通能量占比（0~1）
    """
    v = np.asarray(x, dtype="float64")
    if v.ndim != 1 or len(v) < 8:
        return float("nan"), float("nan"), float("nan"), float("nan")

    m = float(np.nanmean(v))
    z = v - m
    z = np.where(np.isfinite(z), z, 0.0)

    spec = np.fft.rfft(z)
    amp = np.abs(spec)
    if len(amp) <= 2:
        return float("nan"), float("nan"), float("nan"), float("nan")

    k = int(topk)
    if k <= 0:
        return float("nan"), float("nan"), float("nan"), float("nan")

    # 排除 DC（0 频），挑能量最大的 TopK 频率分量
    idx = np.arange(1, len(amp))
    order = idx[np.argsort(amp[1:])[::-1]]
    keep = order[: min(k, len(order))]

    filt = np.zeros_like(spec)
    filt[keep] = spec[keep]

    low = np.fft.irfft(filt, n=len(z)) + m
    if len(low) < 2:
        return float("nan"), float("nan"), float("nan"), float("nan")

    low_last = float(low[-1])
    high_last = float(v[-1] - low_last)
    low_slope = float(low[-1] - low[-2])

    e_all = float(np.sum(np.abs(spec) ** 2))
    e_keep = float(np.sum(np.abs(filt) ** 2))
    energy_ratio = (e_keep / e_all) if (math.isfinite(e_all) and e_all > 0 and math.isfinite(e_keep)) else float("nan")
    return low_last, high_last, low_slope, float(energy_ratio)


def compute_koopman_lite_features(
    *,
    close: pd.Series,
    window: int,
    embed_dim: int,
    stride: int,
    ridge: float,
    pred_horizons: Iterable[int] | None,
    fft_window: int,
    fft_topk: int,
) -> pd.DataFrame:
    """
    由 close 序列生成 Koopa-lite 特征（与 close 对齐）。

    - pred_horizons：例如 [1, 4]，会输出 koop_pred_ret_h1 / koop_pred_ret_h4
    - FFT 与 Koopman 默认共用同一套 stride 更新频率（输出 ffill）
    """
    if close is None or close.empty:
        return pd.DataFrame()

    w = int(window)
    m = int(embed_dim)
    st = int(stride)
    lam = float(ridge)
    fft_w = int(fft_window)
    fft_k = int(fft_topk)

    if w < 32:
        raise ValueError("window 过小：建议 >= 128")
    if m < 2:
        raise ValueError("embed_dim 必须 >= 2")
    if st <= 0:
        st = 1
    if not math.isfinite(lam) or lam < 0:
        lam = 0.0

    h_list = sorted({int(h) for h in (pred_horizons or []) if int(h) > 0})

    # 统一到 log(price) / log-return
    c = close.astype("float64").replace(0.0, np.nan)
    logp = np.log(c).replace([np.inf, -np.inf], np.nan)
    logr = logp.diff()

    cols: list[str] = []
    has_fft = (fft_w > 0) and (fft_k > 0)
    if has_fft:
        cols.extend(["fft_hp_logp", "fft_lp_slope", "fft_lp_energy_ratio"])
    cols.extend(["koop_spectral_radius", "koop_fit_rmse"])
    for h in h_list:
        cols.append(f"koop_pred_ret_h{int(h)}")

    out = pd.DataFrame(index=logp.index, columns=cols, dtype="float64")

    lr = logr.astype("float64").dropna()
    if len(lr) < (w + m + (max(h_list) if h_list else 0) + 5):
        return out

    y = lr.to_numpy(dtype="float64")
    idx = lr.index

    try:
        swv = np.lib.stride_tricks.sliding_window_view  # type: ignore[attr-defined]
    except Exception as e:
        raise RuntimeError("numpy 版本过旧：缺少 sliding_window_view，无法生成延迟嵌入") from e

    states = swv(y, m)[:, ::-1]
    n_states = int(states.shape[0])

    start_end = int(w - 1)
    if start_end >= n_states:
        return out

    I = np.eye(m, dtype="float64")

    for end in range(start_end, n_states, st):
        s0 = end - w + 1
        win = states[s0 : end + 1]  # (w, m)
        if win.shape[0] < 3:
            continue

        X = win[:-1].T  # (m, w-1)
        Y = win[1:].T  # (m, w-1)

        Xt = X @ X.T
        try:
            K = (Y @ X.T) @ np.linalg.inv(Xt + (lam * I))
        except Exception:
            continue

        eig = np.linalg.eigvals(K)
        rho = float(np.max(np.abs(eig))) if eig is not None and len(eig) > 0 else float("nan")

        try:
            Y_hat = K @ X
            err = (Y[0, :] - Y_hat[0, :]).astype("float64")
            rmse = float(np.sqrt(float(np.nanmean(err * err))))
        except Exception:
            rmse = float("nan")

        ts = idx[end + m - 1]

        if has_fft:
            lp = logp.loc[:ts].astype("float64").dropna()
            if len(lp) >= fft_w:
                seg = lp.to_numpy(dtype="float64")[-fft_w:]
                _, hp, slope, er = _fft_lowpass_stats(seg, topk=fft_k)
                out.at[ts, "fft_hp_logp"] = float(hp)
                out.at[ts, "fft_lp_slope"] = float(slope)
                out.at[ts, "fft_lp_energy_ratio"] = float(er)

        out.at[ts, "koop_spectral_radius"] = float(rho)
        out.at[ts, "koop_fit_rmse"] = float(rmse)

        if h_list:
            z = win[-1].astype("float64")
            for h in h_list:
                z2 = z.copy()
                cum_lr = 0.0
                ok = True
                for _ in range(int(h)):
                    try:
                        z2 = (K @ z2).astype("float64")
                    except Exception:
                        ok = False
                        break
                    if not np.isfinite(float(z2[0])):
                        ok = False
                        break
                    cum_lr += float(z2[0])
                if not ok:
                    continue
                x2 = float(np.clip(cum_lr, -20.0, 20.0))
                out.at[ts, f"koop_pred_ret_h{int(h)}"] = float(math.exp(x2) - 1.0)

    return out.sort_index().ffill()

