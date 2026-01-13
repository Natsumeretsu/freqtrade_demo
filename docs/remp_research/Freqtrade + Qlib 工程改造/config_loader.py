# config_loader.py - 统一的配置加载工具
# 位置: 03_integration/utils/config_loader.py

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

class ConfigManager:
    """配置管理器，负责加载和管理所有配置"""
    
    def __init__(self, config_dir: str = "./04_shared/config"):
        self.config_dir = Path(config_dir)
        self.configs: Dict[str, Any] = {}
        load_dotenv(".env")
        self._load_all_configs()
    
    def _load_all_configs(self):
        """加载配置目录下所有 YAML 文件"""
        if not self.config_dir.exists():
            raise FileNotFoundError(f"配置目录不存在: {self.config_dir}")
        
        for yaml_file in self.config_dir.glob("*.yaml"):
            config_name = yaml_file.stem
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    self.configs[config_name] = yaml.safe_load(f)
                print(f"✓ 已加载配置: {config_name}")
            except Exception as e:
                print(f"✗ 加载配置失败 {config_name}: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的嵌套查询"""
        parts = key.split(".")
        value = self.configs
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default
    
    def get_env(self, key: str, default: str = None) -> str:
        """从环境变量获取值"""
        return os.getenv(key, default)
    
    @property
    def freqtrade_user_data(self) -> Path:
        """获取 Freqtrade user_data 目录"""
        return Path(self.get_env("FREQTRADE_USER_DATA", "./01_freqtrade")).expanduser()
    
    @property
    def qlib_data_dir(self) -> Path:
        """获取 Qlib 数据目录"""
        return Path(self.get_env("QLIB_DATA_DIR", "./02_qlib_research/qlib_data")).expanduser()
    
    @property
    def model_dir(self) -> Path:
        """获取模型目录"""
        return Path(self.get_env("MODEL_DIR", "./02_qlib_research/models")).expanduser()
    
    def get_pairs(self) -> Dict[str, list]:
        """获取交易对配置"""
        symbols_config = self.configs.get("symbols", {})
        return {
            "freqtrade": symbols_config.get("pairs", []),
            "qlib": symbols_config.get("qlib_symbols", []),
        }
    
    def display(self):
        """显示当前配置摘要"""
        print("\n=== 配置摘要 ===")
        print(f"Freqtrade user_data: {self.freqtrade_user_data}")
        print(f"Qlib 数据目录: {self.qlib_data_dir}")
        print(f"模型目录: {self.model_dir}")
        print(f"交易对: {self.get_pairs()}")
        print(f"模型版本: {self.get_env('MODEL_VERSION', 'v1')}")
        print("================\n")


# 全局配置实例
_config_instance = None

def get_config() -> ConfigManager:
    """获取全局配置实例（单例）"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance

if __name__ == "__main__":
    config = get_config()
    config.display()
