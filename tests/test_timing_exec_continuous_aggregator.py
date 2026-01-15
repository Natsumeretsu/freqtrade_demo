from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "03_integration"))
sys.path.insert(0, str(_REPO_ROOT / "01_freqtrade" / "strategies"))

from SmallAccountFuturesTimingExecV1 import SmallAccountFuturesTimingExecV1, _FactorSpec  # noqa: E402


class TestTimingExecContinuousAggregator(unittest.TestCase):
    def test_long_short_scores_are_continuous_and_bounded(self) -> None:
        n = 200
        df = pd.DataFrame({"f1": np.arange(n, dtype="float64")})

        specs = [_FactorSpec(name="f1", direction="pos", side="both", weight=1.0)]
        long_s, short_s, net_s = SmallAccountFuturesTimingExecV1._long_short_scores_from_factors(
            df=df,
            factor_specs=specs,
            timeframe="1h",
            quantiles=5,
            lookback_days=1,
        )

        self.assertEqual(long_s.shape, (n,))
        self.assertEqual(short_s.shape, (n,))
        self.assertEqual(net_s.shape, (n,))
        self.assertTrue(np.isfinite(long_s).all())
        self.assertTrue(np.isfinite(short_s).all())
        self.assertTrue(np.isfinite(net_s).all())
        self.assertTrue(((0.0 <= long_s) & (long_s <= 1.0)).all())
        self.assertTrue(((0.0 <= short_s) & (short_s <= 1.0)).all())
        self.assertTrue(((-1.0 <= net_s) & (net_s <= 1.0)).all())

        # 单调上升序列：最后阶段应明显偏多
        self.assertGreater(float(long_s[-1]), 0.8)
        self.assertLess(float(short_s[-1]), 0.2)
        self.assertGreater(float(net_s[-1]), 0.8)

        # direction=neg：同样的序列应被解释为偏空
        specs_neg = [_FactorSpec(name="f1", direction="neg", side="both", weight=1.0)]
        long2, short2, net2 = SmallAccountFuturesTimingExecV1._long_short_scores_from_factors(
            df=df,
            factor_specs=specs_neg,
            timeframe="1h",
            quantiles=5,
            lookback_days=1,
        )
        self.assertGreater(float(short2[-1]), 0.8)
        self.assertLess(float(long2[-1]), 0.2)
        self.assertLess(float(net2[-1]), -0.8)

        # side=long：不应产生任何 short 分数
        specs_long = [_FactorSpec(name="f1", direction="pos", side="long", weight=1.0)]
        long3, short3, net3 = SmallAccountFuturesTimingExecV1._long_short_scores_from_factors(
            df=df,
            factor_specs=specs_long,
            timeframe="1h",
            quantiles=5,
            lookback_days=1,
        )
        self.assertTrue(np.allclose(short3, 0.0))
        self.assertGreater(float(long3[-1]), 0.8)
        self.assertGreater(float(net3[-1]), 0.8)


if __name__ == "__main__":
    unittest.main()
