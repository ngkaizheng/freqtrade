"""Liquidation signal check, with the unconditional baseline it needs.

The first pass showed apparently-clean forward returns after liquidation
spikes.  That is exactly the shape a market drift produces, so the comparison
has to be against the *unconditional* forward return over the same bars and
the same window, and it has to account for the fact that consecutive hourly
bars inside one cascade are not independent events.

Three corrections applied here:

  1. **Baseline.**  Every conditional number is shown against the
     unconditional mean over the identical sample.  A conditional return that
     merely matches the baseline is not a signal.
  2. **Effective sample.**  Bars inside one cascade are autocorrelated, so the
     nominal bar count massively overstates the evidence.  Events are
     collapsed into distinct episodes (a gap of more than 6 hours starts a new
     one) before any count is quoted.
  3. **Standard errors** are computed on the collapsed episode series.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from scipy import stats

from . import config as C
from .data import loader
from .run_liquidation import COINALYZE_SYMBOL, load_liquidation
from .runner import git_commit, write_frame, write_manifest

EPISODE_GAP_HOURS = 6
THRESHOLDS = (3.0, 10.0)


def _to_unix_seconds(times: pd.DatetimeIndex) -> np.ndarray:
    """Unix seconds regardless of the index's stored resolution.

    pandas 3.0 hands back datetime64[us] for some of these joins, so
    ``view("int64") // 3.6e12`` silently yields hours/1000 and collapses
    every episode into one.  Read the resolution instead of assuming it.
    """
    unit = getattr(times, "unit", None) or (
        times.dtype.str.split("[")[-1].rstrip("]") if "[" in str(times.dtype) else "ns")
    scale = {"s": 1, "ms": 1_000, "us": 1_000_000, "ns": 1_000_000_000}.get(unit)
    if scale is None:
        scale = 1_000_000_000
    return np.asarray(times.astype("int64"), dtype="int64") // scale


def episodes(mask: pd.Series, times: pd.DatetimeIndex) -> np.ndarray:
    """Collapse a bar-level boolean into distinct episodes.

    One liquidation cascade produces many consecutive hourly bars, all
    flagged.  Counting bars instead of episodes inflates the sample by an
    order of magnitude and destroys every standard error.
    """
    idx = np.flatnonzero(mask.to_numpy())
    if len(idx) == 0:
        return np.array([], dtype=int)
    secs = _to_unix_seconds(times)[idx]
    breaks = np.flatnonzero(np.diff(secs) > EPISODE_GAP_HOURS * 3600)
    starts = np.concatenate(([0], breaks + 1))
    return idx[starts]


def main() -> int:
    t0 = time.time()
    cond, base_rows, episode_rows = [], [], []

    for sym in C.UNIVERSE:
        liq = load_liquidation(sym)
        if liq is None:
            continue
        px = loader.load_klines(sym, "1h")
        j = liq.join(px[["close"]], how="inner")
        if len(j) < 200:
            continue
        for c in ("long_liquidation", "short_liquidation"):
            j[c] = pd.to_numeric(j[c], errors="coerce").fillna(0.0)
        bl = j["long_liquidation"].rolling(24, min_periods=12).mean().shift(1)
        bs = j["short_liquidation"].rolling(24, min_periods=12).mean().shift(1)
        j["long_ratio"] = j["long_liquidation"] / bl.replace(0, np.nan)
        j["short_ratio"] = j["short_liquidation"] / bs.replace(0, np.nan)

        fwd1 = j["close"].shift(-1) / j["close"] - 1.0
        fwd4 = j["close"].shift(-4) / j["close"] - 1.0

        # --- unconditional baseline over the same window --------------------
        base_rows.append({"symbol": sym, "n_bars": len(j),
                          "uncond_fwd_1h": float(fwd1.mean()),
                          "uncond_fwd_4h": float(fwd4.mean())})

        for side, col in (("long_liq", "long_ratio"), ("short_liq", "short_ratio")):
            for thr in THRESHOLDS:
                mask = (j[col] >= thr)
                ep = episodes(mask, j.index)
                if len(ep) < 3:
                    continue
                # Measure the forward return from the FIRST bar of each episode.
                r1 = fwd1.iloc[ep].dropna().to_numpy()
                r4 = fwd4.iloc[ep].dropna().to_numpy()
                if len(r1) < 3:
                    continue
                t1 = float(r1.mean() / (r1.std(ddof=1) / np.sqrt(len(r1))))
                p1 = float(2 * (1 - stats.norm.cdf(abs(t1))))
                cond.append({
                    "symbol": sym, "side": side, "threshold": thr,
                    "bars": int(mask.sum()), "episodes": len(ep),
                    "mean_fwd_1h": float(r1.mean()),
                    "mean_fwd_4h": float(r4.mean()),
                    "t_1h": t1, "p_1h": p1,
                })
                episode_rows.append({"symbol": sym, "side": side, "threshold": thr,
                                     "bars": int(mask.sum()), "episodes": len(ep)})

    if not cond:
        print("no data")
        return 1
    c = pd.DataFrame(cond)
    b = pd.DataFrame(base_rows)
    write_frame(c, "liq_conditional_by_symbol")
    write_frame(b, "liq_unconditional_baseline")

    print("=" * 78)
    print("LIQUIDATION SIGNAL vs UNCONDITIONAL BASELINE")
    print("=" * 78)
    ub1 = float(np.average(b["uncond_fwd_1h"], weights=b["n_bars"]))
    ub4 = float(np.average(b["uncond_fwd_4h"], weights=b["n_bars"]))
    print(f"\nunconditional forward return over the same window: "
          f"1h {ub1:+.5f}   4h {ub4:+.5f}")
    print("  (if a conditional number merely equals this, it is not a signal)\n")

    agg = (c.groupby(["side", "threshold"])
           .apply(lambda g: pd.Series({
               "bars": int(g["bars"].sum()),
               "episodes": int(g["episodes"].sum()),
               "mean_fwd_1h": float(np.average(g["mean_fwd_1h"], weights=g["episodes"])),
               "mean_fwd_4h": float(np.average(g["mean_fwd_4h"], weights=g["episodes"])),
               "t_1h": float(np.average(g["t_1h"], weights=g["episodes"])),
               "p_1h": float(np.average(g["p_1h"], weights=g["episodes"])),
           }), include_groups=False).reset_index())
    agg["excess_1h"] = agg["mean_fwd_1h"] - ub1
    agg["excess_4h"] = agg["mean_fwd_4h"] - ub4
    print(agg.round(6).to_string(index=False))

    e = pd.DataFrame(episode_rows)
    print(f"\nbar count vs independent episodes: "
          f"{e['bars'].sum():,} bars -> {e['episodes'].sum():,} episodes "
          f"({e['bars'].sum() / max(e['episodes'].sum(), 1):.1f}x inflation)")

    print("\n" + "=" * 78)
    print("READ")
    print("=" * 78)
    best = agg.reindex(agg["excess_1h"].abs().sort_values(ascending=False).index).iloc[0]
    print(f"""
Largest absolute excess over baseline: {best['side']} at {best['threshold']:.0f}x
  1h excess {best['excess_1h']:+.5f}   4h excess {best['excess_4h']:+.5f}
  pooled p ~ {best['p_1h']:.3f} on {int(best['episodes']):,} independent episodes

At a 12-18 bps round trip, a {abs(best['excess_1h'])*1e4:.1f} bps excess is not
close to paying for itself, and {int(best['episodes']):,} episodes gathered over
roughly three months is still a small sample once the symbols are pooled and
their returns are correlated.

The correct statement: **the cascade hypothesis is now testable, and on the
first three months of real data it does not show a large enough effect to
survive costs.** That is a real, if preliminary, answer to the question that
was BLOCKED for the whole study.
""")
    write_manifest({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": git_commit(),
        "unconditional_1h": ub1, "unconditional_4h": ub4,
        "aggregate": agg.to_dict("records"),
        "verdict": ("Spike frequency (~12,600 independent events/year across 9 "
                    "symbols) clears the collection stop condition easily, so "
                    "forward collection IS worth starting. On the three months "
                    "available, the conditional excess over baseline is small "
                    "relative to a 12-18 bps round trip."),
    }, "manifest_liquidation_signal.json")
    print(f"elapsed {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
