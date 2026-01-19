# Backtest Utils API 文档

本文档提供 `scripts.lib.backtest_utils` 模块的完整 API 参考。

---

## BacktestResult

回测结果封装类。

### 初始化

```python
BacktestResult(result_file: str | Path)
```

**参数**:
- `result_file`: Freqtrade 回测结果 JSON 文件路径

**异常**: `FileNotFoundError` - 文件不存在时抛出

---

### 属性

#### strategy_name
```python
@property
def strategy_name(self) -> str
```
策略名称

#### total_trades
```python
@property
def total_trades(self) -> int
```
总交易次数

#### winning_trades
```python
@property
def winning_trades(self) -> int
```
盈利交易次数

#### losing_trades
```python
@property
def losing_trades(self) -> int
```
亏损交易次数

#### win_rate
```python
@property
def win_rate(self) -> float
```
胜率（百分比）

#### total_profit
```python
@property
def total_profit(self) -> float
```
总收益（绝对值）

#### total_profit_pct
```python
@property
def total_profit_pct(self) -> float
```
总收益率（百分比）

#### max_drawdown
```python
@property
def max_drawdown(self) -> float
```
最大回撤（百分比）

#### sharpe_ratio
```python
@property
def sharpe_ratio(self) -> float
```
夏普比率

#### sortino_ratio
```python
@property
def sortino_ratio(self) -> float
```
索提诺比率

---

### 方法

#### get_summary()

```python
def get_summary(self) -> dict[str, Any]
```

获取回测结果摘要。

**返回**: 包含关键指标的字典

**示例**:
```python
result = BacktestResult("backtest_result.json")
summary = result.get_summary()
print(summary)
# {
#     "strategy": "SimpleMVPStrategy",
#     "total_trades": 100,
#     "winning_trades": 60,
#     "losing_trades": 40,
#     "win_rate": 60.0,
#     "total_profit": 1500.0,
#     "total_profit_pct": 15.0,
#     "max_drawdown": 5.2,
#     "sharpe_ratio": 1.85,
#     "sortino_ratio": 2.31
# }
```

---

## 工具函数

### compare_results()

```python
def compare_results(result_files: list[str | Path]) -> pd.DataFrame
```

对比多个回测结果。

**参数**:
- `result_files`: 回测结果文件路径列表

**返回**: 包含所有策略对比数据的 DataFrame（按总收益率降序排序）

**示例**:
```python
from scripts.lib.backtest_utils import compare_results

files = [
    "results/strategy1.json",
    "results/strategy2.json",
    "results/strategy3.json"
]

df = compare_results(files)
print(df)
```

---

### generate_markdown_report()

```python
def generate_markdown_report(df: pd.DataFrame, output_file: str | Path) -> None
```

生成 Markdown 格式的回测报告。

**参数**:
- `df`: 回测结果对比 DataFrame
- `output_file`: 输出文件路径

**示例**:
```python
from scripts.lib.backtest_utils import compare_results, generate_markdown_report

files = ["results/strategy1.json", "results/strategy2.json"]
df = compare_results(files)
generate_markdown_report(df, "reports/backtest_report.md")
```

---

## 使用示例

### 完整工作流

```python
from pathlib import Path
from scripts.lib.backtest_utils import (
    BacktestResult,
    compare_results,
    generate_markdown_report
)

# 1. 加载单个回测结果
result = BacktestResult("results/SimpleMVPStrategy.json")
print(f"策略: {result.strategy_name}")
print(f"胜率: {result.win_rate:.2f}%")
print(f"夏普比率: {result.sharpe_ratio:.3f}")

# 2. 对比多个策略
result_files = list(Path("results").glob("*.json"))
df = compare_results(result_files)

# 3. 生成报告
generate_markdown_report(df, "reports/comparison.md")
print("报告已生成: reports/comparison.md")
```

---

**最后更新**: 2026-01-19
