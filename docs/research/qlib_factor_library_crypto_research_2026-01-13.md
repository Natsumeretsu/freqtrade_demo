<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# qlib自带哪些因子？因子库？怎么使用和研究？针对加密市场

更新日期：2026-01-13


Now I'll create a comprehensive response document for the user.

## Qlib自带因子库、因子使用和加密市场研究指南

### Qlib内置因子库概览

**Qlib**是微软开源的AI导向量化投资平台，内置了两个主要的量价因子库：[^1][^2][^3]

#### **Alpha158因子库**（158个因子）

Alpha158是最常用的因子库，包含158个经过市场验证的量化因子。这些因子基于OHLCV（开盘价、最高价、最低价、收盘价、成交量）数据构建，涵盖多个维度：[^2][^1]

- **KBar因子**（约9个）：KMID（日内涨跌幅）、KLEN（日内振幅）、KMID2、KUP、KUP2、KLOW、KLOW2、KSFT、KSFT2等
- **价格因子**（20个）：4个价格字段（OPEN、HIGH、LOW、CLOSE）× 5个时间窗口
- **成交量因子**（5个）：VOLUME × 5个时间窗口
- **滚动统计因子**（25个）：ROC、MA、STD、MAX、MIN等 × 5个窗口期（5、10、20、30、60天）
- **其他因子**：CORD、RESI、RSV、CORR等，补充至158个


#### **Alpha360因子库**（360个因子）

Alpha360是更加全面的因子库，包含原始价量数据及更多衍生因子，适合需要更丰富特征的应用场景。[^4]

### 因子库的使用方法

#### **基础使用流程**

```python
import qlib
from qlib.contrib.data.handler import Alpha158

# 1. 初始化Qlib（以中国股票为例）
qlib.init(provider_uri='~/.qlib/qlib_data/cn_data', region='CN')

# 2. 配置数据处理器
data_handler_config = {
    "start_time": "2008-01-01",
    "end_time": "2020-08-01",
    "fit_start_time": "2008-01-01",
    "fit_end_time": "2014-12-31",
    "instruments": "csi300",  # 中证300指数成分股
}

# 3. 创建Alpha158处理器
h = Alpha158(**data_handler_config)

# 4. 获取因子列表
feature_names = h.get_cols()
print(f"总因子数: {len(feature_names)}")

# 5. 获取特征数据
features = h.fetch(col_set="feature")

# 6. 获取标签数据（下期收益）
labels = h.fetch(col_set="label")
```


#### **获取特定因子信息**

```python
# 查看所有因子名称
feature_names = h.get_cols()
print(feature_names[:10])  # 显示前10个因子

# 获取特定时间段的特征
features_subset = h.fetch(
    col_set="feature",
    selector=slice("2015-01-01", "2015-12-31")
)

# 获取特定股票的因子数据
features_stock = h.fetch(
    col_set="feature",
    level="instrument",
    selector="SH600000"
)
```


### 自定义因子创建和研究

#### **方法一：通过表达式引擎创建因子**

Qlib的表达式引擎支持复杂的因子定义，无需编写复杂代码：[^5][^6]

```python
from qlib.data.dataset.loader import QlibDataLoader

# 定义MACD因子
MACD_EXP = '(EMA($close, 12) - EMA($close, 26))/$close - EMA((EMA($close, 12) - EMA($close, 26))/$close, 9)/$close'
RSI_EXP = '(CLOSE - REF(CLOSE, 14)) / (MAX(CLOSE - REF(CLOSE, 14), 14) - MIN(CLOSE - REF(CLOSE, 14), 14))'

fields = [MACD_EXP, RSI_EXP]
names = ['MACD', 'RSI']

# 标签定义（下期收益）
labels = ['Ref($close, -2)/Ref($close, -1) - 1']
label_names = ['LABEL']

# 配置加载器
data_loader_config = {
    "feature": (fields, names),
    "label": (labels, label_names)
}

data_loader = QlibDataLoader(config=data_loader_config)
df = data_loader.load(instruments='csi300', start_time='2010-01-01', end_time='2020-12-31')
```


#### **方法二：继承Alpha158创建自定义因子库**

```python
from qlib.contrib.data.handler import Alpha158

class CustomAlpha158(Alpha158):
    def get_feature_config(self):
        # 获取原始Alpha158配置
        conf = super().get_feature_config()
        
        # 添加自定义因子
        conf["custom"] = {
            "MY_FACTOR": "($close - $open) / ($high - $low)",  # K线实体占振幅比例
            "VOLATILITY_20": "STD($close, 20) / MEAN($close, 20)",  # 20日波动率
        }
        
        return conf

# 使用自定义因子库
handler = CustomAlpha158(
    instruments="csi300",
    start_time="2010-01-01",
    end_time="2023-12-31"
)
```


#### **方法三：创建自定义算子**

```python
from qlib.data.ops import ElemOperator, register_op

class RSI(ElemOperator):
    """相对强弱指数(RSI)因子"""
    def __init__(self, window=14):
        self.window = window
    
    def _calc(self, df):
        delta = df["$close"].diff(1)
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=self.window).mean()
        avg_loss = loss.rolling(window=self.window).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

# 注册自定义算子
register_op(RSI)

# 使用自定义因子
from qlib.data import D
data = D.features(["SH600519"], ["RSI(14)"], start_time="2020-01-01")
```


### 因子研究和分析

#### **因子重要性评估**

```python
from qlib.contrib.model.gbdt import LGBModel
from qlib.model.interpret import FeatureImportance

# 训练模型
model = LGBModel()
model.fit(dataset)

# 计算特征重要性
fi = FeatureImportance(model, handler)
importance = fi.get_feature_importance()

# 可视化前10个重要因子
fi.plot_top_k(importance, k=10, figsize=(10, 6))
```


#### **因子IC评估**

```python
# 基于IC值的因子筛选
from qlib.contrib.estimator.filter import ICSelector

filter_pipe = ICSelector(
    ic_threshold=0.05,      # IC值阈值
    rolling_window=60       # 60天滚动计算
)
```


#### **因子动态池**

```python
class DynamicFactorPool(Alpha158):
    def get_feature_config(self):
        # 根据市场状态动态调整因子
        market_state = self._get_market_state()
        
        if market_state == "bull":  # 牛市
            return self._get_bull_features()  # 侧重趋势因子
        else:  # 熊市
            return self._get_bear_features()  # 侧重防御因子
```


### 针对加密市场的应用

#### **当前支持情况**

Qlib官方目前内置的数据主要针对**股票市场**（中国股票和美国股票），**不提供官方加密货币数据源**。但社区已有开发者推出了Qlib加密货币数据接口的二次开发完整教程。[^7][^8][^9]

#### **加密市场数据集成方案**

**第一步：数据准备和转换**

```bash
# 1. 从加密交易所获取CSV数据
# 数据格式要求: date, open, close, high, low, volume, factor

# 2. 转换为Qlib格式
python scripts/dump_bin.py dump_all \
  --csv_path ~/.qlib/csv_data/crypto_data \
  --qlib_dir ~/.qlib/qlib_data/crypto_data \
  --include_fields open,close,high,low,volume,factor \
  --symbol_field_name symbol \
  --date_field_name date
```

**第二步：初始化加密数据**

```python
import qlib
from qlib.constant import REG_US

# 初始化加密货币数据
qlib.init(
    provider_uri='~/.qlib/qlib_data/crypto_data',
    region=REG_US,
    calendar_provider="exchange"
)

# 使用Alpha158或自定义因子库
from qlib.contrib.data.handler import Alpha158

handler = Alpha158(
    instruments=["BTC", "ETH", "BNB"],  # 加密货币代码
    start_time="2020-01-01",
    end_time="2024-01-01",
    freq="day"  # 也可使用 "1h" 或 "1min"
)
```

**第三步：加密特定因子开发**

```python
class CryptoFactors(Alpha158):
    def get_feature_config(self):
        conf = super().get_feature_config()
        
        # 添加加密货币特定因子
        conf["crypto_specific"] = {
            "VOLATILITY": "STD($close, 30) / MEAN($close, 30)",  # 30日波动率
            "MOMENTUM": "($close - REF($close, 20)) / REF($close, 20)",  # 20日动量
            "TREND": "EMA($close, 12) - EMA($close, 26)",  # MACD趋势
            "RSI": "RSI(14)",  # 相对强弱指数
            "VOLUME_TREND": "MEAN($volume, 5) / MEAN($volume, 20)",  # 成交量趋势
        }
        
        return conf
```

**第四步：模型选择**

由于加密市场具有24/7交易、高波动性的特点，推荐：[^10]

- **时间序列模型**：LSTM、GRU、Transformer（捕捉市场动态）
- **梯度提升模型**：LightGBM（快速训练和特征解释）
- **强化学习**：用于交易执行优化和仓位管理

**第五步：回测和评估**

```python
from qlib.backtest import backtest
from qlib.contrib.strategy import TopkDropoutStrategy

# 定义策略
strategy = TopkDropoutStrategy(
    topk=20,           # 选择排名前20的币种
    n_drop=10          # 动态调整前10个
)

# 执行回测
portfolio_metrics = backtest(
    strategy=strategy,
    executor=executor,
    start_date="2020-01-01",
    end_date="2024-01-01"
)

# 分析关键指标
print(portfolio_metrics[["ARR", "Sharpe", "Max Drawdown"]])
```


### 加密市场应用的注意事项

1. **数据质量**：确保交易所数据的准确性，考虑使用多个数据源验证
2. **时间频率**：加密市场24/7交易，可考虑多频率融合（日线+4小时线+1小时线）
3. **交易成本**：加密货币交易成本结构与股票不同，需在回测中调整
4. **流动性差异**：不同币种流动性差异大，小币种可能面临滑点风险
5. **模型更新频率**：考虑更频繁的模型重训（如周更新而非月更新）
6. **风险管理**：加密市场波动性大，需要严格的止损和仓位管理

### 相关资源

- **官方文档**：https://qlib.readthedocs.io[^3][^11]
- **GitHub仓库**：https://github.com/microsoft/qlib[^12]
- **加密货币二次开发**：社区教程（Telegram讨论群：https://t.me/+V7aQPwRaZgo4ZTc1）[^9]
- **Alpha158因子解析**：源码文件 `qlib/contrib/data/handler.py`[^1][^2]

通过Qlib的灵活框架和自定义能力，用户可以将其强大的量化投资工具扩展到加密市场研究中，创建适应加密货币特性的因子和策略。
<span style="display:none">[^13][^14][^15][^16][^17][^18][^19][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29][^30][^31][^32][^33][^34][^35][^36][^37][^38][^39][^40][^41][^42][^43][^44][^45][^46][^47][^48][^49][^50][^51][^52][^53][^54][^55][^56][^57][^58][^59][^60][^61][^62][^63][^64][^65][^66][^67][^68][^69][^70][^71]</span>

<div align="center">⁂</div>

[^1]: https://blog.csdn.net/longma666666/article/details/149266968

[^2]: https://blog.csdn.net/gitblog_00178/article/details/151826589

[^3]: https://qlib.readthedocs.io/en/latest/introduction/introduction.html

[^4]: https://qlib.readthedocs.io/en/latest/component/data.html

[^5]: https://qlib.readthedocs.io/en/stable/advanced/alpha.html

[^6]: https://www.oreateai.com/blog/qlib-intelligent-factor-mining-system-a-beginners-guide-part-four-indepth-analysis-of-the-factor-engine-system/a15d1e8ada9e6c518a34e4a63f644c36

[^7]: https://www.reddit.com/r/algotrading/comments/pqmpsg/did_anyone_try_microsoft_researchs_qlib_library/

[^8]: https://github.com/microsoft/qlib/issues/927

[^9]: https://www.youtube.com/watch?v=po95Ulfua3s

[^10]: https://qlib.readthedocs.io/en/latest/component/rl/overall.html

[^11]: https://qlib.readthedocs.io/en/latest/

[^12]: https://github.com/microsoft/qlib

[^13]: https://journals.uran.ua/bdi/article/view/290983

[^14]: http://www.emerald.com/lm/article/45/6-7/442-455/1212529

[^15]: https://www.tandfonline.com/doi/full/10.1080/10572317.2025.2529723

[^16]: https://credence-publishing.com/journal/uploads/archive/202417141652134342163617.pdf

[^17]: https://www.tandfonline.com/doi/full/10.1080/01930826.2024.2437963

[^18]: http://www.jkmla.org/archive/view_article?doi=10.69528/jkmla.2023.50.1_2.54

[^19]: https://journals.uran.ua/bdi/article/view/294101

[^20]: https://journals.sagepub.com/doi/10.1177/09610006221146298

[^21]: http://librinfosciences.knukim.edu.ua/article/view/259152

[^22]: https://www.emerald.com/lm/article/46/6-7/452/1254609/Enhancing-library-engagement-a-framework-for

[^23]: https://arxiv.org/pdf/2501.15761.pdf

[^24]: https://arxiv.org/pdf/1911.02173.pdf

[^25]: https://arxiv.org/abs/0708.0478

[^26]: https://pmc.ncbi.nlm.nih.gov/articles/PMC8728199/

[^27]: https://arxiv.org/pdf/2311.08990.pdf

[^28]: https://arxiv.org/pdf/2212.10301.pdf

[^29]: http://arxiv.org/pdf/2308.02450.pdf

[^30]: http://arxiv.org/pdf/2409.15926.pdf

[^31]: https://rdagent.readthedocs.io/en/stable/scens/data_agent_fin.html

[^32]: https://wire.insiderfinance.io/ai-for-algorithmic-trading-a-deep-dive-into-microsofts-qlib-dd676a93e9f3

[^33]: https://blog.csdn.net/weixin_38175458/article/details/135751721

[^34]: https://crm.htsc.com.cn/doc/2020/10750101/d287ebf2-7f3f-4382-bf3f-cfabd4b90161.pdf

[^35]: https://www.microsoft.com/en-us/research/articles/rd-agent-quant/

[^36]: https://arxiv.org/html/2505.15155v2

[^37]: https://finance.sina.com.cn/roll/2025-03-21/doc-ineqmfqm9578881.shtml

[^38]: https://blog.csdn.net/zhanghuihua911zha/article/details/149640593

[^39]: https://arxiv.org/pdf/2009.11189.pdf

[^40]: http://arxiv.org/pdf/2212.11144.pdf

[^41]: https://arxiv.org/pdf/2502.02584.pdf

[^42]: http://arxiv.org/pdf/2408.00384.pdf

[^43]: https://advanced.onlinelibrary.wiley.com/doi/10.1002/qute.202400384

[^44]: https://arxiv.org/pdf/2206.01580.pdf

[^45]: https://www.mdpi.com/1422-0067/23/21/12882/pdf?version=1667178713

[^46]: https://kitemetric.com/blogs/mastering-qlib-a-comprehensive-guide-to-building-ai-driven-quant-strategies

[^47]: https://qlib.readthedocs.io/en/v0.5.1/component/estimator.html

[^48]: https://qlib.readthedocs.io/en/stable/component/data.html

[^49]: https://qlib.readthedocs.io/en/v0.6.2/component/data.html

[^50]: https://github.com/microsoft/qlib/blob/main/examples/tutorial/detailed_workflow.ipynb

[^51]: https://github.com/microsoft/qlib/blob/main/examples/benchmarks/README.md

[^52]: https://www.youtube.com/watch?v=z6a4mQTkMwg

[^53]: https://qlib.readthedocs.io/_/downloads/en/v0.8.2/pdf/

[^54]: https://github.com/microsoft/qlib/issues/107

[^55]: https://www.xugj520.cn/en/archives/microsoft-qlib-ai-quantitative-investment.html

[^56]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11348685/

[^57]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11334286/

[^58]: https://engine.scichina.com/doi/10.3724/SP.J.1123.2022.12022

[^59]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10945499/

[^60]: https://blog.csdn.net/weixin_38175458/article/details/121308598

[^61]: https://opendeep.wiki/microsoft/qlib/integration_and_advanced

[^62]: https://quant.csdn.net/691d70f15511483559ebf966.html

[^63]: https://blog.csdn.net/qq_37373209/article/details/125224210

[^64]: https://www.wuzao.com/p/qlib/document/component/data.html

[^65]: https://www.sohu.com/a/507908728_120099896

[^66]: https://blog.csdn.net/mnwl12_0/article/details/135319118

[^67]: https://qlib.moujue.com/component/data.html

[^68]: https://www.hibor.com.cn/data/1ca4f56256cd3c4fb2cc462e81148444.html

[^69]: https://cloud.tencent.com/developer/article/2013352

[^70]: https://www.wuzao.com/qlib/tutorial/data-management

[^71]: https://blog.csdn.net/song19891121/article/details/139956721

