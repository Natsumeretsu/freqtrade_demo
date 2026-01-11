"""
校验 freqtrade_docs/raw_html/*.html 是否被正确转换为对应的 *.zh-CN.md。

目标（偏“防漏”而非逐句翻译校对）：
1) 覆盖率：每个 HTML 都能定位到对应 Markdown 文件。
2) 一致性：Markdown 内容与 scripts/generate_freqtrade_docs.py 的生成结果一致（避免手改漂移/转换遗漏）。
3) 结构健全：H2 标题可在正文中找到；代码块 fence 成对；尽量不残留明显 HTML 标签。

运行（本仓库推荐）：
  uv run python "scripts/docs/check_conversion.py"
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class DocMetrics:
    html_pre_blocks: int
    html_tables: int
    md_fence_lines: int
    md_code_blocks: int
    md_table_headers: int
    md_has_obvious_html_tags: bool
    missing_h2_titles: list[str]


def _iter_html_files(raw_dir: Path) -> list[Path]:
    return sorted([p for p in raw_dir.glob("*.html") if p.is_file()])


def _first_diff_line(expected: str, actual: str) -> tuple[int, str, str] | None:
    exp_lines = expected.splitlines()
    act_lines = actual.splitlines()
    max_len = max(len(exp_lines), len(act_lines))
    for idx in range(max_len):
        exp = exp_lines[idx] if idx < len(exp_lines) else ""
        act = act_lines[idx] if idx < len(act_lines) else ""
        if exp != act:
            return idx + 1, exp, act
    return None


def _md_table_header_count(md: str) -> int:
    # 粗略统计 Markdown 表格：表头行后紧跟分隔行（| --- | --- |）
    lines = md.splitlines()
    count = 0
    for i in range(len(lines) - 1):
        header = lines[i]
        sep = lines[i + 1]
        if not header.lstrip().startswith("|"):
            continue
        if re.match(r"^\|\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", sep.strip()):
            count += 1
    return count


def _has_obvious_html_tags(md: str) -> bool:
    # 只抓“明显是 HTML 标签”的残留，避免把 <https://...> 这类 autolink 误判为问题。
    return bool(
        re.search(
            r"<\s*(div|span|p|table|thead|tbody|tr|td|th|ul|ol|li|pre|code|a|img|h[1-6])\b",
            md,
            flags=re.IGNORECASE,
        )
    )


def _count_fence_lines(md: str) -> int:
    return len(re.findall(r"(?m)^```", md))


def _missing_h2_titles_in_body(h2_titles: Iterable[str], body_md: str) -> list[str]:
    missing: list[str] = []
    for t in h2_titles:
        # 附录里整体下沉一级：原始 H2 会变成 “###”，避免被目录速览中的 bullet 命中。
        if f"\n### {t}\n" not in f"\n{body_md}\n":
            missing.append(t)
    return missing


def _build_metrics(*, article_html: str, h2_titles: list[str], body_md: str) -> DocMetrics:
    html_pre_blocks = len(re.findall(r"(?i)<pre\b", article_html))
    # 只统计“内容表格”；Pygments 的代码高亮经常用 <table class=highlighttable> 包装行号与代码，这类不算内容表格。
    html_tables = len(re.findall(r"(?i)<table\b(?![^>]*\bhighlighttable\b)", article_html))

    md_fence_lines = _count_fence_lines(body_md)
    md_code_blocks = md_fence_lines // 2
    md_table_headers = _md_table_header_count(body_md)

    return DocMetrics(
        html_pre_blocks=html_pre_blocks,
        html_tables=html_tables,
        md_fence_lines=md_fence_lines,
        md_code_blocks=md_code_blocks,
        md_table_headers=md_table_headers,
        md_has_obvious_html_tags=_has_obvious_html_tags(body_md),
        missing_h2_titles=_missing_h2_titles_in_body(h2_titles, body_md),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验 raw_html -> Markdown 的转换一致性（防漏/防漂移）"
    )
    parser.add_argument(
        "--docs-dir",
        default="freqtrade_docs",
        help="文档目录（默认：freqtrade_docs）。",
    )
    parser.add_argument(
        "--raw-html-dirname",
        default="raw_html",
        help="HTML 子目录名（默认：raw_html）。",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出每篇文档的粗略指标（pre/table/fence 等）。",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    docs_dir = Path(args.docs_dir)
    raw_dir = docs_dir / args.raw_html_dirname
    if not raw_dir.exists():
        print(f"未找到 HTML 目录：{raw_dir.as_posix()}")
        return 2

    html_files = _iter_html_files(raw_dir)
    if not html_files:
        print(f"HTML 目录为空：{raw_dir.as_posix()}")
        return 2

    # scripts/docs 同级导入
    try:
        import generate as gen
    except Exception as exc:  # noqa: BLE001
        print("导入 scripts/docs/generate.py 失败：")
        print(str(exc))
        return 2

    issues: list[str] = []
    metrics_rows: list[tuple[str, DocMetrics]] = []

    for html_path in html_files:
        html_text = gen._read_text(html_path)  # type: ignore[attr-defined]
        canonical, saved_date = gen._extract_head_info(html_text)  # type: ignore[attr-defined]
        if not canonical:
            issues.append(f"{html_path.as_posix()}: 未解析到 rel=canonical（无法映射）")
            continue

        slug = gen._slug_from_canonical(canonical)  # type: ignore[attr-defined]
        md_name = gen._md_name_from_slug(slug)  # type: ignore[attr-defined]
        md_path = docs_dir / md_name
        if not md_path.exists():
            issues.append(f"{html_path.as_posix()}: 缺少对应 Markdown：{md_path.as_posix()}")
            continue

        article = gen._extract_article(html_text)  # type: ignore[attr-defined]
        en_title = gen._extract_h1(article) or slug  # type: ignore[attr-defined]
        cn_title = gen.TITLE_MAP.get(slug, en_title or slug)
        h2_titles = gen._extract_h2_titles(article)  # type: ignore[attr-defined]

        body_md = gen.convert_article_to_markdown(article)
        metrics_rows.append(
            (
                md_name,
                _build_metrics(article_html=article, h2_titles=h2_titles, body_md=body_md),
            )
        )

        if md_name in gen.SKIP_OVERWRITE_MD:
            existing = gen._read_text(md_path)  # type: ignore[attr-defined]
            if gen.APPENDIX_MARKER not in existing:
                issues.append(
                    f"{md_path.as_posix()}: 属于人工整理稿，但缺少附录标记：{gen.APPENDIX_MARKER}"
                )
                continue

            # 人工整理稿只要求“附录部分”与转换结果一致，忽略附录前面的分隔线（---）。
            expected_appendix = "\n".join(
                [
                    gen.APPENDIX_MARKER,
                    "",
                    f"- 来源：{canonical}",
                    f"- 离线保存时间：{saved_date}" if saved_date else "",
                    "",
                    body_md.rstrip("\n"),
                    "",
                ]
            )
            expected_appendix = gen._normalize_blank_lines(expected_appendix)  # type: ignore[attr-defined]

            actual_appendix = existing.split(gen.APPENDIX_MARKER, 1)[1]
            actual_appendix = gen.APPENDIX_MARKER + actual_appendix
            actual_appendix = gen._normalize_blank_lines(actual_appendix)  # type: ignore[attr-defined]

            if expected_appendix != actual_appendix:
                diff = _first_diff_line(expected_appendix, actual_appendix)
                if diff:
                    line_no, exp, act = diff
                    issues.append(
                        f"{md_path.as_posix()}: 附录内容与转换结果不一致（首个差异行 {line_no}）\n"
                        f"  期望：{exp}\n"
                        f"  实际：{act}"
                    )
                else:
                    issues.append(f"{md_path.as_posix()}: 附录内容与转换结果不一致（未知差异）")
            continue

        expected_doc = gen.build_doc_markdown(
            cn_title=cn_title,
            en_title=en_title,
            canonical=canonical,
            saved_date=saved_date,
            h2_titles=h2_titles,
            body_md=body_md,
        )
        actual_doc = gen._read_text(md_path)  # type: ignore[attr-defined]
        if expected_doc != actual_doc:
            diff = _first_diff_line(expected_doc, actual_doc)
            if diff:
                line_no, exp, act = diff
                issues.append(
                    f"{md_path.as_posix()}: 内容与转换结果不一致（首个差异行 {line_no}）\n"
                    f"  期望：{exp}\n"
                    f"  实际：{act}"
                )
            else:
                issues.append(f"{md_path.as_posix()}: 内容与转换结果不一致（未知差异）")

    # 额外结构/质量检查：发现明显风险就报错（这些不要求“完全相等”，只做防漏提示）
    for md_name, m in metrics_rows:
        if m.md_fence_lines % 2 != 0:
            issues.append(f"{docs_dir.as_posix()}/{md_name}: 代码块 fence 行数为奇数（疑似缺少闭合 ```）")
        if m.missing_h2_titles:
            issues.append(
                f"{docs_dir.as_posix()}/{md_name}: 正文缺少 {len(m.missing_h2_titles)} 个 H2 标题："
                + "；".join(m.missing_h2_titles[:6])
                + (" …" if len(m.missing_h2_titles) > 6 else "")
            )
        if m.md_has_obvious_html_tags:
            issues.append(f"{docs_dir.as_posix()}/{md_name}: 正文疑似残留明显 HTML 标签（如 <div>/<span>）")
        if m.html_pre_blocks and m.md_code_blocks == 0:
            issues.append(
                f"{docs_dir.as_posix()}/{md_name}: HTML 含 {m.html_pre_blocks} 个 <pre>，但 Markdown 未识别出代码块"
            )
        if m.html_tables and m.md_table_headers == 0:
            issues.append(
                f"{docs_dir.as_posix()}/{md_name}: HTML 含 {m.html_tables} 个 <table>，但 Markdown 未识别出表格（可能丢失）"
            )

    if args.verbose:
        print("粗略指标（用于人工抽查优先级）：")
        for md_name, m in sorted(
            metrics_rows, key=lambda r: (r[1].html_tables, r[1].html_pre_blocks), reverse=True
        ):
            print(
                f"- {md_name}: pre={m.html_pre_blocks}, table={m.html_tables}, "
                f"fence={m.md_fence_lines}, md_tables={m.md_table_headers}"
            )
        print()

    if issues:
        print("发现转换一致性/结构风险：")
        for item in issues:
            for line in item.splitlines():
                print(f"- {line}")
        print()
        print("结论：校验未通过。建议先修复生成脚本或对应 Markdown，再考虑移除 raw_html。")
        return 1

    print(f"校验通过：{len(html_files)} 个 HTML 均能映射且与 Markdown 转换结果一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
