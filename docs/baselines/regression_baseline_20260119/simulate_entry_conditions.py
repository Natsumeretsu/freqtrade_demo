#!/usr/bin/env python3
"""模拟入场条件评估"""

import pyarrow.feather as feather
import pandas as pd
import numpy as np
from pathlib import Path

print("=" * 80)
print("模拟入场条件评估")
print("=" * 80)

# 1. 读取原始数据
print("\n1. 读取原始数据...")
df = feather.read_feather("ft_userdir/data/okx/futures/ETH_USDT_USDT-1m-futures.feather")
df = df[(df['date'] >= '2024-04-01') & (df['date'] <= '2024-06-30')].copy()
print(f"   原始数据行数: {len(df)}")

# 2. 计算 VPIN
print("\n2. 计算 VPIN...")
df['mf_multiplier'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
df['mf_multiplier'] = df['mf_multiplier'].fillna(0)
df['mf_volume'] = df['mf_multiplier'] * df['volume']
df['buy_pressure'] = np.where(df['mf_volume'] > 0, df['mf_volume'], 0)
df['sell_pressure'] = np.where(df['mf_volume'] < 0, abs(df['mf_volume']), 0)
df['volume_imbalance'] = abs(df['buy_pressure'] - df['sell_pressure'])
df['vpin'] = (
    df['volume_imbalance'].rolling(20).sum() /
    (df['volume'].rolling(20).sum() + 1e-10)
)
print(f"   VPIN 计算完成")

# 3. 读取预测数据
print("\n3. 读取预测数据...")
pred_dir = Path("ft_userdir/models/scheme_d_atr_regressor/backtesting_predictions")
pred_files = sorted(pred_dir.glob("*.feather"))

all_predictions = []
for pred_file in pred_files:
    pred_df = feather.read_feather(pred_file)
    all_predictions.append(pred_df)

df_pred = pd.concat(all_predictions, ignore_index=True)
print(f"   预测数据行数: {len(df_pred)}")
print(f"   预测列: {list(df_pred.columns)}")

# 4. 合并数据
print("\n4. 合并数据...")
df_merged = pd.merge(df, df_pred, on='date', how='inner')
print(f"   合并后行数: {len(df_merged)}")

# 5. 评估入场条件
print("\n" + "=" * 80)
print("入场条件评估")
print("=" * 80)

cond1 = df_merged['do_predict'] == 1
cond2 = df_merged['&-action'] == 'trade'
cond3 = df_merged['vpin'] < 0.7
cond4 = df_merged['volume'] > 0

print(f"\n条件 1 - do_predict == 1:")
print(f"  通过: {cond1.sum()} / {len(df_merged)} ({cond1.sum() / len(df_merged) * 100:.2f}%)")

print(f"\n条件 2 - &-action == 'trade':")
print(f"  通过: {cond2.sum()} / {len(df_merged)} ({cond2.sum() / len(df_merged) * 100:.2f}%)")

print(f"\n条件 3 - vpin < 0.7:")
print(f"  通过: {cond3.sum()} / {len(df_merged)} ({cond3.sum() / len(df_merged) * 100:.2f}%)")
print(f"  VPIN 统计:")
print(f"    平均值: {df_merged['vpin'].mean():.4f}")
print(f"    中位数: {df_merged['vpin'].median():.4f}")
print(f"    NaN 数量: {df_merged['vpin'].isna().sum()}")

print(f"\n条件 4 - volume > 0:")
print(f"  通过: {cond4.sum()} / {len(df_merged)} ({cond4.sum() / len(df_merged) * 100:.2f}%)")

# 逐步组合条件
print("\n" + "=" * 80)
print("逐步组合条件")
print("=" * 80)

step1 = cond1
print(f"\n步骤 1 (do_predict == 1): {step1.sum()} ({step1.sum() / len(df_merged) * 100:.2f}%)")

step2 = step1 & cond2
print(f"步骤 2 (+ &-action == 'trade'): {step2.sum()} ({step2.sum() / len(df_merged) * 100:.2f}%)")

step3 = step2 & cond3
print(f"步骤 3 (+ vpin < 0.7): {step3.sum()} ({step3.sum() / len(df_merged) * 100:.2f}%)")

step4 = step3 & cond4
print(f"步骤 4 (+ volume > 0): {step4.sum()} ({step4.sum() / len(df_merged) * 100:.2f}%)")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)

if step4.sum() > 0:
    print(f"\n✓ 有 {step4.sum()} 个样本满足所有入场条件")
    print("\n满足条件的样本示例:")
    print(df_merged[step4][['date', 'close', 'volume', 'vpin', '&-action', 'do_predict']].head(20))
else:
    print("\n✗ 没有样本满足所有入场条件")
    print("\n最可能的原因:")
    if step2.sum() == 0:
        print("  - 模型没有预测任何 'trade'")
    elif step3.sum() == 0:
        print("  - 所有 'trade' 预测的 VPIN 都 >= 0.7")
    else:
        print("  - 其他原因（需要进一步调查）")

print("\n" + "=" * 80)
print("完成")
print("=" * 80)
