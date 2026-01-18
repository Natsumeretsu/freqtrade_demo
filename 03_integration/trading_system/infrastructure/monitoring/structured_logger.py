"""结构化日志模块

提供JSON格式的结构化日志记录。

创建日期: 2026-01-17
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional


class StructuredLogger:
    """结构化日志记录器"""

    def __init__(self, name: str, level: int = logging.INFO):
        """初始化日志记录器
        
        Args:
            name: 日志记录器名称
            level: 日志级别
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

    def _format_message(self, level: str, message: str, **kwargs) -> str:
        """格式化日志消息为JSON"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'logger': self.logger.name
        }
        log_entry.update(kwargs)
        return json.dumps(log_entry, ensure_ascii=False)

    def info(self, message: str, **kwargs) -> None:
        """记录INFO级别日志"""
        self.logger.info(self._format_message('INFO', message, **kwargs))

    def warning(self, message: str, **kwargs) -> None:
        """记录WARNING级别日志"""
        self.logger.warning(self._format_message('WARNING', message, **kwargs))

    def error(self, message: str, **kwargs) -> None:
        """记录ERROR级别日志"""
        self.logger.error(self._format_message('ERROR', message, **kwargs))

    def debug(self, message: str, **kwargs) -> None:
        """记录DEBUG级别日志"""
        self.logger.debug(self._format_message('DEBUG', message, **kwargs))
