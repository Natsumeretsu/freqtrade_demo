# Knowledge & Memory MCP 方案评估

更新日期：2026-01-17

本文档用于回答一个核心问题：在 `awesome-mcp-servers` 的 **Knowledge & Memory** 类目中，哪些 MCP 更适合构建项目知识管理系统？

> **结论先行**：本项目采用 Docker MCP ToolKit 的 `memory` 工具（知识图谱）作为核心知识管理方案，配合 `fetch`/`playwright`/`context7`/`duckduckgo` 实时获取外部资料，符合"实时获取、按需存储"的原则。

---

## 1. 当前架构（推荐）

### 核心工具：Docker MCP ToolKit `memory`

**定位**：项目知识图谱存储

**核心概念**：
- **实体（Entity）**：具有观察的节点（如项目、模块、配置）
- **关系（Relation）**：主动语态的有向连接（如"项目使用技术栈"）
- **观察（Observation）**：原子事实（每个观察一个事实）

**常用工具**：
- `create_entities`：创建新实体
- `create_relations`：创建实体间关系
- `add_observations`：添加观察
- `search_nodes`：搜索节点
- `read_graph`：读取完整图谱

**优势**：
- 结构化存储：实体-关系-观察三层模型
- 语义检索：支持关键词搜索和图谱遍历
- 轻量级：无需额外进程或数据库
- 可追溯：所有知识都有明确来源

### 辅助工具：实时获取外部资料

**网页内容**：
- `fetch`：静态页面抓取，HTML→Markdown 转换
- `playwright`：动态页面交互、表单填写、截图

**官方文档**：
- `context7`：第三方库/框架文档与 API 查询

**搜索查询**：
- `duckduckgo`：网页搜索、关键词检索

**代码语义**：
- `serena`：LSP-based 代码符号检索与编辑（独立 MCP）

---

## 2. 工作流程

### 2.1 知识获取流程

1. **来源登记**：URL 登记在 `docs/knowledge/source_registry.md`
2. **实时获取**：使用 MCP 工具（fetch/playwright/context7/duckduckgo）实时获取内容
3. **提炼要点**：提取关键结论，写入 `docs/` 对应文档
4. **知识存储**：使用 `memory` 工具存储关键知识到知识图谱

### 2.2 知识检索流程

1. **搜索节点**：使用 `search_nodes` 搜索相关实体
2. **读取图谱**：使用 `read_graph` 读取完整知识图谱
3. **文档查询**：查阅 `docs/` 目录中的详细文档

---

## 3. awesome-mcp-servers 候选评估

### 3.1 文档检索类

**候选**：
- `shinpr/mcp-local-rag`：本地向量库 + 本地嵌入 + 混合检索
- `nonatofabio/local-faiss-mcp`：FAISS 向量检索
- `hannesrudolph/mcp-ragdocs`：文档 RAG 检索

**评估结论**：
- ❌ 不推荐：违反"实时获取"原则，引入本地缓存复杂度
- 当前方案（memory + 实时获取）已满足需求

### 3.2 记忆引擎类

**候选**：
- `redleaves/context-keeper`：多维检索（向量/时间线/知识图谱）
- `vectorize-io/hindsight`：Agent 长期记忆
- `topoteretes/cognee (cognee-mcp)`：多图/多向量存储
- `agentic-mcp-tools/memora`：知识图谱可视化

**评估结论**：
- ⚠️ 观望：功能强大但复杂度高，维护成本大
- 当前 `memory` 工具已满足基本需求
- 建议：需求明确后再做 POC 对比

### 3.3 云服务类

**候选**：
- `mem0ai/mem0-mcp`：云端记忆服务
- `pinecone-io/assistant-mcp`：Pinecone 向量数据库
- `graphlit-mcp-server`：云端知识图谱

**评估结论**：
- ❌ 不推荐：需要 API key，数据外流风险，违反"本地优先"原则

### 3.4 笔记软件集成类

**候选**：
- Obsidian/Zotero/Mendeley 相关 MCP

**评估结论**：
- ❌ 不推荐：引入额外依赖，不符合当前工作流

---

## 4. 设计原则

### 4.1 实时获取 vs 本地缓存

**原则**：优先实时获取，按需存储关键知识

**理由**：
- 避免缓存过期问题
- 减少存储空间占用
- 降低维护成本
- 保持信息最新

### 4.2 结构化存储 vs 全文检索

**原则**：结构化存储关键知识，全文检索依赖实时获取

**理由**：
- 知识图谱更适合表达实体关系
- 全文检索可通过 MCP 工具实时完成
- 避免重复存储和同步问题

### 4.3 轻量级 vs 重型平台

**原则**：优先轻量级工具，避免过度工程化

**理由**：
- 降低学习成本
- 减少维护负担
- 提高可控性
- 便于迁移和升级

---

## 5. 下一步建议

1. **完善知识图谱**：
   - 补充项目核心概念实体
   - 建立实体间关系
   - 添加关键观察

2. **优化工作流**：
   - 标准化知识获取流程
   - 建立知识提炼模板
   - 定期审查知识图谱

3. **监控与评估**：
   - 跟踪知识图谱使用情况
   - 评估检索效率
   - 根据需求调整策略

---

## 6. 参考资料

- Docker MCP ToolKit 文档：https://docs.docker.com/mcp/
- awesome-mcp-servers：https://github.com/punkpeye/awesome-mcp-servers
- MCP 协议规范：https://modelcontextprotocol.io/
