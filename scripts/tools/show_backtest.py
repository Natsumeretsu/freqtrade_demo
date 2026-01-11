#!/usr/bin/env python3
"""Quick script to show backtest summary."""
import json
import sys
import zipfile

def main():
    if len(sys.argv) < 2:
        print("Usage: python show_backtest.py <json_or_zip_file>")
        sys.exit(1)

    filepath = sys.argv[1]
    if filepath.endswith('.zip'):
        with zipfile.ZipFile(filepath, 'r') as z:
            json_name = [n for n in z.namelist() if n.endswith('.json')][0]
            data = json.loads(z.read(json_name))
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

    for strat_name, strat in data.get('strategy', {}).items():
        print(f"\n=== {strat_name} ===")
        print(f"Total Trades: {strat.get('total_trades', 0)}")
        print(f"Profit Total: {strat.get('profit_total', 0) * 100:.2f}%")
        print(f"Profit Abs: {strat.get('profit_total_abs', 0):.2f}")
        print(f"Wins/Draws/Losses: {strat.get('wins', 0)}/{strat.get('draws', 0)}/{strat.get('losses', 0)}")
        total = strat.get('total_trades', 1)
        if total > 0:
            print(f"Win Rate: {strat.get('wins', 0) / total * 100:.1f}%")
        print(f"Max Drawdown: {strat.get('max_drawdown', 0) * 100:.2f}%")
        print(f"Sharpe: {strat.get('sharpe', 0):.2f}")
        print(f"Sortino: {strat.get('sortino', 0):.2f}")
        print(f"Profit Factor: {strat.get('profit_factor', 0):.2f}")

        # Exit reasons
        print("\n--- Exit Reasons ---")
        for reason, count in strat.get('exit_reason_summary', {}).items():
            print(f"  {reason}: {count}")

if __name__ == '__main__':
    main()
