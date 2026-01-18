"""集成示例：因子计算流程

展示如何集成错误处理、依赖图优化和配置管理。

创建日期: 2026-01-17
"""

import sys
import os
import random

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.error_handling import retry, FactorComputationError
from trading_system.infrastructure.dependency import DependencyGraph, FactorNode, ParallelScheduler
from trading_system.infrastructure.config import ConfigManager


# ============ 因子计算函数 ============

@retry(max_attempts=3, backoff=2.0)
def compute_sma(price_data, window):
    """计算简单移动平均

    Args:
        price_data: 价格数据列表
        window: 窗口大小

    Returns:
        SMA 结果列表
    """
    try:
        if len(price_data) < window:
            raise ValueError(f"数据长度不足: {len(price_data)} < {window}")

        result = []
        for i in range(len(price_data)):
            if i < window - 1:
                result.append(None)
            else:
                avg = sum(price_data[i-window+1:i+1]) / window
                result.append(avg)
        return result
    except Exception as e:
        raise FactorComputationError(
            message=f"SMA 计算失败",
            operation="compute_sma",
            parameters={"window": window, "data_length": len(price_data)}
        ) from e


@retry(max_attempts=3, backoff=2.0)
def compute_rsi(price_data, period):
    """计算 RSI 指标

    Args:
        price_data: 价格数据列表
        period: 周期

    Returns:
        RSI 结果列表
    """
    try:
        if len(price_data) < period + 1:
            raise ValueError(f"数据长度不足: {len(price_data)} < {period + 1}")

        # 计算价格变化
        changes = [price_data[i] - price_data[i-1] for i in range(1, len(price_data))]
        
        # 分离涨跌
        gains = [max(c, 0) for c in changes]
        losses = [abs(min(c, 0)) for c in changes]
        
        # 计算 RSI
        result = [None] * period
        for i in range(period, len(price_data)):
            avg_gain = sum(gains[i-period:i]) / period
            avg_loss = sum(losses[i-period:i]) / period
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            result.append(rsi)
        
        return result
    except Exception as e:
        raise FactorComputationError(
            message=f"RSI 计算失败",
            operation="compute_rsi",
            parameters={"period": period, "data_length": len(price_data)}
        ) from e


@retry(max_attempts=3, backoff=2.0)
def compute_macd(sma_10, sma_20):
    """计算 MACD 指标

    Args:
        sma_10: 10 日 SMA
        sma_20: 20 日 SMA

    Returns:
        MACD 结果列表
    """
    try:
        if len(sma_10) != len(sma_20):
            raise ValueError(f"SMA 长度不匹配: {len(sma_10)} != {len(sma_20)}")

        result = []
        for i in range(len(sma_10)):
            if sma_10[i] is None or sma_20[i] is None:
                result.append(None)
            else:
                macd = sma_10[i] - sma_20[i]
                result.append(macd)
        return result
    except Exception as e:
        raise FactorComputationError(
            message=f"MACD 计算失败",
            operation="compute_macd",
            parameters={"sma_10_length": len(sma_10), "sma_20_length": len(sma_20)}
        ) from e


# ============ 辅助函数 ============

def generate_price_data(length=100, start_price=100):
    """生成模拟价格数据

    Args:
        length: 数据长度
        start_price: 起始价格

    Returns:
        价格数据列表
    """
    random.seed(42)
    price_data = [start_price]
    for _ in range(length - 1):
        change = random.uniform(-2, 2)
        new_price = price_data[-1] + change
        price_data.append(max(new_price, 1))  # 确保价格为正
    return price_data


def build_factor_graph(config):
    """构建因子依赖图

    Args:
        config: 配置管理器

    Returns:
        依赖图对象
    """
    graph = DependencyGraph()

    # 添加价格数据节点
    graph.add_factor(FactorNode(
        name="price",
        dependencies=[],
        compute_func=lambda data: data
    ))

    # 添加 SMA_10 节点
    sma_10_window = config.get("factors.sma_10.window", default=10)
    graph.add_factor(FactorNode(
        name="sma_10",
        dependencies=["price"],
        compute_func=lambda data, price: compute_sma(price, sma_10_window)
    ))

    # 添加 SMA_20 节点
    sma_20_window = config.get("factors.sma_20.window", default=20)
    graph.add_factor(FactorNode(
        name="sma_20",
        dependencies=["price"],
        compute_func=lambda data, price: compute_sma(price, sma_20_window)
    ))

    # 添加 RSI 节点
    rsi_period = config.get("factors.rsi.period", default=14)
    graph.add_factor(FactorNode(
        name="rsi",
        dependencies=["price"],
        compute_func=lambda data, price: compute_rsi(price, rsi_period)
    ))

    # 添加 MACD 节点
    graph.add_factor(FactorNode(
        name="macd",
        dependencies=["sma_10", "sma_20"],
        compute_func=lambda data, sma_10, sma_20: compute_macd(sma_10, sma_20)
    ))

    return graph


# ============ 主流程 ============

def main():
    """主流程：集成所有优化功能"""
    print("="*60)
    print("因子计算集成示例")
    print("="*60)

    # 1. 加载配置
    print("\n[步骤1] 加载配置")
    config = ConfigManager()
    config_file = os.path.join(os.path.dirname(__file__), "integration_config.json")
    config.load(config_file)
    print(f"  配置加载完成")

    # 2. 生成测试数据
    print("\n[步骤2] 生成测试数据")
    data_length = config.get("data.limit", default=100)
    price_data = generate_price_data(length=data_length)
    print(f"  生成 {len(price_data)} 个价格数据点")
    print(f"  价格范围: {min(price_data):.2f} - {max(price_data):.2f}")

    # 3. 构建因子依赖图
    print("\n[步骤3] 构建因子依赖图")
    graph = build_factor_graph(config)
    print(f"  依赖图包含 {len(graph)} 个因子节点")

    # 4. 创建调度器并查看执行计划
    print("\n[步骤4] 生成执行计划")
    scheduler = ParallelScheduler(graph)
    layers = scheduler.schedule()
    print(f"  执行计划包含 {len(layers)} 个层级:")
    for i, layer in enumerate(layers):
        print(f"    层级 {i}: {layer}")

    # 5. 执行因子计算
    print("\n[步骤5] 执行因子计算")
    results = scheduler.execute(price_data)
    print(f"  计算完成，共 {len(results)} 个因子")

    # 6. 输出结果统计
    print("\n[步骤6] 结果统计")
    for name, value in results.items():
        if value is not None and isinstance(value, list):
            valid_count = sum(1 for v in value if v is not None)
            if valid_count > 0:
                valid_values = [v for v in value if v is not None]
                print(f"  {name}:")
                print(f"    有效数据点: {valid_count}/{len(value)}")
                print(f"    范围: {min(valid_values):.2f} - {max(valid_values):.2f}")
                print(f"    平均值: {sum(valid_values)/len(valid_values):.2f}")

    print("\n" + "="*60)
    print("[SUCCESS] 集成示例执行完成！")
    print("="*60)

    return results


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
