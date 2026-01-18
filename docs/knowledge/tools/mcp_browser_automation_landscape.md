# Browser Automation MCP 抓取选型（vibe brain 采集层）

更新日期：2026-01-11

本文档用于回答一个核心问题：在 `awesome-mcp-servers` 的 **Browser Automation** 类目中，哪些 MCP 更适合本项目的“资料采集层”（网页为主，强调完整性与可复现），并给出本仓库的推荐落地方式。

> 结论先行：**不需要为了“抓网页”再引入一堆新的 MCP**。本项目已经具备一流的采集能力：`markitdown`（静态/直连） + `microsoft/playwright-mcp`（浏览器渲染） +（可选）`chrome_devtools_mcp`（网络/性能深挖）。真正的增益来自“采集产物更完整 + 元数据更规范”，而不是“换一个浏览器 MCP”。

---

## 1) 你的目标（按优先级）

1. **采集尽量完整且精确**：避免 “garbage in, garbage out”。  
2. **本地优先**：采集结果以本地落盘为主；缓存可重建；项目文档沉淀关键结论。  
3. **工作流可复制**：未来可复用到其他仓库（每仓库一份可进化“大脑”）。  
4. **合规边界明确**：遇到验证码/登录墙/订阅墙 → 记录 `blocked`，**不提供绕过方案**（需要人工/合法授权介入）。

---

## 2) Browser Automation（29 项）快速分型（只看“通用抓取”相关）

> 下面仅列出与“通用网页采集”强相关的类型；B 站/YouTube 等站点专用工具不纳入本项目默认栈。

### 2.1 Playwright 系（推荐继续用）

- `microsoft/playwright-mcp`：官方 Playwright MCP（结构化可访问性快照 + 交互）。  
- 其他 Playwright 封装（`automatalabs/*`、`executeautomation/*` 等）：功能重叠，优先级低于官方。

为什么适配本项目？
- Playwright 渲染完整（JS/SPA/懒加载更友好）。
- 可获取“快照 + 截图 + DOM + 网络请求清单”，适合做“高质量原始输入”。

### 2.2 Puppeteer / Selenium 系（不作为默认）

- `modelcontextprotocol/server-puppeteer`（仓库归档/历史实现）、以及若干 Puppeteer/Selenium MCP。  

不作为默认的原因：
- 对本项目而言，“换内核”的收益通常 < 迁移与维护成本；Playwright 已覆盖关键能力。

### 2.3 “控制本机浏览器/用户 Profile”系（可选兜底）

- `browsermcp/mcp`、`ndthanhdev/mcp-browser-kit`：控制本机浏览器，可能更容易复用你本机的登录态/插件环境。  

适用场景（可选）：
- 你对某站点有**合法账号与访问权限**，但 headless/新环境频繁触发验证；你愿意手动登录一次，再由 MCP 采集页面内容。  

注意：
- 这不是“绕过验证码/订阅墙”，而是“在合法登录态下采集”；脚本层仍应记录 `blocked` 并提示人工介入点。

### 2.4 Cloud scraping / 批处理 API（默认不选）

- `browserbase/*`、`olostep/*`：云端浏览器/云端抓取与批处理。  

默认不选的原因：
- 与“本地优先”冲突（数据外流、API key/账单、可控性下降）。  
- 只有在你明确接受云依赖、且需要大规模批量爬取时再做 POC。

### 2.5 “Agent 化浏览器”（不作为采集基础设施）

- `browser-use-*`、`web-eval-agent` 等：强调 agentic 操作/调试。  

对“可复现采集”而言的问题：
- 交互路径更随机、产物不够确定；更适合做任务执行，不适合作为“资料采集管线”的底座。

---

## 3) 本项目推荐的采集架构（保持分层）

### 3.1 一句话版本

**用 `markitdown` 抓“能直连的正文”，用 Playwright 抓“需要浏览器渲染的页面”，并把采集产物扩展为：快照 + DOM + 网络清单 + 元数据。**

### 3.2 采集产物（建议规范）

使用 MCP 工具实时获取网页内容：

- `markitdown` MCP 工具：静态页面抓取，HTML→Markdown 转换
- `playwright` MCP 工具：动态页面交互、表单填写、截图、快照
- 提取关键要点后，写入 `docs/` 对应文档
- 必要时使用 `memory` 工具存储到知识图谱

### 3.3 UA（标准浏览器 UA）策略

优先做“**正常模拟**”：
- 只设置常见桌面浏览器 UA（例如 Windows Chrome 稳定版），不做“反检测”黑魔法。  
- 采集目标是“更一致的页面表现”，不是对抗站点风控。

---

## 4) 结论与下一步落地

结论：
- **不建议替换**：继续以 `microsoft/playwright-mcp` 为主（本项目已在脚本里使用 `@playwright/mcp`）。  
- **建议增强**：把 Playwright 抓取脚本升级为“快照 + DOM + 网络 + UA 覆盖 + blocked 识别”。

下一步（落地文件入口）：
- 使用 `playwright` MCP 工具进行浏览器自动化
- 来源登记：`docs/knowledge/source_registry.md`
- MCP 工具使用参考：`docs/knowledge/index.md`
