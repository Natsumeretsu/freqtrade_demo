# 优化功能集成示例

**创建日期**: 2026-01-17

## 1. 概述

本示例展示如何将以下优化功能集成到实际的因子计算流程中：
- 错误处理（异常类 + 重试装饰器）
- 依赖图优化（拓扑排序 + 并行调度）
- 配置管理（统一配置接口）

## 2. 场景说明

**业务场景**：计算多个技术指标因子
- 基础数据：价格数据（OHLCV）
- 因子 1：SMA_10（10 日简单移动平均）
- 因子 2：SMA_20（20 日简单移动平均）
- 因子 3：RSI（相对强弱指标）
- 因子 4：MACD（依赖 SMA_10 和 SMA_20）

**依赖关系**：
```
价格数据 → SMA_10 → MACD
         → SMA_20 ↗
         → RSI
```

## 3. 配置文件

**config.json**：
```json
{
  "data": {
    "symbols": ["BTC/USDT", "ETH/USDT"],
    "timeframe": "1h",
    "limit": 1000
  },
  "factors": {
    "sma_10": {"window": 10},
    "sma_20": {"window": 20},
    "rsi": {"period": 14},
    "macd": {"fast": 12, "slow": 26, "signal": 9}
  },
  "retry": {
    "max_attempts": 3,
    "backoff": 2.0
  }
}
```

## 4. 实现步骤

### 4.1 定义因子计算函数

每个因子计算函数使用错误处理装饰器：

```python
from trading_system.infrastructure.error_handling import retry, FactorComputationError

@retry(max_attempts=3, backoff=2.0)
def compute_sma(data, window):
    """计算简单移动平均"""
    try:
        if len(data) < window:
            raise ValueError(f"数据长度不足: {len(data)} < {window}")
        
        result = []
        for i in range(len(data)):
            if i < window - 1:
                result.append(None)
            else:
                avg = sum(data[i-window+1:i+1]) / window
                result.append(avg)
        return result
    except Exception as e:
        raise FactorComputationError(
            message=f"SMA 计算失败",
            operation="compute_sma",
            parameters={"window": window, "data_length": len(data)}
        ) from e
```

### 4.2 构建依赖图

使用依赖图优化计算顺序：

```python
from trading_system.infrastructure.dependency import (
    DependencyGraph, FactorNode, ParallelScheduler
)

def build_factor_graph(config):
    """构建因子依赖图"""
    graph = DependencyGraph()
    
    # 添加因子节点
    graph.add_factor(FactorNode(
        name="price",
        dependencies=[],
        compute_func=lambda data: data  # 直接返回价格数据
    ))
    
    graph.add_factor(FactorNode(
        name="sma_10",
        dependencies=["price"],
        compute_func=lambda data, price: compute_sma(price, config.get("factors.sma_10.window"))
    ))
    
    graph.add_factor(FactorNode(
        name="sma_20",
        dependencies=["price"],
        compute_func=lambda data, price: compute_sma(price, config.get("factors.sma_20.window"))
    ))
    
    graph.add_factor(FactorNode(
        name="macd",
        dependencies=["sma_10", "sma_20"],
        compute_func=lambda data, sma_10, sma_20: compute_macd(sma_10, sma_20)
    ))
    
    return graph
```

### 4.3 主流程集成

完整的集成流程：

```python
from trading_system.infrastructure.config import ConfigManager
from trading_system.infrastructure.dependency import ParallelScheduler

def main():
    """主流程：集成所有优化功能"""
    
    # 1. 加载配置
    config = ConfigManager()
    config.load("config.json", environment="prod")
    
    # 2. 构建因子依赖图
    graph = build_factor_graph(config)
    
    # 3. 创建调度器
    scheduler = ParallelScheduler(graph)
    
    # 4. 加载数据
    price_data = load_price_data(config.get("data.symbols")[0])
    
    # 5. 执行因子计算
    results = scheduler.execute(price_data)
    
    # 6. 输出结果
    print(f"计算完成，共 {len(results)} 个因子")
    for name, value in results.items():
        if value is not None:
            print(f"  {name}: {len(value)} 个数据点")
    
    return results
```

## 5. 优势总结

**错误处理**：
- 自动重试失败的计算
- 详细的错误上下文
- 统一的异常处理

**依赖图优化**：
- 自动优化计算顺序
- 识别可并行计算的因子
- 避免重复计算

**配置管理**：
- 统一的配置接口
- 支持多环境配置
- 配置验证
