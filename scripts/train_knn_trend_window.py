from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from freqtrade.data.history import load_pair_history
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# 允许直接用 `python scripts/train_knn_trend_window.py` 运行时也能导入项目根目录下的模块
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from knn_window_features import (
    build_knn_trend_features,
    build_knn_window_features,
    build_trend_indicators,
    get_knn_trend_feature_columns,
    get_knn_window_feature_columns,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="训练：趋势过滤 + 多K线窗口特征 的 KNN 分类模型"
    )
    parser.add_argument("--datadir", default="data/okx", help="Freqtrade 数据目录")
    parser.add_argument("--pair", default="BTC/USDT", help="交易对，例如 BTC/USDT")
    parser.add_argument("--timeframe", default="1h", help="K线周期，例如 1h")
    parser.add_argument(
        "--train-timerange",
        default=None,
        help=(
            "训练集时间范围：YYYYMMDD-YYYYMMDD（end 可省略，end 不包含）。"
            "与 --test-timerange 同时指定时，将按日期做严格样本外切分。"
        ),
    )
    parser.add_argument(
        "--test-timerange",
        default=None,
        help="测试集时间范围：YYYYMMDD-YYYYMMDD（end 可省略，end 不包含）。",
    )

    parser.add_argument("--window", type=int, default=8, help="特征窗口：最近 N 根K线")
    parser.add_argument(
        "--include-trend-features",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="将趋势上下文特征（与 EMA/ADX 相关）加入 KNN 输入向量",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=6,
        help="标签窗口：预测未来 N 根K线后的收益",
    )
    parser.add_argument(
        "--min-return",
        type=float,
        default=0.006,
        help="未来收益阈值：大于该值标记为 1，否则为 -1",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="按时间顺序切分训练集比例（避免时间序列泄露）",
    )

    parser.add_argument("--neighbors", type=int, default=25, help="KNN 的邻居数 k")
    parser.add_argument(
        "--balance",
        choices=["none", "downsample", "upsample"],
        default="downsample",
        help="训练集类别平衡方式（仅作用训练集，避免模型长期预测多数类）",
    )
    parser.add_argument("--random-state", type=int, default=42, help="采样随机种子（用于类别平衡）")

    parser.add_argument("--ema-fast", type=int, default=20, help="趋势过滤 EMA 快线周期")
    parser.add_argument("--ema-slow", type=int, default=50, help="趋势过滤 EMA 慢线周期")
    parser.add_argument("--ema-long", type=int, default=200, help="趋势过滤 EMA 长周期")
    parser.add_argument("--adx-period", type=int, default=14, help="ADX 周期")
    parser.add_argument("--adx-min", type=float, default=10.0, help="趋势过滤 ADX 阈值")
    parser.add_argument(
        "--filter-trend",
        action="store_true",
        help="只用“上升趋势”样本训练（更贴近策略的‘先判趋势再识别’）",
    )

    parser.add_argument(
        "--model-out",
        default="models/knn_trend_window_btc_usdt_1h.pkl",
        help="输出模型路径（joblib .pkl）",
    )
    return parser.parse_args()


def _parse_timerange(timerange: str | None) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    timerange = (timerange or "").strip()
    if timerange in ("", "-"):
        return None, None

    if "-" not in timerange:
        raise ValueError(
            "timerange 格式错误，应为 YYYYMMDD-YYYYMMDD（end 可省略），例如 20180101-20250101"
        )

    start_str, end_str = timerange.split("-", 1)
    start = pd.to_datetime(start_str, format="%Y%m%d", utc=True) if start_str else None
    end = pd.to_datetime(end_str, format="%Y%m%d", utc=True) if end_str else None
    if start is not None and end is not None and start >= end:
        raise ValueError(f"timerange 起止错误：{timerange}")

    return start, end


def _build_timerange_mask(dates: pd.Series, timerange: str) -> pd.Series:
    start, end = _parse_timerange(timerange)
    mask = pd.Series(True, index=dates.index)
    if start is not None:
        mask &= dates >= start
    if end is not None:
        mask &= dates < end
    return mask


def _majority_baseline_accuracy(y: pd.Series) -> float:
    if y.empty:
        return float("nan")
    majority_label = y.value_counts().idxmax()
    return float((y == majority_label).mean())


def _balance_training_set(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    mode: str,
    random_state: int,
) -> tuple[pd.DataFrame, pd.Series]:
    if mode == "none":
        return x_train, y_train

    pos_idx = y_train.index[y_train == 1]
    neg_idx = y_train.index[y_train == -1]
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        raise ValueError(
            "训练集某一类样本为 0，无法做类别平衡；请调整 min-return/horizon/timerange，或关闭 --filter-trend"
        )

    rng = np.random.default_rng(int(random_state))
    if mode == "downsample":
        n = int(min(len(pos_idx), len(neg_idx)))
        pos_sample = rng.choice(pos_idx.to_numpy(), size=n, replace=False)
        neg_sample = rng.choice(neg_idx.to_numpy(), size=n, replace=False)
    elif mode == "upsample":
        n = int(max(len(pos_idx), len(neg_idx)))
        pos_sample = rng.choice(pos_idx.to_numpy(), size=n, replace=True)
        neg_sample = rng.choice(neg_idx.to_numpy(), size=n, replace=True)
    else:
        raise ValueError(f"不支持的 balance 模式：{mode}")

    selected = np.concatenate([pos_sample, neg_sample])
    rng.shuffle(selected)
    selected_idx = pd.Index(selected)

    return x_train.loc[selected_idx], y_train.loc[selected_idx]


def _build_trend_up_mask(
    dataframe: pd.DataFrame,
    trend: pd.DataFrame,
    adx_min: float,
) -> pd.Series:
    return (
        (trend["ema_fast"] > trend["ema_slow"])
        & (trend["ema_slow"] > trend["ema_long"])
        & (dataframe["close"] > trend["ema_long"])
        & (trend["adx"] > adx_min)
    )


def main() -> int:
    args = _parse_args()

    use_timerange_split = bool(args.train_timerange) or bool(args.test_timerange)
    if args.window <= 0 or args.horizon <= 0:
        raise ValueError("window/horizon 必须为正整数")
    if use_timerange_split:
        if not args.train_timerange or not args.test_timerange:
            raise ValueError("使用严格样本外切分时，请同时指定 --train-timerange 与 --test-timerange")
        train_start, train_end = _parse_timerange(args.train_timerange)
        test_start, test_end = _parse_timerange(args.test_timerange)
        if train_end is None or test_start is None:
            raise ValueError(
                "严格样本外切分要求：训练集必须有 end，测试集必须有 start（例如 20180101-20250101 / 20250101-20270101）"
            )
        if test_start < train_end:
            raise ValueError(
                f"训练/测试区间重叠（{args.train_timerange=} {args.test_timerange=}），无法保证严格样本外"
            )
    else:
        if not (0.1 <= args.train_ratio < 1.0):
            raise ValueError("train-ratio 建议在 [0.1, 1.0) 区间内")
    if args.neighbors <= 0:
        raise ValueError("neighbors 必须为正整数")

    df = load_pair_history(
        datadir=Path(args.datadir),
        timeframe=args.timeframe,
        pair=args.pair,
    )
    if df.empty:
        raise ValueError(f"数据为空：{args.datadir=} {args.timeframe=} {args.pair=}")

    # 确保按时间升序
    if "date" in df.columns:
        df = df.sort_values("date")

    window_feature_cols = get_knn_window_feature_columns(args.window)
    window_features = build_knn_window_features(df, window=args.window)

    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], utc=True)
    else:
        dates = pd.Series(pd.to_datetime(df.index, utc=True), index=df.index)
    future_date = dates.shift(-args.horizon)

    # 标签：未来 N 根K线后的收益是否超过阈值（更贴近“做交易”而不是“猜下一根涨跌”）
    future_return = df["close"].shift(-args.horizon) / df["close"] - 1.0
    target = pd.Series(
        np.where(future_return > float(args.min_return), 1, -1),
        index=df.index,
        name="target",
    )

    trend = build_trend_indicators(
        df,
        ema_fast=args.ema_fast,
        ema_slow=args.ema_slow,
        ema_long=args.ema_long,
        adx_period=args.adx_period,
    )
    if args.include_trend_features:
        trend_features = build_knn_trend_features(df, trend)
        feature_cols = window_feature_cols + get_knn_trend_feature_columns()
        features = pd.concat([window_features, trend, trend_features], axis=1).replace([np.inf, -np.inf], np.nan)
    else:
        feature_cols = window_feature_cols
        features = window_features.replace([np.inf, -np.inf], np.nan)

    base_mask = features[feature_cols].notna().all(axis=1) & future_return.notna() & future_date.notna()
    trend_up = _build_trend_up_mask(df, trend, adx_min=float(args.adx_min))

    if args.filter_trend:
        base_mask &= trend_up

    if use_timerange_split:
        train_start, train_end = _parse_timerange(args.train_timerange)
        test_start, test_end = _parse_timerange(args.test_timerange)

        train_mask = base_mask & _build_timerange_mask(dates, args.train_timerange)
        test_mask = base_mask & _build_timerange_mask(dates, args.test_timerange)

        # 严格样本外：训练集样本的标签未来点也必须落在训练区间内
        if train_end is not None:
            train_mask &= future_date < train_end
        if test_end is not None:
            test_mask &= future_date < test_end

        x_train = (
            features.loc[train_mask, feature_cols]
            .astype("float64")
            .replace([np.inf, -np.inf], 0.0)
        )
        y_train = target.loc[train_mask].astype("int64")
        x_test = (
            features.loc[test_mask, feature_cols]
            .astype("float64")
            .replace([np.inf, -np.inf], 0.0)
        )
        y_test = target.loc[test_mask].astype("int64")
    else:
        x_all = (
            features.loc[base_mask, feature_cols]
            .astype("float64")
            .replace([np.inf, -np.inf], 0.0)
        )
        y_all = target.loc[base_mask].astype("int64")
        dates_all = dates.loc[base_mask]
        future_date_all = future_date.loc[base_mask]

        if x_all.empty:
            raise ValueError("可用样本为空：请检查数据、window/horizon/min-return 或趋势过滤参数")

        split_idx = int(len(x_all) * float(args.train_ratio))
        if split_idx <= 0 or split_idx >= len(x_all):
            raise ValueError("train-ratio 切分后训练/测试集为空，请调整 train-ratio")

        split_date = pd.Timestamp(dates_all.iloc[split_idx])
        train_mask = (dates_all < split_date) & (future_date_all < split_date)
        test_mask = dates_all >= split_date

        x_train, y_train = x_all.loc[train_mask], y_all.loc[train_mask]
        x_test, y_test = x_all.loc[test_mask], y_all.loc[test_mask]

    x_train, y_train = _balance_training_set(
        x_train=x_train,
        y_train=y_train,
        mode=str(args.balance),
        random_state=int(args.random_state),
    )

    if len(x_train) < max(200, args.neighbors * 5):
        raise ValueError(
            f"训练样本过少（{len(x_train)}），请增大数据量/调小 window 或 neighbors，或关闭 --filter-trend"
        )
    if len(x_test) < 200:
        raise ValueError(f"测试样本过少（{len(x_test)}），请调整时间区间或数据量")

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("knn", KNeighborsClassifier(n_neighbors=args.neighbors, weights="distance")),
        ]
    )
    model.fit(x_train, y_train)
    model.feature_window = int(args.window)
    model.horizon = int(args.horizon)
    model.min_return = float(args.min_return)
    model.train_timerange = str(args.train_timerange or "")
    model.test_timerange = str(args.test_timerange or "")
    model.balance = str(args.balance)

    train_acc = float(model.score(x_train, y_train))
    test_acc = float(model.score(x_test, y_test))
    baseline_acc = _majority_baseline_accuracy(y_test)

    print(f"训练样本: {len(x_train)}，测试样本: {len(x_test)}")
    if use_timerange_split:
        print(f"训练区间: {args.train_timerange}（严格样本外）")
        print(f"测试区间: {args.test_timerange}（严格样本外）")
    print(f"特征维度: {x_train.shape[1]}（window={args.window}）")
    print(f"标签定义: future_return(t+{args.horizon}) > {args.min_return} => 1 else -1")
    if args.filter_trend:
        print("已启用趋势过滤：仅使用上升趋势样本")
    print(f"训练集类别平衡: {args.balance}")
    print("训练集标签分布:")
    print(y_train.value_counts(normalize=True).sort_index().to_string())
    print(f"训练集准确率: {train_acc:.4f}")
    print(f"测试集准确率: {test_acc:.4f}")
    print(f"测试集基线准确率(多数类): {baseline_acc:.4f}")
    print("测试集标签分布:")
    print(y_test.value_counts(normalize=True).sort_index().to_string())

    y_pred = pd.Series(model.predict(x_test), index=y_test.index, name="pred")
    print("测试集预测分布:")
    print(y_pred.value_counts(normalize=True).sort_index().to_string())

    if hasattr(model, "predict_proba"):
        probas = model.predict_proba(x_test)
        classes = getattr(model, "classes_", None)
        if classes is not None and 1 in list(classes):
            idx = list(classes).index(1)
        else:
            idx = -1
        proba_1 = pd.Series(probas[:, idx], index=x_test.index, name="proba_1")

        print("测试集 proba(=1) 分位数:")
        for q in (0.5, 0.8, 0.9, 0.95, 0.99):
            print(f"  p{int(q * 100)}: {float(proba_1.quantile(q)):.4f}")

        future_return_test = future_return.loc[y_test.index].astype("float64")
        thresholds = [round(x, 2) for x in np.arange(0.20, 0.81, 0.05)]
        print("阈值扫描（用于选 buy_proba_min）:")
        for thr in thresholds:
            sel = proba_1 >= float(thr)
            n_sel = int(sel.sum())
            if n_sel == 0:
                precision = float("nan")
                avg_ret = float("nan")
            else:
                precision = float((y_test.loc[sel] == 1).mean())
                avg_ret = float(future_return_test.loc[sel].mean())
            sel_rate = float(n_sel / len(y_test))
            print(f"  thr>={thr:.2f}: 触发率={sel_rate:.3f}  样本={n_sel}  精确率={precision:.3f}  平均未来收益={avg_ret:.4f}")

    out_path = Path(args.model_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_path)
    print(f"模型已保存: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
