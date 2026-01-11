"""
format_utils.py - 格式化与 IO 工具

提供百分比格式化、JSON 读写等通用功能。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def fmt_pct(v: float, with_sign: bool = True) -> str:
    """
    格式化为百分比字符串。

    Args:
        v: 数值（0.1 表示 10%）
        with_sign: 是否显示正负号

    Returns:
        格式化字符串，如 "+10.00%" 或 "10.00%"
    """
    if not np.isfinite(v):
        return ""
    fmt = f"{v * 100.0:+.2f}%" if with_sign else f"{v * 100.0:.2f}%"
    return fmt


def fmt_pct_from_ratio(v: float) -> str:
    """
    从比率格式化为百分比（v=1.1 表示 +10%）。

    Args:
        v: 比率值（1.0 为基准）

    Returns:
        格式化字符串，如 "+10.00%"
    """
    return fmt_pct(v - 1.0)


def fmt_float(v: float, digits: int = 4) -> str:
    """
    格式化浮点数。

    Args:
        v: 数值
        digits: 小数位数

    Returns:
        格式化字符串
    """
    if not np.isfinite(v):
        return ""
    return f"{v:.{digits}f}"


def fmt_ratio(v: float) -> str:
    """
    格式化比率值（带百分比说明）。

    Args:
        v: 比率值

    Returns:
        格式化字符串，如 "1.100（+10.00%）"
    """
    if not np.isfinite(v):
        return "-"
    return f"{v:.3f}（{fmt_pct(v - 1.0)}）"


def read_json(path: Path) -> dict[str, Any]:
    """
    读取 JSON 文件。

    Args:
        path: 文件路径

    Returns:
        解析后的字典
    """
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    """
    写入 JSON 文件。

    Args:
        path: 文件路径
        data: 要写入的数据
        indent: 缩进空格数
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=indent) + "\n",
        encoding="utf-8",
    )
