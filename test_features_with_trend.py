#!/usr/bin/env python3
"""测试添加趋势和动量特征后的特征-标签相关性"""

import pyarrow.feather as feather
import pandas as pd
import numpy as np

# 读取ETH 5分钟数据
df = feather.read_feather("ft_userdir/data/okx/futures/ETH_USDT_USDT-5m-futures.feather")
df = df[(df['date'] >= '2024-04-01') & (df['date'] <= '2024-06-30')].copy()

print("=" * 80)
print("测试添加趋势和动量特征后的特征-标签相关性")
print("=" * 80)

# ===== 使用 Money Flow 方法计算买卖压力 =====
df['mf_multiplier'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
df['mf_multiplier'] = df['mf_multiplier'].fillna(0)
df['mf_volume'] = df['mf_multiplier'] * df['volume']
df['buy_pressure'] = np.where(df['mf_volume'] > 0, df['mf_volume'], 0)
df['sell_pressure'] = np.where(df['mf_volume'] < 0, abs(df['mf_volume']), 0)

# ===== 计算微观结构特征 =====
window = 10
buy_vol = df['buy_pressure'].rolling(window).sum()
sell_vol = df['sell_pressure'].rolling(window).sum()
total_vol = buy_vol + sell_vol
df['ofi_10'] = np.where(total_vol > 0, (buy_vol - sell_vol) / total_vol, 0)

num_buckets = 20
df['volume_imbalance'] = abs(df['buy_pressure'] - df['sell_pressure'])
df['vpin'] = (
    df['volume_imbalance'].rolling(num_buckets).sum() /
    (df['volume'].rolling(num_buckets).sum() + 1e-10)
)

# ===== 添加趋势特征 =====
# 价格动量（不同时间窗口）
for window in [6, 12, 24]:  # 30分钟, 60分钟, 120分钟
    df[f'momentum_{window}'] = df['close'].pct_change(window)

# 移动平均线
df['sma_12'] = df['close'].rolling(12).mean()
df['sma_24'] = df['close'].rolling(24).mean()
df['ma_cross'] = (df['sma_12'] - df['sma_24']) / df['sma_24']

# ===== 添加波动率特征 =====
# 已实现波动率
for window in [12, 24, 48]:  # 60分钟, 120分钟, 240分钟
    df[f'realized_vol_{window}'] = df['close'].pct_change().rolling(window).std()

# ATR (Average True Range)
df['tr'] = np.maximum(
    df['high'] - df['low'],
    np.maximum(
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    )
)
df['atr_14'] = df['tr'].rolling(14).mean()
df['atr_normalized'] = df['atr_14'] / df['close']

# ===== 添加成交量特征 =====
# 成交量相对强度
df['volume_sma_12'] = df['volume'].rolling(12).mean()
df['volume_ratio'] = df['volume'] / (df['volume_sma_12'] + 1e-10)

# 成交量加权平均价（VWAP）偏离
df['vwap_12'] = (df['close'] * df['volume']).rolling(12).sum() / (df['volume'].rolling(12).sum() + 1e-10)
df['vwap_deviation'] = (df['close'] - df['vwap_12']) / df['vwap_12']

# ===== 生成标签（使用最佳配置：30分钟, 0.5%）=====
forward_window = 6
threshold = 0.005
fee = 0.001
slippage = 0.001
total_cost = 2 * (fee + slippage)

df['future_max'] = df['high'].rolling(forward_window).max().shift(-forward_window)
df['future_min'] = df['low'].rolling(forward_window).min().shift(-forward_window)
df['potential_long_return'] = (df['future_max'] / df['close'] - 1) - total_cost
df['potential_short_return'] = (1 - df['future_min'] / df['close']) - total_cost

df['label'] = 0  # no_trade
df.loc[
    (df['potential_long_return'] > threshold) | (df['potential_short_return'] > threshold),
    'label'
] = 1  # trade

# 移除 NaN
df = df.dropna()

print(f"\n有效数据行数: {len(df)}")
print(f"标签分布:")
print(f"  no_trade (0): {(df['label'] == 0).sum()} ({(df['label'] == 0).sum() / len(df) * 100:.2f}%)")
print(f"  trade (1): {(df['label'] == 1).sum()} ({(df['label'] == 1).sum() / len(df) * 100:.2f}%)")

# ===== 分析所有特征在两个类别中的区分度 =====
print("\n" + "=" * 80)
print("特征区分度分析（区分度 = 差异 / 标准差）")
print("=" * 80)

features = [
    # 微观结构特征
    ('ofi_10', '微观结构'),
    ('vpin', '微观结构'),
    # 趋势特征
    ('momentum_6', '趋势'),
    ('momentum_12', '趋势'),
    ('momentum_24', '趋势'),
    ('ma_cross', '趋势'),
    # 波动率特征
    ('realized_vol_12', '波动率'),
    ('realized_vol_24', '波动率'),
    ('atr_normalized', '波动率'),
    # 成交量特征
    ('volume_ratio', '成交量'),
    ('vwap_deviation', '成交量'),
]

trade_data = df[df['label'] == 1]
no_trade_data = df[df['label'] == 0]

results = []

for feat, category in features:
    trade_mean = trade_data[feat].mean()
    no_trade_mean = no_trade_data[feat].mean()
    diff = abs(trade_mean - no_trade_mean)
    std = df[feat].std()
    discrimination = diff / std if std > 0 else 0

    results.append({
        'feature': feat,
        'category': category,
        'trade_mean': trade_mean,
        'no_trade_mean': no_trade_mean,
        'diff': diff,
        'std': std,
        'discrimination': discrimination,
    })

# 按区分度排序
results.sort(key=lambda x: x['discrimination'], reverse=True)

print(f"\n{'特征':<20} {'类别':<10} {'区分度':<10} {'差异':<12} {'标准差':<12}")
print("-" * 80)

for r in results:
    print(f"{r['feature']:<20} {r['category']:<10} {r['discrimination']:>9.4f} {r['diff']:>11.6f} {r['std']:>11.6f}")

# ===== 按类别汇总 =====
print("\n" + "=" * 80)
print("按类别汇总")
print("=" * 80)

categories = {}
for r in results:
    cat = r['category']
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(r['discrimination'])

print(f"\n{'类别':<15} {'平均区分度':<15} {'最大区分度':<15} {'特征数':<10}")
print("-" * 80)

for cat in ['微观结构', '趋势', '波动率', '成交量']:
    if cat in categories:
        scores = categories[cat]
        avg_score = np.mean(scores)
        max_score = np.max(scores)
        count = len(scores)
        print(f"{cat:<15} {avg_score:>14.4f} {max_score:>14.4f} {count:>9}")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)

# 找出区分度 >0.2 的特征
good_features = [r for r in results if r['discrimination'] > 0.2]

if good_features:
    print(f"\n区分度 >0.2 的特征（有效特征）：")
    for r in good_features:
        print(f"  - {r['feature']}: {r['discrimination']:.4f}")
else:
    print("\n没有特征的区分度 >0.2")

print("\n建议:")
print("  1. 如果趋势/波动率特征的区分度显著高于微观结构特征，")
print("     说明添加这些特征可以改善模型预测能力")
print("  2. 如果所有特征的区分度都很低（<0.2），")
print("     说明需要进一步调整特征工程或预测窗口")

print("\n" + "=" * 80)
print("完成")
print("=" * 80)
