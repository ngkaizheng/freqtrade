import pandas as pd, json, sys
pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 50)

R = r"E:\FreqTrader\freqtrade\shark_results"

for tf in ("4h", "1h"):
    df = pd.read_csv(rf"{R}\phase2_per_symbol_{tf}.csv")
    print("=" * 100)
    print(f"phase2_per_symbol_{tf}.csv  rows={len(df)}  splits={df['split'].unique().tolist()}")
    print(df.groupby(["split"])["total_trades"].sum())
    # per-symbol per split
    piv = df.pivot_table(index="symbol", columns="split", values="total_trades", aggfunc="sum")
    print(piv)
    print("TOTAL by split:")
    print(df.groupby("split")["total_trades"].sum())
    print("TOTAL all splits:")
    print(df["total_trades"].sum())
    print("by strategy (all splits):")
    print(df.groupby("strategy")["total_trades"].sum())
    # oos only per symbol
    for s in df["split"].unique():
        sub = df[df["split"] == s]
        print(f"-- split={s}: total={sub['total_trades'].sum()}, per-symbol mean={sub['total_trades'].mean():.2f}, min={sub['total_trades'].min()}, max={sub['total_trades'].max()}")
