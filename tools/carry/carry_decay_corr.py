"""Q3 (decay) + Q6 (common factor) on the repo's own 20-symbol funding corpus,
cross-validated against the live-exchange measurement in funding_live.py.

Run:  python tools/carry/carry_decay_corr.py
"""
import pathlib

import numpy as np
import pandas as pd

SRC = pathlib.Path("user_data/data/binance_funding")
OUT = pathlib.Path("tools/carry/_src")
OUT.mkdir(parents=True, exist_ok=True)

frames = {}
for f in sorted(SRC.glob("*funding.feather")):
    sym = f.name.split("_")[0]
    df = pd.read_feather(f)
    # find the rate column and the timestamp column, whatever they are called
    # columns are fundingTime (datetime64[ms, UTC]) and fundingRate (float64)
    s = pd.Series(df["fundingRate"].to_numpy(dtype="float64"),
                  index=pd.DatetimeIndex(df["fundingTime"]))
    # TRAP: timestamps are NOT exactly on the 8h grid -- e.g. 2026-09-19 08:00:00.002+00:00.
    # Floor to the 8h grid or every join against another symbol silently returns 0 rows.
    s.index = s.index.floor("8h")
    s = s[~s.index.duplicated()].sort_index()
    frames[sym] = s

print("symbols:", len(frames))
wide = pd.DataFrame(frames).sort_index()
print("span:", wide.index.min(), "->", wide.index.max())
print("full common rows:", int(wide.dropna().shape[0]))

# rate is a fraction per 8h; annualise by 3*365
ANN = 3 * 365 * 100


def ann_stats(panel, label):
    p = panel.dropna()
    if p.shape[0] == 0:
        print(f"{label}: no common rows")
        return None
    per_sym_mean = p.mean() * ANN
    per_sym_sd = p.std() * ANN
    ew = per_sym_mean.mean()
    print(f"\n=== {label}  n_settlements={p.shape[0]}  n_symbols={p.shape[1]}")
    print(f"  equal-weight gross carry         : {ew:+7.2f}%/yr")
    print(f"  median symbol                    : {per_sym_mean.median():+7.2f}%/yr")
    print(f"  min / max symbol                 : {per_sym_mean.min():+7.2f} / {per_sym_mean.max():+7.2f}")
    print(f"  n symbols negative               : {int((per_sym_mean < 0).sum())}/{p.shape[1]}")
    print(f"  median symbol sd/mean            : {(per_sym_sd / per_sym_mean.abs()).median():.2f}")
    print(f"  median symbol % settlements neg  : {(p < 0).mean().median()*100:.1f}%")
    return per_sym_mean, per_sym_sd


ann_stats(wide, "FULL SAMPLE")

# --- yearly decay ---
print("\n--- annualised gross carry by calendar year (equal weight, symbols present) ---")
yr = (wide * ANN).groupby(wide.index.year).mean()
n_present = wide.groupby(wide.index.year).count().gt(0).sum(axis=1)
for y, row in yr.iterrows():
    print(f"  {y}: {row.mean():+7.2f}%/yr   (n_symbols={int(n_present[y])})")

# --- pre/post 2022 split, to compare with He et al. Table 4 Panel B ---
ann_stats(wide[wide.index < "2022-01-01"], "BEFORE 2022-01-01")
ann_stats(wide[wide.index >= "2022-01-01"], "FROM 2022-01-01")
ann_stats(wide[wide.index >= "2023-01-01"], "FROM 2023-01-01")
ann_stats(wide[wide.index >= "2025-01-01"], "FROM 2025-01-01")
ann_stats(wide.tail(365), "TRAILING 365 SETTLEMENTS (~1 year)")
ann_stats(wide.tail(90), "TRAILING 90 SETTLEMENTS (~30 days)")

# --- Q6: common factor in funding CHANGES ---
print("\n--- Q6 common factor: correlation of 8h funding CHANGES ---")
d = wide.diff().dropna()
d = d.dropna(axis=1, how="all")
cols = [c for c in d.columns if d[c].notna().sum() > len(d) * 0.5]
d = d[cols]
C = d.corr()
off = C.values[np.triu_indices(len(cols), 1)]
print(f"  n={len(d)} common changes, {len(cols)} symbols")
print(f"  MEAN off-diagonal correlation : {off.mean():.3f}")
print(f"  median                        : {np.median(off):.3f}")
print(f"  min / max                     : {off.min():.3f} / {off.max():.3f}")
rho = off.mean()
n = len(cols)
print(f"  implied EW portfolio vol / single-name vol at this rho: "
      f"{(rho + (1-rho)/n) ** 0.5:.3f}   (perfect independence would be "
      f"{(1/n) ** 0.5:.3f})")

ev = np.linalg.eigvalsh(C.values)
ev = ev[::-1]
print(f"  eigenvalues: {np.round(ev[:5], 2)} of {n}")
print(f"  PC1 share of equal-variance cross-sectional variance: {ev[0]/n*100:.0f}%")
print(f"  PC1+PC2+PC3 share: {ev[:3].sum()/n*100:.0f}%")

# same for the LEVELS, since the clamp makes levels sticky
Cl = wide[cols].dropna().corr()
offl = Cl.values[np.triu_indices(len(cols), 1)]
print(f"  mean off-diagonal corr of funding LEVELS: {offl.mean():.3f}")

print("\n  BTC/ETH vs alt mean correlation with BTC funding changes:")
if "BTC" in cols:
    b = C["BTC"].drop("BTC")
    print(f"    {b.mean():.3f}  (median {b.median():.3f})")

pd.DataFrame(C).to_csv(OUT / "funding_change_corr.csv")
yr.to_csv(OUT / "carry_by_year_recomputed.csv")
print(f"\nwrote {OUT/'funding_change_corr.csv'} and {OUT/'carry_by_year_recomputed.csv'}")
