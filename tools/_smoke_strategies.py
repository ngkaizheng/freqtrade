"""Offline smoke test: run each user strategy's populate_indicators on real local data.

Validates pandas 3.0 / numpy 2.4 / TA-Lib / technical compatibility without
needing exchange connectivity (which is geo-blocked on this machine).
"""
import sys
import traceback
from pathlib import Path

import pandas as pd

from freqtrade.resolvers import StrategyResolver

PAIR = "ALGO/USDT"
DATA = r"user_data\data\binance\ALGO_USDT-1h.feather"

STRATEGIES = [
    "AlwaysTradeStrategy",
    "FreqaiExampleHybridStrategy",
    "SampleStrategy",
    "Strategy002",
    "Strategy005",
    "TrendFollowingStrategy",
]

df_raw = pd.read_feather(DATA)
print(f"data: {len(df_raw)} rows  {df_raw['date'].min()} -> {df_raw['date'].max()}")
print(f"pandas {pd.__version__}\n")

config = {
    "strategy": "",
    "timeframe": "1h",
    "dry_run": True,
    "stake_currency": "USDT",
    "stake_amount": 100,
    "trading_mode": "spot",
    "margin_mode": "",
    "exchange": {"name": "binance", "key": "", "secret": "", "pair_whitelist": [PAIR]},
    "pairlists": [{"method": "StaticPairList"}],
    "entry_pricing": {"price_side": "same", "use_order_book": False},
    "exit_pricing": {"price_side": "same", "use_order_book": False},
    "dataformat_ohlcv": "feather",
    "user_data_dir": Path("user_data").resolve(),
    "strategy_path": None,
    "runmode": "backtest",
}

results = []
for name in STRATEGIES:
    cfg = dict(config, strategy=name)
    # FreqaiExampleHybridStrategy is can_short=True and needs a futures market.
    if name == "FreqaiExampleHybridStrategy":
        cfg = dict(cfg, trading_mode="futures", margin_mode="isolated")
    try:
        strat = StrategyResolver.load_strategy(cfg)
        df = df_raw.copy()
        df = strat.analyze_ticker(df, {"pair": PAIR})
        cols = [c for c in df.columns if c not in df_raw.columns]
        buy = int(df["enter_long"].sum()) if "enter_long" in df else 0
        sell = int(df["exit_long"].sum()) if "exit_long" in df else 0
        nan_free = not df[cols].isna().all().any()
        results.append((name, "OK", f"{len(cols)} cols, {buy} entries, {sell} exits, finite={nan_free}"))
    except Exception as exc:  # noqa: BLE001
        results.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))
        traceback.print_exc()

print("\n" + "=" * 78)
width = max(len(r[0]) for r in results)
failed = 0
for name, status, detail in results:
    if status == "FAIL":
        failed += 1
    print(f"{name:<{width}}  {status:<5}  {detail}")
print("=" * 78)
print(f"{len(results) - failed}/{len(results)} strategies executed indicator pipeline")
sys.exit(1 if failed else 0)
