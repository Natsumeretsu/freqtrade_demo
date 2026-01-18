"""配置管理测试用例

测试配置加载、验证和管理功能。

创建日期: 2026-01-17
"""

import sys
import os
import json
from pathlib import Path

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, '03_integration'))

from trading_system.infrastructure.config import (
    ConfigLoader,
    ConfigValidator,
    ConfigManager
)


def test_config_loader():
    """测试配置加载器"""
    print("\n[测试1] 配置加载器")

    loader = ConfigLoader()

    # 测试从文件加载
    test_file = os.path.join(os.path.dirname(__file__), "test_config.json")
    config = loader.load_from_file(test_file)

    assert "environment" in config
    assert config["environment"] == "test"
    assert "cache" in config
    assert config["cache"]["max_size"] == 1000
    print(f"  [OK] 从文件加载配置成功，共 {len(config)} 项")

    # 测试配置合并
    base = {"a": 1, "b": {"c": 2}}
    override = {"b": {"d": 3}, "e": 4}
    merged = loader.merge_configs(base, override)

    assert merged["a"] == 1
    assert merged["b"]["c"] == 2
    assert merged["b"]["d"] == 3
    assert merged["e"] == 4
    print("  [OK] 配置合并正确")

    print("  [SUCCESS] 配置加载器测试通过")


def test_config_validator():
    """测试配置验证器"""
    print("\n[测试2] 配置验证器")

    # 定义配置模式
    schema = {
        "required": ["environment", "cache"],
        "properties": {
            "environment": {"type": "string"},
            "cache": {"type": "object"}
        }
    }

    validator = ConfigValidator(schema)

    # 测试有效配置
    valid_config = {
        "environment": "test",
        "cache": {"max_size": 1000}
    }
    assert validator.validate(valid_config)
    print("  [OK] 有效配置验证通过")

    # 测试缺少必填字段
    invalid_config = {"environment": "test"}
    assert not validator.validate(invalid_config)
    errors = validator.get_errors()
    assert len(errors) > 0
    print(f"  [OK] 检测到缺少必填字段: {errors[0]}")

    print("  [SUCCESS] 配置验证器测试通过")


def test_config_manager():
    """测试配置管理器"""
    print("\n[测试3] 配置管理器")

    manager = ConfigManager()

    # 测试加载配置
    test_file = os.path.join(os.path.dirname(__file__), "test_config.json")
    manager.load(test_file)

    # 测试获取配置
    env = manager.get("environment")
    assert env == "test"
    print(f"  [OK] 获取配置: environment = {env}")

    # 测试嵌套键
    cache_size = manager.get("cache.max_size")
    assert cache_size == 1000
    print(f"  [OK] 获取嵌套配置: cache.max_size = {cache_size}")

    # 测试默认值
    missing = manager.get("missing.key", default="default_value")
    assert missing == "default_value"
    print("  [OK] 默认值正常工作")

    # 测试设置配置
    manager.set("cache.max_size", 2000)
    assert manager.get("cache.max_size") == 2000
    print("  [OK] 设置配置成功")

    print("  [SUCCESS] 配置管理器测试通过")


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("开始运行配置管理测试套件")
    print("="*60)

    try:
        test_config_loader()
        test_config_validator()
        test_config_manager()

        print("\n" + "="*60)
        print("[SUCCESS] 所有配置管理测试通过！")
        print("="*60)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run_all_tests()
