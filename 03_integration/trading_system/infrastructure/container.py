from __future__ import annotations

"""
container.py - 轻量依赖注入容器（配置驱动）

目标：
- 策略侧通过容器拿到"抽象用例"，而不是直接 new 具体实现
- 允许通过 04_shared/config/trading_system.yaml 切换实现
"""

import threading
from typing import Any

from trading_system.application.factor_usecase import FactorComputationUseCase
from trading_system.domain.factor_engine import IFactorEngine
from trading_system.infrastructure.config_loader import ConfigManager, get_config
from trading_system.infrastructure.factor_engines.factory import create_factor_engine
from trading_system.infrastructure.auto_risk import AutoRiskService
from trading_system.infrastructure.ml.model_loader import ModelCache
from trading_system.infrastructure.ml.qlib_signal import QlibSignalService


class DependencyContainer:
    def __init__(self, cfg: ConfigManager | None = None) -> None:
        self._cfg = cfg or get_config()
        self._cache: dict[str, Any] = {}

    def factor_engine(self) -> IFactorEngine:
        cached = self._cache.get("factor_engine")
        if isinstance(cached, IFactorEngine):
            return cached

        eng = create_factor_engine(self._cfg)
        self._cache["factor_engine"] = eng
        return eng

    def factor_usecase(self) -> FactorComputationUseCase:
        cached = self._cache.get("factor_usecase")
        if isinstance(cached, FactorComputationUseCase):
            return cached
        uc = FactorComputationUseCase(self.factor_engine())
        self._cache["factor_usecase"] = uc
        return uc

    def model_cache(self) -> ModelCache:
        cached = self._cache.get("model_cache")
        if isinstance(cached, ModelCache):
            return cached
        mc = ModelCache()
        self._cache["model_cache"] = mc
        return mc

    def qlib_signal_service(self) -> QlibSignalService:
        cached = self._cache.get("qlib_signal_service")
        if isinstance(cached, QlibSignalService):
            return cached
        svc = QlibSignalService(cfg=self._cfg, model_cache=self.model_cache())
        self._cache["qlib_signal_service"] = svc
        return svc

    def auto_risk_service(self) -> AutoRiskService:
        cached = self._cache.get("auto_risk_service")
        if isinstance(cached, AutoRiskService):
            return cached
        svc = AutoRiskService(cfg=self._cfg, model_cache=self.model_cache())
        self._cache["auto_risk_service"] = svc
        return svc


_CONTAINER: DependencyContainer | None = None
_CONTAINER_LOCK = threading.Lock()


def get_container() -> DependencyContainer:
    """获取全局容器单例（线程安全）"""
    global _CONTAINER
    if _CONTAINER is None:
        with _CONTAINER_LOCK:
            # Double-checked locking
            if _CONTAINER is None:
                _CONTAINER = DependencyContainer()
    return _CONTAINER
