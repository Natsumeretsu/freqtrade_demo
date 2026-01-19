#!/usr/bin/env python3
"""直接从原始数据计算OFI和VPIN，验证逻辑正确性"""

import pyarrow.feather as feather
import pandas as pd
import numpy as np

# 读取ETH 5分钟数据
df = feather.read_feather("ft_userdir/data/okx/futures/ETH_USDT_USDT-5m-futures.feather")

print("=" * 80)
print("原始数据信息")
print("=" * 80)
print(f"数据行数: {len(df)}")
print(f"时间范围: {df['date'].min()} 到 {df['date'].max()}")
print(f"列名: {list(df.columns)}")

# 筛选回测期间的数据（2024-04-01 到 2024-06-30）
df = df[(df['date'] >= '2024-04-01') & (df['date'] <= '2024-06-30')].copy()
print(f"\n回测期间数据行数: {len(df)}")

# 按照策略代码计算买卖压力
df['price_change'] = df['close'].pct_change()
df['volume_change'] = df['volume'].pct_change()

df['buy_pressure'] = np.where(
    (df['price_change'] > 0) & (df['volume_change'] > 0),
    df['volume'],
    0
)
df['sell_pressure'] = np.where(
    (df['price_change'] < 0) & (df['volume_change'] > 0),
    df['volume'],
    0
)

print("\n" + "=" * 80)
print("买卖压力统计")
print("=" * 80)
print(f"买压非零比例: {(df['buy_pressure'] > 0).sum() / len(df) * 100:.2f}%")
print(f"卖压非零比例: {(df['sell_pressure'] > 0).sum() / len(df) * 100:.2f}%")
print(f"两者都为0: {((df['buy_pressure'] == 0) & (df['sell_pressure'] == 0)).sum() / len(df) * 100:.2f}%")
print(f"两者都非0: {((df['buy_pressure'] > 0) & (df['sell_pressure'] > 0)).sum() / len(df) * 100:.2f}%")

# 计算OFI
window = 10
buy_vol = df['buy_pressure'].rolling(window).sum()
sell_vol = df['sell_pressure'].rolling(window).sum()
total_vol = buy_vol + sell_vol
df['ofi_10'] = np.where(
    total_vol > 0,
    (buy_vol - sell_vol) / total_vol,
    0
)

print("\n" + "=" * 80)
print("OFI_10 统计")
print("=" * 80)
ofi = df['ofi_10'].dropna()
print(f"数据点数: {len(ofi)}")
print(f"均值: {ofi.mean():.6f}")
print(f"标准差: {ofi.std():.6f}")
print(f"最小值: {ofi.min():.6f}")
print(f"最大值: {ofi.max():.6f}")
print(f"中位数: {ofi.median():.6f}")

print(f"\n分位数:")
for q in [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]:
    print(f"  {q*100:5.1f}%: {ofi.quantile(q):8.6f}")

print(f"\n阈值分析:")
print(f"OFI > 0.08: {(ofi > 0.08).sum()} ({(ofi > 0.08).sum() / len(ofi) * 100:.2f}%)")
print(f"OFI < -0.08: {(ofi < -0.08).sum()} ({(ofi < -0.08).sum() / len(ofi) * 100:.2f}%)")
print(f"OFI 在 [-0.08, 0.08]: {((ofi >= -0.08) & (ofi <= 0.08)).sum()} ({((ofi >= -0.08) & (ofi <= 0.08)).sum() / len(ofi) * 100:.2f}%)")

# 计算VPIN
num_buckets = 20
df['volume_imbalance'] = abs(df['buy_pressure'] - df['sell_pressure'])
df['vpin'] = (
    df['volume_imbalance'].rolling(num_buckets).sum() /
    (df['volume'].rolling(num_buckets).sum() + 1e-10)
)

print("\n" + "=" * 80)
print("VPIN 统计")
print("=" * 80)
vpin = df['vpin'].dropna()
print(f"数据点数: {len(vpin)}")
print(f"均值: {vpin.mean():.6f}")
print(f"标准差: {vpin.std():.6f}")
print(f"最小值: {vpin.min():.6f}")
print(f"最大值: {vpin.max():.6f}")
print(f"中位数: {vpin.median():.6f}")

print(f"\n阈值分析:")
print(f"VPIN < 0.7: {(vpin < 0.7).sum()} ({(vpin < 0.7).sum() / len(vpin) * 100:.2f}%)")
print(f"VPIN >= 0.7: {(vpin >= 0.7).sum()} ({(vpin >= 0.7).sum() / len(vpin) * 100:.2f}%)")

# 模拟入场条件
df['ofi_10_prev'] = df['ofi_10'].shift(1)
long_condition = (
    (df['ofi_10'] > 0.08) &
    (df['ofi_10_prev'] > 0.08) &
    (df['vpin'] < 0.7)
)
short_condition = (
    (df['ofi_10'] < -0.08) &
    (df['ofi_10_prev'] < -0.08) &
    (df['vpin'] < 0.7)
)

print("\n" + "=" * 80)
print("入场条件统计（不考虑模型预测）")
print("=" * 80)
print(f"做多条件满足: {long_condition.sum()} ({long_condition.sum() / len(df) * 100:.2f}%)")
print(f"做空条件满足: {short_condition.sum()} ({short_condition.sum() / len(df) * 100:.2f}%)")
print(f"任一条件满足: {(long_condition | short_condition).sum()} ({(long_condition | short_condition).sum() / len(df) * 100:.2f}%)")

print("\n" + "=" * 80)
print("完成")
print("=" * 80)
