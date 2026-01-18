"""配置向导

交互式配置生成工具。

创建日期: 2026-01-17
"""
import json
from pathlib import Path
from typing import Dict, Any


class ConfigWizard:
    """配置向导"""

    def __init__(self):
        self.config: Dict[str, Any] = {}

    def run(self) -> Dict[str, Any]:
        """运行配置向导"""
        print("=" * 60)
        print("Trading System 配置向导")
        print("=" * 60)
        
        self._configure_data()
        self._configure_factors()
        self._configure_cache()
        
        return self.config

    def _configure_data(self) -> None:
        """配置数据源"""
        print("\n[1/3] 数据源配置")
        symbols = input("  交易对 (逗号分隔): ").strip()
        timeframe = input("  时间周期 (如 1h): ").strip()
        
        self.config['data'] = {
            'symbols': [s.strip() for s in symbols.split(',')],
            'timeframe': timeframe
        }

    def _configure_factors(self) -> None:
        """配置因子"""
        print("\n[2/3] 因子配置")
        enable_cache = input("  启用因子缓存? (y/n): ").lower() == 'y'
        
        self.config['factors'] = {
            'enable_cache': enable_cache
        }

    def _configure_cache(self) -> None:
        """配置缓存"""
        print("\n[3/3] 缓存配置")
        max_size = input("  最大缓存大小: ").strip()
        
        self.config['cache'] = {
            'max_size': int(max_size) if max_size else 1000
        }

    def save(self, filename: str) -> None:
        """保存配置到文件"""
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        
        print(f"\n配置已保存到: {path}")


if __name__ == "__main__":
    wizard = ConfigWizard()
    config = wizard.run()
    wizard.save("config/generated_config.json")
