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
        model_path_cfg = None
        if hasattr(self, "_ft_params_from_file") and isinstance(self._ft_params_from_file, dict):
            model_path_cfg = self._ft_params_from_file.get("model_path")

        if model_path_cfg:
            raw_path = Path(str(model_path_cfg))
            model_path = raw_path if raw_path.is_absolute() else Path(self.config["user_data_dir"]) / raw_path
        else:
            model_path = (
                Path(self.config["user_data_dir"]) / "models" / "knn_trend_window_btc_usdt_1h.pkl"
            )

        if not model_path.is_file():
            raise FileNotFoundError(
                f"未找到模型文件：{model_path}。请先运行 scripts/train_knn_trend_window.py 生成模型。"
            )

        print(f"Loading KNN model from: {model_path}")
        self.knn_model = joblib.load(model_path)

        default_cols = get_knn_window_feature_columns(self.feature_window)
        self._feature_columns = list(getattr(self.knn_model, "feature_names_in_", default_cols))

        self._timeframe_minutes = self._timeframe_to_minutes(self.timeframe)
        self._model_horizon = int(getattr(self.knn_model, "horizon", 6))

    def _get_hold_minutes(self) -> int:
        hold_mult = float(self.max_hold_mult.value)
        if hold_mult <= 0:
            return 0

        timeframe_minutes = int(getattr(self, "_timeframe_minutes", self._timeframe_to_minutes(self.timeframe)))
        model_horizon = int(getattr(self, "_model_horizon", int(getattr(self.knn_model, "horizon", 6))))
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
        hold_minutes = int(self._get_hold_minutes())
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

    def _predict(self, dataframe: DataFrame) -> DataFrame:
        if "knn_pred" in dataframe.columns and "knn_proba" in dataframe.columns:
            return dataframe

        if not hasattr(self, "knn_model"):
            raise RuntimeError("KNN 模型未加载：请确认已执行 bot_start()。")

        feature_columns = getattr(self, "_feature_columns", get_knn_window_feature_columns(self.feature_window))
        missing_columns = [col for col in feature_columns if col not in dataframe.columns]
        if missing_columns:
            raise ValueError(f"缺少 KNN 特征列：{missing_columns}")

        x = (
            dataframe[feature_columns]
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .astype("float64")
        )

        preds = self.knn_model.predict(x)
        dataframe["knn_pred"] = preds

        if hasattr(self.knn_model, "predict_proba"):
            probas = self.knn_model.predict_proba(x)
            classes = getattr(self.knn_model, "classes_", None)
            if classes is not None and 1 in list(classes):
                idx = list(classes).index(1)
                dataframe["knn_proba"] = probas[:, idx]
            else:
                dataframe["knn_proba"] = probas[:, -1]
        else:
            dataframe["knn_proba"] = np.where(dataframe["knn_pred"] == 1, 1.0, 0.0)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self._predict(dataframe)

        adx_min = int(self.buy_adx_min.value)
        proba_min = float(self.buy_proba_min.value)
        require_pred = bool(self.buy_require_pred.value)

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
        dataframe = self._predict(dataframe)

        trend_break = (dataframe["ema_fast"] < dataframe["ema_slow"]) | (
            dataframe["close"] < dataframe["ema_long"]
        )

        dataframe.loc[
            (
                trend_break
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1

        return dataframe
