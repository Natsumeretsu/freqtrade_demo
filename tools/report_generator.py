"""性能报告生成器

自动生成性能分析报告。

创建日期: 2026-01-17
"""
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class ReportGenerator:
    """报告生成器"""

    def __init__(self):
        self.sections: List[str] = []

    def add_section(self, title: str, content: str) -> None:
        """添加报告章节"""
        self.sections.append(f"## {title}\n\n{content}\n")

    def generate(self, title: str) -> str:
        """生成完整报告"""
        report = [f"# {title}\n"]
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append("---\n")
        report.extend(self.sections)
        return "\n".join(report)

    def save(self, filename: str, title: str) -> None:
        """保存报告到文件"""
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.generate(title))
        
        print(f"报告已保存到: {path}")
