# 因果特征识别系统深度指南（用户原文归档）

更新日期：2026-01-14

说明：

- 本文件用于**原样归档**用户提供的“因果特征识别系统”文本与外部链接清单，便于跨设备同步与后续逐条核验。
- 外部链接的可用性与相关性**未逐条验证**；如需纳入本仓库可追溯体系，建议逐条登记到 `docs/knowledge/source_registry.md` 并分配 `S-xxx`。

---

## 原文（原样）

## 因果特征识别系统深度指南：理论、实现与加密货币应用

***

## 核心思想：为什么相关性不等于因果

### 传统方法的陷阱[1]

传统量化交易依赖**相关性**：

```
观察：波动率↑ 与 收益↑ 相关 → 买入波动率高的资产
问题：真正导致收益的不是波动率本身，而是背后的"流动性枯竭"
结果：极端行情下，流动性恢复，波动率下降，但收益反而亏损
```

因果方法：

- 寻找X→Y的直接通路，而非同时出现
- 因果因子在市场制度转换中保持稳定
- 20年历史数据中因果因子OOS衰减仅3%，相关因子衰减50%+[2]

***

## 第一部分：理论基础 - Do-Calculus与三大偏差

### 1. 混淆偏差（Confounder Bias）[1]

```
DAG结构：
Z ← M (市场恐慌)
↙      ↘
VIX      股票收益
↓         ↑
观察：VIX↑ → 收益↓

错误推断：VIX导致收益下跌
正确推断：恐慌Z同时导致VIX↑和收益↓
解决：控制Z（恐慌指标）后，VIX系数变为0
```

### 2. 碰撞偏差（Collider Bias） - 标准回归的死穴[1]

```
传统二阶段Fama-French回归：
收益 ~ 市场因子 + 规模因子 + 价值因子

碰撞结构（隐含）：
       市场因子
        ↓    ↑
       /      \
    收益 ← 价值因子

同时控制两个因子（标准做法）→ 引入虚假相关
结果：市场因子的系数被夸大，在新样本上失效
```

### 3. Do-Calculus（Pearl框架）[3]

后门标准：估计X→Y的因果效应，需要：

1. 找出所有从X到Y的后门路径（X←...←Y）
2. 识别混淆变量Z（位于路径上）
3. 控制Z，阻断后门路径
4. **不能控制碰撞变量**（∧形）

```
E[Y | do(X=x)] = ∑_z E[Y|X=x,Z=z]·P(Z=z)
     ↑真实因果效应      ↑回归只能得到条件概率
```

***

## 第二部分：落地方案 - ADIA 7步协议（2025年最新）

### 2.1 步骤概览[4]

| 步骤 | 输入 | 操作 | 输出 | 工具 |
|-----|------|------|------|------|
| 1 | 候选特征100+个 | 机器学习+领域过滤 | 50-100个特征 | SHAP, 互信息 |
| 2 | 时间序列数据 | 因果发现算法 | DAG（父节点集） | VarLiNGAM |
| 3 | DAG + 目标 | Do-calculus | 最小调整集S | DoWhy库 |
| 4 | X,Y,S | 双机器学习 | 因果系数β | CausalML |
| 5 | β + 投资规则 | 投资组合优化 | 权重w | CVX |
| 6 | 历史数据 | 蒙特卡洛模拟 | 收益分布 | 参数扰动 |
| 7 | 多个假设 | FDR/Bonferroni | 调整p值 | 统计检验 |

### 2.2 加密货币的实际案例：DBN自动因果发现[5]

数据：6种主流币 × 4年日数据 × 23个特征

自动学习结果：

```
Bitcoin (最优特征组合: OHLCV + 技术指标)
├─ 根本驱动力: OBV (On-Balance Volume)
├─ 中介: 高点-低点幅度
└─ 预测精度: 72.2% (vs LSTM 45%)

Ethereum (最优: 仅OHLCV)
├─ 根本驱动: 成交量
├─ 次级: RSI
└─ 精度: 73.9%

Binance Coin (最优: OHLCV + 技术指标)
├─ 根本: OBV
├─ 传导: NATR (平均真实波幅)
└─ 精度: 73.6%

关键洞察：
• 添加所有特征反而降低性能（过度拟合）
• 不同币种的因果DAG完全不同
• 技术指标通常强于社交或宏观因子
```

精度对比（所有币平均）：

```
DBN (因果发现): 70.8%  ✓
ARIMA: 55.3%
LSTM: 45.5%
随机森林: 51.5%
```

***

## 第三部分：加密货币市场的因果网络

### 3.1 市场级传染DAG[6][7]

```
Federal Reserve 政策
         ↓ (Granger因果, 1周滞后) [185]
    市场风险情绪 (VIX)
         ↓
    Bitcoin价格
    /    |    \
   /     |     \
ETH   DeFi   Altcoin (69%方差由BTC解释) [185]
```

实证发现：

- Fed→BTC: 单向因果 ✓ (有统计显著性)
- BTC→ETH: 强单向因果 ✓
- BTC→DeFi: 仅在熊市中因果 ⚠️（制度依赖）
- 社交→价格: 非线性因果（价格领先情绪1-2小时）[8]

### 3.2 特有的加密因果因素[9][5]

```
强因子（根本因素）[192]
├─ OBV (On-Balance Volume) ★★★★★
│   └─ 为什么：链上交易量的累积动量，反映真实参与度
├─ 交易所流出量 ★★★★
│   └─ 为什么：鲸鱼提币=看涨信号
└─ MVRV比率 ★★★★
    └─ 为什么：已实现盈亏，极值预示反转

制度相关（时变因果）[202][203]
├─ 熊市中：BTC→Altcoin强化（跟风下跌）
├─ 牛市中：DeFi独立（投资者选择性配置）
└─ 监管叙事：仅"投资"叙事有反向因果 [203]

弱/虚假（应排除）[192]
├─ 推特提及量：与价格相关但不因果
├─ 技术指标的"金叉"：后验规律，非前瞻
└─ 跨市场相关性：通常因共同驱动力，非直接因果
```

***

## 第四部分：实战系统架构

### 4.1 产品级流程设计

```
每月一次（因果学习）
├─ 收集500天数据
├─ 特征工程 (60+维)
├─ VarLiNGAM学习 DAG (2-6小时计算)
└─ 更新β系数表

每日一次（交易推断）
├─ 输入：昨天的OBV、Fed利率、社交情绪等
├─ 推理：E[Price_t+1 | do(factors=昨天值)]
├─ 信号：α = Σ β_i × Factor_i
└─ 执行：若α > 阈值 → 买入；< 0 → 卖空

风险管理
├─ 硬过滤：流动性不足 → 排除
├─ 软过滤：信号强弱 → 动态杠杆
└─ 监控：实时对比预测 vs 实际
```

### 4.2 核心算法对比

| 算法 | 优势 | 劣势 | Crypto适合度 |
|-----|------|------|-----------|
| VarLiNGAM | 快（500币30min） | 假设线性 | ★★★★★ 推荐 |
| 动态贝叶斯网络 | 自动离散化, 可解释 | 需要足量样本 | ★★★★ |
| PC/tsFCI | 处理隐变量 | 超慢（时间指数） | ★★ 仅小样本 |
| TiMINo | 非线性+时变 | 计算复杂 | ★★★ 后续升级 |

推荐：先用VarLiNGAM，后升级TiMINo处理极端行情。

***

## 第五部分：失败模式与应对

| 风险 | 症状 | 根本原因 | 解决方案 |
|-----|------|--------|--------|
| 因果反转 | 预测准确率跌至50% | 市场制度突变 (2024年中) | 月度DAG重学习 + 制度检测 |
| 隐变量崩溃 | 所有币同时暴跌，DAG无法解释 | FTX崩溃等黑天鹅 | 显式监控黑天鹅 + 承认混淆 |
| 非线性失效 | 极端行情（↑>50%）中失效 | VarLiNGAM假设线性 | 升级TiMINo或分制度模型 |
| 过拟合 | 回测60%，实盘-5% | 虚假因果（随机发现） | FDR/Bonferroni调整 + 经济意义滤 |
| 流动性毁灭 | 交易成本（0.5-2%）>预期收益（1-3%） | Altcoin流动性差 | 限制Top 50币种 + TWAP执行 |

***

## 推荐实现路线

第1个月：学习 + 原型

- 学习VarLiNGAM理论（2-3天）
- 用开源库快速原型（1周）
- 在比特币+以太坊测试（1周）

第2个月：产品化

- 全币覆盖（Top 50）
- 集成Do-calculus自动化
- Backtesting框架（过去2年）

第3个月：上线前测试

- 纸张交易（1个月）
- A/B测试（小额真实交易）
- 风险监控告警

第4个月+：持续优化

- 高频制度检测
- 升级TiMINo（非线性）
- 跨交易所套利机制

***

## 关键参考（原样）

[1](https://papers.ssrn.com/sol3/Delivery.cfm/5277078.pdf?abstractid=5277078&mirid=1)  
[2](https://www.sciencedirect.com/science/article/abs/pii/S0925231214005359)  
[3](https://causality.cs.ucla.edu/blog/index.php/category/do-calculus/)  
[4](https://www.adialab.ae/research-series/a-protocol-for-causal-factor-investing)  
[5](http://arxiv.org/pdf/2306.08157.pdf)  
[6](https://proceedings.stis.ac.id/icdsos/article/view/727)  
[7](https://pmc.ncbi.nlm.nih.gov/articles/PMC8427770/)  
[8](https://arxiv.org/pdf/1906.05740.pdf)  
[9](https://www.sciencedirect.com/science/article/abs/pii/S0378437119314736)  
[10](https://arxiv.org/html/2408.15846v2)  
[11](https://ieeexplore.ieee.org/document/11267420/)  
[12](https://academic.oup.com/ehjopen/article/doi/10.1093/ehjopen/oeaf070/8156688)  
[13](https://ieeexplore.ieee.org/document/10903341/)  
[14](https://bmcmedresmethodol.biomedcentral.com/articles/10.1186/s12874-025-02704-0)  
[15](https://medinform.jmir.org/2024/1/e56572)  
[16](https://meth.psychopen.eu/index.php/meth/article/view/15773)  
[17](https://www.semanticscholar.org/paper/5d3a1b471187a4b9e6e3d7ebfc1d8710deb426e6)  
[18](https://www.semanticscholar.org/paper/f45d524b3ab8c48e3143c0899d426314e36367cf)  
[19](https://aacrjournals.org/clincancerres/article/31/13_Supplement/A061/763280/Abstract-A061-Machine-Learning-and-Causal)  
[20](https://academic.oup.com/genetics/article/doi/10.1093/genetics/iyaf064/8105590)  
[21](https://arxiv.org/html/2411.17542v1)  
[22](http://arxiv.org/pdf/2408.09960.pdf)  
[23](http://arxiv.org/pdf/2311.16570.pdf)  
[24](https://arxiv.org/pdf/1912.09104.pdf)  
[25](https://arxiv.org/html/2402.06032v1)  
[26](http://arxiv.org/pdf/2401.05414.pdf)  
[27](https://arxiv.org/pdf/1911.02173.pdf)  
[28](http://arxiv.org/pdf/2410.05177.pdf)  
[29](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4679414_code6394881.pdf?abstractid=4679414&mirid=1)  
[30](http://arxiv.org/pdf/2408.15846.pdf)  
[31](https://rpc.cfainstitute.org/sites/default/files/docs/research-reports/rf_lopezdeprado_causalityprimer_online.pdf)  
[32](https://papers.ssrn.com/sol3/Delivery.cfm/4679870.pdf?abstractid=4679870)  
[33](https://www.linkedin.com/posts/david-forino_causality-and-factor-investing-a-primer-activity-7337810746824626177-vAJm)  
[34](https://economics.smu.edu.sg/sites/economics.smu.edu.sg/files/economics/pdf/Seminar/2024/20241101.pdf)  
[35](http://mrzepczynski.blogspot.com/2025/06/causal-discovery-and-trading.html)  
[36](https://www.nber.org/system/files/working_papers/w26104/w26104.pdf)  
[37](https://ui.adsabs.harvard.edu/abs/2024arXiv240815846T/abstract)  
[38](https://wangari.substack.com/p/how-to-build-a-causal-diagram-for)  
[39](https://www.ewadirect.com/proceedings/aemps/article/view/8653)  
[40](https://www.mdpi.com/2674-1032/4/4/64)  
[41](https://www.tandfonline.com/doi/full/10.1080/00207543.2025.2523527)  
[42](https://ieeexplore.ieee.org/document/10779327/)  
[43](https://arxiv.org/abs/2404.17227)  
[44](https://www.semanticscholar.org/paper/1db20afddc4b2a92bc98666266a34b1243e4cbd9)  
[45](https://www.mdpi.com/2227-7390/13/18/3044)  
[46](https://www.scitepress.org/DigitalLibrary/Link.aspx?doi=10.5220/0013688700004670)  
[47](https://csecurity.kubg.edu.ua/index.php/journal/article/view/982)  
[48](https://arxiv.org/abs/2308.15769)  
[49](https://www.mdpi.com/1099-4300/21/11/1116/pdf)  
[50](https://arxiv.org/html/2411.03035v1)  
[51](https://arxiv.org/html/2409.03674)  
[52](https://arxiv.org/pdf/2303.16148.pdf)  
[53](https://arxiv.org/pdf/2411.12748.pdf)  
[54](https://www.sciencedirect.com/science/article/abs/pii/S1059056024000327)  
[55](https://www.sciencedirect.com/science/article/abs/pii/S1544612322001672)  
[56](https://arxiv.org/html/2509.15232v2)  
[57](https://afajof.org/management/viewp.php?n=36652)  
[58](https://www.bde.es/f/webpi/SES/staff/azquetaandres/1-s2.0-S0378437119314736-main.pdf)  
[59](https://tesi.luiss.it/36246/1/739591_CAMPISANO_GIORGIO.pdf)  
[60](https://www.sciencedirect.com/science/article/abs/pii/S0378437125008374)  
[61](https://pmc.ncbi.nlm.nih.gov/articles/PMC7134290/)  
[62](https://www.sciencedirect.com/science/article/pii/S1059056025009979)  
[63](https://ink.library.smu.edu.sg/cgi/viewcontent.cgi?article=8507&context=lkcsb_research)  
[64](https://arxiv.org/html/2303.16148v2)  
[65](https://cob.unt.edu/sites/default/files/docs/acct/accounting-conference/program/4.02-Dong%20Fang%20Lin-Tracing%20Contagion%20Risk.pdf)  
[66](https://onlinelibrary.wiley.com/doi/10.1111/fire.70026)

