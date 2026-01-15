# 短期时序预测改进计划

创建日期：2026-01-15
目标：以短期时序预测获取超额盈利为目标，系统性改进项目质量

---

## 一、问题总览

| 优先级 | 编号 | 问题 | 影响 | 工作量 | 状态 |
|--------|------|------|------|--------|------|
| **P0** | P0-1 | 前向偏差（分位计算需 shift(1)） | 高 | 小 | ✅ 已完成 |
| **P0** | P0-2 | 配置验证缺失（需 pydantic schema） | 中 | 小 | ✅ 已完成 |
| **P0** | P0-3 | 数据质量检查模块缺失 | 高 | 中 | ✅ 已完成 |
| **P0** | P0-4 | 样本外验证（OOS）自动化缺失 | 高 | 中 | ✅ 已完成 |
| **P1** | P1-1 | 实时漂移监控缺失 | 中 | 中 | 待开始 |
| **P1** | P1-2 | 全局容器线程不安全 | 中 | 小 | ✅ 已完成 |
| **P1** | P1-3 | 端到端集成测试缺失 | 中 | 大 | 待开始 |
| **P2** | P2-1 | Koopman 参数硬编码 | 低 | 中 | 待开始 |
| **P2** | P2-2 | 参数敏感性分析工具缺失 | 中 | 中 | 待开始 |
| **P2** | P2-3 | 成本敏感性分析工具缺失 | 中 | 中 | 待开始 |

---

## 二、P0 级改进（关键）

### P0-1: 修复前向偏差

**问题描述**：
分位阈值计算使用当前数据，导致回测时 t 时刻的阈值包含了 t 时刻的数据，造成数据泄露。

**影响文件**：
- `scripts/qlib/timing_audit.py`
- `03_integration/trading_system/application/timing_audit.py`

**修复方案**：
```python
# 修复前
q_high = xx.rolling(lookback_bars).quantile(high_q)
q_low = xx.rolling(lookback_bars).quantile(low_q)

# 修复后
q_high = xx.rolling(lookback_bars).quantile(high_q).shift(1)
q_low = xx.rolling(lookback_bars).quantile(low_q).shift(1)
```

**验收标准**：
- [ ] 所有分位计算函数添加 shift(1)
- [ ] 单元测试验证无前向偏差
- [ ] 回测收益对比（预期会下降，但更真实）

---

### P0-2: 添加配置验证

**问题描述**：
YAML 配置错误时默默降级到 ema_20，策略行为异常但无感知。

**影响文件**：
- `03_integration/trading_system/infrastructure/config_loader.py`
- 新增：`03_integration/trading_system/domain/timing_policy_schema.py`

**修复方案**：
使用 pydantic 定义严格的配置 schema，配置错误时直接报错而非降级。

**验收标准**：
- [ ] 定义 TimingPolicySchema（pydantic model）
- [ ] 配置加载时强制验证
- [ ] 错误配置抛出明确异常
- [ ] 单元测试覆盖各种错误配置场景

---

### P0-3: 添加数据质量检查模块

**问题描述**：
数据转换流程无质量验证，缺失值/异常值/重复数据可能导致因子计算错误。

**新增文件**：
- `03_integration/trading_system/infrastructure/data_quality.py`

**功能需求**：
1. 缺失值检测（缺失率阈值告警）
2. 异常值检测（Z-score > 5）
3. 重复时间戳检测
4. 数据连续性检测（时间间隔异常）

**验收标准**：
- [ ] 实现 DataQualityChecker 类
- [ ] 在 timing_audit 前强制执行检查
- [ ] 输出数据质量报告
- [ ] 单元测试覆盖各种数据问题

---

### P0-4: 添加样本外验证自动化

**问题描述**：
仅用 30/60 天滚动稳定性筛选，缺少 OOS 验证，因子过拟合风险高。

**新增文件**：
- `scripts/qlib/validate_oos.py`

**功能需求**：
1. 时间序列交叉验证（Purged K-Fold）
2. 训练/验证/测试集自动分割
3. 不同市场制度下分别评估
4. 参数稳定性评估

**验收标准**：
- [ ] 实现 OOS 验证脚本
- [ ] 支持命令行参数配置
- [ ] 输出 OOS 报告（IC 衰减、收益衰减）
- [ ] 集成到因子筛选流程

---

## 三、P1 级改进（重要）

### P1-1: 添加实时漂移监控

**问题描述**：
auto_risk_replay.py 是离线回放，漂移检测到禁新开之间有窗口期。

**新增文件**：
- `scripts/qlib/monitor_drift_realtime.py`

**功能需求**：
1. 在线特征分布监控
2. 实时告警机制
3. 自动降风险闭环

---

### P1-2: 修复容器线程安全

**问题描述**：
全局单例容器无锁保护，多线程环境下可能竞态条件。

**影响文件**：
- `03_integration/trading_system/infrastructure/container.py`

**修复方案**：
```python
import threading
_LOCK = threading.Lock()

def get_container() -> DependencyContainer:
    global _CONTAINER
    if _CONTAINER is None:
        with _LOCK:
            if _CONTAINER is None:
                _CONTAINER = DependencyContainer()
    return _CONTAINER
```

---

### P1-3: 添加端到端集成测试

**问题描述**：
69 个单元测试，但无完整链路验证。

**新增文件**：
- `tests/test_e2e_research_to_backtest.py`

**功能需求**：
覆盖完整链路：数据 → 因子 → 策略 → 回测

---

## 四、P2 级改进（优化）

### P2-1: Koopman 参数化

**问题描述**：
Koopman-Lite 参数硬编码，不同币种/市场可能需要不同参数。

**修复方案**：
参数化到配置文件，支持 pair 级别覆盖。

---

### P2-2: 参数敏感性分析工具

**新增文件**：
- `scripts/analysis/sensitivity_analysis.py`

**功能需求**：
评估阈值/窗口/权重变化对收益的影响，识别"悬崖效应"。

---

### P2-3: 成本敏感性分析工具

**新增文件**：
- `scripts/analysis/cost_sensitivity.py`

**功能需求**：
评估手续费/滑点变化对收益的影响。

---

## 五、执行计划

按优先级顺序执行：

1. **第一阶段（P0）**：修复核心预测有效性问题
   - P0-1 → P0-2 → P0-3 → P0-4

2. **第二阶段（P1）**：增强工程健壮性
   - P1-2 → P1-1 → P1-3

3. **第三阶段（P2）**：优化与扩展
   - P2-1 → P2-2 → P2-3

---

## 六、变更日志

| 日期 | 编号 | 变更内容 | 提交 |
|------|------|----------|------|
| 2026-01-15 | - | 创建改进计划 | - |
