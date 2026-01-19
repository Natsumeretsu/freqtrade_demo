# Factor Library API 文档

本文档提供 `integration.factor_library` 模块的完整 API 参考。

---

## 核心类

### BaseFactor

因子抽象基类，所有因子必须继承此类。

#### 属性

- `params: dict[str, Any]` - 因子参数字典

#### 抽象属性（必须实现）

- `name: str` - 因子唯一标识符
- `description: str` - 因子描述
- `category: str` - 因子类别（technical/volume/price_pattern/composite）
- `dependencies: list[str]` - 依赖的数据列（默认为 OHLCV）

#### 抽象方法（必须实现）

```python
def calculate(self, df: pd.DataFrame) -> pd.Series:
    """计算因子值

    Args:
        df: OHLCV 数据框

    Returns:
        因子值序列
    """
    pass
```

#### 可选方法

```python
def _validate_params(self) -> None:
    """验证参数有效性

    Raises:
        ValueError: 参数无效时抛出
    """
    pass
```

---

## FactorLibrary

因子库管理类。

### 初始化

```python
FactorLibrary(config_path: str | Path | None = None)
```

**参数**:
- `config_path`: 配置文件路径（可选）

### 方法

#### get_factor()

```python
def get_factor(
    self,
    factor_name: str,
    params: dict[str, Any] | None = None
) -> BaseFactor
```

获取因子实例。

**参数**:
- `factor_name`: 因子名称
- `params`: 因子参数（可选）

**返回**: 因子实例

**异常**: `ValueError` - 因子不存在时抛出

---

#### calculate_factors()

```python
def calculate_factors(
    self,
    df: pd.DataFrame,
    factor_names: list[str] | None = None
) -> pd.DataFrame
```

批量计算因子。

**参数**:
- `df`: OHLCV 数据框
- `factor_names`: 因子名称列表（可选）

**返回**: 包含原始数据和因子值的数据框

---

## 注册函数

### register_factor()

```python
@register_factor
class MyFactor(BaseFactor):
    ...
```

因子注册装饰器。

---

### get_factor_class()

```python
def get_factor_class(factor_name: str) -> type[BaseFactor] | None
```

获取因子类。

**参数**:
- `factor_name`: 因子名称

**返回**: 因子类，不存在则返回 None

---

### list_all_factors()

```python
def list_all_factors() -> list[str]
```

列出所有已注册的因子。

**返回**: 因子名称列表

---

## 内置因子

### 动量类

- `momentum_8h` - 8小时动量
- `roc_12` - 变化率指标

### 均线类

- `sma_20` - 简单移动平均线
- `ema_20` - 指数移动平均线
- `macd_12_26_9` - MACD 指标

### 震荡类

- `rsi_14` - 相对强弱指标
- `stoch_rsi_14` - 随机 RSI
- `williams_r_14` - 威廉指标

### 波动率类

- `volatility_24h` - 24小时波动率
- `atr_14` - 平均真实波幅
- `bb_width_20` - 布林带宽度

### 成交量类

- `volume_surge` - 成交量激增
- `obv` - 能量潮指标
- `cmf_20` - 资金流量指标
- `vwap_20` - 成交量加权平均价

---

**最后更新**: 2026-01-19
