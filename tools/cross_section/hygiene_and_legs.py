"""Data hygiene and the leg split, before any cross-sectional verdict.

Two things must be settled before the pre-registered result is interpreted.

1. THE DATA ARTEFACT. The 2026 split produced a -10,020 bps rebalance. A
   dollar-neutral long/short book cannot lose 100% in a period; that requires a
   long leg at -100% or a short leg at +100%. The universe is built from
   `exchangeInfo`, which returns only currently-listed contracts, so a token
   that went to zero but is still quoted, or a venue data glitch, lands in the
   panel. This must be found and handled, or the 2026 number is meaningless.

2. THE LEG SPLIT. If the positive gross edge comes from the short leg alone,
   the "cross-sectional" result is a market-beta bet wearing a costume, and
   the long-short spread is measuring the market, not the ranking. A
   dollar-neutral book whose short leg is doing all the work is not a
   cross-sectional alpha result.
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

BARS_PER_YEAR = 6 * 365.25
MIN_WEEKS = 26
NEED = MIN_WEEKS * 7 * BARS_PER_YEAR / 365.25
# A perpetual can move a lot in 4h, but +100% or -100% in a single bar is a
# redenomination, a chain migration or a relisting far more often than it is a
# trade. Left in, one such symbol compounds over a 42-bar hold into a +4.4e17
# bps "return" and silently destroys every portfolio statistic it touches.
MAX_BAR_RETURN = 1.0
MIN_BAR_RETURN = -1.0


def clean_load(verbose: bool = True) -> tuple[pd.DataFrame, dict]:
    """Load the universe, dropping unusable files and discontinuous series."""
    frames, stats = {}, {"empty_files": 0, "unreadable": 0, "short_history": 0,
                         "zero_price": 0, "discontinuous": 0}
    for p in glob.glob("shark_data/universe/*_4h.csv.gz"):
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
        except Exception:                                   # noqa: BLE001
            stats["unreadable"] += 1
            try:
                os.remove(p)                               # empty file from a dead fetch
                stats["empty_files"] += 1
            except OSError:
                pass
            continue
        if len(df) < NEED:
            stats["short_history"] += 1
            continue
        c = pd.to_numeric(df["close"], errors="coerce")
        c = c[c > 0]                                        # a zero or negative
        if c.empty:                                         # price is not a price
            stats["zero_price"] += 1
            continue
        r = c.pct_change()
        # A perpetual cannot move +190% in 4h except through a redenomination,
        # migration or relisting. Such a series is unusable, and left in place
        # one token compounds over a 42-bar hold into a +4.4e17 bps "return".
        if r.max() > MAX_BAR_RETURN or r.min() < MIN_BAR_RETURN:
            stats["discontinuous"] += 1
            continue
        frames[os.path.basename(p).split("_")[0]] = c
    panel = pd.DataFrame(frames).sort_index()
    if verbose:
        print(f"loaded {panel.shape[1]} symbols x {len(panel):,} bars")
        print(f"  dropped: {stats}")
    return panel, stats


def find_impossible(panel: pd.DataFrame) -> pd.DataFrame:
    """Per-bar returns that a perpetual contract cannot produce."""
    r = panel.pct_change()
    bad = pd.DataFrame({
        "max_4h_return": r.max(),
        "min_4h_return": r.min(),
        "n_gt_+200pct": (r > 2).sum(),
        "n_lt_-50pct": (r < -0.5).sum(),
        "first": panel.apply(lambda s: s.index[0]),
    })
    return bad[(bad["n_gt_+200pct"] > 0) | (bad["n_lt_-50pct"] > 0)
               | (bad["max_4h_return"] > 1.0)].sort_values("min_4h_return")


def leg_split(panel: pd.DataFrame, lookback: int = 42, step: int = 42,
              tercile: int = 3) -> pd.DataFrame:
    """P&L of the long leg, the short leg, and the spread, per split."""
    sig = panel.pct_change(lookback)
    n = sig.notna().sum(axis=1).clip(lower=1)
    k = np.maximum(1, (n // tercile).astype(float))
    rank = sig.rank(axis=1, ascending=False, na_option="keep")
    long_m = rank.le(k, axis=0) & sig.notna()
    short_m = rank.ge(n - k + 1, axis=0) & sig.notna()
    w_l = long_m.div(long_m.sum(axis=1).replace(0, np.nan), axis=0).where(long_m)
    w_s = short_m.div(short_m.sum(axis=1).replace(0, np.nan), axis=0).where(short_m)

    path = (1.0 + panel.pct_change()).cumprod()
    up = path.shift(-1) / path
    leg_l = (w_l * up).sum(axis=1)
    leg_s = -(w_s * up).sum(axis=1)

    def compound(x):
        p = pd.Series(1.0, index=panel.index)
        for k2 in range(1, step + 1):
            p = p * (1.0 + x.shift(-k2)).fillna(0.0)
        return p - 1.0

    gl, gs = compound(leg_l), compound(leg_s)
    gl = gl.reindex(gl.index[::step])
    gs = gs.reindex(gs.index[::step])
    spread = (gl + gs).reindex(gl.index)

    splits = {"develop": ("2023-01-01", "2025-01-01"),
              "oos": ("2025-01-01", "2026-01-01"),
              "final_unseen": ("2026-01-01", "2026-09-01")}
    rows = []
    for name, (a, b) in splits.items():
        s = spread[(spread.index >= a) & (spread.index < b)].dropna()
        l = gl[(gl.index >= a) & (gl.index < b)].dropna()
        s2 = gs[(gs.index >= a) & (gs.index < b)].dropna()
        mkt = panel[(panel.index >= a) & (panel.index < b)].pct_change(step).mean(axis=1)
        rows.append({
            "split": name, "n": len(s),
            "long_leg_bps": float(l.mean() * 1e4) if len(l) else np.nan,
            "short_leg_bps": float(s2.mean() * 1e4) if len(s2) else np.nan,
            "spread_bps": float(s.mean() * 1e4) if len(s) else np.nan,
            "equal_weight_market_bps": float(mkt.mean() * 1e4),
            "n_symbols": int(panel[(panel.index >= a) & (panel.index < b)].notna().sum().max()),
        })
    return pd.DataFrame(rows)


def main() -> int:
    print("=" * 78)
    print("DATA HYGIENE + LEG SPLIT")
    print("=" * 78)
    panel, stats = clean_load()

    print("\n--- symbols with impossible 4h returns ---")
    bad = find_impossible(panel)
    if bad.empty:
        print("  none")
    else:
        print(bad.to_string())

    print("\n--- leg split: is the short leg doing all the work? ---")
    f = leg_split(panel)
    print(f.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    for _, r in f.iterrows():
        tot = r["long_leg_bps"] + r["short_leg_bps"]
        if abs(tot) > 1e-9:
            share = abs(r["short_leg_bps"]) / abs(tot)
            print(f"  {r['split']:<14} short leg is {share:.0%} of the total gross P&L"
                  f"   (market beta over the same window: "
                  f"{r['equal_weight_market_bps']:+.1f} bps/rebalance)")
    f.to_csv("shark_results/crosssection_leg_split.csv", index=False)
    print("\nwritten: shark_results/crosssection_leg_split.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
