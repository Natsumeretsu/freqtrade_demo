"""
ETH 统计套利策略 - Regime 自适应

设计理念（基于学术研究）：
1. 统计显著性检验（z-score）而非固定阈值
2. Regime 识别（上涨/下跌/震荡）+ 自适应交易
3. 下跌趋势不交易（避免系统性亏损）
4. 严格风险控制（冷却期、时间止损）
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class ETHStatArbStrategy(IStrategy):
    """
    ETH 统计套利策略 - Regime 自适应

    核心特性：
    1. 线性回归 R² 识别市场 regime（上涨/下跌/震荡）
    2. 震荡市：z-score 均值回归（统计显著性 < -2）
    3. 上涨趋势：动量突破（价格突破 + 成交量确认）
    4. 下跌趋势：不交易（避免 7-8月 系统性亏损）
    5. 自适应止损：ATR × 2
    6. 冷却机制：连续 3 笔亏损暂停 24 小时
    """

    INTERFACE_VERSION = 3
    can_short = False

    timeframe = "5m"
    startup_candle_count = 100

    # 禁用出场信号（历史证明有害）
    use_exit_signal = False

    # 快速止盈目标
    minimal_roi = {
        "0": 0.03,   # 3% 快速止盈
        "10": 0.02,  # 10分钟后 2%
        "30": 0.01   # 30分钟后 1%
    }

    # 固定止损（将在 custom_stoploss 中动态调整为 ATR × 2）
    stoploss = -0.10  # 最大止损 10%
    trailing_stop = False

    # Regime 识别参数
    regime_period = 20  # 线性回归窗口
    regime_r2_threshold = 0.5  # R² 阈值（> 0.5 为趋势）

    # 统计套利参数
    zscore_period = 20  # z-score 计算窗口
    zscore_entry_threshold = -2.0  # 入场阈值（< -2 为统计显著超卖）

    # 成交量过滤
    volume_ma_period = 20
    volume_min_ratio = 0.5  # 最小成交量比率

    # 冷却机制
    cooling_period_hours = 24  # 冷却期（小时）
    max_consecutive_losses = 3  # 最大连续亏损次数

    def __init__(self, config: dict) -> None:
        """初始化策略"""
        super().__init__(config)
        self.consecutive_losses = 0
        self.last_loss_time = None

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """计算指标"""

        # 1. Regime 识别：线性回归
        dataframe['regime_slope'] = self._calculate_linear_regression_slope(
            dataframe['close'], self.regime_period
        )
        dataframe['regime_r2'] = self._calculate_linear_regression_r2(
            dataframe['close'], self.regime_period
        )

        # 2. Regime 分类
        dataframe['regime'] = 'ranging'  # 默认震荡市
        dataframe.loc[
            (dataframe['regime_slope'] > 0) & (dataframe['regime_r2'] > self.regime_r2_threshold),
            'regime'
        ] = 'uptrend'
        dataframe.loc[
            (dataframe['regime_slope'] < 0) & (dataframe['regime_r2'] > self.regime_r2_threshold),
            'regime'
        ] = 'downtrend'

        # 3. 统计套利：z-score
        dataframe['zscore'] = self._calculate_zscore(
            dataframe['close'], self.zscore_period
        )

        # 4. 动量指标：突破
        dataframe['high_20'] = dataframe['high'].rolling(20).max()

        # 5. 成交量
        dataframe['volume_ma'] = dataframe['volume'].rolling(self.volume_ma_period).mean()

        # 6. ATR（用于动态止损）
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        入场信号 - Regime 自适应
        """

        # 冷却期检查
        if self._is_in_cooling_period():
            return dataframe

        # 成交量过滤（全局）
        volume_filter = dataframe['volume'] > dataframe['volume_ma'] * self.volume_min_ratio

        # 震荡市：z-score 均值回归
        ranging_conditions = (
            (dataframe['regime'] == 'ranging') &
            (dataframe['zscore'] < self.zscore_entry_threshold) &  # 统计显著超卖
            volume_filter
        )

        # 上涨趋势：动量突破
        uptrend_conditions = (
            (dataframe['regime'] == 'uptrend') &
            (dataframe['close'] > dataframe['high_20'].shift(1)) &  # 突破 20 期高点
            (dataframe['volume'] > dataframe['volume_ma'] * 1.5) &  # 成交量放大
            volume_filter
        )

        # 下跌趋势：不交易（关键改进）
        # downtrend_conditions = False

        # 合并入场条件
        dataframe.loc[
            ranging_conditions | uptrend_conditions,
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        出场信号 - 禁用（只依赖 ROI + 止损）
        """
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        自适应止损 - ATR × 2
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if 'atr' in last_candle:
            atr = last_candle['atr']
            # 止损距离 = ATR × 2
            stop_loss_distance = (atr / current_rate) * 2.0
            return -min(stop_loss_distance, 0.10)  # 最大止损 10%

        return self.stoploss

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                   current_rate: float, current_profit: float, **kwargs) -> str | None:
        """
        自定义出场 - 时间止损
        """
        # 时间止损：持仓 > 4 小时
        if (current_time - trade.open_date_utc).total_seconds() > 4 * 3600:
            return 'time_stop_4h'

        return None

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float,
                          rate: float, time_in_force: str, exit_reason: str, **kwargs) -> bool:
        """
        确认出场 - 更新冷却机制
        """
        # 如果是亏损交易，更新连续亏损计数
        if trade.calc_profit_ratio(rate) < 0:
            self.consecutive_losses += 1
            self.last_loss_time = datetime.now()
        else:
            # 盈利交易重置计数
            self.consecutive_losses = 0
            self.last_loss_time = None

        return True

    # ========== 辅助方法 ==========

    def _calculate_linear_regression_slope(self, series: pd.Series, period: int) -> pd.Series:
        """计算线性回归斜率"""
        def calc_slope(y):
            if len(y) < period:
                return 0
            x = np.arange(len(y))
            slope = np.polyfit(x, y, 1)[0]
            return slope

        return series.rolling(period).apply(calc_slope, raw=True)

    def _calculate_linear_regression_r2(self, series: pd.Series, period: int) -> pd.Series:
        """计算线性回归 R²"""
        def calc_r2(y):
            if len(y) < period:
                return 0
            x = np.arange(len(y))
            slope, intercept = np.polyfit(x, y, 1)
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            return r2

        return series.rolling(period).apply(calc_r2, raw=True)

    def _calculate_zscore(self, series: pd.Series, period: int) -> pd.Series:
        """计算 z-score"""
        mean = series.rolling(period).mean()
        std = series.rolling(period).std()
        zscore = (series - mean) / std
        return zscore

    def _is_in_cooling_period(self) -> bool:
        """检查是否在冷却期"""
        if self.consecutive_losses >= self.max_consecutive_losses and self.last_loss_time:
            elapsed = (datetime.now() - self.last_loss_time).total_seconds() / 3600
            return elapsed < self.cooling_period_hours
        return False
