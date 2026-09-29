import pandas as pd, json
pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 300)
pd.set_option("display.max_columns", 60)

R = r"E:\FreqTrader\freqtrade\shark_results"
df = pd.read_csv(rf"{R}\strategy_summary.csv")
print("strategy_summary.csv shape:", df.shape)
print("cols:", list(df.columns))
print(df.head(3).to_string())
for c in ("strategy", "split", "symbol", "timeframe"):
    if c in df.columns:
        print(c, "->", df[c].unique()[:20])
