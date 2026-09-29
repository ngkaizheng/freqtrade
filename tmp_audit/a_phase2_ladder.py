import pandas as pd, json
pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 60)

R = r"E:\FreqTrader\freqtrade\shark_results"

for tf in ("4h", "1h"):
    df = pd.read_csv(rf"{R}\phase2_per_symbol_{tf}.csv")
    print("=" * 100)
    sub = df[df["strategy"] == "SHARK-01"]
    print(f"--- {tf} SHARK-01 oos per-symbol total_trades ---")
    print(sub[["symbol", "total_trades", "expectancy_r", "cost_per_trade_r"]].to_string(index=False))
    print("sum:", sub["total_trades"].sum(), " mean/symbol:", round(sub["total_trades"].mean(), 2))

print("=" * 100)
lad = pd.read_csv(rf"{R}\phase2_strategy_ladder.csv")
print("phase2_strategy_ladder.csv cols:", list(lad.columns))
print(lad.to_string(index=False))

for tf in ("4h", "1h"):
    wf = pd.read_csv(rf"{R}\phase2_walk_forward_{tf}.csv")
    print("=" * 100)
    print(f"phase2_walk_forward_{tf}.csv cols:", list(wf.columns))
    print(wf.to_string(index=False))
    if "n_trades" in wf.columns or "trades" in wf.columns:
        col = "n_trades" if "n_trades" in wf.columns else "trades"
        print("sum of", col, "=", wf[col].sum(), " over 13 quarters -> per year =", round(wf[col].sum() / (13 / 4), 1))
