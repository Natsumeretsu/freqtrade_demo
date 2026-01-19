"""
ETH Microstructure Strategy - 基于市场微观结构的交易策略

核心思想：
1. 使用订单簿微观结构特征替代传统技术指标
2. 基于 Order Flow Imbalance, VPIN, Microprice 等特征
3. 使用 HMM 进行市场状态检测，解决季节性失败问题
4. 多分类预测：做多/做空/不交易

参考文献：
- Easley et al. (2012): VPIN - Volume-Synchronized Probability of Informed Trading
- Cartea et al. (2015): Order Book Imbalance and Price Impact
- Kyle (1985): Market Microstructure and Market Impact
"""

from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame
import pandas as pd
import numpy as np
import talib.abstract as ta
from functools import reduce


class ETHMicrostructureStrategy(IStrategy):

    # 基础配置
    timeframe = '1m'
    can_short = True

    # ROI 和 Stoploss（1分钟剥头皮 - 行业标准）
    minimal_roi = {
        "0": 0.005,   # 0.5% 立即止盈
        "3": 0.003,   # 3分钟后降到 0.3%
        "5": 0.002    # 5分钟后降到 0.2%
    }
    stoploss = -0.99  # 使用 custom_stoploss 动态 ATR 止损
    trailing_stop = True
    trailing_stop_positive = 0.002  # 达到 0.2% 后激活追踪止损
    trailing_stop_positive_offset = 0.003  # 0.3% 后开始追踪
    trailing_only_offset_is_reached = True

    # FreqAI 配置
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count = 100

    # 仓位管理
    position_adjustment_enable = False

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: dict, **kwargs) -> DataFrame:
        """
        特征工程 - 基于市场微观结构

        注意：
        1. Freqtrade 没有实时订单簿数据，我们使用 OHLCV 数据近似计算微观结构特征
        2. 所有特征必须以 % 开头才能被 FreqAI 识别
        """

        # ===== 1. 买卖压力（Money Flow 方法）=====
        # 使用 Money Flow Multiplier 计算买卖压力
        dataframe['%-price_change'] = dataframe['close'].pct_change()

        # Money Flow 方法
        dataframe['mf_multiplier'] = ((dataframe['close'] - dataframe['low']) - (dataframe['high'] - dataframe['close'])) / (dataframe['high'] - dataframe['low'])
        dataframe['mf_multiplier'] = dataframe['mf_multiplier'].fillna(0)
        dataframe['mf_volume'] = dataframe['mf_multiplier'] * dataframe['volume']
        dataframe['buy_pressure'] = np.where(dataframe['mf_volume'] > 0, dataframe['mf_volume'], 0)
        dataframe['sell_pressure'] = np.where(dataframe['mf_volume'] < 0, abs(dataframe['mf_volume']), 0)

        # ===== 2. VPIN 近似 =====
        # 使用成交量桶近似 VPIN
        num_buckets = 20  # 桶数量

        # 计算每根 K 线的买卖不平衡
        dataframe['volume_imbalance'] = abs(dataframe['buy_pressure'] - dataframe['sell_pressure'])

        # VPIN = 滚动窗口内的平均不平衡 / 平均成交量 - 添加 % 前缀
        dataframe['%-vpin'] = (
            dataframe['volume_imbalance'].rolling(num_buckets).sum() /
            (dataframe['volume'].rolling(num_buckets).sum() + 1e-10)
        )

        # ===== 3. ATR 归一化（区分度 2.11）=====
        dataframe['tr'] = np.maximum(
            dataframe['high'] - dataframe['low'],
            np.maximum(
                abs(dataframe['high'] - dataframe['close'].shift(1)),
                abs(dataframe['low'] - dataframe['close'].shift(1))
            )
        )
        dataframe['%-atr_14'] = dataframe['tr'].rolling(14).mean()
        dataframe['%-atr_normalized'] = dataframe['%-atr_14'] / dataframe['close']

        # ===== 4. 已实现波动率（区分度 1.99）=====
        for window in [12, 24, 48]:
            dataframe[f'%-realized_vol_{window}'] = dataframe['close'].pct_change().rolling(window).std()

        # ===== 5. 价格动量（区分度 0.21）=====
        for window in [5, 10, 15]:
            dataframe[f'%-momentum_{window}'] = dataframe['close'].pct_change(window)

        # ===== 6. 成交量相对强度（区分度 0.24）=====
        dataframe['%-volume_sma_12'] = dataframe['volume'].rolling(12).mean()
        dataframe['%-volume_ratio'] = dataframe['volume'] / (dataframe['%-volume_sma_12'] + 1e-10)

        # ===== 7. Microprice 近似 =====
        # 使用 high/low 近似 bid/ask
        dataframe['bid_approx'] = dataframe['low']
        dataframe['ask_approx'] = dataframe['high']
        dataframe['bid_volume_approx'] = dataframe['buy_pressure']
        dataframe['ask_volume_approx'] = dataframe['sell_pressure']

        # Microprice = (V_ask * P_bid + V_bid * P_ask) / (V_bid + V_ask) - 添加 % 前缀
        total_vol = dataframe['bid_volume_approx'] + dataframe['ask_volume_approx']
        dataframe['%-microprice'] = np.where(
            total_vol > 0,
            (dataframe['ask_volume_approx'] * dataframe['bid_approx'] +
             dataframe['bid_volume_approx'] * dataframe['ask_approx']) / total_vol,
            (dataframe['bid_approx'] + dataframe['ask_approx']) / 2
        )

        # Microprice 偏离 - 添加 % 前缀
        dataframe['%-microprice_vs_close'] = (dataframe['%-microprice'] - dataframe['close']) / dataframe['close']

        # ===== 4. 流动性指标 =====
        # Amihud Illiquidity: |return| / volume - 添加 % 前缀
        dataframe['%-amihud'] = abs(dataframe['%-price_change']) / (dataframe['volume'] + 1e-10)
        dataframe['%-amihud_ma'] = dataframe['%-amihud'].rolling(20).mean()

        # Kyle's Lambda 近似: price_impact / volume - 添加 % 前缀
        dataframe['%-kyle_lambda'] = abs(dataframe['%-price_change']) / (dataframe['volume'] + 1e-10)
        dataframe['%-kyle_lambda_ma'] = dataframe['%-kyle_lambda'].rolling(20).mean()

        # ===== 5. 波动率特征 =====
        # 已实现波动率 - 添加 % 前缀
        dataframe['%-realized_vol'] = dataframe['%-price_change'].rolling(20).std()

        # 价格区间 - 添加 % 前缀
        dataframe['%-price_range'] = (dataframe['high'] - dataframe['low']) / dataframe['close']
        dataframe['%-price_range_ma'] = dataframe['%-price_range'].rolling(20).mean()

        # 成交量波动率 - 添加 % 前缀
        dataframe['%-volume_vol'] = dataframe['volume'].rolling(20).std() / (dataframe['volume'].rolling(20).mean() + 1e-10)

        # ===== 6. 市场状态特征 =====
        # 使用简单的趋势和波动率状态分类（HMM 的简化版本）
        # 状态 0: 熊市（下跌 + 高波动）
        # 状态 1: 震荡（低波动）
        # 状态 2: 牛市（上涨 + 高波动）

        # Phase 1 优化：提高趋势阈值（±2% → ±5%），缩短计算窗口（20 → 15）

        # 趋势强度 - 添加 % 前缀
        dataframe['%-trend'] = (dataframe['close'] - dataframe['close'].shift(15)) / dataframe['close'].shift(15)

        # 状态分类 - 添加 % 前缀
        dataframe['%-regime_state'] = 1  # 默认震荡
        dataframe.loc[
            (dataframe['%-trend'] > 0.05) & (dataframe['%-realized_vol'] > dataframe['%-realized_vol'].rolling(100).quantile(0.5)),
            '%-regime_state'
        ] = 2  # 牛市
        dataframe.loc[
            (dataframe['%-trend'] < -0.05) & (dataframe['%-realized_vol'] > dataframe['%-realized_vol'].rolling(100).quantile(0.5)),
            '%-regime_state'
        ] = 0  # 熊市

        # ===== 7. 交易强度特征 =====
        # 成交量相对强度 - 添加 % 前缀
        dataframe['%-volume_ratio'] = dataframe['volume'] / (dataframe['volume'].rolling(20).mean() + 1e-10)

        # 价格动量 - 添加 % 前缀
        dataframe['%-momentum_5'] = (dataframe['close'] - dataframe['close'].shift(5)) / dataframe['close'].shift(5)
        dataframe['%-momentum_10'] = (dataframe['close'] - dataframe['close'].shift(10)) / dataframe['close'].shift(10)

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        基础特征 - 保持简单
        注意：所有特征必须以 % 开头才能被 FreqAI 识别
        """
        # 基础价格特征 - 添加 % 前缀
        dataframe['%-price_pct'] = dataframe['close'].pct_change()
        dataframe['%-volume_pct'] = dataframe['volume'].pct_change()

        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        标准化特征 - 不使用传统技术指标
        """
        # 不添加任何传统技术指标
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        设置预测目标 - 回归模型预测未来收益率

        1分钟剥头皮优化（行业标准）：
        - 预测窗口：5 分钟（5 根 1m K 线）
        - 预测目标：未来最大可获得收益率（扣除交易成本）
        - 交易成本：0.4%（双向 0.1% 手续费 + 0.1% 滑点）
        """
        # 计算未来收益（5 分钟预测窗口）
        forward_window = 5  # 未来 5 根 K 线（5 分钟）

        # 计算未来最高价和最低价
        dataframe['future_max'] = dataframe['high'].rolling(forward_window).max().shift(-forward_window)
        dataframe['future_min'] = dataframe['low'].rolling(forward_window).min().shift(-forward_window)

        # 交易成本
        fee = 0.001  # 0.1% 交易费
        slippage = 0.001  # 0.1% 滑点
        total_cost = 2 * (fee + slippage)  # 双向成本 0.4%

        # 潜在收益（做多和做空）
        dataframe['potential_long_return'] = (dataframe['future_max'] / dataframe['close'] - 1) - total_cost
        dataframe['potential_short_return'] = (1 - dataframe['future_min'] / dataframe['close']) - total_cost

        # 回归目标：预测未来最大可获得收益率（取做多和做空中的较大值）
        dataframe['&-s_target_roi'] = np.maximum(
            dataframe['potential_long_return'],
            dataframe['potential_short_return']
        )

        # 调试：打印收益率分布
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"收益率统计 - 均值: {dataframe['&-s_target_roi'].mean():.4f}, "
                   f"中位数: {dataframe['&-s_target_roi'].median():.4f}, "
                   f">0.2%: {(dataframe['&-s_target_roi'] > 0.002).sum()} ({(dataframe['&-s_target_roi'] > 0.002).sum()/len(dataframe)*100:.1f}%), "
                   f">0.5%: {(dataframe['&-s_target_roi'] > 0.005).sum()} ({(dataframe['&-s_target_roi'] > 0.005).sum()/len(dataframe)*100:.1f}%)")

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        填充指标 - 启动 FreqAI 并创建基础特征供出场信号使用
        """
        # 启动 FreqAI（这会调用所有 feature_engineering_* 和 set_freqai_targets）
        dataframe = self.freqai.start(dataframe, metadata, self)

        # 创建基础特征（用于出场信号）
        dataframe['price_change'] = dataframe['close'].pct_change()

        # Money Flow 方法计算买卖压力
        dataframe['mf_multiplier'] = ((dataframe['close'] - dataframe['low']) - (dataframe['high'] - dataframe['close'])) / (dataframe['high'] - dataframe['low'])
        dataframe['mf_multiplier'] = dataframe['mf_multiplier'].fillna(0)
        dataframe['mf_volume'] = dataframe['mf_multiplier'] * dataframe['volume']
        dataframe['buy_pressure'] = np.where(dataframe['mf_volume'] > 0, dataframe['mf_volume'], 0)
        dataframe['sell_pressure'] = np.where(dataframe['mf_volume'] < 0, abs(dataframe['mf_volume']), 0)

        # VPIN
        dataframe['volume_imbalance'] = abs(dataframe['buy_pressure'] - dataframe['sell_pressure'])
        dataframe['vpin'] = (
            dataframe['volume_imbalance'].rolling(20).sum() /
            (dataframe['volume'].rolling(20).sum() + 1e-10)
        )

        # 市场状态（Phase 1 优化：±2% → ±5%，20 → 15）
        dataframe['trend'] = (dataframe['close'] - dataframe['close'].shift(15)) / dataframe['close'].shift(15)
        dataframe['realized_vol'] = dataframe['price_change'].rolling(20).std()

        dataframe['regime_state'] = 1  # 默认震荡
        dataframe.loc[
            (dataframe['trend'] > 0.05) & (dataframe['realized_vol'] > dataframe['realized_vol'].rolling(100).quantile(0.5)),
            'regime_state'
        ] = 2  # 牛市
        dataframe.loc[
            (dataframe['trend'] < -0.05) & (dataframe['realized_vol'] > dataframe['realized_vol'].rolling(100).quantile(0.5)),
            'regime_state'
        ] = 0  # 熊市

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        入场信号 - 基于 FreqAI 回归预测 + 收益率阈值过滤

        高频优化（1 分钟数据）：
        - 模型预测未来收益率（&-s_target_roi）
        - 入场条件：预测收益率 > 0.5%（行业标准）+ VPIN < 0.7（风险控制）
        - 使用短期动量判断方向（做多/做空）
        """
        # 检查 FreqAI 列是否存在
        if 'do_predict' not in dataframe.columns:
            dataframe['enter_long'] = 0
            dataframe['enter_short'] = 0
            return dataframe

        # 计算方向指标（使用短期动量）
        dataframe['momentum_signal'] = dataframe['close'].pct_change(5)  # 5 分钟动量

        # 收益率阈值（行业标准 0.5%）
        roi_threshold = 0.005

        # 做多条件：预测收益率 > 0.5% + 正动量
        dataframe.loc[
            (dataframe['do_predict'] == 1) &
            (dataframe['&-s_target_roi'] > roi_threshold) &  # 预测收益率 > 0.5%
            (dataframe['vpin'] < 0.7) &  # 风险控制
            (dataframe['volume'] > 0) &  # 有成交量
            (dataframe['momentum_signal'] > 0),  # 正动量 -> 做多
            'enter_long'
        ] = 1

        # 做空条件：预测收益率 > 0.5% + 负动量
        dataframe.loc[
            (dataframe['do_predict'] == 1) &
            (dataframe['&-s_target_roi'] > roi_threshold) &  # 预测收益率 > 0.5%
            (dataframe['vpin'] < 0.7) &  # 风险控制
            (dataframe['volume'] > 0) &  # 有成交量
            (dataframe['momentum_signal'] < 0),  # 负动量 -> 做空
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号 - 禁用（完全依赖 ROI + 追踪止损）
        """
        # 不使用出场信号，完全依赖 ROI 和追踪止损
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: 'datetime',
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        动态 ATR 止损（行业标准：1.5 × 20周期 ATR）
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        # 计算 ATR 止损距离
        if 'atr_14' in last_candle:
            atr = last_candle['atr_14']
            close = last_candle['close']
            atr_stop_distance = (atr * 1.5) / close  # 1.5 × ATR，归一化

            # 限制止损范围：最小 0.2%，最大 0.5%
            atr_stop_distance = max(0.002, min(0.005, atr_stop_distance))

            return -atr_stop_distance

        # 回退到固定止损
        return -0.003
