#!/usr/bin/env python3
"""依赖安全扫描脚本

使用 pip-audit 扫描项目依赖的已知安全漏洞。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_security_scan() -> int:
    """运行依赖安全扫描

    Returns:
        退出码（0 表示无漏洞，1 表示发现漏洞）
    """
    print("🔍 开始依赖安全扫描...")
    print("=" * 60)

    try:
        # 运行 pip-audit
        result = subprocess.run(
            ["pip-audit", "--desc", "--format", "markdown"],
            capture_output=True,
            text=True,
            check=False,
        )

        print(result.stdout)

        if result.returncode == 0:
            print("\n✅ 未发现安全漏洞")
            return 0
        else:
            print("\n⚠️ 发现安全漏洞，请查看上述报告")
            return 1

    except FileNotFoundError:
        print("\n❌ 错误：未安装 pip-audit")
        print("请运行：pip install pip-audit")
        return 2


if __name__ == "__main__":
    sys.exit(run_security_scan())
