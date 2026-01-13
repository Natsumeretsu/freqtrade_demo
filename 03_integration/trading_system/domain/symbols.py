from __future__ import annotations

"""
symbols.py - 交易对/文件名/研究符号的统一转换

目标：把 Freqtrade 的 pair（可能带 futures 的 ":USDT" 后缀）映射到本项目常用的
文件名与研究符号（例如 BTC_USDT）。

位置说明：
- 本模块属于领域层（domain），稳定且与框架无关。
"""


def freqtrade_pair_to_spot_pair(pair: str) -> str:
    """
    将 Freqtrade 交易对转换为“现货格式”的 pair（去掉 futures 的 :USDT 后缀）。

    示例：
    - "BTC/USDT:USDT" -> "BTC/USDT"
    - "BTC/USDT" -> "BTC/USDT"
    """
    s = str(pair or "").strip()
    if not s:
        return ""
    return s.split(":", 1)[0].strip()


def freqtrade_pair_to_symbol(pair: str) -> str:
    """
    将 Freqtrade 交易对转换为文件/研究常用符号：用 "_" 替换 "/"，并去掉 futures 后缀。

    示例：
    - "BTC/USDT:USDT" -> "BTC_USDT"
    - "ETH/USDT" -> "ETH_USDT"
    """
    spot = freqtrade_pair_to_spot_pair(pair)
    return spot.replace("/", "_")


def freqtrade_pair_to_data_filename(pair: str, timeframe: str) -> str:
    """
    将交易对转换为本仓库常见的 feather 数据文件名：<SYMBOL>-<TF>.feather
    """
    sym = freqtrade_pair_to_symbol(pair)
    tf = str(timeframe or "").strip()
    if not sym or not tf:
        return ""
    return f"{sym}-{tf}.feather"
