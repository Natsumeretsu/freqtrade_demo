# qlib_model_wrapper.py - Qlib 模型加载和预测
# 位置: 03_integration/model_loader/qlib_model_wrapper.py

import json
import joblib
from pathlib import Path
from typing import Optional, Union
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class QlibModelLoader:
    """Qlib 模型加载和预测包装器"""
    
    def __init__(self, model_path: Union[str, Path]):
        """
        初始化模型加载器
        
        Args:
            model_path: 模型文件路径（包含 model.pkl）
        """
        self.model_path = Path(model_path)
        self.model = None
        self.features = []
        self.feature_count = 0
        self.model_info = {}
        
        self._load_model()
        self._load_features()
        self._load_model_info()
    
    def _load_model(self):
        """加载 Qlib 模型"""
        model_file = self.model_path / "model.pkl"
        
        if not model_file.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_file}")
        
        try:
            self.model = joblib.load(model_file)
            logger.info(f"✓ 模型已加载: {model_file}")
        except Exception as e:
            logger.error(f"✗ 加载模型失败: {e}")
            raise
    
    def _load_features(self):
        """加载特征列表"""
        features_file = self.model_path / "features.json"
        
        if not features_file.exists():
            logger.warning(f"特征文件不存在: {features_file}")
            return
        
        try:
            with open(features_file, 'r') as f:
                data = json.load(f)
                self.features = data.get("features") or data.get("feature_columns", [])
                self.feature_count = len(self.features)
            logger.info(f"✓ 已加载 {self.feature_count} 个特征")
        except Exception as e:
            logger.error(f"✗ 加载特征列表失败: {e}")
    
    def _load_model_info(self):
        """加载模型信息"""
        info_file = self.model_path / "model_info.json"
        
        if info_file.exists():
            try:
                with open(info_file, 'r') as f:
                    self.model_info = json.load(f)
                logger.info(f"✓ 模型信息已加载: v{self.model_info.get('version', 'unknown')}")
            except Exception as e:
                logger.warning(f"加载模型信息失败: {e}")
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        进行预测
        
        Args:
            X: 特征矩阵 (DataFrame 或 numpy array)
        
        Returns:
            预测值 numpy array
        """
        if self.model is None:
            raise RuntimeError("模型未加载")
        
        # 确保特征顺序正确
        if isinstance(X, pd.DataFrame):
            if self.features:
                missing_features = set(self.features) - set(X.columns)
                if missing_features:
                    logger.warning(f"缺少特征: {missing_features}")
                
                X = X[[f for f in self.features if f in X.columns]]
            
            X = X.values
        
        try:
            predictions = self.model.predict(X)
            return predictions
        except Exception as e:
            logger.error(f"✗ 预测失败: {e}")
            raise
    
    def get_feature_importance(self) -> dict:
        """获取特征重要性"""
        if not hasattr(self.model, 'feature_importances_'):
            logger.warning("模型不提供特征重要性")
            return {}
        
        importances = self.model.feature_importances_
        feature_importance = dict(zip(self.features, importances))
        
        # 按重要性排序
        return dict(sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        ))
    
    def validate_features(self, dataframe: pd.DataFrame) -> bool:
        """验证输入数据特征"""
        if not self.features:
            logger.warning("未设置特征列表，跳过验证")
            return True
        
        missing = set(self.features) - set(dataframe.columns)
        if missing:
            logger.error(f"缺少必要特征: {missing}")
            return False
        
        return True
    
    def get_model_info(self) -> dict:
        """获取模型信息"""
        return {
            "model_type": type(self.model).__name__,
            "feature_count": self.feature_count,
            "features_sample": self.features[:5] if len(self.features) > 5 else self.features,
            "info": self.model_info
        }


class ModelCache:
    """模型缓存管理器"""
    
    def __init__(self, cache_dir: Union[str, Path] = "./model_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.loaders = {}
    
    def get_loader(self, model_name: str, model_path: Union[str, Path]) -> QlibModelLoader:
        """获取或创建模型加载器"""
        if model_name not in self.loaders:
            self.loaders[model_name] = QlibModelLoader(model_path)
            logger.info(f"✓ 缓存模型加载器: {model_name}")
        return self.loaders[model_name]
    
    def reload_model(self, model_name: str, model_path: Union[str, Path]):
        """重新加载模型"""
        self.loaders[model_name] = QlibModelLoader(model_path)
        logger.info(f"✓ 模型已重新加载: {model_name}")
    
    def clear_cache(self):
        """清空缓存"""
        self.loaders.clear()
        logger.info("✓ 模型缓存已清空")


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) > 1:
        model_path = sys.argv[1]
        loader = QlibModelLoader(model_path)
        print("\n模型信息:")
        print(json.dumps(loader.get_model_info(), indent=2))
    else:
        print("用法: python qlib_model_wrapper.py <model_path>")
