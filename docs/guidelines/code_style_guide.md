# 代码风格指南

更新日期：2026-01-17

## 1. 通用原则

**核心理念**：
- KISS（Keep It Simple, Stupid）：保持简单
- YAGNI（You Aren't Gonna Need It）：不做过度设计
- DRY（Don't Repeat Yourself）：避免重复代码
- 可读性优先：代码是写给人看的

---

## 2. Python 代码规范

### 2.1 命名规范

**变量和函数**：
- 使用小写字母和下划线：`my_variable`, `calculate_profit()`
- 布尔变量使用 `is_`, `has_`, `can_` 前缀：`is_valid`, `has_data`
- 私有变量/方法使用单下划线前缀：`_internal_method()`

**类名**：
- 使用大驼峰命名：`MyStrategy`, `DataLoader`
- 异常类以 `Error` 结尾：`ValidationError`

**常量**：
- 使用全大写字母和下划线：`MAX_RETRIES`, `DEFAULT_TIMEOUT`

**示例**：
```python
# 好的命名
class TrendStrategy:
    MAX_POSITIONS = 5

    def __init__(self):
        self.is_active = True
        self._cache = {}

    def calculate_signal(self, data):
        return self._process_data(data)

# 不好的命名
class trend_strategy:  # 应该用大驼峰
    maxPositions = 5  # 常量应该全大写

    def __init__(self):
        self.active = True  # 布尔变量应该用 is_ 前缀
```

### 2.2 代码格式

**缩进**：
- 使用 4 个空格（不使用 Tab）
- 最大嵌套深度：3 层

**行长度**：
- 最大 88 字符（Black 默认）
- 超长行使用括号换行

**空行**：
- 顶层函数/类之间：2 个空行
- 类方法之间：1 个空行
- 函数内逻辑块之间：1 个空行

**示例**：
```python
# 好的格式
def process_data(
    data: pd.DataFrame,
    window: int = 20,
    threshold: float = 0.5
) -> pd.DataFrame:
    """处理数据并返回结果"""
    # 计算指标
    data['ma'] = data['close'].rolling(window).mean()

    # 生成信号
    data['signal'] = (data['close'] > data['ma']).astype(int)

    return data
```

### 2.3 注释规范

**文档字符串（Docstring）**：
- 所有公共函数/类必须有 docstring
- 使用中文描述
- 格式：简短描述 + 参数说明 + 返回值说明

**行内注释**：
- 使用中文
- 解释"为什么"而不是"做什么"
- 复杂逻辑必须注释

**示例**：
```python
def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    计算相对强弱指标（RSI）

    参数：
        data: 包含 'close' 列的 DataFrame
        period: RSI 周期，默认 14

    返回：
        RSI 值的 Series，范围 0-100
    """
    delta = data['close'].diff()

    # 分离涨跌幅，避免负数影响计算
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    # 避免除零错误
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))

    return rsi
```

### 2.4 类型注解

**必须使用类型注解**：
- 所有函数参数和返回值
- 类属性（Python 3.6+）
- 复杂变量

**示例**：
```python
from typing import Dict, List, Optional, Tuple

class Strategy:
    name: str
    params: Dict[str, float]

    def __init__(self, name: str, params: Optional[Dict[str, float]] = None):
        self.name = name
        self.params = params or {}

    def generate_signals(
        self,
        data: pd.DataFrame
    ) -> Tuple[pd.Series, pd.Series]:
        """生成买卖信号"""
        buy_signal = self._calculate_buy(data)
        sell_signal = self._calculate_sell(data)
        return buy_signal, sell_signal
```

---

## 3. 策略代码规范

### 3.1 策略结构

**标准结构**：
```python
class MyStrategy(IStrategy):
    """策略简短描述"""

    # 1. 元数据
    INTERFACE_VERSION = 3

    # 2. 策略参数
    minimal_roi = {...}
    stoploss = -0.10

    # 3. 指标计算
    def populate_indicators(self, dataframe, metadata):
        """计算技术指标"""
        pass

    # 4. 买入信号
    def populate_entry_trend(self, dataframe, metadata):
        """生成买入信号"""
        pass

    # 5. 卖出信号
    def populate_exit_trend(self, dataframe, metadata):
        """生成卖出信号"""
        pass
```

### 3.2 指标计算原则

**分离关注点**：
- 指标计算与信号生成分离
- 每个指标独立计算
- 避免在信号函数中计算指标

**示例**：
```python
# 好的做法
def populate_indicators(self, dataframe, metadata):
    # 计算所有需要的指标
    dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=12)
    dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=26)
    dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
    return dataframe

def populate_entry_trend(self, dataframe, metadata):
    # 只使用已计算的指标
    dataframe.loc[
        (dataframe['ema_fast'] > dataframe['ema_slow']) &
        (dataframe['rsi'] < 30),
        'enter_long'
    ] = 1
    return dataframe

# 不好的做法
def populate_entry_trend(self, dataframe, metadata):
    # 在信号函数中计算指标（不推荐）
    ema_fast = ta.EMA(dataframe, timeperiod=12)
    ema_slow = ta.EMA(dataframe, timeperiod=26)
    # ...
```

---

## 4. 配置文件规范

### 4.1 YAML 格式

**命名**：
- 使用小写字母和下划线
- 文件名描述性强：`binance_futures_config.yaml`

**结构**：
- 使用缩进表示层级（2 个空格）
- 相关配置分组
- 添加注释说明

**示例**：
```yaml
# 交易所配置
exchange:
  name: binance
  key: ${BINANCE_API_KEY}
  secret: ${BINANCE_API_SECRET}

# 策略配置
strategy:
  name: TrendFollowing
  timeframe: 5m

  # 风险参数
  risk:
    max_open_trades: 3
    stake_amount: 100
    stoploss: -0.05
```

---

## 5. 测试代码规范

### 5.1 测试命名

**测试文件**：
- 以 `test_` 开头：`test_strategy.py`
- 与被测试文件对应

**测试函数**：
- 以 `test_` 开头
- 描述测试场景：`test_buy_signal_when_ema_crossover()`

### 5.2 测试结构

**AAA 模式**：
- Arrange（准备）：设置测试数据
- Act（执行）：调用被测试函数
- Assert（断言）：验证结果

**示例**：
```python
def test_calculate_rsi_returns_correct_values():
    # Arrange
    data = pd.DataFrame({
        'close': [100, 102, 101, 103, 105, 104, 106]
    })

    # Act
    result = calculate_rsi(data, period=3)

    # Assert
    assert result.iloc[-1] > 50  # 上涨趋势，RSI > 50
    assert 0 <= result.iloc[-1] <= 100  # RSI 范围正确
```

---

## 6. Git 提交规范

### 6.1 提交信息格式

**格式**：`<类型>: <简短描述>`

**类型**：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例**：
```
feat: 添加 RSI 超买超卖信号
fix: 修复 EMA 计算中的空值处理
docs: 更新策略参数说明
refactor: 简化信号生成逻辑
```

---

## 7. 检查清单

在提交代码前，请检查：

- [ ] 代码符合命名规范
- [ ] 所有函数有类型注解
- [ ] 公共函数有 docstring（中文）
- [ ] 复杂逻辑有注释说明
- [ ] 代码格式符合 Black 标准
- [ ] 没有超过 3 层嵌套
- [ ] 测试用例已通过
- [ ] Git 提交信息符合规范

---

**参考资源**：
- PEP 8: https://pep8.org/
- Black: https://black.readthedocs.io/
- Type Hints: https://docs.python.org/3/library/typing.html
