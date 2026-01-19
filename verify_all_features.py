#!/usr/bin/env python3
"""全面验证策略中所有特征的计算逻辑"""

import pyarrow.feather as feather
import pandas as pd
import numpy as np

# 读取ETH 5分钟数据
df = feather.read_feather("ft_userdir/data/okx/futures/ETH_USDT_USDT-5m-futures.feather")
df = df[(df['date'] >= '2024-04-01') & (df['date'] <= '2024-06-30')].copy()

print("=" * 80)
print("第1部分：买卖压力计算验证")
print("=" * 80)

# 当前策略的买卖压力计算
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

print(f"买压非零: {(df['buy_pressure'] > 0).sum()} ({(df['buy_pressure'] > 0).sum() / len(df) * 100:.2f}%)")
print(f"卖压非零: {(df['sell_pressure'] > 0).sum()} ({(df['sell_pressure'] > 0).sum() / len(df) * 100:.2f}%)")
print(f"两者都为0: {((df['buy_pressure'] == 0) & (df['sell_pressure'] == 0)).sum()} ({((df['buy_pressure'] == 0) & (df['sell_pressure'] == 0)).sum() / len(df) * 100:.2f}%)")

# 检查价格和成交量变化的分布
print(f"\n价格上涨: {(df['price_change'] > 0).sum()} ({(df['price_change'] > 0).sum() / len(df) * 100:.2f}%)")
print(f"价格下跌: {(df['price_change'] < 0).sum()} ({(df['price_change'] < 0).sum() / len(df) * 100:.2f}%)")
print(f"价格不变: {(df['price_change'] == 0).sum()} ({(df['price_change'] == 0).sum() / len(df) * 100:.2f}%)")

print(f"\n成交量增加: {(df['volume_change'] > 0).sum()} ({(df['volume_change'] > 0).sum() / len(df) * 100:.2f}%)")
print(f"成交量减少: {(df['volume_change'] < 0).sum()} ({(df['volume_change'] < 0).sum() / len(df) * 100:.2f}%)")
print(f"成交量不变: {(df['volume_change'] == 0).sum()} ({(df['volume_change'] == 0).sum() / len(df) * 100:.2f}%)")

print(f"\n价格上涨且成交量增加: {((df['price_change'] > 0) & (df['volume_change'] > 0)).sum()} ({((df['price_change'] > 0) & (df['volume_change'] > 0)).sum() / len(df) * 100:.2f}%)")
print(f"价格下跌且成交量增加: {((df['price_change'] < 0) & (df['volume_change'] > 0)).sum()} ({((df['price_change'] < 0) & (df['volume_change'] > 0)).sum() / len(df) * 100:.2f}%)")

print("\n" + "=" * 80)
print("第2部分：OFI计算验证")
print("=" * 80)

for window in [5, 10, 20]:
    buy_vol = df['buy_pressure'].rolling(window).sum()
    sell_vol = df['sell_pressure'].rolling(window).sum()
    total_vol = buy_vol + sell_vol
    df[f'ofi_{window}'] = np.where(
        total_vol > 0,
        (buy_vol - sell_vol) / total_vol,
        0
    )

    ofi = df[f'ofi_{window}'].dropna()
    print(f"\nOFI_{window}:")
    print(f"  均值: {ofi.mean():.6f}, 标准差: {ofi.std():.6f}")
    print(f"  > 0.08: {(ofi > 0.08).sum()} ({(ofi > 0.08).sum() / len(ofi) * 100:.2f}%)")
    print(f"  < -0.08: {(ofi < -0.08).sum()} ({(ofi < -0.08).sum() / len(ofi) * 100:.2f}%)")
    print(f"  [-0.08, 0.08]: {((ofi >= -0.08) & (ofi <= 0.08)).sum()} ({((ofi >= -0.08) & (ofi <= 0.08)).sum() / len(ofi) * 100:.2f}%)")

print("\n保存中间结果到文件...")

print("\n" + "=" * 80)
print("第3部分：VPIN计算验证")
print("=" * 80)

num_buckets = 20
df['volume_imbalance'] = abs(df['buy_pressure'] - df['sell_pressure'])
df['vpin'] = (
    df['volume_imbalance'].rolling(num_buckets).sum() /
    (df['volume'].rolling(num_buckets).sum() + 1e-10)
)

vpin = df['vpin'].dropna()
print(f"VPIN统计:")
print(f"  均值: {vpin.mean():.6f}, 标准差: {vpin.std():.6f}")
print(f"  最小值: {vpin.min():.6f}, 最大值: {vpin.max():.6f}")
print(f"  < 0.7: {(vpin < 0.7).sum()} ({(vpin < 0.7).sum() / len(vpin) * 100:.2f}%)")
print(f"  >= 0.7: {(vpin >= 0.7).sum()} ({(vpin >= 0.7).sum() / len(vpin) * 100:.2f}%)")

# 检查VPIN的问题
print(f"\n问题检查:")
print(f"  volume_imbalance全为0: {(df['volume_imbalance'] == 0).sum()} ({(df['volume_imbalance'] == 0).sum() / len(df) * 100:.2f}%)")
print(f"  VPIN为0: {(df['vpin'] == 0).sum()} ({(df['vpin'] == 0).sum() / len(df) * 100:.2f}%)")

print("\n" + "=" * 80)
print("第4部分：Microprice计算验证")
print("=" * 80)

# Microprice 近似计算
df['bid_approx'] = df['low']
df['ask_approx'] = df['high']
df['bid_volume_approx'] = df['buy_pressure']
df['ask_volume_approx'] = df['sell_pressure']

total_vol = df['bid_volume_approx'] + df['ask_volume_approx']
df['microprice'] = np.where(
    total_vol > 0,
    (df['ask_volume_approx'] * df['bid_approx'] + df['bid_volume_approx'] * df['ask_approx']) / total_vol,
    (df['bid_approx'] + df['ask_approx']) / 2
)
df['microprice_vs_close'] = (df['microprice'] - df['close']) / df['close']

microprice_vs_close = df['microprice_vs_close'].dropna()
print(f"Microprice偏离统计:")
print(f"  均值: {microprice_vs_close.mean():.6f}, 标准差: {microprice_vs_close.std():.6f}")
print(f"  最小值: {microprice_vs_close.min():.6f}, 最大值: {microprice_vs_close.max():.6f}")
print(f"  中位数: {microprice_vs_close.median():.6f}")

# 检查 microprice 使用默认值的比例
using_default = (total_vol == 0).sum()
print(f"\n使用默认值(bid+ask)/2的比例: {using_default} ({using_default / len(df) * 100:.2f}%)")
print(f"这与买卖压力都为0的比例一致: {((df['buy_pressure'] == 0) & (df['sell_pressure'] == 0)).sum() / len(df) * 100:.2f}%")

print("\n" + "=" * 80)
print("第5部分：流动性指标验证")
print("=" * 80)

# Amihud Illiquidity
df['amihud'] = abs(df['price_change']) / (df['volume'] + 1e-10)
df['amihud_ma'] = df['amihud'].rolling(20).mean()

amihud = df['amihud'].dropna()
amihud_ma = df['amihud_ma'].dropna()
print(f"Amihud Illiquidity统计:")
print(f"  均值: {amihud.mean():.10f}, 标准差: {amihud.std():.10f}")
print(f"  最小值: {amihud.min():.10f}, 最大值: {amihud.max():.10f}")
print(f"  中位数: {amihud.median():.10f}")
print(f"\nAmihud MA(20)统计:")
print(f"  均值: {amihud_ma.mean():.10f}, 标准差: {amihud_ma.std():.10f}")

# Kyle's Lambda
df['kyle_lambda'] = abs(df['price_change']) / (df['volume'] + 1e-10)
df['kyle_lambda_ma'] = df['kyle_lambda'].rolling(20).mean()

kyle = df['kyle_lambda'].dropna()
kyle_ma = df['kyle_lambda_ma'].dropna()
print(f"\nKyle's Lambda统计:")
print(f"  均值: {kyle.mean():.10f}, 标准差: {kyle.std():.10f}")
print(f"  最小值: {kyle.min():.10f}, 最大值: {kyle.max():.10f}")
print(f"  中位数: {kyle.median():.10f}")
print(f"\nKyle's Lambda MA(20)统计:")
print(f"  均值: {kyle_ma.mean():.10f}, 标准差: {kyle_ma.std():.10f}")

# 检查问题：Amihud 和 Kyle's Lambda 在策略中是相同的计算
print(f"\n问题检查:")
print(f"  Amihud 和 Kyle's Lambda 是否完全相同: {(df['amihud'] == df['kyle_lambda']).all()}")

print("\n" + "=" * 80)
print("第6部分：波动率特征验证")
print("=" * 80)

# 已实现波动率
df['realized_vol'] = df['price_change'].rolling(20).std()

realized_vol = df['realized_vol'].dropna()
print(f"已实现波动率统计:")
print(f"  均值: {realized_vol.mean():.6f}, 标准差: {realized_vol.std():.6f}")
print(f"  最小值: {realized_vol.min():.6f}, 最大值: {realized_vol.max():.6f}")
print(f"  中位数: {realized_vol.median():.6f}")

# 价格区间
df['price_range'] = (df['high'] - df['low']) / df['close']
df['price_range_ma'] = df['price_range'].rolling(20).mean()

price_range = df['price_range'].dropna()
price_range_ma = df['price_range_ma'].dropna()
print(f"\n价格区间统计:")
print(f"  均值: {price_range.mean():.6f}, 标准差: {price_range.std():.6f}")
print(f"  最小值: {price_range.min():.6f}, 最大值: {price_range.max():.6f}")
print(f"  中位数: {price_range.median():.6f}")
print(f"\n价格区间 MA(20)统计:")
print(f"  均值: {price_range_ma.mean():.6f}, 标准差: {price_range_ma.std():.6f}")

# 成交量波动率
df['volume_vol'] = df['volume'].rolling(20).std() / (df['volume'].rolling(20).mean() + 1e-10)

volume_vol = df['volume_vol'].dropna()
print(f"\n成交量波动率统计:")
print(f"  均值: {volume_vol.mean():.6f}, 标准差: {volume_vol.std():.6f}")
print(f"  最小值: {volume_vol.min():.6f}, 最大值: {volume_vol.max():.6f}")
print(f"  中位数: {volume_vol.median():.6f}")

print("\n" + "=" * 80)
print("第7部分：市场状态分类验证")
print("=" * 80)

# 趋势强度
df['trend'] = (df['close'] - df['close'].shift(15)) / df['close'].shift(15)

# 状态分类
df['regime_state'] = 1  # 默认震荡
df.loc[
    (df['trend'] > 0.05) & (df['realized_vol'] > df['realized_vol'].rolling(100).quantile(0.5)),
    'regime_state'
] = 2  # 牛市
df.loc[
    (df['trend'] < -0.05) & (df['realized_vol'] > df['realized_vol'].rolling(100).quantile(0.5)),
    'regime_state'
] = 0  # 熊市

regime_counts = df['regime_state'].value_counts().sort_index()
print(f"市场状态分布:")
print(f"  熊市(0): {regime_counts.get(0, 0)} ({regime_counts.get(0, 0) / len(df) * 100:.2f}%)")
print(f"  震荡(1): {regime_counts.get(1, 0)} ({regime_counts.get(1, 0) / len(df) * 100:.2f}%)")
print(f"  牛市(2): {regime_counts.get(2, 0)} ({regime_counts.get(2, 0) / len(df) * 100:.2f}%)")

trend = df['trend'].dropna()
print(f"\n趋势强度统计:")
print(f"  均值: {trend.mean():.6f}, 标准差: {trend.std():.6f}")
print(f"  最小值: {trend.min():.6f}, 最大值: {trend.max():.6f}")
print(f"  中位数: {trend.median():.6f}")
print(f"\n趋势阈值分析:")
print(f"  > 0.05: {(trend > 0.05).sum()} ({(trend > 0.05).sum() / len(trend) * 100:.2f}%)")
print(f"  < -0.05: {(trend < -0.05).sum()} ({(trend < -0.05).sum() / len(trend) * 100:.2f}%)")
print(f"  [-0.05, 0.05]: {((trend >= -0.05) & (trend <= 0.05)).sum()} ({((trend >= -0.05) & (trend <= 0.05)).sum() / len(trend) * 100:.2f}%)")

print("\n" + "=" * 80)
print("第8部分：动量特征和成交量强度验证")
print("=" * 80)

# 成交量相对强度
df['volume_ratio'] = df['volume'] / (df['volume'].rolling(20).mean() + 1e-10)

volume_ratio = df['volume_ratio'].dropna()
print(f"成交量相对强度统计:")
print(f"  均值: {volume_ratio.mean():.6f}, 标准差: {volume_ratio.std():.6f}")
print(f"  最小值: {volume_ratio.min():.6f}, 最大值: {volume_ratio.max():.6f}")
print(f"  中位数: {volume_ratio.median():.6f}")

# 价格动量
df['momentum_5'] = (df['close'] - df['close'].shift(5)) / df['close'].shift(5)
df['momentum_10'] = (df['close'] - df['close'].shift(10)) / df['close'].shift(10)

momentum_5 = df['momentum_5'].dropna()
momentum_10 = df['momentum_10'].dropna()
print(f"\n动量5统计:")
print(f"  均值: {momentum_5.mean():.6f}, 标准差: {momentum_5.std():.6f}")
print(f"  最小值: {momentum_5.min():.6f}, 最大值: {momentum_5.max():.6f}")
print(f"  中位数: {momentum_5.median():.6f}")

print(f"\n动量10统计:")
print(f"  均值: {momentum_10.mean():.6f}, 标准差: {momentum_10.std():.6f}")
print(f"  最小值: {momentum_10.min():.6f}, 最大值: {momentum_10.max():.6f}")
print(f"  中位数: {momentum_10.median():.6f}")

print("\n" + "=" * 80)
print("完成所有特征验证")
print("=" * 80)
