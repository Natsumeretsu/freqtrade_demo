# 外部来源抓取与固化流程（Policy）

更新日期：2026-01-10

本记忆定义“抓取→登记→提炼→回灌”的统一流程，保证可追溯与可迭代。

---

## 1) 唯一登记表（文档侧权威）

- 外部来源唯一清单：`project_docs/knowledge/source_registry.md`
- 知识索引入口：`project_docs/knowledge/index.md`

---

## 2) 标准流程（必须遵守）

1. 先登记：为每个 URL 分配唯一编号 `S-xxx`，标注分类（网格/均值回归/套利/期货风控/框架/研究等）。
2. 再采集（vharvest）：静态优先（markitdown）→ 需要 JS/交互则浏览器渲染（playwright）→ 失败则标注 blocked。
3. 只沉淀“可复用要点”：参数、风险、边界、工程落地提示；避免粘贴大段原文。
4. 回灌到正确位置：
   - 赛道级结论回灌到 `project_docs/design/crypto_futures_strategy_options.md`
   - 策略级结论回灌到对应“策略唯一基底文档”
   - 索引文件只挂链接，不重复写内容

---

## 3) 抓取状态分类（统一口径）

- `ok`：可抓取并可提炼要点
- `blocked`：不可稳定抓取（例如 403/robot/js-required/406/460/订阅墙）

blocked 的处理原则：
- 先登记原因，再寻找替代来源（优先官方文档/开放 PDF/arXiv/GitHub）。
- 若你对该内容**确有合法访问权限**（账号/订阅/授权），允许人工介入：  
  使用 `python -X utf8 scripts/tools/vharvest.py fetch-playwright -- --interactive`（默认 `--interactive-mode deferred`，不阻塞其它条目），按提示在浏览器窗口完成验证/登录；脚本会自动等待并在检测到页面可访问后继续抓取；如仍受阻，可选择导出 HTML/PDF 并离线转写为 `manual_markitdown.md`，再进行提炼回灌。  
  注意：只做“合法访问 + 人工导出”，不提供或实施任何绕过验证码/付费墙的方案。

---

## 4) 优先级（推荐抓取顺序）

1) 官方文档（Freqtrade/FreqAI、交易所规则等）
2) 开放 PDF / arXiv / 高校库
3) GitHub 开源实现（用于验证“怎么做”）
4) 商业博客/营销站点（只取可执行要点，谨慎引用）
