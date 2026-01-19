#!/usr/bin/env python3
"""验证标签设计的正确性"""

import pyarrow.feather as feather
import pandas as pd
import numpy as np

# 读取ETH 5分钟数据
df = feather.read_feather("ft_userdir/data/okx/futures/ETH_USDT_USDT-5m-futures.feather")

# 筛选回测期间的数据
df = df[(df['date'] >= '2024-04-01') & (df['date'] <= '2024-06-30')].copy()

print("=" * 80)
print("标签设计验证")
print("=" * 80)

# 按照策略代码计算标签
forward_window = 6  # 30分钟
fee = 0.001
slippage = 0.001
total_cost = 2 * (fee + slippage)  # 0.4%
threshold = 0.005  # 0.5%

# 计算未来收益
df['future_max'] = df['high'].rolling(forward_window).max().shift(-forward_window)
df['future_min'] = df['low'].rolling(forward_window).min().shift(-forward_window)

df['potential_long_return'] = (df['future_max'] / df['close'] - 1) - total_cost
df['potential_short_return'] = (1 - df['future_min'] / df['close']) - total_cost

# 生成标签
df['label'] = 'no_trade'
df.loc[
    (df['potential_long_return'] > threshold) |
    (df['potential_short_return'] > threshold),
    'label'
] = 'trade'

# 统计
label_counts = df['label'].value_counts()
print(f"\n标签分布:")
print(f"no_trade: {label_counts.get('no_trade', 0)} ({label_counts.get('no_trade', 0)/len(df)*100:.2f}%)")
print(f"trade: {label_counts.get('trade', 0)} ({label_counts.get('trade', 0)/len(df)*100:.2f}%)")
