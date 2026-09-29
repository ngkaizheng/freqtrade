"""Measure (a) settlement cadence per symbol over time, (b) share of settlements
paid at exactly Binance's fixed interest component (0.01%/8h), (c) implied
interest-component carry vs total carry, using the repo's funding corpus."""
import glob
import os

import numpy as np
import pandas as pd

ROOT = r"E:\FreqTrader\freqtrade\user_data\data\binance_funding"
FILES = sorted(glob.glob(os.path.join(ROOT, "*-funding.feather")))

IRATE_8H = 0.0001          # Binance default 0.01% per 8h funding interval
CUTOVER = pd.Timestamp("2025-05-02 08:00", tz="UTC")

rows = []
daily_counts = []
for f in FILES:
    sym = os.path.basename(f).split("-")[0]
    d = pd.read_feather(f)
    t = pd.to_datetime(d["fundingTime"], utc=True)
    r = pd.to_numeric(d["fundingRate"], errors="coerce").to_numpy()
    s = pd.Series(r, index=pd.DatetimeIndex(t)).sort_index()

    # (a) settlement cadence before/after the Binance cutover
    pre = s.loc[s.index < CUTOVER]
    post = s.loc[s.index >= CUTOVER]
    d_pre = pre.index.to_series().diff().dt.total_seconds().div(3600).median()
    d_post = post.index.to_series().diff().dt.total_seconds().div(3600).median()
    n_pre, n_post = len(pre), len(post)

    # (b) share of settlements at exactly the fixed interest component
    at_ir = np.isclose(s.to_numpy(), IRATE_8H, atol=5e-7)
    at_ir_pre = at_ir[s.index < CUTOVER].mean() if n_pre else np.nan
    at_ir_post = at_ir[s.index >= CUTOVER].mean() if n_post else np.nan

    # (c) mean carry per year vs the interest-component floor
    days = (s.index[-1] - s.index[0]).total_seconds() / 86400.0
    mean_per_settle = s.mean()
    s_per_year = len(s) / days
    total_carry_annual = mean_per_settle * s_per_year
    irate_annual = IRATE_8H * s_per_year      # scales with actual cadence

    rows.append(dict(
        symbol=sym, n=len(s), first=str(s.index[0].date()), last=str(s.index[-1].date()),
        days=round(days, 0), settles_per_day=round(s_per_year, 3),
        med_gap_h_pre=d_pre, med_gap_h_post=d_post,
        n_pre=n_pre, n_post=n_post,
        mean_rate=mean_per_settle, carry_ann_pct=100 * total_carry_annual,
        irate_ann_pct=100 * irate_annual,
        excess_ann_pct=100 * (total_carry_annual - irate_annual),
        pct_at_irate=100 * at_ir.mean(),
        pct_at_irate_pre=100 * at_ir_pre, pct_at_irate_post=100 * at_ir_post,
        pct_neg=100 * (s < 0).mean(),
        max_rate=s.max(), min_rate=s.min(),
    ))
    # daily count of settlements, for a cadence time series
    c = s.groupby(s.index.floor("D")).size()
    daily_counts.append(c.rename(sym))

out = pd.DataFrame(rows).sort_values("carry_ann_pct", ascending=False)
pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 40)
print("=== PER SYMBOL ===")
print(out.to_string(index=False, float_format=lambda v: f"{v:9.4f}"))

print("\n=== EQUAL-WEIGHT (all 20) ===")
print(f"  mean carry /yr              : {out.carry_ann_pct.mean():8.3f} %")
print(f"  mean interest-component /yr : {out.irate_ann_pct.mean():8.3f} %")
print(f"  mean EXCESS over interest    : {out.excess_ann_pct.mean():8.3f} %")
print(f"  mean share of settles at exactly 0.01% : {out.pct_at_irate.mean():6.2f} %")
print(f"  min/max share at exactly 0.01%        : {out.pct_at_irate.min():6.2f} / {out.pct_at_irate.max():.2f} %")

dc = pd.concat(daily_counts, axis=1)
print("\n=== SETTLEMENTS PER DAY, monthly mean (first 5 symbols) ===")
m = dc.resample("MS").mean().round(2)
print(m.iloc[:, :5].to_string())

print("\n=== EQUAL-WEIGHT SETTLEMENTS PER DAY, by month (all 20) ===")
mm = dc.mean(axis=1).resample("MS").mean().round(3)
print(mm.to_string())
