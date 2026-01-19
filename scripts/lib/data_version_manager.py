"""数据版本管理模块

提供轻量级的数据版本控制功能，用于管理历史数据、因子数据等。
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


class DataVersionManager:
    """数据版本管理器"""

    def __init__(self, data_dir: str | Path = "ft_userdir/data", version_dir: str | Path = ".data_versions"):
        """初始化数据版本管理器

        Args:
            data_dir: 数据目录
            version_dir: 版本元数据目录
        """
        self.data_dir = Path(data_dir)
        self.version_dir = Path(version_dir)
        self.version_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_file = self.version_dir / "manifest.json"
        self._load_manifest()

    def _load_manifest(self) -> None:
        """加载版本清单"""
        if self.manifest_file.exists():
            with open(self.manifest_file, encoding="utf-8") as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {"versions": []}

    def _save_manifest(self) -> None:
        """保存版本清单"""
        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, indent=2, ensure_ascii=False)

    def _calculate_hash(self, file_path: Path) -> str:
        """计算文件哈希值

        Args:
            file_path: 文件路径

        Returns:
            SHA256 哈希值
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def create_snapshot(self, description: str = "", tags: list[str] | None = None) -> str:
        """创建数据快照

        Args:
            description: 快照描述
            tags: 标签列表

        Returns:
            版本ID
        """
        version_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_dir = self.version_dir / version_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # 复制数据文件
        files_info = []
        if self.data_dir.exists():
            for file_path in self.data_dir.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(self.data_dir)
                    target_path = snapshot_dir / rel_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, target_path)

                    files_info.append({
                        "path": str(rel_path),
                        "size": file_path.stat().st_size,
                        "hash": self._calculate_hash(file_path)
                    })

        # 记录版本信息
        version_info = {
            "version_id": version_id,
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "tags": tags or [],
            "files": files_info,
            "file_count": len(files_info)
        }

        self.manifest["versions"].append(version_info)
        self._save_manifest()

        return version_id

    def list_versions(self) -> list[dict[str, Any]]:
        """列出所有版本

        Returns:
            版本信息列表
        """
        return self.manifest["versions"]

    def get_version(self, version_id: str) -> dict[str, Any] | None:
        """获取指定版本信息

        Args:
            version_id: 版本ID

        Returns:
            版本信息，不存在则返回 None
        """
        for version in self.manifest["versions"]:
            if version["version_id"] == version_id:
                return version
        return None

    def restore_version(self, version_id: str) -> bool:
        """恢复到指定版本

        Args:
            version_id: 版本ID

        Returns:
            是否成功
        """
        version = self.get_version(version_id)
        if not version:
            return False

        snapshot_dir = self.version_dir / version_id
        if not snapshot_dir.exists():
            return False

        # 清空当前数据目录
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 恢复数据文件
        for file_path in snapshot_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(snapshot_dir)
                target_path = self.data_dir / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, target_path)

        return True
