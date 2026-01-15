"""
monitor_drift_realtime.py - 实时漂移监控脚本

目标：
- 在线监控特征分布漂移
- 触发告警并自动降风险
- 支持定时轮询或事件驱动

用法示例：
  uv run python -X utf8 scripts/qlib/monitor_drift_realtime.py ^
    --baseline artifacts/baselines/baseline_15m.json ^
    --interval 300 ^
    --alert-webhook ""
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))

from trading_system.infrastructure.ml.drift import (
    DriftThresholds,
    evaluate_feature_drift,
)


@dataclass
class MonitorConfig:
    """监控配置"""
    baseline_path: Path
    interval_seconds: int = 300  # 轮询间隔
    window_bars: int = 96        # 监控窗口（K线数）
    alert_on_warn: bool = False  # warn 级别是否告警
    alert_on_crit: bool = True   # crit 级别是否告警


@dataclass
class DriftAlert:
    """漂移告警"""
    timestamp: str
    status: str  # ok / warn / crit
    features_affected: list[str]
    message: str


def load_baseline(path: Path) -> dict[str, Any]:
    """加载基线文件"""
    if not path.is_file():
        raise FileNotFoundError(f"基线文件不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def check_drift(
    X_window: pd.DataFrame,
    baseline: dict[str, Any],
    thresholds: DriftThresholds | None = None,
) -> DriftAlert | None:
    """执行一次漂移检查"""
    report = evaluate_feature_drift(
        X_window, baseline=baseline, thresholds=thresholds
    )
    status = report.get("status", "ok")
    if status == "ok":
        return None

    affected = [
        name for name, feat in report.get("features", {}).items()
        if feat.get("status") in ("warn", "crit")
    ]
    return DriftAlert(
        timestamp=datetime.now(timezone.utc).isoformat(),
        status=status,
        features_affected=affected,
        message=f"检测到 {len(affected)} 个特征漂移",
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="实时漂移监控")
    p.add_argument("--baseline", required=True, help="基线 JSON 文件路径")
    p.add_argument("--interval", type=int, default=300, help="轮询间隔（秒）")
    p.add_argument("--once", action="store_true", help="只运行一次（用于测试）")
    p.add_argument("--window", type=int, default=96, help="监控窗口（K线数）")
    p.add_argument("--data-source", default="", help="数据源路径（CSV 或 Parquet）")
    return p.parse_args()


def _fetch_latest_window(
    data_source: str,
    window_bars: int,
) -> pd.DataFrame:
    """
    获取最新的数据窗口。

    实际生产中应从交易所 API 或数据库获取实时数据。
    这里提供文件读取作为示例。
    """
    if not data_source:
        # 返回空 DataFrame，触发跳过逻辑
        return pd.DataFrame()

    path = Path(data_source)
    if not path.is_file():
        print(f"警告: 数据源不存在: {path}")
        return pd.DataFrame()

    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, parse_dates=["datetime"], index_col="datetime")

    # 取最后 window_bars 行
    return df.tail(window_bars)


def _send_alert(alert: DriftAlert, webhook_url: str = "") -> None:
    """发送告警（可扩展为 webhook/邮件/Telegram）"""
    print(f"\n{'='*50}")
    print(f"[ALERT] {alert.timestamp}")
    print(f"状态: {alert.status.upper()}")
    print(f"消息: {alert.message}")
    if alert.features_affected:
        print(f"受影响特征: {', '.join(alert.features_affected[:10])}")
        if len(alert.features_affected) > 10:
            print(f"  ... 还有 {len(alert.features_affected) - 10} 个")
    print(f"{'='*50}\n")

    # TODO: 实现 webhook 推送
    # if webhook_url:
    #     requests.post(webhook_url, json=asdict(alert))


def main() -> int:
    """主函数"""
    args = _parse_args()

    baseline_path = Path(args.baseline).resolve()
    print(f"实时漂移监控启动")
    print(f"  基线文件: {baseline_path}")
    print(f"  轮询间隔: {args.interval}s")
    print(f"  监控窗口: {args.window} bars")
    print(f"  单次模式: {args.once}")

    # 加载基线
    try:
        baseline = load_baseline(baseline_path)
        print(f"  基线特征数: {len(baseline.get('features', {}))}")
    except FileNotFoundError as e:
        print(f"错误: {e}")
        return 1

    config = MonitorConfig(
        baseline_path=baseline_path,
        interval_seconds=args.interval,
        window_bars=args.window,
    )

    iteration = 0
    while True:
        iteration += 1
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"\n[{now}] 第 {iteration} 次检查...")

        # 获取数据窗口
        X_window = _fetch_latest_window(args.data_source, config.window_bars)

        if X_window.empty:
            print("  跳过: 无数据")
        else:
            # 执行漂移检查
            alert = check_drift(X_window, baseline)

            if alert is None:
                print("  状态: OK - 无漂移")
            else:
                _send_alert(alert)

                # 如果是 crit 级别，可以触发自动降风险
                if alert.status == "crit" and config.alert_on_crit:
                    print("  [ACTION] 建议: 降低仓位或暂停交易")

        # 单次模式退出
        if args.once:
            print("\n单次模式，退出")
            break

        # 等待下一次轮询
        print(f"  等待 {config.interval_seconds}s...")
        time.sleep(config.interval_seconds)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
