from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from freqtrade.persistence import Trade
from freqtrade.strategy import BooleanParameter, DecimalParameter, IStrategy, IntParameter
from pandas import DataFrame

# 允许 Freqtrade 按文件加载策略时，也能导入项目根目录下的共享特征工程模块
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from knn_window_features import (
    build_knn_trend_features,
    build_knn_window_features,
    build_trend_indicators,
    get_knn_window_feature_columns,
)


class KNNTrendWindowStrategy(IStrategy):
    """
    升级版 KNN 策略：先做趋势过滤，再用“多 K 线窗口特征”做模式识别。

    设计动机（贴近价格行为/威科夫的工作流）：
    1) 先判断市场是否处于“可交易的趋势段”（过滤震荡期的噪音）
    2) 只在趋势段内，使用最近 N 根K线组合的形态/动量/波动特征做分类
    """

    INTERFACE_VERSION = 3

    timeframe = "1h"
    process_only_new_candles = True

    # EMA200 + ADX + 特征窗口预热
    startup_candle_count: int = 240

    # 让策略更贴近训练标签：在持仓窗口内尝试吃到约 0.6% 的目标收益
    minimal_roi = {"0": 0.006}
    stoploss = -0.10

    use_exit_signal = True

    # --- 可调参数（用于优化“趋势过滤”强度 & KNN 置信度阈值）---
    buy_adx_min = IntParameter(5, 40, default=10, space="buy", optimize=True)
    buy_proba_min = DecimalParameter(0.20, 0.80, default=0.35, decimals=2, space="buy", optimize=True)
    buy_require_pred = BooleanParameter(default=True, space="buy", optimize=False)

    # --- 可调参数（退出/持仓周期）---
    sell_use_model_exit = BooleanParameter(default=False, space="sell", optimize=False)
    # 趋势破坏退出：当趋势结构被破坏时，提前离场以压缩 time_exit 的尾部大亏
    # - 默认关闭：避免“加了退出条件反而过拟合”的错觉，需在验证集上选参后再启用
    sell_trend_exit = BooleanParameter(default=False, space="sell", optimize=False)
    # 趋势破坏确认根数：要求连续 N 根满足趋势破坏条件，避免单根噪音触发
    sell_trend_exit_confirm = IntParameter(1, 3, default=2, space="sell", optimize=True)
    # 价格相对 EMA 的“破位缓冲”：例如 0.005 表示需跌破 EMA0.5% 才算破位（更抗噪）
    sell_trend_exit_buffer = DecimalParameter(0.0, 0.02, default=0.0, decimals=3, space="sell", optimize=True)
    # 趋势退出是否要求模型翻空确认（knn_pred == -1）；开启更保守，但可能更慢
    sell_trend_exit_require_model = BooleanParameter(default=False, space="sell", optimize=False)
    # 到达模型 horizon 后仍浮亏超过阈值，则提前截断（防止少量 time_exit 大亏吞噬整体收益）
    # - 0 表示禁用
    # - 例如 0.01 表示浮亏 <= -1% 时触发
    sell_time_loss_cut = DecimalParameter(0.0, 0.05, default=0.0, decimals=3, space="sell", optimize=True)
    # 典型持仓周期偏“几小时”的场景下，建议用它控制 time_exit：
    # - 0 表示禁用 time_exit（仅靠 roi / exit_signal / stoploss 出场）
    # - 1.0 表示按模型 horizon 出场（例如 horizon=6 且 1h => 6 小时）
    # - 2.0 表示放宽为 2*horizon
    max_hold_mult = DecimalParameter(0.0, 4.0, default=1.0, decimals=1, space="sell", optimize=True)

    # --- 固定配置：窗口特征 & 趋势指标周期 ---
    feature_window: int = 8
    ema_fast: int = 20
    ema_slow: int = 50
    ema_long: int = 200
    adx_period: int = 14

    def bot_start(self, **kwargs):
        self._models_by_pair: dict[str, object] = {}
        self._feature_columns_by_pair: dict[str, list[str]] = {}
        self._model_horizon_by_pair: dict[str, int] = {}

        self._timeframe_minutes = self._timeframe_to_minutes(self.timeframe)

        params_from_file: dict = {}
        if hasattr(self, "_ft_params_from_file") and isinstance(self._ft_params_from_file, dict):
            params_from_file = self._ft_params_from_file

        self._params_from_file = params_from_file
        pair_overrides = params_from_file.get("pair_overrides")
        self._pair_overrides = pair_overrides if isinstance(pair_overrides, dict) else {}

        self._default_model_path_cfg = params_from_file.get("model_path") or "models/knn_trend_window_btc_usdt_1h.pkl"

        # 预检：如果配置了 per-pair 模型路径，尽早暴露拼写/缺文件
        for pair, cfg in self._pair_overrides.items():
            if not isinstance(cfg, dict):
                continue
            model_path_cfg = cfg.get("model_path")
            if not model_path_cfg:
                continue
            model_path = self._resolve_model_path(model_path_cfg)
            if not model_path.is_file():
                raise FileNotFoundError(
                    f"未找到模型文件：{model_path}（pair={pair}）。请先运行 scripts/train_knn_trend_window.py 生成模型。"
                )

        # 兼容：未启用 per-pair 覆盖时，保持“启动即加载模型”的行为
        if not self._pair_overrides:
            self._ensure_model_loaded(pair=None)

    def _get_pair_param(self, pair: str | None, key: str, default):
        if not pair:
            return default

        overrides = getattr(self, "_pair_overrides", None)
        if not isinstance(overrides, dict):
            return default

        cfg = overrides.get(pair)
        if not isinstance(cfg, dict):
            return default

        return cfg.get(key, default)

    def _get_model_path_cfg(self, pair: str | None) -> str:
        model_path_cfg = self._get_pair_param(pair, "model_path", None)
        if model_path_cfg:
            return str(model_path_cfg)

        return str(getattr(self, "_default_model_path_cfg", "models/knn_trend_window_btc_usdt_1h.pkl"))

    def _resolve_model_path(self, model_path_cfg: str) -> Path:
        raw_path = Path(str(model_path_cfg))
        if raw_path.is_absolute():
            return raw_path
        return Path(self.config["user_data_dir"]) / raw_path

    def _ensure_model_loaded(self, pair: str | None):
        cache_key = pair or "__default__"
        models = getattr(self, "_models_by_pair", None)
        if isinstance(models, dict) and cache_key in models:
            return models[cache_key]

        model_path_cfg = self._get_model_path_cfg(pair)
        model_path = self._resolve_model_path(model_path_cfg)
        if not model_path.is_file():
            raise FileNotFoundError(
                f"未找到模型文件：{model_path}。请先运行 scripts/train_knn_trend_window.py 生成模型。"
            )

        print(f"Loading KNN model from: {model_path}")
        model = joblib.load(model_path)

        default_cols = get_knn_window_feature_columns(self.feature_window)
        self._models_by_pair[cache_key] = model
        self._feature_columns_by_pair[cache_key] = list(getattr(model, "feature_names_in_", default_cols))
        self._model_horizon_by_pair[cache_key] = int(getattr(model, "horizon", 6))

        return model

    def _get_hold_minutes(self, pair: str | None = None) -> int:
        default_hold_mult = float(self.max_hold_mult.value)
        hold_mult = float(self._get_pair_param(pair, "max_hold_mult", default_hold_mult))
        if hold_mult <= 0:
            return 0

        timeframe_minutes = int(getattr(self, "_timeframe_minutes", self._timeframe_to_minutes(self.timeframe)))
        cache_key = pair or "__default__"
        if cache_key not in self._model_horizon_by_pair:
            self._ensure_model_loaded(pair)
        model_horizon = int(self._model_horizon_by_pair.get(cache_key, 6))
        return int(round(timeframe_minutes * model_horizon * hold_mult))

    @staticmethod
    def _timeframe_to_minutes(timeframe: str) -> int:
        match = re.fullmatch(r"(\d+)([mhdw])", timeframe.strip())
        if not match:
            raise ValueError(f"不支持的 timeframe：{timeframe}")

        value = int(match.group(1))
        unit = match.group(2)
        if unit == "m":
            return value
        if unit == "h":
            return value * 60
        if unit == "d":
            return value * 60 * 24
        if unit == "w":
            return value * 60 * 24 * 7
        raise ValueError(f"不支持的 timeframe：{timeframe}")

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        loss_cut = float(
            self._get_pair_param(pair, "sell_time_loss_cut", float(self.sell_time_loss_cut.value))
        )
        if loss_cut > 0:
            timeframe_minutes = int(getattr(self, "_timeframe_minutes", self._timeframe_to_minutes(self.timeframe)))
            cache_key = pair or "__default__"
            if cache_key not in self._model_horizon_by_pair:
                self._ensure_model_loaded(pair)
            model_horizon = int(self._model_horizon_by_pair.get(cache_key, 6))
            horizon_minutes = int(round(timeframe_minutes * model_horizon))
            if horizon_minutes > 0 and current_time - trade.open_date_utc >= timedelta(minutes=horizon_minutes):
                if float(current_profit) <= -loss_cut:
                    return "time_loss_cut"

        hold_minutes = int(self._get_hold_minutes(pair=pair))
        if hold_minutes <= 0:
            return None

        if current_time - trade.open_date_utc >= timedelta(minutes=hold_minutes):
            return "time_exit"

        return None

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1) 多 K 线窗口特征（仅用历史数据，不泄露未来）
        window_features = build_knn_window_features(dataframe, window=self.feature_window)

        # 2) 趋势指标（用于过滤交易环境）
        trend = build_trend_indicators(
            dataframe,
            ema_fast=self.ema_fast,
            ema_slow=self.ema_slow,
            ema_long=self.ema_long,
            adx_period=self.adx_period,
        )
        trend_features = build_knn_trend_features(dataframe, trend)

        # 一次性合并，避免逐列插入导致 DataFrame 碎片化
        new_df = pd.concat([window_features, trend, trend_features], axis=1).replace([np.inf, -np.inf], np.nan)
        existing_cols = [c for c in new_df.columns if c in dataframe.columns]
        if existing_cols:
            dataframe = dataframe.drop(columns=existing_cols)
        dataframe = pd.concat([dataframe, new_df], axis=1)

        return dataframe

    def _predict(self, dataframe: DataFrame, pair: str | None = None) -> DataFrame:
        if "knn_pred" in dataframe.columns and "knn_proba" in dataframe.columns:
            return dataframe

        model = self._ensure_model_loaded(pair)
        cache_key = pair or "__default__"

        feature_columns = self._feature_columns_by_pair.get(
            cache_key,
            get_knn_window_feature_columns(self.feature_window),
        )
        missing_columns = [col for col in feature_columns if col not in dataframe.columns]
        if missing_columns:
            raise ValueError(f"缺少 KNN 特征列：{missing_columns}")

        x = (
            dataframe[feature_columns]
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .astype("float64")
        )

        preds = model.predict(x)
        dataframe["knn_pred"] = preds

        if hasattr(model, "predict_proba"):
            probas = model.predict_proba(x)
            classes = getattr(model, "classes_", None)
            if classes is not None and 1 in list(classes):
                idx = list(classes).index(1)
                dataframe["knn_proba"] = probas[:, idx]
            else:
                dataframe["knn_proba"] = probas[:, -1]
        else:
            dataframe["knn_proba"] = np.where(dataframe["knn_pred"] == 1, 1.0, 0.0)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = str(metadata.get("pair")) if isinstance(metadata, dict) and metadata.get("pair") else None
        dataframe = self._predict(dataframe, pair=pair)

        adx_min = int(self._get_pair_param(pair, "buy_adx_min", int(self.buy_adx_min.value)))
        proba_min = float(self._get_pair_param(pair, "buy_proba_min", float(self.buy_proba_min.value)))
        require_pred = bool(self._get_pair_param(pair, "buy_require_pred", bool(self.buy_require_pred.value)))

        trend_up = (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["ema_slow"] > dataframe["ema_long"])
            & (dataframe["close"] > dataframe["ema_long"])
            & (dataframe["adx"] > adx_min)
        )

        if require_pred:
            pred_ok = dataframe["knn_pred"] == 1
            enter_tag = "KNN_PRED_PROBA"
        else:
            pred_ok = pd.Series(True, index=dataframe.index)
            enter_tag = "KNN_PROBA"

        dataframe.loc[
            (
                trend_up
                & pred_ok
                & (dataframe["knn_proba"] >= proba_min)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        dataframe.loc[
            (
                trend_up
                & pred_ok
                & (dataframe["knn_proba"] >= proba_min)
                & (dataframe["volume"] > 0)
            ),
            "enter_tag",
        ] = enter_tag

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = str(metadata.get("pair")) if isinstance(metadata, dict) and metadata.get("pair") else None
        use_model_exit = bool(
            self._get_pair_param(pair, "sell_use_model_exit", bool(self.sell_use_model_exit.value))
        )
        use_trend_exit = bool(
            self._get_pair_param(pair, "sell_trend_exit", bool(self.sell_trend_exit.value))
        )
        if not use_model_exit and not use_trend_exit:
            return dataframe

        if use_model_exit or bool(
            self._get_pair_param(pair, "sell_trend_exit_require_model", bool(self.sell_trend_exit_require_model.value))
        ):
            dataframe = self._predict(dataframe, pair=pair)

        vol_ok = dataframe["volume"] > 0
        exit_mask = pd.Series(False, index=dataframe.index)

        if use_model_exit:
            exit_by_model = dataframe["knn_pred"] == -1
            model_mask = exit_by_model & vol_ok
            exit_mask = exit_mask | model_mask
            dataframe.loc[model_mask, "exit_tag"] = "MODEL_PRED"

        if use_trend_exit:
            confirm = int(
                self._get_pair_param(
                    pair,
                    "sell_trend_exit_confirm",
                    int(self.sell_trend_exit_confirm.value),
                )
            )
            confirm = max(1, min(3, confirm))
            buffer = float(
                self._get_pair_param(
                    pair,
                    "sell_trend_exit_buffer",
                    float(self.sell_trend_exit_buffer.value),
                )
            )
            buffer = max(0.0, min(0.02, buffer))
            require_model = bool(
                self._get_pair_param(
                    pair,
                    "sell_trend_exit_require_model",
                    bool(self.sell_trend_exit_require_model.value),
                )
            )

            ema_slow = dataframe["ema_slow"]
            ema_long = dataframe["ema_long"]

            # 趋势破坏：长周期破位（收盘跌破 EMA200）或短周期结构破坏（快慢线转弱且跌破 EMA50）
            trend_break = (dataframe["close"] < ema_long) | (
                (dataframe["ema_fast"] < ema_slow) & (dataframe["close"] < (ema_slow * (1.0 - buffer)))
            )
            if confirm > 1:
                trend_break = trend_break.rolling(window=confirm, min_periods=confirm).sum() >= confirm

            if require_model:
                trend_break = trend_break & (dataframe["knn_pred"] == -1)

            trend_mask = trend_break & vol_ok
            exit_mask = exit_mask | trend_mask
            dataframe.loc[trend_mask, "exit_tag"] = "TREND_BREAK"

        dataframe.loc[exit_mask, "exit_long"] = 1

        return dataframe
