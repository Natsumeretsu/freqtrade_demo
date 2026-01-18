"""
因子分析模块

提供基于 Alphalens 的统一因子分析接口。
"""

from .alphalens_adapter import convert_to_alphalens_format
from .unified_analyzer import FactorAnalyzer

__all__ = [
    'convert_to_alphalens_format',
    'FactorAnalyzer',
]
