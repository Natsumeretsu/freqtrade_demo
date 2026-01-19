#!/usr/bin/env python3
"""验证OFI和VPIN计算逻辑的正确性"""

import pandas as pd
import numpy as np
import pyarrow.feather as feather

# 读取最近一次回测的预测数据
prediction_file = "ft_userdir/models/eth_lgb_clf_v1/backtesting_predictions/cb_eth_1719446400_prediction.feather"
df = feather.read_feather(prediction_file)

print("=" * 80)
print("数据基本信息")
print("=" * 80)
print(f"数据行数: {len(df)}")
print(f"列数: {len(df.columns)}")
print(f"\n所有列名:")
for i, col in enumerate(df.columns, 1):
    print(f"  {i:3d}. {col}")

# 查找OFI相关列
ofi_cols = [col for col in df.columns if 'ofi' in col.lower()]
vpin_cols = [col for col in df.columns if 'vpin' in col.lower()]
pressure_cols = [col for col in df.columns if 'pressure' in col.lower()]

print(f"\n" + "=" * 80)
print(f"OFI相关列: {ofi_cols}")
print(f"VPIN相关列: {vpin_cols}")
print(f"压力相关列: {pressure_cols}")

# 分析OFI分布
if ofi_cols:
    for col in ofi_cols:
        print(f"\n" + "=" * 80)
        print(f"{col} 分布统计")
        print("=" * 80)
        data = df[col].dropna()
        if len(data) > 0:
            print(f"数据点数: {len(data)}")
            print(f"均值: {data.mean():.6f}")
            print(f"标准差: {data.std():.6f}")
            print(f"最小值: {data.min():.6f}")
            print(f"最大值: {data.max():.6f}")
            print(f"中位数: {data.median():.6f}")
            print(f"\n分位数:")
            for q in [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]:
                print(f"  {q*100:5.1f}%: {data.quantile(q):8.6f}")

            # 检查阈值
            if '10' in col:
                print(f"\n> 0.08 的比例: {(data > 0.08).sum() / len(data) * 100:.2f}%")
                print(f"< -0.08 的比例: {(data < -0.08).sum() / len(data) * 100:.2f}%")
                print(f"在 [-0.08, 0.08] 范围内: {((data >= -0.08) & (data <= 0.08)).sum() / len(data) * 100:.2f}%")

# 分析VPIN分布
if vpin_cols:
    for col in vpin_cols:
        print(f"\n" + "=" * 80)
        print(f"{col} 分布统计")
        print("=" * 80)
        data = df[col].dropna()
        if len(data) > 0:
            print(f"数据点数: {len(data)}")
            print(f"均值: {data.mean():.6f}")
            print(f"标准差: {data.std():.6f}")
            print(f"最小值: {data.min():.6f}")
            print(f"最大值: {data.max():.6f}")
            print(f"< 0.7 的比例: {(data < 0.7).sum() / len(data) * 100:.2f}%")
            print(f">= 0.7 的比例: {(data >= 0.7).sum() / len(data) * 100:.2f}%")

# 检查模型预测
if '&-action' in df.columns:
    print(f"\n" + "=" * 80)
    print("模型预测分布")
    print("=" * 80)
    print(df['&-action'].value_counts())
    print(f"\ntrade 比例: {(df['&-action'] == 'trade').sum() / len(df) * 100:.2f}%")

# 检查do_predict
if 'do_predict' in df.columns:
    print(f"\ndo_predict=1 的比例: {(df['do_predict'] == 1).sum() / len(df) * 100:.2f}%")

print("\n" + "=" * 80)
print("完成")
print("=" * 80)
