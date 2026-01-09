from datetime import datetime

from freqtrade.optimize.hyperopt import IHyperOptLoss
from pandas import DataFrame


class MoonshotLoss(IHyperOptLoss):
    """
    Moonshot 专用裁判：
    1. 极度贪婪：主要看总利润 (Profit)。
    2. 生存优先：严厉惩罚最大回撤 (Drawdown)，防止 10U 归零。
    3. 忽略稳定性：只要最终赚钱且不爆仓，过程抖动无所谓。
    """

    def hyperopt_loss_function(
        self,
        results: DataFrame,
        trade_count: int,
        min_date: datetime,
        max_date: datetime,
        config: dict,
        processed: dict,
        *args,
        **kwargs,
    ) -> float:
        """
        目标：Loss 越小越好。
        """
        if trade_count < 20:  # 交易次数太少（比如只开了2单运气好）直接淘汰
            return 100.0

        total_profit = results["profit_ratio"].sum()

        # 计算最大回撤 (Max Drawdown)
        try:
            cumulative_profit = results["profit_ratio"].cumsum()
            max_profit = cumulative_profit.cummax()
            drawdown = cumulative_profit - max_profit
            max_drawdown = abs(drawdown.min())
        except Exception:
            max_drawdown = 1.0

        # --- 评分公式 ---

        # 1. 利润奖励：赚得越多，分数越低（越好）
        # 放大系数 2.0，鼓励进攻
        profit_score = -total_profit * 2.0

        # 2. 回撤惩罚：回撤越大，分数越高（越差）
        # 惩罚系数 8.0：对于 10U 账户，回撤是致命的。
        # 意味着：每 10% 的回撤，需要 40% 的额外利润才能抵消。
        drawdown_penalty = max_drawdown * 8.0

        total_loss = profit_score + drawdown_penalty
        return total_loss
