"""
Measure rho_resid and sigma_cs off the project's own corpus. Corrected:
close price is column 4 (column 5 is volume), and symbols are aligned on the
bar timestamp rather than on row position.
"""

import glob
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)

ROOT = Path(r"user_data/data/binance_v2/archive/klines")


def load(sym, tf="1h"):
    files = sorted(glob.glob(str(ROOT / sym / tf / f"{sym}-{tf}-*.zip")))
    ts, cl = [], []
    for f in files:
        with zipfile.ZipFile(f) as z:
            with z.open(z.namelist()[0]) as fh:
                raw = fh.read()
        df = pd.read_csv(io.BytesIO(raw), header=None)
        if df.iloc[0, 0] == "open_time":          # later archives carry a header
            df = df.iloc[1:]
        ts.append(pd.to_numeric(df.iloc[:, 0], errors="coerce").to_numpy())
        cl.append(pd.to_numeric(df.iloc[:, 4], errors="coerce").to_numpy())
    t = np.concatenate(ts); c = np.concatenate(cl)
    ok = ~np.isnan(t) & ~np.isnan(c) & (c > 0)
    idx = pd.to_datetime(t[ok], unit="ms", utc=True)
    s = pd.Series(c[ok], index=idx).sort_index()
    return s[~s.index.duplicated()]


syms = sorted(p.name for p in ROOT.iterdir() if p.is_dir())
print(f"symbols on disk: {syms}\n")

series = {}
for s in syms:
    series[s] = load(s)
    if len(series[s]):
        print(f"  {s}: {len(series[s]):,} bars  {series[s].index[0].date()} -> {series[s].index[-1].date()}")

px = pd.DataFrame(series).dropna()
print(f"\naligned intersection: {px.shape[0]:,} hourly bars, "
      f"{px.index[0].date()} -> {px.index[-1].date()}, {px.shape[1]} symbols\n")

rets = px.pct_change().dropna()
alts = [c for c in rets.columns if c != "BTCUSDT"]

print("=" * 78)
print("A. RAW pairwise correlation of hourly returns")
print("=" * 78)
raw = rets.corr()
print(raw.round(3).to_string())
pr = [raw.loc[a, b] for i, a in enumerate(alts) for b in alts[i + 1:]]
print(f"\nmean pairwise RAW correlation among alts: {np.mean(pr):.3f}")

print()
print("=" * 78)
print("B. MARKET-NEUTRAL RESIDUALS -- BTC-orthogonalised by regression, not demeaning")
print("=" * 78)
print("With only a handful of names, cross-sectional demeaning forces the")
print("residuals to sum to zero and manufactures negative correlation, so each")
print("alt is instead regressed on BTC and the regression residual is kept.\n")
b = rets["BTCUSDT"]
resid = {}
for c in alts:
    beta = rets[c].cov(b) / b.var()
    resid[c] = rets[c] - beta * b
    print(f"  {c}: beta vs BTC = {beta:.3f}, residual sd = {resid[c].std():.5f} "
          f"(raw sd {rets[c].std():.5f}, so {resid[c].std()/rets[c].std():.2f}x left)")
R = pd.DataFrame(resid)
rc = R.corr()
print()
print(rc.round(3).to_string())
prr = [rc.loc[a, b2] for i, a in enumerate(alts) for b2 in alts[i + 1:]]
rho = float(np.mean(prr))
print(f"\nMEASURED rho_resid among alts: {rho:.3f}")

print()
print("=" * 78)
print("C. CROSS-SECTIONAL DISPERSION (what a cross-sectional book trades against)")
print("=" * 78)
rows = []
for label, days in [("1d", 1), ("7d", 7), ("14d", 14), ("30d", 30)]:
    bars = 24 * days
    grp = np.arange(len(rets)) // bars
    h = rets.groupby(grp).sum()
    disp = h.std(axis=1)
    spread = h.max(axis=1) - h.min(axis=1)
    rows.append({"horizon": label, "sigma_cs_%": disp.mean() * 100,
                 "mean_maxmin_spread_%": spread.mean() * 100})
    print(f"  {label:>4}: cross-sectional sigma = {disp.mean()*100:6.2f}%   "
          f"mean best-minus-worst = {spread.mean()*100:6.2f}%")

print()
print("=" * 78)
print("D. FRONTIER INPUTS: assumed vs measured")
print("=" * 78)
print(f"  rho_resid: assumed 0.20 -> measured {rho:.3f}")
for N in (5, 20, 50, 100, 200):
    d = np.sqrt((1 + (N - 1) * rho) / N)
    print(f"  N={N:>3}: diversification factor = {d:.3f}"
          f"   (a 5-name book is {np.sqrt(N):.1f}x diversified, a 100-name book "
          f"{1/np.sqrt(100):.2f}x the single-name vol)")

print()
print("=" * 78)
print("E. THE DECISIVE CONSTRAINT")
print("=" * 78)
print(f"  symbols available for a cross-sectional book: {px.shape[1]}")
print(f"  symbols the frontier needs for meaningful diversification: 50-200")
print("  A 5-name book is not a cross-sectional strategy. It is 5 individual")
print("  bets, and the diversification argument that makes the design affordable")
print("  does not exist at this width.")

pd.DataFrame(rows).to_csv("tmp_audit/measured_dispersion.csv", index=False)
print("\nwritten tmp_audit/measured_dispersion.csv")
