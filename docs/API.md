# API 文档

本文档提供集成层（03_integration/）所有公共函数的 API 参考。

---

## 📦 模块概览

| 模块 | 功能 | 文件路径 |
|------|------|----------|
| **因子计算** | 基础因子计算函数 | `03_integration/simple_factors/basic_factors.py` |
| **因子验证** | IC 分析、t 值检验、分位数分析 | `03_integration/factor_validator.py` |
| **数据处理** | 数据清洗、特征工程、样本分割 | `03_integration/data_pipeline.py` |

---

## 🔢 因子计算模块

### calculate_momentum()

计算动量因子（价格变化率）。

**函数签名**：
```python
def calculate_momentum(df: pd.DataFrame, window: int = 32) -> pd.Series
```

**参数**：
- `df` (pd.DataFrame): OHLCV DataFrame，必须包含 'close' 列
- `window` (int): 回看窗口，默认 32（8小时，15分钟K线）

**返回**：
- `pd.Series`: 动量因子值序列

**示例**：
```python
from simple_factors.basic_factors import calculate_momentum

# 计算 8 小时动量
momentum = calculate_momentum(df, window=32)

# 计算 24 小时动量
momentum_24h = calculate_momentum(df, window=96)
```

**假设**：短期价格动量在加密市场中有效期约 8 小时。

---

### calculate_volatility()

计算波动率因子（收益率标准差）。

**函数签名**：
```python
def calculate_volatility(df: pd.DataFrame, window: int = 96) -> pd.Series
```

**参数**：
- `df` (pd.DataFrame): OHLCV DataFrame
- `window` (int): 回看窗口，默认 96（24小时）

**返回**：
- `pd.Series`: 波动率序列

**示例**：
```python
from simple_factors.basic_factors import calculate_volatility

volatility = calculate_volatility(df, window=96)
```

**假设**：高波动率预示价格不稳定，可能出现反转。

---

### calculate_volume_surge()

计算成交量激增因子（成交量相对均值的倍数）。

**函数签名**：
```python
def calculate_volume_surge(df: pd.DataFrame, window: int = 96) -> pd.Series
```

**参数**：
- `df` (pd.DataFrame): OHLCV DataFrame，必须包含 'volume' 列
- `window` (int): 回看窗口，默认 96

**返回**：
- `pd.Series`: 成交量激增倍数

**示例**：
```python
from simple_factors.basic_factors import calculate_volume_surge

volume_surge = calculate_volume_surge(df, window=96)
```

**假设**：成交量突然放大预示趋势启动或反转。

---

### calculate_all_factors()

一次性计算所有因子。

**函数签名**：
```python
def calculate_all_factors(df: pd.DataFrame) -> pd.DataFrame
```

**参数**：
- `df` (pd.DataFrame): OHLCV DataFrame

**返回**：
- `pd.DataFrame`: 包含原始列和所有因子列的 DataFrame

**新增列**：
- `momentum_8h`: 8小时动量
- `volatility_24h`: 24小时波动率
- `volume_surge`: 成交量激增

**示例**：
```python
from simple_factors.basic_factors import calculate_all_factors

df_with_factors = calculate_all_factors(df)
print(df_with_factors.columns)
# ['open', 'high', 'low', 'close', 'volume', 'momentum_8h', 'volatility_24h', 'volume_surge']
```

---

## ✅ 因子验证模块

### calculate_ic()

计算信息系数（IC），衡量因子与未来收益的相关性。

**函数签名**：
```python
def calculate_ic(
    factor: pd.Series,
    forward_return: pd.Series,
    method: str = 'pearson'
) -> float
```

**参数**：
- `factor` (pd.Series): 因子值序列
- `forward_return` (pd.Series): 未来收益序列
- `method` (str): 相关系数方法，'pearson' 或 'spearman'

**返回**：
- `float`: IC 值（-1 到 1 之间）

**示例**：
```python
from factor_validator import calculate_ic

ic = calculate_ic(df['momentum_8h'], df['forward_return_1p'])
print(f"IC: {ic:.3f}")
```

**验收标准**：
- IC > 0.05：有效因子
- IC > 0.10：非常有效
- IC < 0.02：无效因子

---

### validate_factor()

验证因子是否有效（综合 IC 和 t 值）。

**函数签名**：
```python
def validate_factor(
    df: pd.DataFrame,
    factor_col: str,
    return_col: str,
    ic_threshold: float = 0.05,
    t_threshold: float = 2.0
) -> Tuple[bool, Dict[str, float]]
```

**参数**：
- `df` (pd.DataFrame): 包含因子和收益的 DataFrame
- `factor_col` (str): 因子列名
- `return_col` (str): 收益列名
- `ic_threshold` (float): IC 阈值，默认 0.05
- `t_threshold` (float): t 值阈值，默认 2.0

**返回**：
- `Tuple[bool, Dict]`: (是否通过验证, 统计指标字典)

**示例**：
```python
from factor_validator import validate_factor

passed, stats = validate_factor(df, 'momentum_8h', 'forward_return_1p')
if passed:
    print(f"✓ 因子有效 (IC={stats['ic']:.3f}, t={stats['t_stat']:.2f})")
else:
    print(f"✗ 因子无效")
```

---

## 🔧 数据处理模块

### clean_ohlcv_data()

清洗 OHLCV 数据（移除异常值、验证 OHLC 关系）。

**函数签名**：
```python
def clean_ohlcv_data(
    df: pd.DataFrame,
    max_price_change: float = 0.2,
    remove_duplicates: bool = True
) -> pd.DataFrame
```

**参数**：
- `df` (pd.DataFrame): 原始 OHLCV DataFrame
- `max_price_change` (float): 单根K线最大涨跌幅，默认 0.2（20%）
- `remove_duplicates` (bool): 是否移除重复时间戳

**返回**：
- `pd.DataFrame`: 清洗后的 DataFrame

**示例**：
```python
from data_pipeline import clean_ohlcv_data

df_clean = clean_ohlcv_data(df, max_price_change=0.2)
```

---

### calculate_forward_returns()

计算未来收益。

**函数签名**：
```python
def calculate_forward_returns(
    df: pd.DataFrame,
    price_col: str = 'close',
    periods: list[int] = [1, 4, 8]
) -> pd.DataFrame
```

**参数**：
- `df` (pd.DataFrame): OHLCV DataFrame
- `price_col` (str): 价格列名
- `periods` (list[int]): 未来周期列表

**返回**：
- `pd.DataFrame`: 添加了未来收益列的 DataFrame

**新增列**：
- `forward_return_1p`: 1期后收益
- `forward_return_4p`: 4期后收益
- `forward_return_8p`: 8期后收益

**示例**：
```python
from data_pipeline import calculate_forward_returns

df = calculate_forward_returns(df, periods=[1, 4, 8])
```

---

### split_train_val_test()

分割训练集、验证集、测试集。

**函数签名**：
```python
def split_train_val_test(
    df: pd.DataFrame,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
```

**参数**：
- `df` (pd.DataFrame): 完整 DataFrame
- `train_ratio` (float): 训练集比例
- `val_ratio` (float): 验证集比例
- `test_ratio` (float): 测试集比例

**返回**：
- `Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`: (训练集, 验证集, 测试集)

**示例**：
```python
from data_pipeline import split_train_val_test

train_df, val_df, test_df = split_train_val_test(df)
print(f"训练集: {len(train_df)}, 验证集: {len(val_df)}, 测试集: {len(test_df)}")
```

---

**最后更新**：2026-01-18
