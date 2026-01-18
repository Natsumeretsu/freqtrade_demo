# 因子挖掘研究目录

本目录用于系统化的因子挖掘和评估研究。

## 目录结构

```
research/factor_mining/
├── README.md                    # 本文件
├── factor_evaluator.py          # 因子评估器（IC/IR/分组回测）
├── factor_generator.py          # 因子生成器（批量生成候选因子）
├── visualizer.py                # 可视化工具
├── pipeline.py                  # 端到端研究流程
├── research_config.yaml         # 研究配置
└── notebooks/                   # Jupyter notebooks
    ├── 01_factor_exploration.ipynb
    ├── 02_factor_evaluation.ipynb
    └── 03_factor_combination.ipynb
```

## 研究流程

### 1. 数据准备
```bash
# 下载历史数据
./scripts/data/download.ps1
```

### 2. 因子挖掘
```bash
# 运行因子挖掘流程
python scripts/research/run_factor_mining.py --config research/factor_mining/research_config.yaml
```

### 3. 因子评估
- IC（信息系数）：因子与未来收益的相关性
- IR（信息比率）：IC 的稳定性
- 分组回测：按因子值分组，比较收益差异
- 稳定性测试：不同时间段的表现

### 4. 生成报告
```bash
# 生成因子研究报告
python scripts/research/generate_factor_report.py --output docs/reports/factor_research/
```

## 因子评估标准

### 有效因子的标准
- IC 绝对值 > 0.02
- IC 的 t 统计量 > 2（显著性）
- IR > 0.5（稳定性）
- 分组收益单调性（Q5 > Q4 > Q3 > Q2 > Q1）

### 因子筛选流程
1. 初步筛选：IC 绝对值 > 0.02
2. 显著性检验：t 统计量 > 2
3. 稳定性测试：不同时间段 IC 方向一致
4. 相关性分析：去除高度相关的冗余因子（相关系数 > 0.8）

## 研究成果归档

每次因子研究完成后，在 `docs/reports/factor_research/` 下归档研究报告：
- 因子描述和参数
- 评估指标（IC/IR/分组收益）
- 可视化图表
- 推荐的因子配置
