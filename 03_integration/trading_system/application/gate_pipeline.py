from __future__ import annotations

"""
gate_pipeline.py - 门控组合与“漏斗统计”（funnel）

用途：
- 将一组 Gate（布尔条件）组合为最终信号（AND/OR 由策略决定；本模块聚焦 AND 漏斗）
- 提供可观测性：每个 Gate 的通过率、边际淘汰量（卡口贡献），便于消融/定位瓶颈

设计原则：
- 纯函数 + 数据结构，可单测
- 不依赖 Freqtrade；只处理 pandas Series/DataFrame
"""

from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class GateFunnelRow:
    name: str
    pass_rate: float
    survivors_rate: float
    survivors: int
    total: int
    marginal_drop: int
    marginal_drop_rate: float

    def to_dict(self) -> dict:
        return asdict(self)


def _const_bool(index: pd.Index, value: bool) -> pd.Series:
    return pd.Series(bool(value), index=index, dtype="bool")


def _as_bool_series(mask: object, index: pd.Index, *, fillna: bool) -> pd.Series:
    if isinstance(mask, (bool, np.bool_)):
        return _const_bool(index, bool(mask))
    if isinstance(mask, pd.Series):
        s = mask.reindex(index)
        if fillna:
            s = s.fillna(False)
        return s.astype("bool")
    raise TypeError(f"不支持的 gate mask 类型：{type(mask).__name__}")


def combine_gates(
    gates: Sequence[tuple[str, object]],
    *,
    index: pd.Index,
    fillna: bool = True,
) -> pd.Series:
    """
    将多个 gate 以 AND 方式组合为最终 mask。

    - gates: [(name, mask)]，mask 可以是 pd.Series 或 bool
    - index: 目标 index（用于对齐与常量展开）
    """
    out = _const_bool(index, True)
    for _, mask in gates:
        out = out & _as_bool_series(mask, index, fillna=fillna)
    return out


def gate_funnel(
    gates: Sequence[tuple[str, object]],
    *,
    index: pd.Index,
    base_mask: pd.Series | None = None,
    fillna: bool = True,
) -> tuple[pd.Series, list[GateFunnelRow]]:
    """
    计算 gate 漏斗统计（AND 顺序敏感）：返回 (final_mask, rows)。

    说明：
    - pass_rate：该 gate 自身为 True 的比例
    - survivors_rate：应用到当前 gate 后，仍存活的比例（相对 total）
    - marginal_drop：该 gate 相对上一个 gate 额外淘汰的数量
    - marginal_drop_rate：相对上一步 survivors 的淘汰比例
    """
    total = int(len(index))
    if total <= 0:
        return pd.Series(dtype="bool"), []

    survivors = base_mask.reindex(index).astype("bool") if isinstance(base_mask, pd.Series) else _const_bool(index, True)
    if fillna:
        survivors = survivors.fillna(False)

    rows: list[GateFunnelRow] = []
    for name, mask in gates:
        g = _as_bool_series(mask, index, fillna=fillna)

        prev = int(survivors.sum())
        survivors = survivors & g
        now = int(survivors.sum())

        drop = int(prev - now)
        drop_rate = float(drop / prev) if prev > 0 else 0.0

        pass_rate = float(g.mean()) if total > 0 else 0.0
        survive_rate = float(now / total) if total > 0 else 0.0

        rows.append(
            GateFunnelRow(
                name=str(name),
                pass_rate=pass_rate,
                survivors_rate=survive_rate,
                survivors=now,
                total=total,
                marginal_drop=drop,
                marginal_drop_rate=drop_rate,
            )
        )

    return survivors, rows


def top_bottlenecks(rows: Iterable[GateFunnelRow], *, top_k: int = 5) -> list[GateFunnelRow]:
    """
    找到“边际淘汰量”最大的 gate（用于快速定位瓶颈）。
    """
    k = int(top_k)
    if k <= 0:
        return []
    items = [r for r in rows if isinstance(r, GateFunnelRow)]
    items.sort(key=lambda r: int(r.marginal_drop), reverse=True)
    return items[:k]


def render_gate_funnel_summary(rows: Sequence[GateFunnelRow], *, top_k: int = 3) -> str:
    """
    将 gate 漏斗统计渲染为一行摘要，便于日志输出。

    示例：
    - final=12/240 (5.0%), bottlenecks=[macro:-80 (66.7%), adx:-20 (25.0%)]

    注意：
    - bottleneck 的百分比是“相对上一步 survivors 的边际淘汰率”。
    """
    if not rows:
        return "empty"

    total = int(rows[0].total)
    final = int(rows[-1].survivors)
    final_rate = float(rows[-1].survivors_rate)

    k = int(top_k)
    bottlenecks = top_bottlenecks(rows, top_k=k if k > 0 else 0)
    if bottlenecks:
        parts = [f"{r.name}:-{int(r.marginal_drop)} ({float(r.marginal_drop_rate):.1%})" for r in bottlenecks]
        bottleneck_text = ", ".join(parts)
    else:
        bottleneck_text = "n/a"

    return f"final={final}/{total} ({final_rate:.1%}), bottlenecks=[{bottleneck_text}]"
