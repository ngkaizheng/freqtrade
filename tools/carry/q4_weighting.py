"""Resolve the discrepancy: equal-weight-of-symbols vs settlement-pooled funding excess."""
import glob
import os

import numpy as np
import pandas as pd

ROOT = r"E:\FreqTrader\freqtrade\user_data\data\binance_funding"
IRATE = 0.0001
files = sorted(glob.glob(os.path.join(ROOT, "*-funding.feather")))

per_sym, pooled = [], []
for f in files:
    sym = os.path.basename(f).split("-")[0]
    d = pd.read_feather(f)
    t = pd.DatetimeIndex(pd.to_datetime(d["fundingTime"], utc=True))
    r = pd.to_numeric(d["fundingRate"], errors="coerce").to_numpy()
    r = r[~np.isnan(r)]
    s = pd.Series(r, index=t[~np.isnan(r)]).sort_index()
    days = (s.index[-1] - s.index[0]).total_seconds() / 86400.0
    spd = len(s) / days                       # settlements per day
    ann = s.mean() * spd * 365.0 * 100         # per-symbol annualised %
    irate_ann = IRATE * spd * 365.0 * 100      # per-symbol interest floor %
    per_sym.append(dict(symbol=sym, n=len(s), ann=ann, irate=irate_ann,
                        excess=ann - irate_ann, spd=spd))
    pooled.append((r, spd, len(s)))

ps = pd.DataFrame(per_sym).sort_values("excess", ascending=False)
print("=== PER SYMBOL (equal weight across symbols) ===")
print(ps.to_string(index=False, float_format=lambda v: f"{v:9.4f}"))
print(f"\n  EQUAL-WEIGHT mean excess : {ps.excess.mean():8.3f} %/yr")
print(f"  symbols with excess < 0 : {(ps.excess < 0).sum()} of {len(ps)}")
print(f"  BTC excess              : {ps.loc[ps.symbol=='BTC_USDT','excess'].iloc[0]:8.3f} %/yr")

# --- pooled: weight every settlement equally across the whole panel ---
allr = np.concatenate([p[0] for p in pooled])
allspd = np.mean([p[1] for p in pooled])
ann = allr.mean() * allspd * 365.0 * 100
irate_ann = IRATE * allspd * 365.0 * 100
print(f"\n=== POOLED (every settlement weighted equally) ===")
print(f"  pooled mean excess      : {ann - irate_ann:8.3f} %/yr")
print(f"  pooled mean carry       : {ann:8.3f} %/yr")
print(f"  pooled interest floor   : {irate_ann:8.3f} %/yr")
print(f"  n settlements pooled    : {len(allr)}")
