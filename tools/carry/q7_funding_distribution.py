"""
Q7: distribution (not just mean) of the Binance 8h funding rate, from the repo's own
on-disk 20-symbol history. This is the "skew" evidence the review asked for.
Reports my own measurement; the raw source is Binance REST via the repo collector.
"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(r"E:\FreqTrader\freqtrade")
FDIR = ROOT / "user_data" / "data" / "binance_funding"
print("dir exists:", FDIR.exists())
files = sorted(FDIR.glob("*"))
print("n files:", len(files))
for f in files[:25]:
    print("   ", f.name, f.stat().st_size)


def load() -> pd.DataFrame:
    frames = []
    for f in files:
        if f.suffix not in (".csv", ".gz", ".csv.gz", ".feather", ".parquet"):
            continue
        try:
            if f.suffix == ".feather":
                d = pd.read_feather(f)
            elif ".parquet" in f.name:
                d = pd.read_parquet(f)
            elif f.name.endswith(".gz"):
                d = pd.read_csv(f, compression="gzip")
            else:
                d = pd.read_csv(f)
        except Exception as e:  # noqa: BLE001
            print("skip", f.name, e)
            continue
        d.columns = [str(c).lower().replace("_", "") for c in d.columns]
        if "fundingrate" in d.columns and "fundingtime" in d.columns:
            sym = f.name.split("-")[0].upper()
            frames.append(d[["fundingtime", "fundingrate"]].assign(symbol=sym))
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out


df = load()
print("\nrows:", len(df), "cols:", list(df.columns))
if df.empty:
    raise SystemExit("no funding data loaded")

r = pd.to_numeric(df["fundingrate"], errors="coerce")
df = df.assign(fr=r).dropna(subset=["fr"])
print("usable rows:", len(df), "symbols:", df["symbol"].nunique())
print("span:", df["fundingtime"].min(), "->", df["fundingtime"].max())

# equal-weighted cross-symbol settlement series on the common calendar
piv = df.pivot_table(index="fundingtime", columns="symbol", values="fr")
full = piv.dropna()
print("fully-common 8h settlements:", len(full))
ew = full.mean(axis=1)
print("\n=== POOL SETTLEMENT DISTRIBUTION (all symbol-settlements) ===")
print("n symbol-settlements :", len(df))
print("mean   %              :", round(df["fr"].mean() * 100, 6))
print("median %              :", round(df["fr"].median() * 100, 6))
print("std    %              :", round(df["fr"].std() * 100, 6))
print("skew                  :", round(df["fr"].skew(), 3))
print("excess kurtosis       :", round(df["fr"].kurt(), 3))
qs = [0.001, 0.005, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.995, 0.999]
print("quantiles %           :",
      {f"{q:.3f}": round(df["fr"].quantile(q) * 100, 5) for q in qs})
print("min / max %           :", round(df["fr"].min() * 100, 5),
      "/", round(df["fr"].max() * 100, 5))
print("share NEGATIVE        :", f"{100 * (df['fr'] < 0).mean():.2f}%")
print("share negative beyond -0.01% (1bp):",
      f"{100 * (df['fr'] < -0.0001).mean():.2f}%")

print("\n=== EQUAL-WEIGHT CROSS-SYMBOL 8h SETTLEMENT SERIES (n=%d) ===" % len(ew))
print("mean   % :", round(ew.mean() * 100, 6))
print("std    % :", round(ew.std() * 100, 6))
print("skew     :", round(ew.skew(), 3))
print("exkurt   :", round(ew.kurt(), 3))
print("quantiles %:", {f"{q:.4f}": round(ew.quantile(q) * 100, 5)
                      for q in (0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999)})
print("min/max  %:", round(ew.min() * 100, 5), "/", round(ew.max() * 100, 5))
print("share negative            :", f"{100 * (ew < 0).mean():.2f}%")
print("share negative beyond -1bp:", f"{100 * (ew < -0.0001).mean():.2f}%")
# longest consecutive run of negative equal-weight settlements
neg = (ew < 0).to_numpy()
best = cur = 0
for b in neg:
    cur = cur + 1 if b else 0
    best = max(best, cur)
print("longest run of consecutive negative settlements:", best,
      f"= {best * 8 / 24:.2f} days")
# 1st-order autocorrelation of the funding series (persistence -> the mean is not iid)
print("lag-1 autocorr of equal-weight series:", round(ew.autocorr(1), 4))
print("lag-3 autocorr (24h)                :", round(ew.autocorr(3), 4))
# rolling 30d annualised
ann30 = ew.rolling(90).mean() * 3 * 365 * 100
print("\nrolling-90-settlement (30d) annualised pct: min {:.2f}  p5 {:.2f}  "
      "median {:.2f}  max {:.2f}  last {:.2f}".format(
          ann30.min(), ann30.quantile(0.05), ann30.median(), ann30.max(), ann30.iloc[-1]))
print("last 30d window annualised is below zero:",
      bool(ann30.iloc[-1] < 0))
ann365 = ew.rolling(1095).mean() * 3 * 365 * 100
print("rolling-365d annualised pct: min {:.2f}  median {:.2f}  last {:.2f}".format(
    ann365.min(), ann365.median(), ann365.iloc[-1]))
print("\nstructural floor: Binance interestRate = 0.01pct per 8h = "
      "{:.2f}pct/yr for a short-perp holder when premium is inside the clamp".format(
          0.0001 * 3 * 365 * 100))

# how often is a symbol's whole 8h settlement negative for a long stretch
print("\n=== PER-SYMBOL ===")
rows = []
for s, g in df.groupby("symbol"):
    x = g["fr"]
    # longest run of consecutive negative settlements in file order
    neg = (x < 0).to_numpy()
    best = cur = 0
    for b in neg:
        cur = cur + 1 if b else 0
        best = max(best, cur)
    rows.append(dict(symbol=s, n=len(x), mean_pct=round(x.mean() * 100, 5),
                     neg_pct=round(100 * (x < 0).mean(), 2),
                     min_pct=round(x.min() * 100, 5),
                     max_pct=round(x.max() * 100, 5),
                     worst_run_neg=best,
                     ann_pct_at_vip0=round(x.mean() * 3 * 365 * 100, 2)))
out = pd.DataFrame(rows).sort_values("mean_pct", ascending=False)
pd.set_option("display.width", 200)
print(out.to_string(index=False))
out.to_csv(ROOT / "tools" / "carry" / "funding_distribution.csv", index=False)
print("\nwrote tools/carry/funding_distribution.csv")

# What does the LONG-SHORT carry book pay per year at VIP0 taker cost?
print("\n=== CARRY vs ROUND-TRIP COST (taker, VIP0) ===")
n = out["n"].max()
ann = out["mean_pct_at_vip0"].mean()
print(f"equal-weight annualised gross carry at mean settlement: {ann:.2f}%/yr")
for label, cost in (("0.30% taker round trip", 0.30),
                    ("0.24% taker + BNB disc", 0.24)):
    print(f"  net if re-established {int(365 * 3 / max(n, 1))}x/yr? -> see REPORT.md; "
          f"one-shot cost {cost:.2f}% pays back in "
          f"{cost / (ann / 100) * 365:.1f} days")
