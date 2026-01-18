"""
Structural Break Detection for Factor Testing

Purpose:
1. Detect regime changes in factor effectiveness
2. Identify periods when factors fail
3. Implement Chow test and rolling IC analysis

Usage:
    uv run python scripts/evaluation/structural_break_detection.py
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "03_integration"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from trading_system.infrastructure.factor_engines.talib_engine import TalibFactorEngine
from ic_calculation_improved import calculate_ic_timeseries


def calculate_rolling_ic(
    factor_values: pd.Series,
    forward_returns: pd.Series,
    window: int = 500
) -> pd.Series:
    """Calculate rolling IC"""
    rolling_ic = []
    dates = []
    
    for i in range(window, len(factor_values)):
        f_w = factor_values.iloc[i-window:i]
        r_w = forward_returns.iloc[i-window:i]
        
        valid_mask = ~(f_w.isna() | r_w.isna())
        if valid_mask.sum() >= 30:
            ic, _ = stats.spearmanr(f_w[valid_mask], r_w[valid_mask])
            rolling_ic.append(ic)
            dates.append(factor_values.index[i])
    
    return pd.Series(rolling_ic, index=dates)


def chow_test(
    y1: np.ndarray,
    x1: np.ndarray,
    y2: np.ndarray,
    x2: np.ndarray
) -> dict:
    """
    Chow test for structural break
    
    Tests if two regressions have the same coefficients
    """
    from sklearn.linear_model import LinearRegression
    
    # Fit separate models
    model1 = LinearRegression().fit(x1.reshape(-1, 1), y1)
    model2 = LinearRegression().fit(x2.reshape(-1, 1), y2)
    
    # Fit pooled model
    x_pooled = np.concatenate([x1, x2])
    y_pooled = np.concatenate([y1, y2])
    model_pooled = LinearRegression().fit(x_pooled.reshape(-1, 1), y_pooled)
    
    # Calculate RSS
    rss1 = np.sum((y1 - model1.predict(x1.reshape(-1, 1)))**2)
    rss2 = np.sum((y2 - model2.predict(x2.reshape(-1, 1)))**2)
    rss_pooled = np.sum((y_pooled - model_pooled.predict(x_pooled.reshape(-1, 1)))**2)
    
    # Chow statistic
    k = 2  # number of parameters
    n1, n2 = len(y1), len(y2)
    
    numerator = (rss_pooled - (rss1 + rss2)) / k
    denominator = (rss1 + rss2) / (n1 + n2 - 2*k)
    
    if denominator > 0:
        f_stat = numerator / denominator
        p_value = 1 - stats.f.cdf(f_stat, k, n1 + n2 - 2*k)
    else:
        f_stat = np.nan
        p_value = np.nan
    
    return {
        "f_stat": f_stat,
        "p_value": p_value,
        "has_break": p_value < 0.05 if not np.isnan(p_value) else False
    }


def main():
    """Main execution"""
    print("=" * 80)
    print("Structural Break Detection")
    print("=" * 80)
    print()

    data_dir = Path("01_freqtrade/data/okx/futures")
    pair = "BTC/USDT:USDT"
    factors = ["reversal_1", "reversal_3", "reversal_5"]  # vol_28 removed: failed validation
    horizon = 4
    
    # Load data
    pair_clean = pair.replace("/", "_").replace(":", "_")
    filepath = data_dir / f"{pair_clean}-15m-futures.feather"
    df = pd.read_feather(filepath)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    
    print(f"Data: {len(df):,} rows")
    print()
    
    engine = TalibFactorEngine()
    
    for factor in factors:
        print(f"Analyzing {factor}...")
        
        # Compute factor and returns
        df[factor] = engine.compute(df, [factor])[factor]
        df["fwd_ret"] = df["close"].shift(-horizon) / df["close"] - 1
        
        # Calculate rolling IC
        rolling_ic = calculate_rolling_ic(df[factor], df["fwd_ret"], window=500)
        
        print(f"  Rolling IC mean: {rolling_ic.mean():.4f}")
        print(f"  Rolling IC std: {rolling_ic.std():.4f}")
        print()
    
    print("✓ Analysis complete")


if __name__ == "__main__":
    main()
