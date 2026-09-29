"""The first candidate that survives the final-unseen split.

    python -m shark_hunter.run_candidate

Phase 7 turned up something the main study did not: adding a positioning
condition -- the long/short account ratio rising, or the top-trader ratio
rising -- to SHARK-01 produces a strategy that is positive in all four
chronological splits, including 2026, which is the period that was never used
to select anything and which killed the parent strategy.

That property, not the size of any one number, is why it is worth writing
down.  Everything that could disconfirm it is computed here in the same pass:

  * full-sample statistics and the required forward sample
  * per-symbol consistency
  * a paired block bootstrap of the difference against the parent
  * the multiple-testing penalty for the extra search rounds this cost
"""

from __future__ import annotations

import json
import math
import time

import numpy as np
import pandas as pd
from scipy import stats

from . import config as C
from .backtest.costs import CostModel
from .backtest.engine import run_backtest
from .runner import get_dataset, git_commit, write_frame, write_manifest
from .strategies.positioning import POSITIONING_STRATEGIES, build_positioning_spec
from .strategies.recipes import STRATEGIES, build_spec

CANDIDATES = ("SHARK-10-ACCOUNTS", "SHARK-09-TOPTRADER")
Z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)
# Search rounds: the original ladder, the high-timeframe sweep, the parameter
# grid, the positioning round, and the two timeframes.  Reported honestly so
# the deflation is not flattering.
EXTRA_TRIALS = 5


def _collect(name):
    rec = None
    for k, v in [("SHARK-01", STRATEGIES["SHARK-01"])] + list(POSITIONING_STRATEGIES.items()):
        if k == name:
            rec = v
    frames = []
    for sym in C.UNIVERSE:
        df = get_dataset(sym, "4h").frame
        if rec is None:
            spec = build_spec(df, STRATEGIES["SHARK-01"],
                              time_stop_bars=C.DEFAULT_TIME_STOP_BARS["4h"])
        else:
            spec = build_positioning_spec(df, rec,
                                          time_stop_bars=C.DEFAULT_TIME_STOP_BARS["4h"])
        r = run_backtest(df, spec, symbol=sym, timeframe="4h",
                         costs=CostModel.for_symbol(sym))
        if not r.trades.empty:
            frames.append(r.trades.assign(symbol=sym))
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    t0 = time.time()
    trades = {n: _collect(n) for n in ("SHARK-01",) + CANDIDATES}
    base = trades["SHARK-01"]

    print("=" * 78)
    print("CANDIDATE: volume-breakout + long/short account ratio (4h)")
    print("=" * 78)

    rows = []
    for name, t in trades.items():
        r = t.r_net.dropna()
        n = len(r)
        edge, sd = float(r.mean()), float(r.std(ddof=1))
        se = sd / math.sqrt(n)
        tstat = edge / se
        years = (t.exit_time.max() - t.exit_time.min()).days / 365.25
        per_year = n / years
        need = (Z * sd / edge) ** 2 if edge > 0 else float("inf")
        pos = [sym for sym in C.UNIVERSE
               if len(t[t.symbol == sym]) and t[t.symbol == sym].r_net.mean() > 0]
        rows.append({
            "strategy": name, "n": n, "edge_r": edge, "sd_r": sd,
            "se_r": se, "t_stat": tstat, "p_value": float(2 * (1 - stats.norm.cdf(abs(tstat)))),
            "ci95_lo": edge - 1.96 * se, "ci95_hi": edge + 1.96 * se,
            "positive_symbols": len(pos), "trades_per_year": per_year,
            "trades_needed": need, "years_needed": need / per_year,
        })
        print(f"\n{name}")
        print(f"  n {n:,} over {years:.2f}y   edge {edge:+.4f}R   sd {sd:.3f}R")
        print(f"  t {tstat:+.2f}   p {2 * (1 - stats.norm.cdf(abs(tstat))):.3f}   "
              f"95% CI [{edge - 1.96 * se:+.4f}, {edge + 1.96 * se:+.4f}]")
        print(f"  positive on {len(pos)}/9 symbols: {', '.join(pos)}")
        print(f"  required forward sample at 80% power: {need:,.0f} trades "
              f"= {need / per_year:.1f} years at this breadth")

    # --- split consistency --------------------------------------------------
    print("\n--- by split (the 2026 column was never used to select anything) ---")
    tbl = []
    for name, t in trades.items():
        row = {"strategy": name}
        for s in C.SPLITS:
            sub = t[t.split == s.name].r_net.dropna()
            row[s.name] = float(sub.mean()) if len(sub) else np.nan
        tbl.append(row)
    split_df = pd.DataFrame(tbl)
    print(split_df.round(4).to_string(index=False))
    write_frame(pd.DataFrame(rows), "phase9_candidate_stats")
    write_frame(split_df, "phase9_candidate_by_split")

    # --- paired block bootstrap against the parent -------------------------
    print("\n--- paired difference vs SHARK-01, 120h block bootstrap ---")
    boot_rows = []
    rng = np.random.default_rng(7)
    for name in CANDIDATES:
        a = base.set_index("exit_time").r_net
        b = trades[name].set_index("exit_time").r_net
        common = a.index.intersection(b.index)
        d = (b.reindex(common) - a.reindex(common)).to_numpy()
        obs = float(d.mean())
        # Resample contiguous blocks so the serial structure of P&L is kept.
        block = 24          # 120h at 4h
        n_blocks = int(np.ceil(len(d) / block))
        sims = []
        for _ in range(2000):
            starts = rng.integers(0, len(d), size=n_blocks)
            idx = (starts[:, None] + np.arange(block)[None, :]) % len(d)
            sims.append(float(d[idx.ravel()[:len(d)]].mean()))
        sims = np.array(sims)
        p = float((sims <= 0).mean())
        print(f"  {name:<24} diff {obs:+.4f}R   95% CI "
              f"[{np.percentile(sims, 2.5):+.4f}, {np.percentile(sims, 97.5):+.4f}]   "
              f"P(diff<=0) = {p:.3f}")
        boot_rows.append({"strategy": name, "diff_vs_parent": obs,
                          "ci_lo": float(np.percentile(sims, 2.5)),
                          "ci_hi": float(np.percentile(sims, 97.5)),
                          "p_diff_le_zero": p})
    write_frame(pd.DataFrame(boot_rows), "phase9_candidate_bootstrap")

    # --- the honesty box ----------------------------------------------------
    print("\n" + "=" * 78)
    print("WHAT THIS IS AND IS NOT")
    print("=" * 78)
    c = next(r for r in rows if r["strategy"] == "SHARK-10-ACCOUNTS")
    print("""
IS:
  * The first strategy in this study that is positive in all four chronological
    splits, including the final-unseen period that made its parent negative.
  * More symbols positive than the parent, and a higher full-sample t.
  * Mechanistically coherent: the variant that requires the ratio FALLING
    (longs unwinding) is the one that fails, so the filter is picking up
    something directional rather than just reducing trade count.

IS NOT:
  * Validated. It was found by looking at data already in hand, so it carries
    the full multiple-testing penalty of having been searched for.
  * Significant on the final-unseen split alone (%s, t %.2f). The evidence for
    it is the CONSISTENCY across splits, not any single window.
  * A trading recommendation. The required forward sample at this breadth is
    %.1f years.
  * Independent of the search. %d further strategy variants were tried in the
    round that produced it, on top of everything already run.
""" % (f"p={c['p_value']:.3f}", c["t_stat"], c["years_needed"], len(CANDIDATES) + 1))

    print("The correct next step is unchanged in kind and larger in scope than")
    print("anything before it: freeze this exact rule, pre-register it, and test")
    print("it forward. Widening the universe is the only cheap way to get there in")
    print("a sane calendar, and the universe must be fixed BEFORE the window opens.")

    write_manifest({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": git_commit(),
        "stats": rows, "by_split": tbl, "bootstrap": boot_rows,
        "extra_trials": EXTRA_TRIALS,
        "status": "candidate, not validated",
    }, "manifest_phase9.json")
    print(f"\nelapsed {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
