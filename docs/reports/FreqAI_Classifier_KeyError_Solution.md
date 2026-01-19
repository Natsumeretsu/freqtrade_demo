# FreqAI 分类器 KeyError 问题解决方案

## 问题描述

### 错误现象

在使用 FreqAI 的 LightGBMClassifier 进行回测时,模型训练成功但在保存预测结果时崩溃:

```
KeyError: 0
  File "freqtrade/freqai/data_kitchen.py", line 437, in get_predictions_to_append
    append_df[f"{label}_mean"] = self.data["labels_mean"][label]
```

### 错误上下文

- **发生时机**: 模型训练完成后,尝试保存预测结果到 dataframe 时
- **训练状态**: FreqAI 成功训练模型(585特征,12698数据点,29.66秒)
- **标签分布**: 合理(79.5% / 20.5%)
- **FreqAI 版本**: Freqtrade 2026.1-dev

## 根本原因

### 技术分析

FreqAI 的分类器要求使用**字符串标签**,而不是整数标签。

**错误的实现**:
```python
def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
    dataframe['&-action'] = 0  # ❌ 整数标签
    dataframe.loc[condition, '&-action'] = 1  # ❌ 整数标签
    return dataframe
```

**正确的实现**:
```python
def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
    # 必须设置 class_names
    self.freqai.class_names = ["no_trade", "trade"]

    # 使用字符串标签
    dataframe['&-action'] = 'no_trade'  # ✅ 字符串标签
    dataframe.loc[condition, '&-action'] = 'trade'  # ✅ 字符串标签
    return dataframe
```

### 为什么必须使用字符串标签?

1. **labels_mean 字典的键类型**:
   - FreqAI 在训练时计算每个标签的统计信息
   - 存储在 `self.data["labels_mean"]` 字典中
   - 字典的键是标签的**名称**(字符串),不是标签的**值**(整数)

2. **错误发生机制**:
   ```python
   # data_kitchen.py:437
   append_df[f"{label}_mean"] = self.data["labels_mean"][label]
   ```
   - `label` 变量是从训练数据中提取的标签值
   - 如果标签是整数 `0`,会尝试访问 `self.data["labels_mean"][0]`
   - 但字典的键应该是字符串 `"no_trade"`,而不是整数 `0`
   - 导致 `KeyError: 0`

3. **设计理由**:
   - 字符串标签更具可读性和可维护性
   - 避免整数索引的歧义(0 是标签值还是索引?)
   - 便于日志输出和调试
   - 符合 sklearn 等机器学习库的最佳实践

## 解决方案

### 完整修改步骤

#### 1. 修改 `set_freqai_targets()` 方法

```python
def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
    """
    设置预测目标 - 二分类（交易/不交易）

    注意：FreqAI 分类器必须使用字符串标签
    """
    # ✅ 步骤1: 设置分类标签名称
    self.freqai.class_names = ["no_trade", "trade"]

    # 计算未来收益
    forward_window = 12
    dataframe['future_max'] = dataframe['high'].rolling(forward_window).max().shift(-forward_window)
    dataframe['future_min'] = dataframe['low'].rolling(forward_window).min().shift(-forward_window)

    # 计算潜在收益
    fee = 0.001
    slippage = 0.0005
    total_cost = 2 * (fee + slippage)
    dataframe['potential_long_return'] = (dataframe['future_max'] / dataframe['close'] - 1) - total_cost
    dataframe['potential_short_return'] = (1 - dataframe['future_min'] / dataframe['close']) - total_cost

    threshold = 0.008

    # ✅ 步骤2: 使用字符串标签
    dataframe['&-action'] = 'no_trade'  # 默认值
    dataframe.loc[
        (dataframe['potential_long_return'] > threshold) |
        (dataframe['potential_short_return'] > threshold),
        '&-action'
    ] = 'trade'

    # ✅ 步骤3: 更新日志输出
    import logging
    logger = logging.getLogger(__name__)
    label_counts = dataframe['&-action'].value_counts()
    total = len(dataframe)
    logger.info(f"标签分布 - no_trade(不交易): {label_counts.get('no_trade', 0)} "
               f"({label_counts.get('no_trade', 0)/total*100:.1f}%), "
               f"trade(交易): {label_counts.get('trade', 0)} "
               f"({label_counts.get('trade', 0)/total*100:.1f}%)")

    return dataframe
```

#### 2. 修改 `populate_entry_trend()` 方法

```python
def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    """
    入场信号 - 基于 FreqAI 预测 + 微观结构确认
    """
    if 'do_predict' not in dataframe.columns:
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0
        return dataframe

    # ✅ 修改标签比较为字符串
    dataframe.loc[
        (dataframe['do_predict'] == 1) &
        (dataframe['&-action'] == 'trade') &  # 字符串比较
        (dataframe['ofi_10'] > 0.1) &
        (dataframe['vpin'] < 0.6) &
        (dataframe['regime_state'] != 0) &
        (dataframe['volume'] > 0),
        'enter_long'
    ] = 1

    dataframe.loc[
        (dataframe['do_predict'] == 1) &
        (dataframe['&-action'] == 'trade') &  # 字符串比较
        (dataframe['ofi_10'] < -0.1) &
        (dataframe['vpin'] < 0.6) &
        (dataframe['regime_state'] != 2) &
        (dataframe['volume'] > 0),
        'enter_short'
    ] = 1

    return dataframe
```

### 关键要点

1. **必须设置 `class_names`**:
   ```python
   self.freqai.class_names = ["no_trade", "trade"]
   ```
   - 在 `set_freqai_targets()` 方法开头设置
   - 列表顺序应该与标签的语义对应

2. **所有标签赋值使用字符串**:
   ```python
   dataframe['&-action'] = 'no_trade'  # 不是 0
   dataframe['&-action'] = 'trade'     # 不是 1
   ```

3. **所有标签比较使用字符串**:
   ```python
   dataframe['&-action'] == 'trade'  # 不是 == 1
   ```

4. **日志输出适配字符串**:
   ```python
   label_counts.get('no_trade', 0)  # 不是 get(0, 0)
   ```

## 验证结果

### 修复前

```
2026-01-19 16:44:39,148 - Training model on 585 features
2026-01-19 16:44:39,149 - Training model on 12698 data points
2026-01-19 16:45:03,876 - Done training ETH/USDT:USDT (29.66 secs)

KeyError: 0
  File "freqtrade/freqai/data_kitchen.py", line 437
```

### 修复后

```
2026-01-19 16:57:21,679 - 标签分布 - no_trade(不交易): 14446 (79.2%), trade(交易): 3798 (20.8%)
2026-01-19 16:57:26,705 - Training model on 585 features
2026-01-19 16:57:26,705 - Training model on 12698 data points
2026-01-19 16:57:46,878 - Done training ETH/USDT:USDT (25.13 secs)
2026-01-19 16:57:46,885 - Saving metadata to disk.
```

✅ **成功完成 30/30 个训练周期,无任何错误**

### 回测结果

- **总交易**: 148 笔
- **胜率**: 33.1% (49胜/99负)
- **总收益**: -16.28% (-162.8 USDT)
- **技术验证**: ✅ FreqAI 正常工作,无 KeyError

## 官方文档参考

### 官方示例

来自 Freqtrade 官方文档:

```python
def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
    # 设置分类标签名称
    self.freqai.class_names = ["down", "up"]

    # 使用字符串标签
    dataframe['&s-up_or_down'] = np.where(
        dataframe["close"].shift(-100) > dataframe["close"],
        'up',    # 字符串
        'down'   # 字符串
    )
    return dataframe
```

### 关键文档说明

> "For classification models, the classes need to be set using strings"
>
> — Freqtrade FreqAI 官方文档

## 常见错误模式

### ❌ 错误模式 1: 使用整数标签

```python
dataframe['&-action'] = 0
dataframe.loc[condition, '&-action'] = 1
```

**错误**: `KeyError: 0`

### ❌ 错误模式 2: 忘记设置 class_names

```python
# 缺少这一行
# self.freqai.class_names = ["no_trade", "trade"]

dataframe['&-action'] = 'no_trade'
dataframe.loc[condition, '&-action'] = 'trade'
```

**错误**: 可能导致预测结果异常

### ❌ 错误模式 3: class_names 与标签不匹配

```python
self.freqai.class_names = ["down", "up"]  # 不匹配
dataframe['&-action'] = 'no_trade'        # 不匹配
dataframe.loc[condition, '&-action'] = 'trade'  # 不匹配
```

**错误**: 标签映射错误

### ✅ 正确模式

```python
# 1. 设置 class_names
self.freqai.class_names = ["no_trade", "trade"]

# 2. 使用匹配的字符串标签
dataframe['&-action'] = 'no_trade'
dataframe.loc[condition, '&-action'] = 'trade'

# 3. 比较时使用字符串
dataframe['&-action'] == 'trade'
```

## 适用范围

### 适用的 FreqAI 模型

此解决方案适用于所有 FreqAI 分类器:

- ✅ `LightGBMClassifier`
- ✅ `CatboostClassifier`
- ✅ `XGBoostClassifier`
- ✅ `SklearnClassifier`
- ✅ 所有自定义分类器

### 不适用的模型

回归模型不需要字符串标签:

- ❌ `LightGBMRegressor` (使用数值标签)
- ❌ `CatboostRegressor` (使用数值标签)
- ❌ `XGBoostRegressor` (使用数值标签)

## 调试技巧

### 1. 检查标签类型

```python
# 在 set_freqai_targets() 中添加
print(f"标签类型: {type(dataframe['&-action'].iloc[0])}")
print(f"标签唯一值: {dataframe['&-action'].unique()}")
```

**期望输出**:
```
标签类型: <class 'str'>
标签唯一值: ['no_trade' 'trade']
```

### 2. 检查 class_names

```python
# 在 set_freqai_targets() 中添加
print(f"class_names: {self.freqai.class_names}")
```

**期望输出**:
```
class_names: ['no_trade', 'trade']
```

### 3. 检查标签分布

```python
# 在 set_freqai_targets() 中添加
print(dataframe['&-action'].value_counts())
```

**期望输出**:
```
no_trade    14446
trade        3798
Name: &-action, dtype: int64
```

## 相关问题

### GitHub Issues

- [#10997](https://github.com/freqtrade/freqtrade/issues/10997): KeyError with LightGBMClassifier
- [#10828](https://github.com/freqtrade/freqtrade/issues/10828): Classification labels must be strings
- [#8529](https://github.com/freqtrade/freqtrade/issues/8529): FreqAI classifier KeyError

### 社区讨论

多个用户报告了相同的问题,解决方案一致:

> "Convert numeric values to strings to avoid KeyError with integer indices"
>
> — Freqtrade 社区策略示例

## 总结

### 核心要点

1. **FreqAI 分类器必须使用字符串标签**
2. **必须设置 `self.freqai.class_names`**
3. **所有标签操作(赋值、比较、日志)都使用字符串**

### 检查清单

- [ ] `set_freqai_targets()` 开头设置 `self.freqai.class_names`
- [ ] 所有标签赋值使用字符串 (`'no_trade'`, `'trade'`)
- [ ] `populate_entry_trend()` 中的标签比较使用字符串
- [ ] 日志输出使用字符串键 (`label_counts.get('no_trade', 0)`)
- [ ] 运行回测验证无 KeyError

### 经验教训

1. **阅读官方文档**: 官方文档明确说明了分类器需要字符串标签
2. **使用搜索工具**: Tavily 搜索快速找到了社区解决方案
3. **交叉验证**: Sequential thinking 帮助系统分析问题根源
4. **完整测试**: 回测验证确保修复有效

## 参考资料

- [Freqtrade FreqAI 官方文档](https://www.freqtrade.io/en/stable/freqai/)
- [Freqtrade FreqAI Feature Engineering](https://www.freqtrade.io/en/stable/freqai-feature-engineering/)
- [GitHub Issue #10997](https://github.com/freqtrade/freqtrade/issues/10997)

---

**文档版本**: 1.0
**创建日期**: 2026-01-19
**最后更新**: 2026-01-19
**作者**: Claude (AI Assistant)
**验证状态**: ✅ 已在 Freqtrade 2026.1-dev 上验证
