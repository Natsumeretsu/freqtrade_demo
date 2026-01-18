# 新功能说明文档

本文档介绍最近添加的新功能和改进。

**更新日期**: 2026-01-17

---

## 1. 代码质量提升

### 1.1 类型注解工具

**位置**: `tools/type_annotation_tool.py`

**功能**: 分析 Python 代码的类型注解覆盖率

**使用方法**:
```python
from type_annotation_tool import analyze_directory
results = analyze_directory(Path('03_integration/trading_system'))
```

**输出**: 函数和类的类型注解覆盖率统计

### 1.2 性能分析工具

**位置**: `tools/performance_profiler.py`

**功能**: 装饰器式性能分析，追踪函数执行时间

**使用方法**:
```python
from performance_profiler import PerformanceProfiler

profiler = PerformanceProfiler()

@profiler.profile
def my_function():
    # 你的代码
    pass
```

---

## 2. 监控与可观测性

### 2.1 性能监控

**位置**: `03_integration/trading_system/infrastructure/monitoring/performance_monitor.py`

**功能**: 实时监控系统 CPU、内存、磁盘 I/O

**使用方法**:
```python
from trading_system.infrastructure.monitoring import PerformanceMonitor

monitor = PerformanceMonitor(interval=1.0)
monitor.start()
# ... 运行你的代码
report = monitor.get_report()
monitor.stop()
```

### 2.2 结构化日志

**位置**: `03_integration/trading_system/infrastructure/monitoring/structured_logger.py`

**功能**: JSON 格式的结构化日志记录

**使用方法**:
```python
from trading_system.infrastructure.monitoring import StructuredLogger

logger = StructuredLogger('my_module')
logger.info('操作完成', user_id=123, action='login')
```

---

## 3. 高级功能

### 3.1 自适应缓存

**位置**: `03_integration/trading_system/infrastructure/cache/adaptive_cache.py`

**功能**: 基于访问频率和时间衰减的智能缓存

**特性**:
- LRU 驱逐策略
- 访问频率追踪
- 时间衰减评分

### 3.2 智能降级

**位置**: `03_integration/trading_system/infrastructure/degradation/`

**功能**: 服务熔断和自动降级

**组件**:
- `CircuitBreaker`: 熔断器（三态：CLOSED/OPEN/HALF_OPEN）
- `DegradationManager`: 降级策略管理

**使用方法**:
```python
from trading_system.infrastructure.degradation import DegradationManager

manager = DegradationManager()
manager.register_strategy('my_service', primary_func, fallback_func)
result = manager.execute('my_service')
```

### 3.3 增量回测

**位置**: `03_integration/trading_system/backtest/incremental_backtest.py`

**功能**: 支持增量回测，避免重复计算历史数据

**特性**:
- 检查点机制
- 配置哈希验证
- 自动结果合并

**使用方法**:
```python
from trading_system.backtest import IncrementalBacktest

backtest = IncrementalBacktest()
result = backtest.run('strategy_name', data, config, backtest_func)
```

---

## 4. 用户体验优化

### 4.1 CLI 工具

**位置**: `tools/cli.py`

**功能**: 命令行工具集

**命令**:
- `check-types`: 检查类型注解覆盖率
- `monitor`: 启动性能监控
- `benchmark`: 运行性能基准测试

**使用方法**:
```bash
python tools/cli.py check-types
python tools/cli.py monitor
python tools/cli.py benchmark
```

### 4.2 配置向导

**位置**: `tools/config_wizard.py`

**功能**: 交互式配置生成工具

**使用方法**:
```bash
python tools/config_wizard.py
```

### 4.3 报告生成器

**位置**: `tools/report_generator.py`

**功能**: 生成 Markdown 格式的性能报告

---

## 5. 系统集成

### 5.1 系统管理器

**位置**: `03_integration/trading_system/system_manager.py`

**功能**: 统一管理所有新功能的集成接口

**使用方法**:
```python
from trading_system import SystemManager

system = SystemManager()
system.start()
# ... 使用系统功能
system.stop()
```

---

## 6. 测试覆盖

所有新功能都包含完整的单元测试和集成测试：

- **单元测试**: `tests/infrastructure/`, `tests/backtest/`
- **集成测试**: `tests/integration/`
- **性能测试**: `tests/performance_benchmark.py`

运行测试：
```bash
python -m pytest tests/
```
