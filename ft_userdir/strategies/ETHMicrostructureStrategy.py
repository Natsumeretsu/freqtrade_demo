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
    timeframe = '5m'
    can_short = True

    # ROI 和 Stoploss（Phase 6 平衡优化）
    minimal_roi = {
        "0": 0.012,   # 1.2% 立即止盈
        "15": 0.008,  # 15分钟后降到 0.8%
        "30": 0.005,  # 30分钟后降到 0.5%
        "45": 0.003   # 45分钟后降到 0.3%（保本）
    }
    stoploss = -0.008  # -0.8% 止损（平衡风险控制）

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

        # ===== 1. Order Flow Imbalance 近似 =====
        # 使用成交量和价格变化近似订单流
        dataframe['%-price_change'] = dataframe['close'].pct_change()
        dataframe['%-volume_change'] = dataframe['volume'].pct_change()

        # 买卖压力近似：价格上涨 + 成交量增加 = 买压
        dataframe['buy_pressure'] = np.where(
            (dataframe['%-price_change'] > 0) & (dataframe['%-volume_change'] > 0),
            dataframe['volume'],
            0
        )
        dataframe['sell_pressure'] = np.where(
            (dataframe['%-price_change'] < 0) & (dataframe['%-volume_change'] > 0),
            dataframe['volume'],
            0
        )

        # Order Flow Imbalance (多周期) - 添加 % 前缀
        for window in [5, 10, 20]:
            buy_vol = dataframe['buy_pressure'].rolling(window).sum()
            sell_vol = dataframe['sell_pressure'].rolling(window).sum()
            total_vol = buy_vol + sell_vol
            dataframe[f'%-ofi_{window}'] = np.where(
                total_vol > 0,
                (buy_vol - sell_vol) / total_vol,
                0
            )

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

        # ===== 3. Microprice 近似 =====
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
        设置预测目标 - 二分类（交易/不交易）

        高频策略优化（Phase 5）：
        - 预测窗口：60分钟 → 20分钟（适配5分钟高频交易）
        - 收益阈值：0.8% → 0.4%（快进快出，小收益高频率）
        - 交易成本：更保守估计（0.1%滑点 → 0.1%滑点，保持不变）
        """
        # 设置分类标签名称（FreqAI 分类器必须使用字符串标签）
        self.freqai.class_names = ["no_trade", "trade"]

        # 计算未来收益（Phase 6：平衡优化）
        forward_window = 6  # 未来 6 根 K 线（30 分钟）- 平衡短期和稳定性

        # 修复：直接使用 rolling，不要 shift(-1)
        dataframe['future_max'] = dataframe['high'].rolling(forward_window).max().shift(-forward_window)
        dataframe['future_min'] = dataframe['low'].rolling(forward_window).min().shift(-forward_window)

        # 交易成本（高频策略：更保守的滑点估计）
        fee = 0.001  # 0.1% 交易费
        slippage = 0.001  # 0.1% 滑点（从 0.05% 提高）
        total_cost = 2 * (fee + slippage)  # 双向成本 0.4%

        # 潜在收益
        dataframe['potential_long_return'] = (dataframe['future_max'] / dataframe['close'] - 1) - total_cost
        dataframe['potential_short_return'] = (1 - dataframe['future_min'] / dataframe['close']) - total_cost

        # 目标收益阈值（Phase 6：平衡优化）
        threshold = 0.005  # 0.5% - 平衡机会和质量

        # 二分类标签（使用字符串标签）
        # 'no_trade': 不交易
        # 'trade': 交易（做多或做空）
        dataframe['&-action'] = 'no_trade'

        # 交易条件：任一方向的潜在收益 > threshold
        dataframe.loc[
            (dataframe['potential_long_return'] > threshold) |
            (dataframe['potential_short_return'] > threshold),
            '&-action'
        ] = 'trade'

        # 调试：打印标签分布
        import logging
        logger = logging.getLogger(__name__)
        label_counts = dataframe['&-action'].value_counts()
        total = len(dataframe)
        logger.info(f"标签分布 - no_trade(不交易): {label_counts.get('no_trade', 0)} ({label_counts.get('no_trade', 0)/total*100:.1f}%), "
                   f"trade(交易): {label_counts.get('trade', 0)} ({label_counts.get('trade', 0)/total*100:.1f}%)")

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        填充指标 - 启动 FreqAI 并创建基础特征供出场信号使用
        """
        # 启动 FreqAI（这会调用所有 feature_engineering_* 和 set_freqai_targets）
        dataframe = self.freqai.start(dataframe, metadata, self)

        # 创建基础特征（用于出场信号）
        dataframe['price_change'] = dataframe['close'].pct_change()
        dataframe['volume_change'] = dataframe['volume'].pct_change()

        # 买卖压力近似
        dataframe['buy_pressure'] = np.where(
            (dataframe['price_change'] > 0) & (dataframe['volume_change'] > 0),
            dataframe['volume'],
            0
        )
        dataframe['sell_pressure'] = np.where(
            (dataframe['price_change'] < 0) & (dataframe['volume_change'] > 0),
            dataframe['volume'],
            0
        )

        # Order Flow Imbalance
        for window in [5, 10, 20]:
            buy_vol = dataframe['buy_pressure'].rolling(window).sum()
            sell_vol = dataframe['sell_pressure'].rolling(window).sum()
            total_vol = buy_vol + sell_vol
            dataframe[f'ofi_{window}'] = np.where(
                total_vol > 0,
                (buy_vol - sell_vol) / total_vol,
                0
            )

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
        入场信号 - 基于 FreqAI 预测 + 微观结构确认

        Phase 6 平衡优化：
        - 提高 OFI 阈值：0.05/-0.05 → 0.08/-0.08（提高入场质量）
        - 恢复单根K线持续性确认（减少假信号）
        - 保持 VPIN 风险阈值：0.7
        - 目标：120-180 笔交易，平衡频率和质量
        """
        # 检查 FreqAI 列是否存在
        if 'do_predict' not in dataframe.columns:
            dataframe['enter_long'] = 0
            dataframe['enter_short'] = 0
            return dataframe

        # 计算持续性确认（单根K线）
        dataframe['ofi_10_prev'] = dataframe['ofi_10'].shift(1)

        # 做多条件（平衡版 - 恢复持续性确认）
        dataframe.loc[
            (dataframe['do_predict'] == 1) &
            (dataframe['&-action'] == 'trade') &  # 模型预测交易
            (dataframe['ofi_10'] > 0.08) &  # 提高阈值：0.05 → 0.08
            (dataframe['ofi_10_prev'] > 0.08) &  # 持续性确认（单根K线）
            (dataframe['vpin'] < 0.7) &  # 风险控制
            (dataframe['volume'] > 0),  # 有成交量
            'enter_long'
        ] = 1

        # 做空条件（平衡版 - 恢复持续性确认）
        dataframe.loc[
            (dataframe['do_predict'] == 1) &
            (dataframe['&-action'] == 'trade') &  # 模型预测交易
            (dataframe['ofi_10'] < -0.08) &  # 提高阈值：-0.05 → -0.08
            (dataframe['ofi_10_prev'] < -0.08) &  # 持续性确认（单根K线）
            (dataframe['vpin'] < 0.7) &  # 风险控制
            (dataframe['volume'] > 0),  # 有成交量
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号 - 基于微观结构反转

        Phase 6 平衡优化：
        - 放宽 OFI 阈值：±0.15 → ±0.2（减少过早出场）
        - 保持单根K线触发
        - 保留 VPIN 风险控制
        - 目标：配合 ROI 梯度和适中止损，实现平衡收益
        """
        # 平多条件（放宽阈值 - 减少过早出场）
        dataframe.loc[
            (
                # 订单流反转（-0.15 → -0.2，单根K线）
                (dataframe['ofi_10'] < -0.2) |
                # 风险过高
                (dataframe['vpin'] > 0.8)
            ),
            'exit_long'
        ] = 1

        # 平空条件（放宽阈值 - 减少过早出场）
        dataframe.loc[
            (
                # 订单流反转（0.15 → 0.2，单根K线）
                (dataframe['ofi_10'] > 0.2) |
                # 风险过高
                (dataframe['vpin'] > 0.8)
            ),
            'exit_short'
        ] = 1

        return dataframe
