import json, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
p = r"E:\FreqTrader\freqtrade\user_data\strategy_factory_runs\full-mvp-20260925\manifest.json"
d = json.load(open(p))
print("data_start", d["data_start"], "data_end", d["data_end"], "pairs", d["pairs"])
f = pd.DataFrame(d["folds"])
print("n folds:", len(f))
print("validation span:", f["validation_start"].min(), "->", f["validation_end"].max())
span_days = (pd.Timestamp(f["validation_end"].max()) - pd.Timestamp(f["validation_start"].min())).days
print("OOS span days:", span_days, "=", round(span_days/365.25, 3), "years")
lb = pd.read_csv(r"E:\FreqTrader\freqtrade\user_data\strategy_factory_runs\full-mvp-20260925\leaderboard.csv")
print(lb[["hypothesis_id", "oos_trades", "btc_expectancy", "eth_expectancy"]].to_string(index=False))
for _, row in lb.iterrows():
    n = row["oos_trades"]; yrs = span_days/365.25
    print(f"{row['hypothesis_id']:<24} oos_trades={n:>7}  -> {n/yrs:,.0f}/yr across 2 symbols = {n/yrs/2:,.0f} per symbol/yr  (ESTIMATE)")
hs = pd.read_csv(r"E:\FreqTrader\freqtrade\user_data\strategy_factory_runs\full-mvp-20260925\hypothesis_summary.csv")
print("\nhypothesis_summary cols:", list(hs.columns))
print(hs.to_string(index=False))
