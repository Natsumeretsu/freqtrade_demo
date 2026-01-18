"""性能监控模块

实时监控系统性能指标。

创建日期: 2026-01-17
"""
from __future__ import annotations

import time
import psutil
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from collections import deque


@dataclass
class PerformanceSnapshot:
    """性能快照"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_io_read: float = 0.0
    disk_io_write: float = 0.0


class PerformanceMonitor:
    """性能监控器
    
    实时监控系统性能指标。
    """

    def __init__(self, max_history: int = 1000, interval: float = 1.0):
        """初始化监控器
        
        Args:
            max_history: 最大历史记录数
            interval: 采样间隔（秒）
        """
        self.max_history = max_history
        self.interval = interval
        self._history: deque = deque(maxlen=max_history)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_disk_io = None

    def _collect_metrics(self) -> PerformanceSnapshot:
        """收集性能指标"""
        # CPU和内存
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_mb = memory.used / (1024 * 1024)
        
        # 磁盘I/O
        disk_io = psutil.disk_io_counters()
        disk_io_read = 0.0
        disk_io_write = 0.0
        
        if self._last_disk_io:
            time_delta = self.interval
            read_delta = disk_io.read_bytes - self._last_disk_io.read_bytes
            write_delta = disk_io.write_bytes - self._last_disk_io.write_bytes
            disk_io_read = (read_delta / time_delta) / (1024 * 1024)
            disk_io_write = (write_delta / time_delta) / (1024 * 1024)
        
        self._last_disk_io = disk_io
        
        return PerformanceSnapshot(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_mb=memory_mb,
            disk_io_read=disk_io_read,
            disk_io_write=disk_io_write
        )

    def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            snapshot = self._collect_metrics()
            self._history.append(snapshot)
            time.sleep(self.interval)

    def start(self) -> None:
        """启动监控"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def get_current_metrics(self) -> Optional[PerformanceSnapshot]:
        """获取当前性能指标"""
        if not self._history:
            return None
        return self._history[-1]

    def get_average_metrics(self, last_n: int = 60) -> Dict[str, float]:
        """获取平均性能指标"""
        if not self._history:
            return {}
        
        snapshots = list(self._history)[-last_n:]
        
        return {
            'avg_cpu': sum(s.cpu_percent for s in snapshots) / len(snapshots),
            'avg_memory': sum(s.memory_percent for s in snapshots) / len(snapshots),
            'avg_memory_mb': sum(s.memory_mb for s in snapshots) / len(snapshots),
            'avg_disk_read': sum(s.disk_io_read for s in snapshots) / len(snapshots),
            'avg_disk_write': sum(s.disk_io_write for s in snapshots) / len(snapshots)
        }

    def get_report(self) -> str:
        """生成性能报告"""
        if not self._history:
            return "没有性能数据"
        
        current = self.get_current_metrics()
        avg = self.get_average_metrics()
        
        report = ["=" * 60, "性能监控报告", "=" * 60, ""]
        report.append(f"当前指标:")
        report.append(f"  CPU使用率: {current.cpu_percent:.2f}%")
        report.append(f"  内存使用率: {current.memory_percent:.2f}%")
        report.append(f"  内存使用量: {current.memory_mb:.2f} MB")
        report.append("")
        report.append(f"平均指标 (最近60次):")
        report.append(f"  平均CPU: {avg['avg_cpu']:.2f}%")
        report.append(f"  平均内存: {avg['avg_memory']:.2f}%")
        
        return "\n".join(report)
