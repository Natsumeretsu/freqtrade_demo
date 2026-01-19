#!/usr/bin/env python3
"""测试 1 分钟数据下的特征区分度"""

import pyarrow.feather as feather
import pandas as pd
import numpy as np

# 读取ETH 1分钟数据
df = feather.read_feather("ft_userdir/data/okx/futures/ETH_USDT_USDT-1m-futures.feather")
df = df[(df['date'] >= '2024-04-01') & (df['date'] <= '2024-06-30')].copy()

print("=" * 80)
print("1 分钟数据特征区分度测试")
print("=" * 80)
print(f"\n数据行数: {len(df)}")

# ===== Money Flow 方法计算买卖压力 =====
df['mf_multiplier'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
df['mf_multiplier'] = df['mf_multiplier'].fillna(0)
df['mf_volume'] = df['mf_multiplier'] * df['volume']
df['buy_pressure'] = np.where(df['mf_volume'] > 0, df['mf_volume'], 0)
df['sell_pressure'] = np.where(df['mf_volume'] < 0, abs(df['mf_volume']), 0)

# ===== 计算 VPIN（保留）=====
num_buckets = 20
df['volume_imbalance'] = abs(df['buy_pressure'] - df['sell_pressure'])
df['vpin'] = (
    df['volume_imbalance'].rolling(num_buckets).sum() /
    (df['volume'].rolling(num_buckets).sum() + 1e-10)
)

# ===== 计算波动率特征 =====
# ATR
df['tr'] = np.maximum(
    df['high'] - df['low'],
    np.maximum(
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    )
)
df['atr_14'] = df['tr'].rolling(14).mean()
df['atr_normalized'] = df['atr_14'] / df['close']

# 已实现波动率
for window in [12, 24, 48]:
    df[f'realized_vol_{window}'] = df['close'].pct_change().rolling(window).std()

# ===== 计算趋势特征 =====
for window in [5, 10, 15]:
    df[f'momentum_{window}'] = df['close'].pct_change(window)

# ===== 计算成交量特征 =====
df['volume_sma_12'] = df['volume'].rolling(12).mean()
df['volume_ratio'] = df['volume'] / (df['volume_sma_12'] + 1e-10)

# ===== 测试不同预测窗口 =====
test_configs = [
    (5, 0.002, "5分钟, 0.2%"),
    (10, 0.003, "10分钟, 0.3%"),
    (15, 0.004, "15分钟, 0.4%"),
]

fee = 0.001
slippage = 0.001
total_cost = 2 * (fee + slippage)

print("\n" + "=" * 80)
print("测试不同预测窗口")
print("=" * 80)

for forward_window, threshold, desc in test_configs:
    df_test = df.copy()

    # 生成标签
    df_test['future_max'] = df_test['high'].rolling(forward_window).max().shift(-forward_window)
    df_test['future_min'] = df_test['low'].rolling(forward_window).min().shift(-forward_window)
    df_test['potential_long_return'] = (df_test['future_max'] / df_test['close'] - 1) - total_cost
    df_test['potential_short_return'] = (1 - df_test['future_min'] / df_test['close']) - total_cost

    df_test['label'] = 0
    df_test.loc[
        (df_test['potential_long_return'] > threshold) | (df_test['potential_short_return'] > threshold),
        'label'
    ] = 1

    df_test = df_test.dropna()

    total = len(df_test)
    trade_count = (df_test['label'] == 1).sum()
    trade_pct = trade_count / total * 100

    # 计算特征区分度
    trade_data = df_test[df_test['label'] == 1]
    no_trade_data = df_test[df_test['label'] == 0]

    features = ['vpin', 'atr_normalized', 'realized_vol_12', 'momentum_10', 'volume_ratio']
    discriminations = []

    for feat in features:
        diff = abs(trade_data[feat].mean() - no_trade_data[feat].mean())
        std = df_test[feat].std()
        disc = diff / std if std > 0 else 0
        discriminations.append(disc)

    avg_disc = np.mean(discriminations)

    print(f"\n{desc}:")
    print(f"  trade%: {trade_pct:.2f}%")
    print(f"  平均区分度: {avg_disc:.4f}")
    print(f"  VPIN: {discriminations[0]:.4f}, ATR: {discriminations[1]:.4f}, Vol: {discriminations[2]:.4f}")

print("\n" + "=" * 80)
print("完成")
print("=" * 80)
