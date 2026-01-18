# 项目进一步改进清单

**日期**：2026-01-18
**分析方法**：Sequential Thinking（系统性分析）
**状态**：待确认执行

---

## 📊 改进概览

基于深度分析，识别出 **9个可改进维度**，预计可进一步删除 **~950K** 文件。

### 改进优先级

| 优先级 | 类别 | 影响 | 风险 |
|--------|------|------|------|
| P0 | 失效代码 | 高 | 低 |
| P1 | 冗余脚本 | 中 | 低 |
| P2 | 优化建议 | 低 | 中 |

---

## 🔴 P0：高优先级改进（影响功能）

### 1. 删除失效的策略文件

**问题**：4个策略依赖已删除的 `trading_system` 模块，无法运行

**失效策略清单**：
```
01_freqtrade/strategies/
├── OptimizedIntegrationStrategy.py          # 依赖 trading_system
├── SmallAccountFuturesTimingExecV1.py       # 依赖 trading_system
├── SmallAccountFuturesTrendV1.py            # 依赖 trading_system
└── SmallAccountSpotTrendFilteredV1.py       # 依赖 trading_system
```

**建议操作**：
- **选项A（推荐）**：移动到 `01_freqtrade/strategies_archive/` 供将来参考
- **选项B（激进）**：直接删除

**预计影响**：删除 ~100K

### 2. 删除失效的测试文件

**问题**：60+个测试文件全部基于旧架构的 `trading_system` 模块，已失效

**失效测试清单**：
```
tests/
├── test_arc_cache.py
├── test_auto_risk_service.py
├── test_batch_optimization.py
├── test_cache_strategy_comparison.py
├── test_config_management.py
├── test_data_prefetcher.py
├── test_dependency_graph.py
├── test_error_handling.py
├── test_factor_*.py (多个)
├── test_incremental_computation.py
├── test_integration_validation.py
├── test_koopman_*.py (多个)
├── test_memory_pool.py
├── test_performance_*.py (多个)
└── ... (共60+个文件)
```

**建议操作**：
- **删除整个 tests/ 目录**
- 为新的MVP架构编写简单测试（可选）

**预计影响**：删除 ~300K

## 🟡 P1：中优先级改进（占用空间）

### 3. 删除冗余的脚本目录

**问题**：scripts/ 目录包含大量基于旧架构的脚本

**冗余脚本清单**：
```
scripts/
├── archive/        # 54K  - 归档脚本
├── qlib/           # 220K - Qlib相关脚本（基于旧架构）
├── analysis/       # 160K - 分析脚本（基于旧架构）
├── docs/           # 65K  - 文档生成脚本
└── evaluation/     # 53K  - 评估脚本（基于旧架构）
```

**建议操作**：
- **删除**：archive/、qlib/、analysis/、docs/、evaluation/
- **保留**：ft.ps1、bootstrap.ps1、data/、lib/、tools/（核心脚本）

**预计影响**：删除 ~550K

---

## 🟢 P2：低优先级改进（优化建议）

### 4. 优化 04_shared/ 目录结构

**问题**：存在 `config/` 和 `configs/` 两个配置目录，结构混乱

**当前结构**：
```
04_shared/
├── config/           # 旧配置目录？
├── configs/          # 新配置目录？
└── utils/            # 工具目录
```

**建议操作**：
- 检查两个目录的内容和用途
- 合并到统一的 `configs/` 目录
- 更新相关引用路径

**预计影响**：优化目录结构，提升可维护性

### 5. 简化 README.md

**问题**：README.md 可能包含过时信息，不符合新的MVP架构

**建议操作**：
- 重写为快速开始指南
- 只保留核心内容：
  - 项目简介（1-2句话）
  - 快速开始（3步：安装、下载数据、运行策略）
  - 目录结构（简化版）
  - 参考文档链接
- 删除过时的架构说明、详细配置说明

**预计影响**：提升新用户上手体验

### 6. 审查 pyproject.toml 依赖

**问题**：可能存在未使用的依赖包

**建议操作**：
- 审查 `[project.dependencies]` 中的每个包
- 删除未使用的依赖（如旧架构相关的包）
- 保留核心依赖：
  - freqtrade（执行层）
  - pandas/numpy（数据处理）
  - ccxt（交易所接口）
  - jupyter（研究层）
  - ta-lib（技术指标，可选）

**预计影响**：减少依赖体积，加快安装速度

---

## 📊 改进总结

### 预计清理统计

| 优先级 | 项目数 | 预计删除 | 风险等级 |
|--------|--------|----------|----------|
| P0 | 2 | ~400K | 低 |
| P1 | 1 | ~550K | 低 |
| P2 | 3 | 优化 | 中 |
| **总计** | **6** | **~950K** | **低-中** |

### 执行顺序建议

**阶段1：清理失效代码（P0）**
1. 先处理失效策略（移动到归档或删除）
2. 再删除失效测试（整个 tests/ 目录）
3. 验证：确保没有其他文件依赖这些代码

**阶段2：清理冗余脚本（P1）**
1. 删除 scripts/ 下的冗余目录
2. 保留核心脚本（ft.ps1、bootstrap.ps1 等）
3. 验证：确保核心脚本仍可正常运行

**阶段3：优化建议（P2，可选）**
1. 优化 04_shared/ 目录结构
2. 简化 README.md
3. 审查并清理 pyproject.toml 依赖

### 风险评估

**P0 风险（低）**：
- ✅ 失效策略已无法运行，删除无影响
- ✅ 失效测试基于旧架构，删除无影响
- ⚠️ 建议先移动到归档，观察1周后再永久删除

**P1 风险（低）**：
- ✅ 冗余脚本基于旧架构，删除无影响
- ✅ 核心脚本已验证可正常运行
- ⚠️ 建议保留 scripts/archive/ 作为备份

**P2 风险（中）**：
- ⚠️ 04_shared/ 优化需要检查引用路径
- ⚠️ README.md 重写需要保留关键信息
- ⚠️ 依赖清理需要逐个验证是否使用

---

## 🔧 执行命令参考

### P0-1：移动失效策略到归档

```bash
# 创建归档目录
mkdir -p 01_freqtrade/strategies_archive/broken_strategies

# 移动失效策略
mv 01_freqtrade/strategies/OptimizedIntegrationStrategy.py 01_freqtrade/strategies_archive/broken_strategies/
mv 01_freqtrade/strategies/SmallAccountFuturesTimingExecV1.py 01_freqtrade/strategies_archive/broken_strategies/
mv 01_freqtrade/strategies/SmallAccountFuturesTrendV1.py 01_freqtrade/strategies_archive/broken_strategies/
mv 01_freqtrade/strategies/SmallAccountSpotTrendFilteredV1.py 01_freqtrade/strategies_archive/broken_strategies/
```

### P0-2：删除失效测试

```bash
# 删除整个 tests/ 目录
rm -rf tests/

# 或者先移动到归档
mkdir -p docs/archive/old_tests
mv tests/ docs/archive/old_tests/
```

### P1-3：删除冗余脚本

```bash
# 删除冗余脚本目录
rm -rf scripts/archive/
rm -rf scripts/qlib/
rm -rf scripts/analysis/
rm -rf scripts/docs/
rm -rf scripts/evaluation/

# 验证核心脚本
ls scripts/*.ps1
ls scripts/data/
ls scripts/lib/
ls scripts/tools/
```

---

## ✅ 验收标准

### P0 验收
- [ ] 4个失效策略已移动到归档或删除
- [ ] tests/ 目录已删除或移动到归档
- [ ] 运行 `./scripts/ft.ps1 list-strategies` 确认可用策略列表
- [ ] 确认没有其他文件依赖已删除的代码

### P1 验收
- [ ] scripts/ 下的冗余目录已删除
- [ ] 核心脚本（ft.ps1、bootstrap.ps1）仍可正常运行
- [ ] 运行 `./scripts/bootstrap.ps1` 验证环境初始化
- [ ] 运行 `./scripts/data/download.ps1` 验证数据下载

### P2 验收（可选）
- [ ] 04_shared/ 目录结构已优化
- [ ] README.md 已更新为快速开始指南
- [ ] pyproject.toml 依赖已清理
- [ ] 运行 `uv sync --frozen` 验证依赖安装

---

## 📝 执行建议

### 推荐方案（保守）

**选项A（推荐）**：分阶段执行，先归档后删除
1. 执行 P0-1：移动失效策略到归档
2. 执行 P0-2：移动失效测试到归档
3. 观察1周，确认无影响
4. 执行 P1-3：删除冗余脚本
5. 可选：执行 P2 优化建议

**选项B（激进）**：直接删除
1. 直接删除失效策略和测试
2. 直接删除冗余脚本
3. 立即执行 P2 优化

**选项C（最保守）**：仅执行 P0
1. 只处理失效代码（P0）
2. 暂不处理冗余脚本（P1）
3. 暂不执行优化建议（P2）

---

## 🎯 下一步行动

1. **用户确认**：选择执行方案（A/B/C）
2. **执行清理**：按照选定方案执行
3. **验证功能**：运行验收标准中的命令
4. **提交变更**：`git add -A && git commit -m "chore: cleanup broken code and redundant scripts"`
5. **开始MVP开发**：按照 [REFACTOR_SUMMARY.md](REFACTOR_SUMMARY.md) 中的3阶段计划执行

---

**报告版本**：v1.0
**完成时间**：2026-01-18
**分析方法**：Sequential Thinking（10步系统性分析）
