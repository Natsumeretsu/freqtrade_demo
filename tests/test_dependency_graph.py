"""因子依赖图测试用例

测试依赖图构建、拓扑排序和并行调度功能。

创建日期: 2026-01-17
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.dependency import (
    DependencyGraph,
    FactorNode,
    TopologicalSorter,
    ParallelScheduler
)


def test_dependency_graph():
    """测试依赖图构建"""
    print("\n[测试1] 依赖图构建")

    graph = DependencyGraph()

    # 添加因子节点
    graph.add_factor(FactorNode(name="price", dependencies=[]))
    graph.add_factor(FactorNode(name="sma_10", dependencies=["price"]))
    graph.add_factor(FactorNode(name="sma_20", dependencies=["price"]))
    graph.add_factor(FactorNode(name="rsi", dependencies=["price"]))
    graph.add_factor(FactorNode(name="macd", dependencies=["sma_10", "sma_20"]))

    # 验证节点数量
    assert len(graph) == 5
    print(f"  [OK] 添加了 {len(graph)} 个因子节点")

    # 验证依赖关系
    assert graph.get_dependencies("macd") == ["sma_10", "sma_20"]
    assert graph.get_dependencies("sma_10") == ["price"]
    print("  [OK] 依赖关系正确")

    # 验证入度
    assert graph.get_in_degree("price") == 0
    assert graph.get_in_degree("sma_10") == 1
    assert graph.get_in_degree("macd") == 2
    print("  [OK] 入度计算正确")

    print("  [SUCCESS] 依赖图构建测试通过")


def test_cycle_detection():
    """测试循环依赖检测"""
    print("\n[测试2] 循环依赖检测")

    graph = DependencyGraph()

    # 添加正常的依赖关系
    graph.add_factor(FactorNode(name="a", dependencies=[]))
    graph.add_factor(FactorNode(name="b", dependencies=["a"]))
    graph.add_factor(FactorNode(name="c", dependencies=["b"]))

    # 验证无环
    cycle = graph.detect_cycle()
    assert cycle is None
    print("  [OK] 正常依赖图无环")

    # 创建循环依赖
    graph2 = DependencyGraph()
    graph2.add_factor(FactorNode(name="x", dependencies=["z"]))
    graph2.add_factor(FactorNode(name="y", dependencies=["x"]))
    graph2.add_factor(FactorNode(name="z", dependencies=["y"]))

    # 验证检测到环
    cycle = graph2.detect_cycle()
    assert cycle is not None
    print(f"  [OK] 检测到循环依赖: {' -> '.join(cycle)}")

    print("  [SUCCESS] 循环依赖检测测试通过")


def test_topological_sort():
    """测试拓扑排序"""
    print("\n[测试3] 拓扑排序")

    graph = DependencyGraph()
    graph.add_factor(FactorNode(name="price", dependencies=[]))
    graph.add_factor(FactorNode(name="sma_10", dependencies=["price"]))
    graph.add_factor(FactorNode(name="sma_20", dependencies=["price"]))
    graph.add_factor(FactorNode(name="rsi", dependencies=["price"]))
    graph.add_factor(FactorNode(name="macd", dependencies=["sma_10", "sma_20"]))

    sorter = TopologicalSorter(graph)
    order = sorter.sort()

    # 验证排序结果
    assert len(order) == 5
    print(f"  [OK] 排序结果: {order}")

    # 验证依赖关系：依赖的因子必须在前面
    price_idx = order.index("price")
    sma_10_idx = order.index("sma_10")
    sma_20_idx = order.index("sma_20")
    macd_idx = order.index("macd")

    assert price_idx < sma_10_idx
    assert price_idx < sma_20_idx
    assert sma_10_idx < macd_idx
    assert sma_20_idx < macd_idx
    print("  [OK] 依赖关系顺序正确")

    print("  [SUCCESS] 拓扑排序测试通过")


def test_layer_division():
    """测试层级划分"""
    print("\n[测试4] 层级划分")

    graph = DependencyGraph()
    graph.add_factor(FactorNode(name="price", dependencies=[]))
    graph.add_factor(FactorNode(name="sma_10", dependencies=["price"]))
    graph.add_factor(FactorNode(name="sma_20", dependencies=["price"]))
    graph.add_factor(FactorNode(name="rsi", dependencies=["price"]))
    graph.add_factor(FactorNode(name="macd", dependencies=["sma_10", "sma_20"]))

    sorter = TopologicalSorter(graph)
    layers = sorter.get_layers()

    # 验证层级数量
    assert len(layers) == 3
    print(f"  [OK] 共 {len(layers)} 个层级")

    # 验证第 0 层（无依赖）
    assert "price" in layers[0]
    print(f"  [OK] 第 0 层: {layers[0]}")

    # 验证第 1 层（依赖 price）
    assert "sma_10" in layers[1]
    assert "sma_20" in layers[1]
    assert "rsi" in layers[1]
    print(f"  [OK] 第 1 层: {layers[1]}")

    # 验证第 2 层（依赖 sma_10 和 sma_20）
    assert "macd" in layers[2]
    print(f"  [OK] 第 2 层: {layers[2]}")

    print("  [SUCCESS] 层级划分测试通过")


def test_parallel_scheduler():
    """测试并行调度器"""
    print("\n[测试5] 并行调度器")

    # 定义简单的计算函数
    def compute_price(data):
        return data

    def compute_sma(data, price):
        return sum(price) / len(price) if price else 0

    def compute_macd(data, sma_10, sma_20):
        return sma_10 - sma_20

    # 构建依赖图
    graph = DependencyGraph()
    graph.add_factor(FactorNode(name="price", dependencies=[], compute_func=compute_price))
    graph.add_factor(FactorNode(name="sma_10", dependencies=["price"], compute_func=compute_sma))
    graph.add_factor(FactorNode(name="sma_20", dependencies=["price"], compute_func=compute_sma))
    graph.add_factor(FactorNode(name="macd", dependencies=["sma_10", "sma_20"], compute_func=compute_macd))

    # 执行计算
    scheduler = ParallelScheduler(graph)
    data = [100, 101, 102, 103, 104]
    results = scheduler.execute(data)

    # 验证结果
    assert "price" in results
    assert "sma_10" in results
    assert "sma_20" in results
    assert "macd" in results
    print(f"  [OK] 计算了 {len(results)} 个因子")
    print(f"  [OK] MACD = {results['macd']}")

    print("  [SUCCESS] 并行调度器测试通过")


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("开始运行因子依赖图测试套件")
    print("="*60)

    try:
        test_dependency_graph()
        test_cycle_detection()
        test_topological_sort()
        test_layer_division()
        test_parallel_scheduler()

        print("\n" + "="*60)
        print("[SUCCESS] 所有因子依赖图测试通过！")
        print("="*60)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run_all_tests()
