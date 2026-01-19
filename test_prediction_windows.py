#!/usr/bin/env python3
"""测试不同预测窗口下的特征-标签相关性"""

import pyarrow.feather as feather
import pandas as pd
import numpy as np

# 读取ETH 5分钟数据
df = feather.read_feather("ft_userdir/data/okx/futures/ETH_USDT_USDT-5m-futures.feather")
df = df[(df['date'] >= '2024-04-01') & (df['date'] <= '2024-06-30')].copy()

print("=" * 80)
print("测试不同预测窗口下的特征-标签相关性")
print("=" * 80)

# ===== 使用 Money Flow 方法计算买卖压力 =====
df['mf_multiplier'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
df['mf_multiplier'] = df['mf_multiplier'].fillna(0)
df['mf_volume'] = df['mf_multiplier'] * df['volume']
df['buy_pressure'] = np.where(df['mf_volume'] > 0, df['mf_volume'], 0)
df['sell_pressure'] = np.where(df['mf_volume'] < 0, abs(df['mf_volume']), 0)

# ===== 计算 OFI =====
window = 10
buy_vol = df['buy_pressure'].rolling(window).sum()
sell_vol = df['sell_pressure'].rolling(window).sum()
total_vol = buy_vol + sell_vol
df['ofi_10'] = np.where(total_vol > 0, (buy_vol - sell_vol) / total_vol, 0)

# ===== 计算 VPIN =====
num_buckets = 20
df['volume_imbalance'] = abs(df['buy_pressure'] - df['sell_pressure'])
df['vpin'] = (
    df['volume_imbalance'].rolling(num_buckets).sum() /
    (df['volume'].rolling(num_buckets).sum() + 1e-10)
)

# ===== 测试不同的 forward_window 和 threshold =====
test_configs = [
    # (forward_window, threshold, 描述)
    (1, 0.001, "5分钟, 0.1%"),
    (2, 0.002, "10分钟, 0.2%"),
    (3, 0.003, "15分钟, 0.3%"),
    (4, 0.004, "20分钟, 0.4%"),
    (6, 0.005, "30分钟, 0.5%"),
    (12, 0.005, "60分钟, 0.5%"),
]

fee = 0.001
slippage = 0.001
total_cost = 2 * (fee + slippage)

results = []

for forward_window, threshold, desc in test_configs:
    df_test = df.copy()

    # 生成标签
    df_test['future_max'] = df_test['high'].rolling(forward_window).max().shift(-forward_window)
    df_test['future_min'] = df_test['low'].rolling(forward_window).min().shift(-forward_window)
    df_test['potential_long_return'] = (df_test['future_max'] / df_test['close'] - 1) - total_cost
    df_test['potential_short_return'] = (1 - df_test['future_min'] / df_test['close']) - total_cost

    df_test['label'] = 0  # no_trade
    df_test.loc[
        (df_test['potential_long_return'] > threshold) | (df_test['potential_short_return'] > threshold),
        'label'
    ] = 1  # trade

    # 移除 NaN
    df_test = df_test.dropna()

    # 计算标签分布
    total = len(df_test)
    trade_count = (df_test['label'] == 1).sum()
    no_trade_count = (df_test['label'] == 0).sum()
    trade_pct = trade_count / total * 100

    # 计算特征在两个类别中的差异
    trade_data = df_test[df_test['label'] == 1]
    no_trade_data = df_test[df_test['label'] == 0]

    ofi_diff = abs(trade_data['ofi_10'].mean() - no_trade_data['ofi_10'].mean())
    ofi_std = df_test['ofi_10'].std()
    ofi_discrimination = ofi_diff / ofi_std if ofi_std > 0 else 0

    vpin_diff = abs(trade_data['vpin'].mean() - no_trade_data['vpin'].mean())
    vpin_std = df_test['vpin'].std()
    vpin_discrimination = vpin_diff / vpin_std if vpin_std > 0 else 0

    results.append({
        'forward_window': forward_window,
        'threshold': threshold,
        'desc': desc,
        'total': total,
        'trade_count': trade_count,
        'trade_pct': trade_pct,
        'ofi_diff': ofi_diff,
        'ofi_discrimination': ofi_discrimination,
        'vpin_diff': vpin_diff,
        'vpin_discrimination': vpin_discrimination,
    })

# ===== 输出结果 =====
print(f"\n{'配置':<15} {'trade%':<8} {'OFI差异':<10} {'OFI区分度':<12} {'VPIN差异':<10} {'VPIN区分度':<12}")
print("-" * 80)

for r in results:
    print(f"{r['desc']:<15} {r['trade_pct']:>6.2f}% {r['ofi_diff']:>9.6f} {r['ofi_discrimination']:>11.4f} {r['vpin_diff']:>9.6f} {r['vpin_discrimination']:>11.4f}")

print("\n" + "=" * 80)
print("分析建议")
print("=" * 80)

# 找到最佳配置（trade% 在 10-20% 之间，且特征区分度最高）
best_config = None
best_score = 0

for r in results:
    if 10 <= r['trade_pct'] <= 20:
        # 综合评分：特征区分度的平均值
        score = (r['ofi_discrimination'] + r['vpin_discrimination']) / 2
        if score > best_score:
            best_score = score
            best_config = r

if best_config:
    print(f"\n推荐配置: {best_config['desc']}")
    print(f"  - trade 比例: {best_config['trade_pct']:.2f}%")
    print(f"  - OFI 区分度: {best_config['ofi_discrimination']:.4f}")
    print(f"  - VPIN 区分度: {best_config['vpin_discrimination']:.4f}")
    print(f"  - 综合评分: {best_score:.4f}")
else:
    print("\n未找到满足条件的配置（trade% 在 10-20% 之间）")

print("\n说明:")
print("  - OFI/VPIN 差异: trade 和 no_trade 类别中特征均值的绝对差异")
print("  - OFI/VPIN 区分度: 差异 / 标准差（越大越好，>0.2 表示有区分度）")
print("  - 理想的 trade% 应该在 10-20% 之间（不要太少也不要太多）")

print("\n" + "=" * 80)
print("完成")
print("=" * 80)
