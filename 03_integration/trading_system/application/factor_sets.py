from __future__ import annotations

"""
factor_sets.py - 因子清单配置化（Zipline Pipeline 风格的“声明式依赖”）

目标：
- 策略只声明“需要哪些因子”（配置驱动），不再在代码里硬编码一长串列表
- 因子名支持简单模板：使用 `{var}` 占位符（例如 ema_short_{ema_short_len}）
- 渲染后交给 factor_engine 统一计算
"""

import re
from typing import Any

from trading_system.infrastructure.config_loader import get_config


_PLACEHOLDER_RE = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)}")
_INCLUDE_PREFIX = "@"


def get_factor_templates(set_name: str) -> list[str]:
    """
    从 04_shared/config/factors.yaml 读取因子模板列表。

    约定：
    - YAML 文件名必须为 factors.yaml（ConfigManager 会以 stem=factors 加载到 configs['factors']）
    - 路径：factors.factor_sets.<set_name> → list[str]
    """
    name = str(set_name or "").strip()
    if not name:
        return []

    cfg = get_config()
    return _expand_templates(cfg=cfg, set_name=name, visiting=set())


def _expand_templates(*, cfg, set_name: str, visiting: set[str]) -> list[str]:
    """
    递归展开模板（支持引用公共集合）。

    语法：
    - 列表项以 '@' 开头：表示插入另一个 factor_set（例如 '@cta_core'）
    """
    name = str(set_name or "").strip()
    if not name:
        return []
    if name in visiting:
        # 防止循环引用导致死递归
        return []

    raw = cfg.get(f"factors.factor_sets.{name}", None)
    if not isinstance(raw, list):
        return []

    visiting2 = set(visiting)
    visiting2.add(name)

    out: list[str] = []
    for item in raw:
        s = str(item).strip()
        if not s:
            continue
        if s.startswith(_INCLUDE_PREFIX):
            ref = str(s[len(_INCLUDE_PREFIX) :]).strip()
            if not ref:
                continue
            out.extend(_expand_templates(cfg=cfg, set_name=ref, visiting=visiting2))
            continue
        out.append(s)
    return out


def render_factor_names(templates: list[str], variables: dict[str, Any]) -> list[str]:
    """
    将模板列表渲染为最终因子名列表（去重、保持顺序）。

    规则：
    - '@xxx' 引用在 get_factor_templates() 阶段已展开；这里不再处理
    - 模板中的占位符缺失 / 为 None / 数值<=0 → 跳过该模板
    - 渲染失败 → 跳过
    """
    if not templates:
        return []

    vars_map = dict(variables or {})
    rendered: list[str] = []

    for tpl in templates:
        s = str(tpl).strip()
        if not s:
            continue

        keys = _PLACEHOLDER_RE.findall(s)
        ok = True
        for k in keys:
            v = vars_map.get(k)
            if v is None:
                ok = False
                break
            if isinstance(v, (int, float)):
                try:
                    if int(v) <= 0:
                        ok = False
                        break
                except Exception:
                    ok = False
                    break

        if not ok:
            continue

        try:
            out = s.format(**vars_map).strip()
        except Exception:
            continue

        if out:
            rendered.append(out)

    # 去重但保持顺序
    seen: set[str] = set()
    uniq: list[str] = []
    for n in rendered:
        if n in seen:
            continue
        seen.add(n)
        uniq.append(n)
    return uniq
