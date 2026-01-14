"""
qlib 适配层（本仓库）

目标：
- 在不改变执行层（Freqtrade）约束的前提下，引入真实 Qlib（pyqlib）作为研究层框架；
- 研究层统一通过 Qlib 的 Dataset/DataHandler/DataLoader 组织数据与训练输入；
- 数据源仍以本仓库的 OHLCV（Freqtrade 数据）为权威，避免“研究/执行口径漂移”。
"""

