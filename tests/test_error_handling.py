"""错误处理测试用例

测试自定义异常类和重试装饰器的功能。

创建日期: 2026-01-17
"""

import sys
import os
import time
from datetime import datetime

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.error_handling import (
    TradingSystemError,
    DataError,
    DataNotFoundError,
    DataValidationError,
    DataLoadError,
    ComputationError,
    FactorComputationError,
    InvalidParameterError,
    CacheError,
    retry
)


def test_custom_exceptions():
    """测试自定义异常类"""
    print("\n[测试1] 自定义异常类")

    # 测试基础异常
    try:
        raise TradingSystemError(
            message="测试错误",
            operation="test_operation",
            parameters={"param1": "value1"}
        )
    except TradingSystemError as e:
        assert e.message == "测试错误"
        assert e.operation == "test_operation"
        assert e.parameters == {"param1": "value1"}
        assert e.timestamp is not None
        print(f"  [OK] TradingSystemError: {e}")

    # 测试数据错误
    try:
        raise DataNotFoundError(
            message="数据未找到",
            operation="load_data",
            parameters={"symbol": "BTC/USDT"}
        )
    except DataError as e:
        assert isinstance(e, DataNotFoundError)
        assert e.message == "数据未找到"
        print(f"  [OK] DataNotFoundError: {e}")

    # 测试计算错误
    try:
        raise FactorComputationError(
            message="因子计算失败",
            operation="compute_factor",
            parameters={"factor": "RSI"}
        )
    except ComputationError as e:
        assert isinstance(e, FactorComputationError)
        assert e.message == "因子计算失败"
        print(f"  [OK] FactorComputationError: {e}")

    # 测试缓存错误
    try:
        raise CacheError(
            message="缓存操作失败",
            operation="cache_get"
        )
    except CacheError as e:
        assert e.message == "缓存操作失败"
        print(f"  [OK] CacheError: {e}")

    print("  [SUCCESS] 所有异常类测试通过")


def test_exception_hierarchy():
    """测试异常层次结构"""
    print("\n[测试2] 异常层次结构")

    # 测试继承关系
    assert issubclass(DataError, TradingSystemError)
    assert issubclass(DataNotFoundError, DataError)
    assert issubclass(ComputationError, TradingSystemError)
    assert issubclass(CacheError, TradingSystemError)
    print("  [OK] 异常继承关系正确")

    # 测试捕获父类异常
    try:
        raise DataNotFoundError("测试")
    except TradingSystemError:
        print("  [OK] 可以用父类捕获子类异常")

    print("  [SUCCESS] 异常层次结构测试通过")


def test_retry_decorator_success():
    """测试重试装饰器 - 成功场景"""
    print("\n[测试3] 重试装饰器 - 成功场景")

    call_count = [0]

    @retry(max_attempts=3, backoff=0.1)
    def successful_function():
        call_count[0] += 1
        return "success"

    result = successful_function()
    assert result == "success"
    assert call_count[0] == 1
    print(f"  [OK] 函数成功执行，调用次数: {call_count[0]}")
    print("  [SUCCESS] 成功场景测试通过")


def test_retry_decorator_eventual_success():
    """测试重试装饰器 - 最终成功场景"""
    print("\n[测试4] 重试装饰器 - 最终成功场景")

    call_count = [0]

    @retry(max_attempts=3, backoff=0.1, exceptions=(ValueError,))
    def eventually_successful_function():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError(f"尝试 {call_count[0]} 失败")
        return "success"

    start_time = time.time()
    result = eventually_successful_function()
    elapsed = time.time() - start_time

    assert result == "success"
    assert call_count[0] == 3
    assert elapsed >= 0.2, f"退避时间不足: {elapsed}"
    print(f"  [OK] 函数在第3次尝试成功，总调用次数: {call_count[0]}")
    print(f"  [OK] 总耗时: {elapsed:.2f}秒（包含退避时间）")
    print("  [SUCCESS] 最终成功场景测试通过")


def test_retry_decorator_max_attempts():
    """测试重试装饰器 - 达到最大重试次数"""
    print("\n[测试5] 重试装饰器 - 达到最大重试次数")

    call_count = [0]

    @retry(max_attempts=3, backoff=0.1, exceptions=(ValueError,))
    def always_failing_function():
        call_count[0] += 1
        raise ValueError(f"尝试 {call_count[0]} 失败")

    try:
        always_failing_function()
        assert False, "应该抛出异常"
    except ValueError as e:
        assert call_count[0] == 3
        assert "尝试 3 失败" in str(e)
        print(f"  [OK] 达到最大重试次数 {call_count[0]}，正确抛出异常")
        print(f"  [OK] 异常信息: {e}")

    print("  [SUCCESS] 最大重试次数测试通过")


def test_retry_decorator_exception_filtering():
    """测试重试装饰器 - 异常过滤"""
    print("\n[测试6] 重试装饰器 - 异常过滤")

    call_count = [0]

    @retry(max_attempts=3, backoff=0.1, exceptions=(ValueError,))
    def function_with_different_exception():
        call_count[0] += 1
        if call_count[0] == 1:
            raise TypeError("不应该重试的异常")
        return "success"

    try:
        function_with_different_exception()
        assert False, "应该抛出 TypeError"
    except TypeError as e:
        assert call_count[0] == 1
        assert "不应该重试的异常" in str(e)
        print(f"  [OK] 非指定异常类型不重试，调用次数: {call_count[0]}")
        print(f"  [OK] 异常信息: {e}")

    print("  [SUCCESS] 异常过滤测试通过")


def test_retry_with_custom_exceptions():
    """测试重试装饰器与自定义异常"""
    print("\n[测试7] 重试装饰器与自定义异常")

    call_count = [0]

    @retry(max_attempts=3, backoff=0.1, exceptions=(DataLoadError,))
    def load_data_with_retry():
        call_count[0] += 1
        if call_count[0] < 2:
            raise DataLoadError(
                message="数据加载失败",
                operation="load_data",
                parameters={"symbol": "BTC/USDT"}
            )
        return {"data": "loaded"}

    result = load_data_with_retry()
    assert result == {"data": "loaded"}
    assert call_count[0] == 2
    print(f"  [OK] 自定义异常重试成功，调用次数: {call_count[0]}")
    print("  [SUCCESS] 自定义异常重试测试通过")


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("开始运行错误处理测试套件")
    print("="*60)

    try:
        test_custom_exceptions()
        test_exception_hierarchy()
        test_retry_decorator_success()
        test_retry_decorator_eventual_success()
        test_retry_decorator_max_attempts()
        test_retry_decorator_exception_filtering()
        test_retry_with_custom_exceptions()

        print("\n" + "="*60)
        print("[SUCCESS] 所有错误处理测试通过！")
        print("="*60)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run_all_tests()
