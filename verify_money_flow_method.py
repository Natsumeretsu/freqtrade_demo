#!/usr/bin/env python3
"""验证基于 Money Flow 的买卖压力计算方法"""

import pyarrow.feather as feather
import pandas as pd
import numpy as np

# 读取ETH 5分钟数据
df = feather.read_feather("ft_userdir/data/okx/futures/ETH_USDT_USDT-5m-futures.feather")
df = df[(df['date'] >= '2024-04-01') & (df['date'] <= '2024-06-30')].copy()

print("=" * 80)
print("对比：旧方法 vs Money Flow 方法")
print("=" * 80)

# ===== 旧方法 =====
df['price_change'] = df['close'].pct_change()
df['volume_change'] = df['volume'].pct_change()

df['buy_pressure_old'] = np.where(
    (df['price_change'] > 0) & (df['volume_change'] > 0),
    df['volume'],
    0
)
df['sell_pressure_old'] = np.where(
    (df['price_change'] < 0) & (df['volume_change'] > 0),
    df['volume'],
    0
)

print("\n旧方法统计:")
print(f"  买压非零: {(df['buy_pressure_old'] > 0).sum()} ({(df['buy_pressure_old'] > 0).sum() / len(df) * 100:.2f}%)")
print(f"  卖压非零: {(df['sell_pressure_old'] > 0).sum()} ({(df['sell_pressure_old'] > 0).sum() / len(df) * 100:.2f}%)")
print(f"  两者都为0: {((df['buy_pressure_old'] == 0) & (df['sell_pressure_old'] == 0)).sum()} ({((df['buy_pressure_old'] == 0) & (df['sell_pressure_old'] == 0)).sum() / len(df) * 100:.2f}%)")

# ===== Money Flow 方法 =====
# Money Flow Multiplier = [(Close - Low) - (High - Close)] / (High - Low)
df['mf_multiplier'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])

# 处理 high == low 的情况（无波动）
df['mf_multiplier'] = df['mf_multiplier'].fillna(0)

# Money Flow Volume = MF_Multiplier * Volume
df['mf_volume'] = df['mf_multiplier'] * df['volume']

# 分离买卖压力
df['buy_pressure_new'] = np.where(df['mf_volume'] > 0, df['mf_volume'], 0)
df['sell_pressure_new'] = np.where(df['mf_volume'] < 0, abs(df['mf_volume']), 0)

print("\nMoney Flow 方法统计:")
print(f"  买压非零: {(df['buy_pressure_new'] > 0).sum()} ({(df['buy_pressure_new'] > 0).sum() / len(df) * 100:.2f}%)")
print(f"  卖压非零: {(df['sell_pressure_new'] > 0).sum()} ({(df['sell_pressure_new'] > 0).sum() / len(df) * 100:.2f}%)")
print(f"  两者都为0: {((df['buy_pressure_new'] == 0) & (df['sell_pressure_new'] == 0)).sum()} ({((df['buy_pressure_new'] == 0) & (df['sell_pressure_new'] == 0)).sum() / len(df) * 100:.2f}%)")

print(f"\nMoney Flow Multiplier 统计:")
mf_mult = df['mf_multiplier'].dropna()
print(f"  均值: {mf_mult.mean():.6f}, 标准差: {mf_mult.std():.6f}")
print(f"  最小值: {mf_mult.min():.6f}, 最大值: {mf_mult.max():.6f}")
print(f"  中位数: {mf_mult.median():.6f}")
print(f"  = 1.0: {(mf_mult == 1.0).sum()} ({(mf_mult == 1.0).sum() / len(mf_mult) * 100:.2f}%)")
print(f"  = -1.0: {(mf_mult == -1.0).sum()} ({(mf_mult == -1.0).sum() / len(mf_mult) * 100:.2f}%)")
print(f"  = 0.0: {(mf_mult == 0.0).sum()} ({(mf_mult == 0.0).sum() / len(mf_mult) * 100:.2f}%)")

# ===== 计算新方法的 OFI =====
print("\n" + "=" * 80)
print("新方法的 OFI 计算")
print("=" * 80)

for window in [5, 10, 20]:
    buy_vol = df['buy_pressure_new'].rolling(window).sum()
    sell_vol = df['sell_pressure_new'].rolling(window).sum()
    total_vol = buy_vol + sell_vol
    df[f'ofi_new_{window}'] = np.where(
        total_vol > 0,
        (buy_vol - sell_vol) / total_vol,
        0
    )

    ofi = df[f'ofi_new_{window}'].dropna()
    print(f"\nOFI_{window} (新方法):")
    print(f"  均值: {ofi.mean():.6f}, 标准差: {ofi.std():.6f}")
    print(f"  最小值: {ofi.min():.6f}, 最大值: {ofi.max():.6f}")
    print(f"  中位数: {ofi.median():.6f}")
    print(f"  > 0.08: {(ofi > 0.08).sum()} ({(ofi > 0.08).sum() / len(ofi) * 100:.2f}%)")
    print(f"  < -0.08: {(ofi < -0.08).sum()} ({(ofi < -0.08).sum() / len(ofi) * 100:.2f}%)")
    print(f"  [-0.08, 0.08]: {((ofi >= -0.08) & (ofi <= 0.08)).sum()} ({((ofi >= -0.08) & (ofi <= 0.08)).sum() / len(ofi) * 100:.2f}%)")

# ===== 计算新方法的 VPIN =====
print("\n" + "=" * 80)
print("新方法的 VPIN 计算")
print("=" * 80)

num_buckets = 20
df['volume_imbalance_new'] = abs(df['buy_pressure_new'] - df['sell_pressure_new'])
df['vpin_new'] = (
    df['volume_imbalance_new'].rolling(num_buckets).sum() /
    (df['volume'].rolling(num_buckets).sum() + 1e-10)
)

vpin = df['vpin_new'].dropna()
print(f"VPIN统计 (新方法):")
print(f"  均值: {vpin.mean():.6f}, 标准差: {vpin.std():.6f}")
print(f"  最小值: {vpin.min():.6f}, 最大值: {vpin.max():.6f}")
print(f"  中位数: {vpin.median():.6f}")
print(f"  < 0.7: {(vpin < 0.7).sum()} ({(vpin < 0.7).sum() / len(vpin) * 100:.2f}%)")
print(f"  >= 0.7: {(vpin >= 0.7).sum()} ({(vpin >= 0.7).sum() / len(vpin) * 100:.2f}%)")

print(f"\n问题检查:")
print(f"  volume_imbalance为0: {(df['volume_imbalance_new'] == 0).sum()} ({(df['volume_imbalance_new'] == 0).sum() / len(df) * 100:.2f}%)")

print("\n" + "=" * 80)
print("完成")
print("=" * 80)
