"""
把 freqtrade_docs/raw_html 下的离线 Freqtrade 文档 HTML，批量整理成更适合“vibe coding 查阅使用”的中文 Markdown。

目标：
- 结构化：统一的“元信息 + 仓库运行方式 + 目录速览 + 原文（自动 Markdown 化）”
- 可搜索：尽量把正文转换为纯文本/Markdown，避免大量残留 HTML 标签
- 可复制：保留并清洗 <pre><code> 代码块为 fenced code block

说明：
- 本脚本不追求逐句翻译；主要目的是让 AI/人类都能在本仓库里快速检索、复制示例、定位参数。
- `configuration.zh-CN.md` 与 `data_download.zh-CN.md` 属于人工整理稿，本脚本会在其末尾追加“附录：官方原文（自动 Markdown 化）”（避免覆盖原文整理结构）。
"""

from __future__ import annotations

import html as html_lib
import re
from pathlib import Path


DOCS_DIR_DEFAULT = Path("freqtrade_docs")
RAW_HTML_DIRNAME = "raw_html"

SKIP_OVERWRITE_MD = {
    "configuration.zh-CN.md",
    "data_download.zh-CN.md",
}

APPENDIX_MARKER = "## 附录：官方原文（自动 Markdown 化）"


TITLE_MAP = {
    "advanced-backtesting": "回测分析（高级）",
    "advanced-hyperopt": "超参优化（高级）",
    "advanced-orderflow": "订单流（高级）",
    "advanced-setup": "高级安装后任务",
    "backtesting": "回测",
    "bot-basics": "基础概念",
    "bot-usage": "启动与使用 Bot",
    "configuration": "配置",
    "data-analysis": "数据分析与 Notebook",
    "data-download": "数据下载",
    "deprecated": "已弃用功能",
    "developer": "贡献者指南",
    "docker_quickstart": "Docker 快速开始",
    "exchanges": "交易所说明",
    "faq": "常见问题",
    "freq-ui": "freqUI 界面",
    "freqai-configuration": "FreqAI 配置",
    "freqai-developers": "FreqAI 开发者指南",
    "freqai-feature-engineering": "FreqAI 特征工程",
    "freqai-parameter-table": "FreqAI 参数表",
    "freqai-reinforcement-learning": "FreqAI 强化学习",
    "freqai-running": "运行 FreqAI",
    "freqai": "FreqAI 介绍",
    "hyperopt": "超参优化",
    "installation": "安装（Linux/macOS/Raspberry）",
    "leverage": "做空与杠杆",
    "lookahead-analysis": "前视偏差分析",
    "plotting": "绘图与可视化",
    "plugins": "插件与扩展",
    "producer-consumer": "生产者/消费者模式",
    "recursive-analysis": "递归分析",
    "rest-api": "REST API",
    "sql_cheatsheet": "SQL 速查",
    "stable": "Freqtrade（文档首页）",
    "stoploss": "止损",
    "strategy-101": "策略快速开始",
    "strategy-advanced": "高级策略",
    "strategy_analysis_example": "策略分析示例",
    "strategy-callbacks": "策略回调",
    "strategy-customization": "策略自定义",
    "strategy_migration": "策略迁移",
    "telegram-usage": "Telegram 使用",
    "trade-object": "Trade 对象",
    "updating": "更新 Freqtrade",
    "utils": "工具子命令",
    "webhook-config": "Webhook 配置",
    "windows_installation": "Windows 安装",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _strip_tags(text: str, *, collapse_ws: bool = True) -> str:
    if not text:
        return ""
    text = re.sub(
        r"<a\s+class=headerlink[^>]*>.*?</a>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    if collapse_ws:
        text = re.sub(r"\s+", " ", text).strip()
    return text


def _strip_tags_preserve_ws(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip("\n")


def _guess_code_language(code: str) -> str:
    s = code.lstrip()
    if s.startswith("usage:"):
        return "text"
    if re.search(r"(?m)^\s*(uv run )?freqtrade\b", code):
        return "bash"
    if s.startswith("{") or s.startswith("["):
        return "json"
    if re.search(r"(?m)^\s*(def|class)\s+\w+", code) or "import " in code:
        return "python"
    return "text"


def _extract_head_info(html: str) -> tuple[str, str]:
    # canonical（兼容引号、href/rel 顺序差异）
    canonical = ""
    canonical_patterns = (
        r"<link\b[^>]*\brel=(?:\"|')?canonical(?:\"|')?[^>]*\bhref=(?:\"|')?([^\s\"'>]+)",
        r"<link\b[^>]*\bhref=(?:\"|')?([^\s\"'>]+)[^>]*\brel=(?:\"|')?canonical(?:\"|')?",
    )
    for pat in canonical_patterns:
        m = re.search(pat, html, flags=re.IGNORECASE)
        if m:
            canonical = m.group(1).strip()
            break

    # saved date
    m = re.search(r"saved date:\s*(.+)$", html, flags=re.IGNORECASE | re.MULTILINE)
    saved_date = m.group(1).strip() if m else ""
    return canonical, saved_date


def _slug_from_canonical(canonical: str) -> str:
    # canonical looks like https://www.freqtrade.io/en/stable/backtesting/
    path = canonical.split("://", 1)[-1].split("/", 1)[-1]
    path = "/" + path if not path.startswith("/") else path
    # /en/stable/<slug>/  or /en/stable/
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "stable"
    return parts[-1]


def _md_name_from_slug(slug: str) -> str:
    return re.sub(r"\s+", "_", slug.replace("-", "_")) + ".zh-CN.md"


def _extract_article(html: str) -> str:
    m = re.search(
        r'<article\s+class="md-content__inner[^"]*"\s*>(.*?)</article>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return m.group(1) if m else html


def _extract_h1(article_html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", article_html, flags=re.IGNORECASE | re.DOTALL)
    return _strip_tags(m.group(1)) if m else ""


def _extract_h2_titles(article_html: str) -> list[str]:
    titles: list[str] = []
    for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", article_html, flags=re.IGNORECASE | re.DOTALL):
        t = _strip_tags(m.group(1))
        if t:
            titles.append(t)
    return titles


def _normalize_blank_lines(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _convert_inline_code(html_text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        inner = _strip_tags(m.group(1))
        if not inner:
            return "``"
        # 简单处理：如果内容里含 `，就退化为普通文本
        if "`" in inner:
            return inner.replace("`", "'")
        return f"`{inner}`"

    return re.sub(
        r"<code[^>]*>(.*?)</code>",
        repl,
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _convert_links(html_text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        href = m.group(1).strip().strip('"').strip("'")
        text = _strip_tags(m.group(2))
        if not text:
            return href
        return f"[{text}]({href})"

    # href 可能没有引号
    return re.sub(
        r"<a[^>]*href=([^\s>]+)[^>]*>(.*?)</a>",
        repl,
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _convert_headings(html_text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        level = int(m.group(1))
        # 附录里整体下沉一级：h2 -> ###，h3 -> ####
        new_level = min(level + 1, 6)
        content = _strip_tags(m.group(2))
        if not content:
            return ""
        return f"\n\n{'#' * new_level} {content}\n\n"

    # 先移除 h1（页面标题会在文档头部重复）
    html_text = re.sub(r"<h1[^>]*>.*?</h1>", "", html_text, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(
        r"<h([2-6])[^>]*>(.*?)</h\1>",
        repl,
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _convert_lists_and_paragraphs(html_text: str) -> str:
    # 段落
    html_text = re.sub(r"</p>", "\n\n", html_text, flags=re.IGNORECASE)
    html_text = re.sub(r"<p[^>]*>", "", html_text, flags=re.IGNORECASE)

    # 换行
    html_text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)

    # 列表（统一降级为无序列表，便于检索）
    html_text = re.sub(r"<li[^>]*>", "\n- ", html_text, flags=re.IGNORECASE)
    html_text = re.sub(r"</li>", "", html_text, flags=re.IGNORECASE)
    html_text = re.sub(r"</?(ul|ol)[^>]*>", "\n", html_text, flags=re.IGNORECASE)

    return html_text


def _table_to_markdown(table_html: str) -> str:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL)
    if not rows:
        return ""

    parsed: list[list[str]] = []
    for row in rows:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, flags=re.IGNORECASE | re.DOTALL)
        cell_texts = []
        for cell in cells:
            t = _strip_tags(cell)
            t = t.replace("|", "\\|")
            cell_texts.append(t)
        if cell_texts:
            parsed.append(cell_texts)

    if not parsed:
        return ""

    # 对齐列数
    width = max(len(r) for r in parsed)
    for r in parsed:
        if len(r) < width:
            r.extend([""] * (width - len(r)))

    header = parsed[0]
    sep = ["---"] * width
    body = parsed[1:]

    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    for r in body:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _convert_tables(html_text: str) -> tuple[str, list[str]]:
    tables: list[str] = []

    def repl(m: re.Match[str]) -> str:
        md = _table_to_markdown(m.group(1))
        idx = len(tables)
        tables.append(md)
        return f"\n\n@@TABLE_{idx}@@\n\n"

    new_text = re.sub(
        r"<table[^>]*>(.*?)</table>",
        repl,
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return new_text, tables


def _convert_codeblocks(html_text: str) -> tuple[str, list[str]]:
    codeblocks: list[str] = []

    # 同时捕获可选的“文件名”提示：<span class=filename>...</span>
    pattern = re.compile(
        r"(?:<span\s+class=filename>(.*?)</span>\s*)?"
        r"<pre[^>]*>.*?<code[^>]*>(.*?)</code>.*?</pre>",
        flags=re.IGNORECASE | re.DOTALL,
    )

    def repl(m: re.Match[str]) -> str:
        filename_html = m.group(1) or ""
        code_html = m.group(2) or ""

        filename = _strip_tags(filename_html)
        code = _strip_tags_preserve_ws(code_html)
        lang = _guess_code_language(code)

        fence = f"```{lang}\n{code}\n```"
        if filename:
            fence = f"文件：`{filename}`\n\n{fence}"

        idx = len(codeblocks)
        codeblocks.append(fence)
        return f"\n\n@@CODE_{idx}@@\n\n"

    new_text = pattern.sub(repl, html_text)
    return new_text, codeblocks


def _finalize_placeholders(text: str, *, codeblocks: list[str], tables: list[str]) -> str:
    for i, block in enumerate(codeblocks):
        text = text.replace(f"@@CODE_{i}@@", block)
    for i, table in enumerate(tables):
        # 空表格就直接移除占位符
        text = text.replace(f"@@TABLE_{i}@@", table if table else "")
    return text


def convert_article_to_markdown(article_html: str) -> str:
    # 清理一些与正文无关的 UI 元素
    cleaned = re.sub(
        r"<a[^>]*rel=edit[^>]*>.*?</a>",
        "",
        article_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(r"<nav\s+class=md-code__nav>.*?</nav>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<button[^>]*md-code__button[^>]*>.*?</button>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<a\s+class=headerlink[^>]*>.*?</a>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)

    cleaned, codeblocks = _convert_codeblocks(cleaned)
    cleaned, tables = _convert_tables(cleaned)

    cleaned = _convert_headings(cleaned)
    cleaned = _convert_inline_code(cleaned)
    cleaned = _convert_links(cleaned)
    cleaned = _convert_lists_and_paragraphs(cleaned)

    # 强调/加粗（尽量晚做，避免影响内部替换）
    cleaned = re.sub(r"</?strong[^>]*>", "**", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</?em[^>]*>", "*", cleaned, flags=re.IGNORECASE)

    # 去掉剩余标签
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = html_lib.unescape(cleaned)

    cleaned = _finalize_placeholders(cleaned, codeblocks=codeblocks, tables=tables)
    return _normalize_blank_lines(cleaned)


def build_doc_markdown(
    *,
    cn_title: str,
    en_title: str,
    canonical: str,
    saved_date: str,
    h2_titles: list[str],
    body_md: str,
) -> str:
    lines: list[str] = []
    display_en = en_title or cn_title
    lines.append(f"# {cn_title}（{display_en}）")
    lines.append("")
    lines.append("这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。")
    lines.append("")
    lines.append(f"- 来源：{canonical}")
    if saved_date:
        lines.append(f"- 离线保存时间：{saved_date}")
    lines.append("")
    lines.append("## 0) 本仓库的推荐运行方式（Windows + uv）")
    lines.append("")
    lines.append("本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：")
    lines.append("")
    lines.append("```bash")
    lines.append('uv run freqtrade <命令> --userdir "." <参数...>')
    lines.append("```")
    lines.append("")
    lines.append('下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。')
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1) 目录速览（H2）")
    lines.append("")
    lines.append("下面列出原文的一级小节标题（H2），便于你快速定位内容：")
    lines.append("")
    for t in h2_titles:
        lines.append(f"- {t}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2) 原文（自动 Markdown 化，便于搜索与复制）")
    lines.append("")
    lines.append(body_md.rstrip("\n"))
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    docs_dir = DOCS_DIR_DEFAULT
    raw_dir = docs_dir / RAW_HTML_DIRNAME
    if not raw_dir.exists():
        raise SystemExit(
            "\n".join(
                [
                    f"未找到目录：{raw_dir.as_posix()}",
                    "说明：该目录可能被 gitignore（用于减小仓库体积）。",
                    '如需重新生成，请先运行：uv run python "scripts/download_freqtrade_docs_html.py"',
                ]
            )
        )

    html_files = sorted(raw_dir.glob("*.html"))
    if not html_files:
        raise SystemExit(f"目录为空：{raw_dir.as_posix()}")

    generated: list[str] = []
    appended: list[str] = []

    for html_path in html_files:
        html_text = _read_text(html_path)
        canonical, saved_date = _extract_head_info(html_text)
        if not canonical:
            continue

        slug = _slug_from_canonical(canonical)
        md_name = _md_name_from_slug(slug)
        md_path = docs_dir / md_name

        article = _extract_article(html_text)
        en_title = _extract_h1(article) or slug
        cn_title = TITLE_MAP.get(slug, en_title or slug)
        h2_titles = _extract_h2_titles(article)

        body_md = convert_article_to_markdown(article)

        if md_name in SKIP_OVERWRITE_MD and md_path.exists():
            existing = _read_text(md_path)
            if APPENDIX_MARKER in existing:
                continue
            appendix = "\n".join(
                [
                    "",
                    "---",
                    "",
                    APPENDIX_MARKER,
                    "",
                    f"- 来源：{canonical}",
                    f"- 离线保存时间：{saved_date}" if saved_date else "",
                    "",
                    body_md.rstrip("\n"),
                    "",
                ]
            )
            appendix = _normalize_blank_lines(appendix)
            _write_text(md_path, existing.rstrip() + "\n\n" + appendix)
            appended.append(md_name)
            continue

        doc_md = build_doc_markdown(
            cn_title=cn_title,
            en_title=en_title,
            canonical=canonical,
            saved_date=saved_date,
            h2_titles=h2_titles,
            body_md=body_md,
        )
        _write_text(md_path, doc_md)
        generated.append(md_name)

    print(f"生成/覆盖：{len(generated)} 个")
    for name in generated:
        print(f"- {name}")
    print(f"追加附录：{len(appended)} 个")
    for name in appended:
        print(f"- {name}")


if __name__ == "__main__":
    main()
