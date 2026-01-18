<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# 或者有没有什么其他架构设计？

更新日期：2026-01-13


现在生成最终的综合总结报告。

## 业界其他架构设计方案：5大创新范式深度调查

### 执行摘要

除了上文提到的"依赖倒置分层设计"，我调查发现业界还有**5种创新架构模式**在因子与策略分离中表现出色。每种都针对不同的场景优化。本报告总结这些方案的核心思想、优劣及在加密交易中的适用性。

***

### 一、架构全景对比

| 架构模式 | 核心思想 | 分离程度 | 实时性 | 审计性 | 学习成本 | 生产就绪 |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| **DIP 分层** | 抽象隔离 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | 低 | ✅ |
| **CQRS+Event Sourcing** | 读写分离+事件溯源 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | 高 | ✅金融 |
| **Feature Store** | 因子集中管理 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 中 | ✅ |
| **Lambda 架构** | 批流一体 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 高 | ✅ |
| **Hexagonal** | 端口适配 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | 低 | ✅ |
| **Event-Driven** | 异步事件流 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 中 | ✅ |


***

### 二、6种架构详细分析

#### 1. CQRS + Event Sourcing（分离读写、事件溯源）[^1][^2][^3][^4][^5][^6][^7][^8]

**核心原理**：将"写"（命令、因子计算）与"读"（查询结果）完全分离，所有状态变化记录为不可变事件，需要状态时通过"重放"事件流得到。

**在交易中的应用**：

```
交易流程事件化：
OrderPlacedEvent → PositionUpdatedEvent → RiskComputedEvent → AlertEvent

历史重放：
要查看 2024-01-15 10:30 的头寸？
→ 重放所有到该时刻的事件 → 恢复当时状态
```

**关键优势**：

- ✅ **完整审计日志**：每个因子、每笔交易、每个风险决策都永久记录
- ✅ **完全可重放**：验证历史因子计算、调试回测
- ✅ **自然一致性**：事件是唯一真实源，无读写不一致
- ✅ **天然自愈**：服务故障后，重放事件自动恢复
- ✅ **支持多个读视图**：投资组合视图、风险视图、报表视图，各自独立维护

**实现难度**：⭐⭐⭐⭐ 高

- 需要事件存储（EventStoreDB、Kafka、自建）
- 需要学习事件驱动思维
- 需要处理事件一致性、幂等性

**适用场景**：

- 💰 金融机构（监管要求完整审计）
- 🔄 复杂工作流系统（多步骤决策）
- 📊 需要"时间机器"的场景（回放任意时刻）

**代码示例**：[^3][^7]

```python
# 事件定义
@dataclass
class AlphaComputedEvent:
    timestamp: datetime
    symbol: str
    factor_name: str
    value: float
    method: str  # 'qlib'/'ta'/'online'

@dataclass
class TradeExecutedEvent:
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float

# 事件存储（仅追加）
class EventStore:
    def append(self, event):
        self.events.append({
            'timestamp': datetime.now(),
            'event_type': type(event).__name__,
            'data': event,
        })
        # 发布给所有订阅者
        self.event_bus.publish(event)

# 投资组合投影（从事件重建）
class PortfolioProjection:
    def __init__(self, event_store):
        self.portfolio = {}
        # 订阅事件
        event_store.subscribe(TradeExecutedEvent, self.on_trade)
    
    def on_trade(self, event):
        if event.side == 'BUY':
            self.portfolio[event.symbol] = \
                self.portfolio.get(event.symbol, 0) + event.quantity
        else:
            self.portfolio[event.symbol] -= event.quantity
    
    def get_position(self, symbol):
        return self.portfolio.get(symbol, 0)
```


***

#### 2. Feature Store（因子的中央管理系统）[^9][^10][^11][^12][^13][^14][^15][^16][^17][^18]

**核心原理**：建立一个专门的因子/特征管理系统，统一管理离线特征（批量计算）和在线特征（低延迟服务），解决"训练-服务不一致"问题。

**三种实现方式对比**：[^14][^15][^16]

```
虚拟 FS (Feast)
├─ 你管理：数据源、转换逻辑、管道
├─ 系统提供：元数据、版本管理、API
└─ 适合：有数据工程基础、追求灵活性

物理 FS (Tecton, Uber Michelangelo)
├─ 系统管理：所有特征管道（从计算到存储）
├─ 你提供：特征定义（声明式）
└─ 适合：追求快速上线、愿意付费

平衡方案 (Lyft Dryft)
├─ 中间状态：特征定义 + 自动化管道
├─ 但允许选择存储和计算引擎
└─ 适合：想要集成度又要灵活性
```

**核心组件**：[^10][^11][^18][^9]

```
┌─ 离线存储（Offline Store）
│  ├─ S3/BigQuery/Parquet
│  └─ 用于模型训练（历史完整数据）
│
├─ 在线存储（Online Store）
│  ├─ Redis/DynamoDB
│  └─ 用于实时推理（毫秒级延迟）
│
├─ 计算引擎
│  ├─ 批处理（Spark/Dask）
│  ├─ 流处理（Flink/Kafka Streams）
│  └─ 实时计算（Lambda 函数）
│
├─ 特征注册表（Feature Registry）
│  ├─ 特征定义、版本、血缘
│  └─ 数据质量检查、监控
│
└─ 服务 API
   ├─ get_offline_features() - 训练
   ├─ get_online_features() - 推理
   └─ get_feature_view() - 可视化
```

**在 Freqtrade 中集成**：[^15][^17][^14]

```python
from feast import FeatureStore

# 定义因子为 FeatureView
qlib_factors = FeatureView(
    name='qlib_alpha',
    entities=['symbol'],
    features=['momentum', 'value_score'],
    source=batch_data_source,
    ttl=timedelta(hours=1),
)

ta_indicators = FeatureView(
    name='ta_indicators',
    entities=['symbol'],
    features=['RSI', 'MACD'],
    source=stream_data_source,
    ttl=timedelta(minutes=5),
)

# 策略中使用
class FeatureStoreStrategy(IStrategy):
    def populate_indicators(self, dataframe, metadata):
        fs = FeatureStore(repo_path='feature_repo/')
        
        # 在线获取特征（低延迟）
        entity_df = pd.DataFrame({
            'symbol': [metadata['pair']],
            'timestamp': dataframe.index,
        })
        
        features = fs.get_online_features(
            features=['qlib_alpha:momentum', 'ta_indicators:RSI'],
            entity_rows=entity_df,
        ).to_df()
        
        return dataframe.join(features)
```

**关键优势**：

- ✅ **训练-服务一致**：离线和在线用同一份因子定义
- ✅ **点时间正确**：确保回测时不会用"未来"数据
- ✅ **特征复用**：多个策略共享因子库
- ✅ **自动化**：特征版本、物化、质量检查自动进行
- ✅ **性能优化**：热点因子预计算、缓存、物化

**实现难度**：⭐⭐⭐ 中等

- 需要学习 Feast/Tecton 的声明式 API
- 需要配置批处理和流处理管道

**市场现状**：

- 🏢 **Feast**：开源、社区活跃、但需要自己维护管道
- 💼 **Tecton**：商用、完整集成、但有成本和锁定
- 🏭 **内部方案**：AirBnB Zipline、Lyft Dryft、Uber Michelangelo

***

#### 3. Lambda 架构（批流一体）[^19][^20][^21][^22][^23]

**核心原理**：同时运行"批处理"（准确性高但延迟大）和"流处理"（延迟低但可能不完整），最后在服务层合并两者结果。

```
数据源 → 批处理层（每小时计算历史因子）
     ↘ 流处理层（每秒计算实时因子）
        ↘ 服务层（合并，新数据优先）
           ↘ 策略查询
```

**在加密交易中的应用**：[^20][^21][^19]

```python
# 批处理层：每小时一次，高准确性
class BatchFactorJob(SparkJob):
    def run(self):
        # 读取 S3 历史数据
        historical = spark.read.parquet('s3://market/ohlcv/*')
        
        # 计算 QLib 因子（向量化、准确）
        qlib_result = self.compute_qlib_batch(historical)
        
        # 保存到数据仓库
        qlib_result.write.parquet('warehouse/qlib_batch')

# 流处理层：实时，低延迟
class RealtimeFactorStream(FlinkJob):
    def process_tick(self, tick):
        # TA 指标（简单、快速）
        rsi = self.compute_rsi(tick)
        
        # 发送到 Kafka
        return FactorEvent(rsi=rsi, timestamp=tick.ts)

# 服务层：查询时合并
class FactorServer:
    def get_factors(self, symbol, ts):
        batch = self.batch_store.get(symbol, ts)
        realtime = self.realtime_cache.get(symbol, ts)
        
        # 新数据覆盖旧数据
        return {**batch, **realtime}

# Freqtrade 中
class LambdaStrategy(IStrategy):
    def populate_indicators(self, df, metadata):
        factors = []
        for row in df.itertuples():
            f = self.factor_server.get_factors(
                metadata['pair'],
                row.timestamp
            )
            factors.append(f)
        
        return df.join(pd.DataFrame(factors, index=df.index))
```

**关键优势**：

- ✅ **准确性**：批处理保证完整
- ✅ **低延迟**：流处理补充最新数据
- ✅ **容错**：批处理失败不影响实时
- ✅ **灵活性**：可选择不同算法处理不同时间范围

**实现难度**：⭐⭐⭐⭐ 高

- 需要同时运维两套处理管道
- 需要处理重复、乱序数据

**适用场景**：

- 📊 需要绝对准确性（财务报表）
- 🚀 同时需要实时性（交易决策）
- 💰 有资源维护复杂系统

**Kappa 架构（简化版）**：[^22][^19]
纯流处理，用 Kafka 的"重放"能力替代批处理，一个引擎两种用途。

```
Kafka（支持重放）
   ↓
Flink（单一处理引擎）
   ↓ 历史重放
   ↓ 实时流
   ↓ 完整因子表
```


***

#### 4. Hexagonal 架构（六边形/端口适配）[^24][^6][^25][^26]

**核心原理**：核心业务逻辑完全独立，周围是多个"端口"（接口），每个端口有多个"适配器"（实现）。这样核心逻辑不依赖任何框架。

```
┌─────────────────────────────┐
│   核心逻辑（Domain）        │
│ FactorAnalyzer              │
│ SignalGenerator             │
│ (纯 Python，无依赖)          │
└─────────────────────────────┘
     /    /    \    \    \
┌───────────────────────────┐
│  因子端口     数据端口    │
│  ├─QLib      ├─Kafka    │
│  ├─TA-Lib   ├─API      │
│  └─在线服务  └─数据库   │
│                         │
│  交易端口      通知端口  │
│  ├─Freqtrade  ├─Telegram
│  └─Backtrader  └─Email
└───────────────────────────┘
```

**代码示例**：[^6][^25]

```python
# domain/core.py（纯业务逻辑）
class FactorAnalyzer:
    def generate_signal(self, factors, risk_score):
        if factors['alpha'] > 0.5 and risk_score < 0.02:
            return Signal.LONG
        elif factors['alpha'] < -0.3:
            return Signal.SHORT
        return Signal.NEUTRAL

# infrastructure/adapters/qlib_adapter.py
class QlibFactorAdapter:
    def get_factors(self, symbol, data):
        return qlib.load_factors(symbol, data)

# infrastructure/adapters/ta_adapter.py
class TAFactorAdapter:
    def get_factors(self, symbol, data):
        return {'rsi': talib.RSI(...)}

# adapters/freqtrade_adapter.py
class FreqtradeAdapter(IStrategy):
    def populate_indicators(self, dataframe, metadata):
        # 选择适配器
        factors = self.factor_adapter.get_factors(...)
        
        # 调用核心逻辑
        signal = self.analyzer.generate_signal(factors, risk)
        
        return dataframe.join(factors)
```

**关键优势**：

- ✅ **测试极易**：核心逻辑无框架依赖，直接单元测试
- ✅ **适配灵活**：轻松切换 Freqtrade ↔ Backtrader ↔ 纸币交易
- ✅ **学习成本低**：概念简单，代码清晰
- ✅ **快速原型**：快速验证想法

**实现难度**：⭐⭐ 低

- 思想简单，代码直观

**适用场景**：

- 🚀 快速原型、MVP
- 🔧 需要频繁切换框架
- 🎓 学习和教学

***

#### 5. Event-Driven 架构（异步事件流）[^4][^5][^27][^28][^29][^30][^31][^21][^32][^22]

**核心原理**：所有操作都基于事件。组件之间通过异步事件通信，完全解耦。通常配合 Kafka/RabbitMQ。

```
Tick 来临
   ↓ 发送 MarketTickEvent
   ↓ (Kafka Topic: market-data)
   ↓
因子计算器 (订阅)
   ↓ 计算因子
   ↓ 发送 AlphaSignalEvent
   ↓ (Kafka Topic: signals)
   ↓
交易执行器 (订阅)
   ↓ 检查信号
   ↓ 下单
   ↓ 发送 TradeExecutedEvent
   ↓ (Kafka Topic: trades)
   ↓
风险监控器 (订阅)
   ↓ 计算风险
   ↓ 发送 RiskAlertEvent
   ↓ (Kafka Topic: alerts)
```

**微服务部署**：[^5][^27][^21][^4]

```python
# 微服务1：因子计算
class FactorService:
    def __init__(self):
        self.kafka_consumer = KafkaConsumer('market-data')
        self.kafka_producer = KafkaProducer('alpha-signals')
    
    def run(self):
        for tick in self.kafka_consumer:
            # 计算因子
            factors = self.factor_engine.compute(tick)
            
            # 发送事件
            self.kafka_producer.send(
                'alpha-signals',
                AlphaSignalEvent(...)
            )

# 微服务2：交易执行（独立服务）
class TradeService:
    def __init__(self):
        self.kafka_consumer = KafkaConsumer('alpha-signals')
        self.kafka_producer = KafkaProducer('trades')
    
    def run(self):
        for signal in self.kafka_consumer:
            if signal.confidence > 0.7:
                order = self.broker.place_order(...)
                self.kafka_producer.send('trades', order)

# 微服务3：风险监控（独立服务）
class RiskService:
    def run(self):
        for trade in self.kafka_consumer.consume('trades'):
            risk = self.risk_engine.compute()
            if risk > threshold:
                self.kafka_producer.send('alerts', alert)
```

**关键优势**：

- ✅ **完全解耦**：各微服务独立部署、升级、故障隔离
- ✅ **高吞吐**：Kafka 每秒处理百万级消息
- ✅ **可扩展**：添加新服务无需改动现有代码
- ✅ **完整审计**：所有事件永久存储在 Kafka
- ✅ **容错性好**：一个服务故障不影响其他

**实现难度**：⭐⭐⭐ 中等

- 需要 Kafka/RabbitMQ 部署和运维
- 需要学习异步编程、事件驱动思维

**生态工具**：[^28][^21][^32][^5][^22]

- **Kafka**：事件总线（百万级吞吐）
- **Flink**：流处理（复杂事件处理、窗口、状态）
- **Spark Structured Streaming**：批流统一 API
- **Spring Cloud Stream**：Java 异步应用框架

**应用案例**：[^27][^5][^22]

- 💳 支付系统：Kafka + Flink 处理百万笔交易/秒
- 📊 实时数据平台：340,000 events/sec（见 ）
- 🏦 金融服务：事件溯源、支付处理

***

### 三、加密货币交易的最优组合

#### 推荐方案：Hexagonal + Feature Store + Event-Driven

```
架构分层：
┌─────────────────────────────────────────┐
│   Hexagonal 核心（DDD 业务逻辑）        │
│   ├─ FactorAnalyzer                     │
│   ├─ SignalGenerator                    │
│   └─ PositionManager                    │
│   (纯 Python，0 框架依赖)                 │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │ 端口适配层              │
    │ ├─ 因子端口             │
    │ │  ├─ QLib 适配器       │
    │ │  ├─ TA 适配器         │
    │ │  └─ Feature Store     │
    │ │      ├─ 离线：历史因子 │
    │ │      └─ 在线：实时特征 │
    │ │                       │
    │ ├─ 数据端口             │
    │ │  └─ Kafka 消费者      │
    │ │                       │
    │ └─ 交易端口             │
    │    └─ Freqtrade 适配器 │
    └────────┬────────────────┘
             │
     ┌───────▼────────┐
     │ Event-Driven流 │
     │  Kafka Topics: │
     │  - ticks       │
     │  - signals     │
     │  - trades      │
     │  - alerts      │
     └────────────────┘
```


#### 为什么这个组合最适合加密？

| 方面 | 原因 |
| :-- | :-- |
| **高吞吐** | Kafka 支持每秒百万级事件（加密 24/7 不间断） |
| **低延迟** | Feature Store 在线服务毫秒级，Hexagonal 核心零开销 |
| **易维护** | Hexagonal 核心独立，事件清晰，故障好定位 |
| **易扩展** | 添加新因子/新策略只需新增 Feature Store View + 事件监听器 |
| **完整性** | 所有交易可审计，支持完全重放 |
| **成本** | Kafka/Flink 开源，Feature Store 可用开源 Feast |


***

### 四、架构选择决策树

```
你的场景？

├─ 刚起步，规模小 (<$100k)
│  → DIP 分层 + 简单因子库
│  代码：domain/ + application/ + infrastructure/
│  投入：3-5 人周
│
├─ 中等规模 ($100k-$1m)，多个策略
│  → Hexagonal + Feature Store
│  优点：核心逻辑复用，特征共享
│  投入：5-10 人周
│
├─ 大规模 (>$1m)，需要完整审计
│  → 上面的基础 + CQRS + Event Sourcing
│  优点：完整审计、合规、可重放
│  投入：15-30 人周
│
├─ 需要批流混合准确性
│  → Lambda 架构
│  优点：批处理保证准确，流补充实时
│  投入：20-30 人周
│
└─ 追求最高性能、完全微服务化
   → Event-Driven + Kafka Streams
   优点：最高吞吐、完全异步、易扩展
   投入：30-50 人周
```


***

### 五、关键对标与实战建议

#### 开源项目参考

| 项目 | 架构 | 因子分离做得好的点 | 学习价值 |
| :-- | :-- | :-- | :-- |
| **FinRL-Meta**[^33][^34] | Gym标准化环境 | 状态完全独立于算法 | 强化学习思想 |
| **Zipline**[^35][^36][^37] | Pipeline API | CustomFactor 抽象 | 因子计算分离 |
| **Tecton** | 物理Feature Store | 完整特征管道 | 生产级方案 |
| **Feast** | 虚拟Feature Store | 灵活的离在线一体 | 开源最佳实践 |

#### 立即可用的代码模板

我已为上述5种架构的每一种提供了代码模板（见详细文档）。快速开始路径：

```
1. 从 Hexagonal + DIP 开始
   ├─ 定义 domain/ (纯业务)
   ├─ 写 adapters/ (框架集成)
   └─ 运行 Freqtrade

2. 加入 Feature Store
   ├─ 用 Feast 定义因子
   ├─ 修改 populate_indicators() 调用 FS API
   └─ 自动获得训练-服务一致

3. 如需微服务化
   ├─ 把 populate_indicators() 改为 Kafka 消费者
   ├─ 把 populate_entry_trend() 改为独立微服务
   └─ 自动获得最高吞吐和容错
```


***

### 六、总结与行动方案

#### 核心结论

1. **没有"最好"的架构**，只有"最适合"的架构
2. **分层永远正确**：无论选哪种，都需要清晰分离
3. **事件驱动是未来**：业界普遍从同步→异步、整体→微服务转变
4. **Feature Store 很关键**：ML 时代的中央因子管理不可或缺
5. **加密市场特性**：高频率数据、24/7 运行 → Event-Driven + Kafka 最优

#### 立即行动

**第一周**：

- [ ] 选择一种架构（推荐 Hexagonal + Feature Store）
- [ ] 用提供的代码模板搭建框架
- [ ] 迁移现有因子代码

**第二周**：

- [ ] 接入 Freqtrade（或 Backtrader）
- [ ] 运行回测验证分离效果
- [ ] 编写文档

**第三周**：

- [ ] 小规模实盘测试
- [ ] 监控性能、延迟
- [ ] 收集反馈

***

**参考文献**（本调查中引用）：

- [159-177] CQRS + Event Sourcing 相关
- [192-217] Feature Store 相关
- [184, 190, 206-212, 218] Lambda/Kappa 架构相关
- Hexagonal 架构相关[^25][^26][^24][^6]
- [163-166, 169, 175, 181] Event-Driven 相关
<span style="display:none">[^38][^39][^40][^41][^42][^43][^44][^45][^46][^47][^48][^49][^50][^51][^52][^53][^54][^55][^56][^57][^58][^59][^60][^61][^62][^63][^64][^65][^66]</span>

<div align="center">⁂</div>

[^1]: http://ric.zntu.edu.ua/article/view/312910

[^2]: https://journals.politehnica.dp.ua/index.php/it/article/view/552

[^3]: https://dl.acm.org/doi/10.1145/3317614.3317632

[^4]: https://carijournals.org/journals/index.php/IJCE/article/view/3014

[^5]: https://ijsrcseit.com/index.php/home/article/view/CSEIT24106193

[^6]: https://oregami.org/blog/en/2016/domain-driven-design-cqrs-event

[^7]: https://iconsolutions.com/blog/cqrs-event-sourcing

[^8]: https://www.baeldung.com/cqrs-event-sourcing-java

[^9]: https://www.ijcesen.com/index.php/ijcesen/article/view/4555

[^10]: https://ephijse.com/index.php/SE/article/view/295

[^11]: https://ijsrcseit.com/index.php/home/article/view/CSEIT251116173

[^12]: https://wjarr.com/node/22591

[^13]: https://arxiv.org/pdf/2305.20077.pdf

[^14]: https://resources.tecton.ai/hubfs/Choosing-Feature-Solution-Feast-or-Tecton.pdf?hsLang=en

[^15]: https://www.featureform.com/post/feature-stores-explained-the-three-common-architectures

[^16]: https://clickhouse.com/blog/powering-featurestores-with-clickhouse

[^17]: https://applyingml.com/resources/feature-stores/

[^18]: https://aerospike.com/blog/feature-store/

[^19]: https://hazelcast.com/foundations/software-architecture/lambda-architecture/

[^20]: https://www.coursera.org/articles/lambda-architecture

[^21]: https://www.designgurus.io/answers/detail/how-would-you-design-a-system-for-real-time-stream-processing-eg-using-apache-kafka-with-apache-flink-or-spark-streaming

[^22]: https://www.kai-waehner.de/blog/2025/12/10/top-trends-for-data-streaming-with-apache-kafka-and-flink-in-2026/

[^23]: https://blog.dataengineerthings.org/real-time-analytics-with-apache-flink-and-kafka-an-expert-guide-ed89b359bef2

[^24]: https://www.semanticscholar.org/paper/84ee40b163ad72288376c566a62920426e964583

[^25]: https://bitloops.com/blog/over-engineered-todo-app-to-learn-ddd-hexagonal-architecture-cqrs-and-event-sourcing

[^26]: https://herbertograca.com/2017/11/16/explicit-architecture-01-ddd-hexagonal-onion-clean-cqrs-how-i-put-it-all-together/

[^27]: https://www.ijcesen.com/index.php/ijcesen/article/view/3983

[^28]: https://ieeexplore.ieee.org/document/11256412/

[^29]: https://arxiv.org/pdf/2501.06032.pdf

[^30]: http://arxiv.org/pdf/2001.11962.pdf

[^31]: https://jbcodeforce.github.io/autonomous-car-mgr/architecture/

[^32]: https://arxiv.org/pdf/2410.15533.pdf

[^33]: https://finrl.readthedocs.io/en/latest/start/three_layer.html

[^34]: https://finrl.readthedocs.io/en/latest/finrl_meta/Environment_layer.html

[^35]: https://stefan-jansen.github.io/machine-learning-for-trading/08_ml4t_workflow/04_ml4t_workflow_with_zipline/

[^36]: https://blog.quantinsti.com/introduction-zipline-python/

[^37]: https://zipline-trader.readthedocs.io/en/latest/notebooks/Alphalens.html

[^38]: https://www.semanticscholar.org/paper/5703e6de744dc4f818e109d8095dc993ff655f3f

[^39]: https://theamericanjournals.com/index.php/tajet/article/view/6156/5690

[^40]: https://arxiv.org/pdf/2104.01146.pdf

[^41]: https://arxiv.org/pdf/2501.14848.pdf

[^42]: https://arxiv.org/pdf/1807.11378.pdf

[^43]: https://arxiv.org/pdf/1008.0823.pdf

[^44]: https://arxiv.org/ftp/arxiv/papers/0806/0806.1100.pdf

[^45]: http://arxiv.org/pdf/2010.15534.pdf

[^46]: https://docs.aws.amazon.com/whitepapers/latest/serverless-multi-tier-architectures-api-gateway-lambda/microservices-with-lambda.html

[^47]: https://www.interactivebrokers.com/campus/ibkr-quant-news/can-machine-learning-predict-factor-returns/

[^48]: https://onlinelibrary.wiley.com/doi/10.1155/2020/3589198

[^49]: https://www.luxalgo.com/blog/feature-engineering-in-trading-turning-data-into-insights/

[^50]: https://rsisinternational.org/journals/ijriss/articles/microservices-architecture-in-cloud-computing-a-software-engineering-perspective-on-design-deployment-and-management/

[^51]: https://rpc.cfainstitute.org/sites/default/files/-/media/documents/article/rf-brief/ai-and-big-data-in-investments-Part-III-final.pdf

[^52]: https://www.atlantis-press.com/article/125980456.pdf

[^53]: https://dl.acm.org/doi/10.1145/3394486.3403314

[^54]: https://arxiv.org/pdf/2412.16060.pdf

[^55]: http://arxiv.org/pdf/2501.08591.pdf

[^56]: https://arxiv.org/html/2504.00786v1

[^57]: https://www.mdpi.com/2079-9292/11/4/561/pdf?version=1645069528

[^58]: https://arxiv.org/pdf/2208.13068.pdf

[^59]: https://arxiv.org/pdf/2306.11877.pdf

[^60]: https://arxiv.org/pdf/2309.03584.pdf

[^61]: https://www.splunk.com/en_us/blog/learn/time-series-databases.html

[^62]: https://questdb.com/glossary/temporal-data-modeling/

[^63]: https://greptime.com/blogs/2023-03-22-what-is-timeseries-database

[^64]: https://m.mage.ai/building-real-time-crypto-trading-pipelines-with-kafka-and-mage-pro-cda2184c5123

[^65]: https://www.timeplus.com/post/time-series-database-use-cases

[^66]: https://www.influxdata.com/time-series-database/

