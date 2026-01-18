#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时脚本：清理文档中的 vbrain 引用"""

import re
from pathlib import Path

# 需要处理的文件列表
files_to_clean = [
    "docs/knowledge/ema_macd_vegas_playbook.md",
    "docs/knowledge/industry_best_practices_improvement_space.md",
    "docs/knowledge/industry_best_practices_support_analysis.md",
    "docs/knowledge/mcp_browser_automation_landscape.md",
    "docs/knowledge/mcp_knowledge_memory_landscape.md",
    "docs/knowledge/small_account_10_to_10000_practice_guide.md",
    "docs/reports/change_summary_2026-01-12.md",
    "docs/reports/change_summary_2026-01-13.md",
    "docs/reports/change_summary_2026-01-15.md",
    "docs/reports/local_vector_db_review_2026-01-15_v1.0.md",
    "docs/reports/no_wheel_audit_2026-01-14.md",
    "docs/reports/quant_trading_full_stack_guide_2026-01-15_v1.0.md",
    "docs/reports/tech_debt_review_2026-01-15_v1.0.md",
]

base_dir = Path("F:/Code/freqtrade_demo")
cleaned_count = 0

for file_path in files_to_clean:
    full_path = base_dir / file_path
    if not full_path.exists():
        print(f"跳过（文件不存在）：{file_path}")
        continue

    # 读取文件
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 清理标题中的 "（vbrain 回灌）"
    content = re.sub(r'（vbrain 回灌）', '', content)

    # 清理其他 vbrain 相关引用（保持上下文完整）
    # 这里只做简单的文本替换，不删除整段内容

    if content != original_content:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        cleaned_count += 1
        print(f"已清理：{file_path}")
    else:
        print(f"无需清理：{file_path}")

print(f"\n完成！共清理 {cleaned_count} 个文件")
