# Qlib + Freqtrade 框架重构实施计划

更新日期：2026-01-17

## 执行摘要

本文档是《Qlib + Freqtrade 框架全方位优化分析报告》的配套实施计划，提供详细的技术设计和执行步骤。

**目标**：
- 性能提升 50-70%
- 测试覆盖率达到 80%
- 代码重复减少 30%
- 解决依赖风险

**执行周期**：7-10 周

---

## P0 任务清单（必须完成）

### P0.1 为 TalibFactorEngine 创建单元测试

**目标**：测试覆盖率 ≥ 80%

**文件位置**：
- 源文件：`03_integration/trading_system/infrastructure/factor_engines/talib_engine.py`
- 测试文件：`tests/unit/test_talib_engine.py`（新建）

**测试范围**：
1. 基础因子计算（EMA, SMA, RSI 等）
2. 复杂因子计算（Koopman, 波动率等）
3. 边界条件（空数据、单行数据、NaN 处理）
4. 错误处理（无效因子名称、数据格式错误）

**预计时间**：2-3 天

---

### P0.2 为策略创建集成测试

**目标**：验证策略端到端流程

**文件位置**：
- 测试文件：`tests/integration/test_strategies.py`（新建）

**测试范围**：
1. 策略初始化
2. 因子计算流程
3. 信号生成逻辑
4. 入场/出场条件

**预计时间**：2-3 天

---

### P0.3 创建性能基准测试

**目标**：建立性能基线，用于对比优化效果

**文件位置**：
- 测试文件：`tests/benchmarks/test_performance.py`（新建）

**测试指标**：
1. 因子计算耗时
2. Koopman 计算耗时
3. 完整回测耗时
4. 内存占用

**预计时间**：1-2 天

---

### P0.4 实现因子缓存层

**目标**：性能提升 50-70%

**设计方案**：见下文"因子缓存层设计"章节

**预计时间**：3-4 天

---

### P0.5 拆分 TalibFactorEngine 巨型方法

**目标**：性能提升 40-50%，可读性提升 80%

**设计方案**：见下文"因子计算器重构设计"章节

**预计时间**：5-7 天

---

### P0.6 优化 Koopman 计算

**目标**：性能提升 80-90%

**设计方案**：见下文"Koopman 优化设计"章节

**预计时间**：3-4 天

---

### P0.7 解决 NumPy 2.0 兼容性

**目标**：确保系统稳定性

**任务**：
1. 运行完整测试套件
2. 修复不兼容问题
3. 必要时降级到 NumPy 1.26.x

**预计时间**：2-3 天

---

## 详细技术设计

### 1. 因子缓存层设计

#### 1.1 缓存键设计

```python
from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class FactorCacheKey:
    """因子缓存键"""
    pair: str              # 交易对，如 "BTC/USDT"
    timeframe: str         # 时间周期，如 "1h"
    factor_name: str       # 因子名称，如 "ema_20"
    end_timestamp: int     # 数据截止时间戳

    def __hash__(self) -> int:
        return hash((self.pair, self.timeframe, self.factor_name, self.end_timestamp))
```

#### 1.2 缓存实现

```python
from functools import lru_cache
from typing import Dict, Optional
import pandas as pd

class FactorCache:
    """因子缓存层"""

    def __init__(self, max_size: int = 1000):
        self._cache: Dict[FactorCacheKey, pd.Series] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: FactorCacheKey) -> Optional[pd.Series]:
        """获取缓存的因子值"""
        if key in self._cache:
            self._hits += 1
            return self._cache[key].copy()
        self._misses += 1
        return None

    def set(self, key: FactorCacheKey, value: pd.Series) -> None:
        """设置缓存的因子值"""
        if len(self._cache) >= self._max_size:
            # LRU 淘汰：移除最早的键
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = value.copy()

    def get_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
```

#### 1.3 集成到 TalibFactorEngine

```python
class TalibFactorEngine:
    def __init__(self, cache: Optional[FactorCache] = None):
        self._cache = cache or FactorCache()

    def compute(self, data: pd.DataFrame, factor_names: list[str]) -> pd.DataFrame:
        """计算因子（带缓存）"""
        result = pd.DataFrame(index=data.index)

        for factor_name in factor_names:
            # 构建缓存键
            cache_key = FactorCacheKey(
                pair=self._current_pair,
                timeframe=self._current_timeframe,
                factor_name=factor_name,
                end_timestamp=int(data.index[-1].timestamp())
            )

            # 尝试从缓存获取
            cached_value = self._cache.get(cache_key)
            if cached_value is not None:
                result[factor_name] = cached_value
                continue

            # 缓存未命中，计算因子
            factor_value = self._compute_single_factor(data, factor_name)

            # 存入缓存
            self._cache.set(cache_key, factor_value)
            result[factor_name] = factor_value

        return result
```

---

### 2. 因子计算器重构设计

#### 2.1 接口定义

```python
from abc import ABC, abstractmethod
import pandas as pd
import re

class IFactorComputer(ABC):
    """因子计算器接口"""

    @abstractmethod
    def can_compute(self, factor_name: str) -> bool:
        """判断是否可以计算该因子"""
        pass

    @abstractmethod
    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算因子"""
        pass
```

#### 2.2 具体实现示例

```python
class EMAFactorComputer(IFactorComputer):
    """EMA 因子计算器"""

    # 预编译正则表达式
    _EMA_RE = re.compile(r'^ema_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        return self._EMA_RE.match(factor_name) is not None

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        match = self._EMA_RE.match(factor_name)
        if not match:
            raise ValueError(f"Invalid EMA factor name: {factor_name}")

        period = int(match.group(1))
        return data['close'].ewm(span=period, adjust=False).mean()


class MomentumFactorComputer(IFactorComputer):
    """动量因子计算器"""

    _RET_RE = re.compile(r'^ret_(\d+)$')
    _ROC_RE = re.compile(r'^roc_(\d+)$')

    def can_compute(self, factor_name: str) -> bool:
        return (self._RET_RE.match(factor_name) is not None or
                self._ROC_RE.match(factor_name) is not None)

    def compute(self, data: pd.DataFrame, factor_name: str) -> pd.Series:
        if match := self._RET_RE.match(factor_name):
            period = int(match.group(1))
            return data['close'].pct_change(period)

        if match := self._ROC_RE.match(factor_name):
            period = int(match.group(1))
            return (data['close'] - data['close'].shift(period)) / data['close'].shift(period) * 100

        raise ValueError(f"Invalid momentum factor name: {factor_name}")
```

#### 2.3 因子注册表

```python
class FactorComputerRegistry:
    """因子计算器注册表"""

    def __init__(self):
        self._computers: list[IFactorComputer] = []

    def register(self, computer: IFactorComputer) -> None:
        """注册因子计算器"""
        self._computers.append(computer)

    def get_computer(self, factor_name: str) -> Optional[IFactorComputer]:
        """根据因子名称获取对应的计算器"""
        for computer in self._computers:
            if computer.can_compute(factor_name):
                return computer
        return None
```

#### 2.4 重构后的 TalibFactorEngine

```python
class TalibFactorEngine:
    """重构后的因子引擎（协调器）"""

    def __init__(self, cache: Optional[FactorCache] = None):
        self._cache = cache or FactorCache()
        self._registry = FactorComputerRegistry()

        # 注册所有因子计算器
        self._registry.register(EMAFactorComputer())
        self._registry.register(MomentumFactorComputer())
        self._registry.register(VolatilityFactorComputer())
        # ... 注册其他计算器

    def compute(self, data: pd.DataFrame, factor_names: list[str]) -> pd.DataFrame:
        """计算因子（协调器模式）"""
        result = pd.DataFrame(index=data.index)

        for factor_name in factor_names:
            # 尝试从缓存获取
            cached_value = self._get_from_cache(factor_name, data)
            if cached_value is not None:
                result[factor_name] = cached_value
                continue

            # 获取对应的计算器
            computer = self._registry.get_computer(factor_name)
            if computer is None:
                raise ValueError(f"No computer found for factor: {factor_name}")

            # 计算因子
            factor_value = computer.compute(data, factor_name)

            # 存入缓存
            self._set_to_cache(factor_name, data, factor_value)
            result[factor_name] = factor_value

        return result
```

---

## 实施顺序

**第 1 周**：
- P0.1: 创建 TalibFactorEngine 单元测试
- P0.3: 创建性能基准测试

**第 2 周**：
- P0.2: 创建策略集成测试
- P0.7: 解决 NumPy 2.0 兼容性

**第 3-4 周**：
- P0.4: 实现因子缓存层
- 验证性能提升

**第 5-6 周**：
- P0.5: 拆分 TalibFactorEngine 巨型方法
- 验证性能提升和代码质量

**第 7 周**：
- P0.6: 优化 Koopman 计算
- 最终验证

---

**文档版本**：v1.0
**创建日期**：2026-01-17
**状态**：进行中
