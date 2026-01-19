# 因子开发指南

本指南介绍如何开发和使用自定义因子。

---

## 什么是因子？

因子是从原始市场数据（OHLCV）中提取的特征，用于：
- 策略信号生成
- 机器学习模型输入
- 市场状态判断

---

## 因子库架构

```
integration/factor_library/
├── base.py           # 因子基类
├── registry.py       # 因子注册中心
├── factor_library.py # 因子库管理
└── technical.py      # 技术指标因子
```

---

## 开发自定义因子

### 1. 创建因子类

继承 `BaseFactor` 并实现必需方法：

```python
from integration.factor_library import BaseFactor, register_factor
import pandas as pd

@register_factor
class MyCustomFactor(BaseFactor):
    def __init__(self, window: int = 20):
        self.window = window
        super().__init__(window=window)

    @property
    def name(self) -> str:
        return f"my_custom_{self.window}"

    @property
    def description(self) -> str:
        return f"我的自定义因子（窗口={self.window}）"

    @property
    def category(self) -> str:
        return "technical"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        # 实现因子计算逻辑
        return df["close"].rolling(self.window).mean()

    def _validate_params(self) -> None:
        if self.window <= 0:
            raise ValueError(f"window 必须大于0，当前值: {self.window}")
```

### 2. 注册因子

使用 `@register_factor` 装饰器自动注册：

```python
@register_factor
class MyFactor(BaseFactor):
    ...
```

### 3. 使用因子

```python
from integration.factor_library import FactorLibrary

# 创建因子库
factor_lib = FactorLibrary()

# 计算单个因子
df_with_factor = factor_lib.calculate_factors(df, ["my_custom_20"])

# 批量计算因子
df_with_factors = factor_lib.calculate_factors(df, [
    "my_custom_20",
    "momentum_8h",
    "volatility_24h"
])
```

---

## 因子类别

### technical（技术指标）
- 动量类：momentum、ROC
- 均线类：SMA、EMA、MACD
- 震荡类：RSI、StochRSI、Williams %R
- 波动率类：ATR、Bollinger Bands

### volume（成交量）
- OBV、CMF、VWAP、VolumeSurge

### price_pattern（价格形态）
- 自定义价格形态识别

### composite（复合因子）
- 多因子组合

---

## 最佳实践

### 1. 参数验证

始终在 `_validate_params()` 中验证参数：

```python
def _validate_params(self) -> None:
    if self.window <= 0:
        raise ValueError("window 必须大于0")
    if self.threshold < 0:
        raise ValueError("threshold 不能为负数")
```

### 2. 处理边界条件

考虑窗口不足的情况：

```python
def calculate(self, df: pd.DataFrame) -> pd.Series:
    if len(df) < self.window:
        return pd.Series([np.nan] * len(df), index=df.index)
    return df["close"].rolling(self.window).mean()
```

### 3. 性能优化

- 使用向量化操作（pandas/numpy）
- 避免循环
- 缓存中间结果

---

## 测试因子

创建单元测试：

```python
def test_my_custom_factor():
    df = pd.DataFrame({
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [100, 101, 102],
        "volume": [1000, 1100, 1200],
    })

    factor = MyCustomFactor(window=2)
    result = factor.calculate(df)

    assert isinstance(result, pd.Series)
    assert len(result) == len(df)
```

---

## 下一步

- [回测指南](backtesting-guide.md) - 在回测中使用因子
- [API 文档](../api/factor-library-api.md) - 完整 API 参考

---

**最后更新**: 2026-01-19
