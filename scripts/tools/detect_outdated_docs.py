#!/usr/bin/env python3
"""检测过时文档的脚本"""
import re
from pathlib import Path
from datetime import datetime, timedelta

def extract_date_from_content(file_path):
    """从文档内容中提取更新日期"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(500)  # 只读前500字符

        match = re.search(r'更新日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
        if match:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
    except Exception as e:
        print(f"读取文件失败 {file_path}: {e}")
    return None

def main():
    docs_dir = Path('F:/Code/freqtrade_demo/docs')

    # 查找所有非归档的 markdown 文件
    md_files = []
    for file in docs_dir.glob('**/*.md'):
        if 'archive' not in str(file):
            md_files.append(file)

    # 检测过时文档（6个月未更新）
    threshold_date = datetime.now() - timedelta(days=180)
    outdated_docs = []
    no_date_docs = []

    for file in md_files:
        rel_path = file.relative_to(docs_dir.parent)
        update_date = extract_date_from_content(file)

        if update_date is None:
            no_date_docs.append(str(rel_path))
        elif update_date < threshold_date:
            days_old = (datetime.now() - update_date).days
            outdated_docs.append((str(rel_path), days_old))

    # 输出结果
    print(f"=== 文档过时检测报告 ===")
    print(f"检测日期: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"总文档数: {len(md_files)}")
    print(f"过时阈值: 180 天\n")

    if outdated_docs:
        print(f"过时文档 ({len(outdated_docs)} 个):")
        outdated_docs.sort(key=lambda x: x[1], reverse=True)
        for path, days in outdated_docs:
            print(f"  - {path} (已 {days} 天未更新)")
    else:
        print("未发现过时文档")

    if no_date_docs:
        print(f"\n缺少日期的文档 ({len(no_date_docs)} 个):")
        for path in no_date_docs:
            print(f"  - {path}")

    print(f"\n建议:")
    print(f"- 审查过时文档，决定是否更新或归档")
    print(f"- 为缺少日期的文档添加元数据")

if __name__ == '__main__':
    main()
