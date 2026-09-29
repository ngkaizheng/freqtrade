"""Verify the two load-bearing claims for Q4:
  (a) what share of settlements are paid at EXACTLY the fixed interest component (0.0001)
  (b) mean total carry minus the fixed interest component  (3*365*0.0001 = 10.95%/yr)
  (c) the realised max funding rate per symbol vs the Binance cap (0.75 * MMR)
"""
import pathlib

import pandas as pd

SRC = pathlib.Path("user_data/data/binance_funding")
IOTA = 0.0001  # Binance flat 8h interest component
ANN = 3 * 365 * 100

frames = {}
for f in sorted(SRC.glob("*funding.feather")):
    sym = f.name.split("_")[0]
    df = pd.read_feather(f)
    s = pd.Series(df["fundingRate"].to_numpy(dtype="float64"),
                  index=pd.DatetimeIndex(df["fundingTime"]))
    s.index = s.index.floor("8h")
    frames[sym] = s[~s.index.duplicated()].sort_index()

wide = pd.DataFrame(frames).sort_index()
print("panel span:", wide.index.min(), "->", wide.index.max())

print("\n--- (a) share of settlements paid EXACTLY at the 0.0001 interest component ---")
at_iota = (wide.round(8) == IOTA)
pct = at_iota.mean() * 100
print(f"pooled (all rows, all symbols): {at_iota.to_numpy().mean()*100:.2f}%")
for s in pct.sort_values(ascending=False).index:
    print(f"  {s:5s} {pct[s]:6.2f}%   n={int(wide[s].notna().sum())}")

print("\n--- post-2025-05-02 (the 1h/4h policy date) ---")
late = wide[wide.index >= "2025-05-02"]
pct2 = (late.round(8) == IOTA).mean() * 100
print(f"pooled: {(late.round(8) == IOTA).to_numpy().mean()*100:.2f}%   "
      f"range {pct2.min():.1f}% .. {pct2.max():.1f}%")

print("\n--- (b) carry decomposition: total vs fixed interest component ---")
p = wide.dropna()
tot = p.mean() * ANN
iota_ann = IOTA * ANN
print(f"equal-weight mean TOTAL carry        : {tot.mean():+7.2f}%/yr")
print(f"equal-weight mean INTEREST component: {iota_ann:7.2f}%/yr  (0.0001 x 3 x 365)")
print(f"equal-weight mean EXCESS             : {(tot - iota_ann).mean():+7.2f}%/yr")
print()
ex = (tot - iota_ann).sort_values(ascending=False)
for s in ex.index:
    print(f"  {s:5s} total {tot[s]:+7.2f}%/yr   excess {ex[s]:+7.2f}%/yr")
print(f"\n  n symbols with NEGATIVE excess: {int((ex < 0).sum())}/{len(ex)}")

print("\n--- (c) realised max funding rate per symbol, vs Binance cap ---")
caps = {"BTCUSDT": 0.00300, "ETHUSDT": 0.00300, "BNBUSDT": 0.00375, "SOLUSDT": 0.00375,
        "XRPUSDT": 0.00375, "ADAUSDT": 0.00375, "DOGEUSDT": 0.004875, "LINKUSDT": 0.00375,
        "AVAXUSDT": 0.00375, "LTCUSDT": 0.00375, "TRXUSDT": 0.00375, "UNIUSDT": 0.00375}
mx = wide.max() * 100
mn = wide.min() * 100
for s in wide.columns:
    c = caps.get(s + "USDT")
    ctxt = f"{c*100:7.4f}%" if c else "      ?"
    flag = ""
    if c and abs(mx[s] / 100 - c) < 1e-6:
        flag = "  <-- AT CAP"
    print(f"  {s:5s} max {mx[s]:+7.4f}%   min {mn[s]:+7.4f}%   cap {ctxt}{flag}")

print("\n--- arithmetic check on the cap, stated properly ---")
for c in (0.003, 0.00375, 0.004875, 0.02):
    print(f"  cap {c*100:.4f}% per settlement x3/day x365 = "
          f"{c*3*365*100:.1f}%/yr annualised")
print("  -> a per-settlement cap is a DAILY-scale parameter; annualised it is very wide")
print("     and therefore economically non-binding at an 8h interval.")
