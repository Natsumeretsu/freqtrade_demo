#!/usr/bin/env python3
"""批量修复文档链接的脚本"""
import re
from pathlib import Path

def fix_links_in_file(file_path, replacements):
    """修复单个文件中的链接"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        for old_link, new_link in replacements.items():
            content = content.replace(old_link, new_link)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"处理文件失败 {file_path}: {e}")
        return False

def main():
    docs_dir = Path('F:/Code/freqtrade_demo/docs')

    # 定义需要修复的链接映射
    link_fixes = {
        # evaluation/ 目录内的链接修复
        'evaluation': {
            'parameter_optimization_failure_analysis_plan_b.md':
                'parameter_optimization_failure_analysis_plan_b_2026-01-16.md',
            'p0_2_risk_warning_design.md':
                'p0_2_risk_warning_design_2026-01-16.md',
            'strategy_fix_proposal_SmallAccountFuturesTimingExecV1.md':
                'strategy_fix_proposal_SmallAccountFuturesTimingExecV1_2026-01-16.md',
            'gap_analysis.md':
                'gap_analysis_2026-01-16.md',
        }
    }

    # 修复 evaluation/ 目录的链接
    eval_dir = docs_dir / 'evaluation'
    fixed_count = 0

    for file in eval_dir.glob('*.md'):
        if fix_links_in_file(file, link_fixes['evaluation']):
            print(f"[OK] 修复链接: {file.name}")
            fixed_count += 1

    print(f"\n完成！共修复 {fixed_count} 个文件的链接")

if __name__ == '__main__':
    main()
