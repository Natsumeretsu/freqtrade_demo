#!/usr/bin/env python3
"""为文档添加元数据的脚本"""
import re
from pathlib import Path

def extract_date_from_filename(filename):
    """从文件名中提取日期"""
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    return match.group(1) if match else None

def has_metadata(content):
    """检查是否已有元数据"""
    first_lines = '\n'.join(content[:10])
    return bool(re.search(r'更新日期[：:]\s*\d{4}-\d{2}-\d{2}', first_lines))

def add_metadata(file_path):
    """为单个文档添加元数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 检查是否已有元数据
    if has_metadata(lines):
        return False, "已有元数据"

    # 从文件名提取日期
    date = extract_date_from_filename(file_path.name)
    if not date:
        date = "2026-01-17"  # 默认日期

    # 找到第一个标题行
    title_line_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('# '):
            title_line_idx = i
            break

    if title_line_idx == -1:
        return False, "未找到标题行"

    # 在标题后插入元数据
    metadata = f"\n更新日期：{date}\n\n"
    lines.insert(title_line_idx + 1, metadata)

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    return True, f"已添加日期：{date}"

def main():
    docs_dir = Path('F:/Code/freqtrade_demo/docs')

    # 需要处理的文档列表
    missing_date_files = [
        # research/ 目录
        "research/cta_factors_series_crypto_research_2026-01-13.md",
        "research/huatai_cta_factors_crypto_research_2026-01-13.md",
        "research/industry_factor_strategy_separation_research_2026-01-13.md",
        "research/industry_factor_strategy_separation_research_part2_2026-01-13.md",
        "research/qlib_factor_library_crypto_research_2026-01-13.md",
        "research/qlib_freqtrade_factors_research_2026-01-13.md",
        # setup/ 目录
        "setup/claude_mcp_sync.md",
    ]

    print(f"开始处理 {len(missing_date_files)} 个文档...\n")

    success_count = 0
    for rel_path in missing_date_files:
        file_path = docs_dir / rel_path
        if not file_path.exists():
            print(f"[ERROR] {rel_path}: 文件不存在")
            continue

        success, message = add_metadata(file_path)
        if success:
            print(f"[OK] {rel_path}: {message}")
            success_count += 1
        else:
            print(f"[SKIP] {rel_path}: {message}")

    print(f"\n完成！成功处理 {success_count}/{len(missing_date_files)} 个文档")

if __name__ == '__main__':
    main()
