from pathlib import Path

import joblib
from freqtrade.strategy import IStrategy
from pandas import DataFrame


class KNNStrategy(IStrategy):
    stoploss = -0.1  # 表示最大止损为-10%

    def ft_bot_start(self, **kwargs):
        model_path = (
            Path(self.config["user_data_dir"]) / "models" / "knn_btc_usdt_1h.pkl"
        )
        print(f"Loading KNN model from: {model_path}")
        self.knn_model = joblib.load(model_path)
        self._feature_columns = list(
            getattr(self.knn_model, "feature_names_in_", ["Open-Close", "High-Low"])
        )

    def populate_indicators(
        self, df: DataFrame, metadata: dict
    ) -> DataFrame:  # 构造特征
        df["Open-Close"] = df["open"] - df["close"]
        df["High-Low"] = df["high"] - df["low"]
        df.fillna(0, inplace=True)
        return df

    def predict(self, df):
        """预测下一根K线是涨还是跌"""
        if "knn_pred" in df.columns:
            return df

        if not hasattr(self, "knn_model"):
            raise RuntimeError("KNN 模型未加载：请确认已执行 ft_bot_start()。")

        feature_columns = getattr(self, "_feature_columns", ["Open-Close", "High-Low"])
        missing_columns = [col for col in feature_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"缺少 KNN 特征列：{missing_columns}")

        x = df[feature_columns].astype("float64")
        preds = self.knn_model.predict(x)
        df["knn_pred"] = preds  # 将预测结果放入数据集
        return df

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df = self.predict(df)
        # 预测到它下一根k线是涨的话，就在数据集加一个enterlong的入场信号
        df.loc[(df["knn_pred"] == 1), "enter_long"] = 1
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df = self.predict(df)
        df.loc[(df["knn_pred"] == -1), "exit_long"] = 1
        return df
