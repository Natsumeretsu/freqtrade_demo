"""模式检测器

检测数据访问模式并预测下一次访问。

创建日期: 2026-01-17
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from .tracker import AccessTracker

logger = logging.getLogger(__name__)


@dataclass
class AccessPattern:
    """访问模式

    Attributes:
        pattern_type: 模式类型
        confidence: 置信度
        next_keys: 预测的下一个键
    """
    pattern_type: str
    confidence: float
    next_keys: List[str]


class PatternDetector:
    """模式检测器

    分析访问历史，检测访问模式并预测下一次访问。
    """

    def __init__(self, tracker: AccessTracker, min_confidence: float = 0.7):
        """初始化检测器

        Args:
            tracker: 访问跟踪器
            min_confidence: 最小置信度阈值
        """
        self.tracker = tracker
        self.min_confidence = min_confidence

    def detect_sequential(self, window: int = 5) -> Optional[AccessPattern]:
        """检测顺序访问模式

        Args:
            window: 检测窗口大小

        Returns:
            访问模式（如果检测到）
        """
        history = self.tracker.get_history(limit=window)
        if len(history) < 2:
            return None

        # 检查是否为顺序访问（键名递增）
        keys = [record.key for record in history]
        
        # 简单的顺序检测：检查键是否包含递增的数字
        try:
            # 提取键中的数字部分
            numbers = []
            for key in keys:
                # 尝试从键中提取数字
                num_str = ''.join(c for c in key if c.isdigit())
                if num_str:
                    numbers.append(int(num_str))
            
            if len(numbers) >= 2:
                # 检查是否递增
                is_sequential = all(numbers[i] < numbers[i+1] for i in range(len(numbers)-1))
                if is_sequential:
                    # 预测下一个键
                    last_key = keys[-1]
                    last_num = numbers[-1]
                    next_key = last_key.replace(str(last_num), str(last_num + 1))
                    
                    confidence = min(0.9, len(numbers) / window)
                    return AccessPattern(
                        pattern_type="sequential",
                        confidence=confidence,
                        next_keys=[next_key]
                    )
        except Exception as e:
            logger.debug(f"顺序检测失败: {e}")
        
        return None

    def detect_associated(self, window: int = 10) -> Optional[AccessPattern]:
        """检测关联访问模式

        Args:
            window: 检测窗口大小

        Returns:
            访问模式（如果检测到）
        """
        history = self.tracker.get_history(limit=window)
        if len(history) < 3:
            return None

        # 统计键的共现关系
        keys = [record.key for record in history]
        last_key = keys[-1]
        
        # 查找与最后一个键经常一起出现的键
        associations = {}
        for i in range(len(keys) - 1):
            if keys[i] == last_key:
                next_key = keys[i + 1]
                associations[next_key] = associations.get(next_key, 0) + 1
        
        if associations:
            # 找到最常关联的键
            best_key = max(associations.items(), key=lambda x: x[1])
            confidence = best_key[1] / len(keys)
            
            if confidence >= self.min_confidence:
                return AccessPattern(
                    pattern_type="associated",
                    confidence=confidence,
                    next_keys=[best_key[0]]
                )
        
        return None

    def predict_next(self) -> Optional[AccessPattern]:
        """预测下一次访问

        Returns:
            访问模式（如果检测到）
        """
        # 优先检测顺序模式
        pattern = self.detect_sequential()
        if pattern and pattern.confidence >= self.min_confidence:
            logger.debug(f"检测到顺序模式，置信度: {pattern.confidence:.2f}")
            return pattern
        
        # 检测关联模式
        pattern = self.detect_associated()
        if pattern and pattern.confidence >= self.min_confidence:
            logger.debug(f"检测到关联模式，置信度: {pattern.confidence:.2f}")
            return pattern
        
        return None
