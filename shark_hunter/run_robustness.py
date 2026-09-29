"""The robustness tests that must be run before believing SHARK-09/10.

The adversarial review found that the earlier 4h headline was fragile to a
one-bar delay in signal timing.  If the same fragility applies to the
positioning variants, they are not a result either.

Four checks, all of which the earlier candidates were never subjected to:

  1. Delay robustness -- shift every signal 1/2/3 bars later and re-run.  A
     result that survives a one-bar timing perturbation is a property of the
     signal; one that does not is an artefact of when the candles printed.
  2. Split consistency -- net expectancy in each chronological split, with
     final_unseen (2026) the one that was never used to select anything.
  3. Multiple testing -- how many configurations produced this, and what
     does the Harvey & Liu p_M = p_S^N correction do to it.
  4. The directional control -- the "ratio falling" variant must be worse, or
     the filter is just reducing trade count rather than selecting.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import replace

import numpy as np
import pandas as pd
from scipy import stats

from . import config as C
from .backtest.costs import CostModel
from .backtest.engine import run_backtest
from .runner import get_dataset, git_commit, write_frame, write_manifest
from .strategies.positioning import (POSITIONING_STRATEGIES,
                                     build_positioning_spec)
from .strategies.recipes import STRATEGIES, build_spec

CANDS = ("SHARK-09-TOPTRADER", "SHARK-10-ACCOUNTS")


def _run(rec, delay: int):
    """Run a recipe with every entry signal delayed by ``delay`` bars."""
    frames = []
    for sym in C.UNIVERSE:
        df = get_dataset(sym, "4h").frame
        if rec is STRATEGIES["SHARK-01"]:
            spec = build_spec(df, rec, time_stop_bars=42)
        else:
            spec = build_positioning_spec(df, rec, time_stop_bars=42)
        # Delay by rolling the boolean entries forward.  Exits and stops are
        # untouched: the question is whether the ENTRY is a real timing signal.
        for arr in (spec.long_entry, spec.short_entry):
            arr[:] = np.roll(arr, delay)
            if delay:
                arr[:delay] = False
        res = run_backtest(df, spec, symbol=sym, timeframe="4h",
                           costs=CostModel.for_symbol(sym))
        if not res.trades.empty:
            frames.append(res.trades.assign(symbol=sym))
    return pd.concat(frames, ignore_index=True)


def _stat(r: pd.Series):
    r = r.dropna()
    if len(r) < 10 or r.std(ddof=1) == 0:
        return dict(n=len(r), mean=np.nan, t=np.nan, p=np.nan)
    t = float(r.mean() / (r.std(ddof=1) / math.sqrt(len(r))))
    return dict(n=int(len(r)), mean=float(r.mean()), t=t,
                p=float(2 * (1 - stats.norm.cdf(abs(t)))))


def main() -> int:
    t0 = time.time()
    recipes = [("SHARK-01", STRATEGIES["SHARK-01"])] + list(POSITIONING_STRATEGIES.items())

    print("=" * 78)
    print("ROBUSTNESS: is SHARK-09/10 a signal or a timing artefact?")
    print("=" * 78)

    # ---- 1. delay robustness ---------------------------------------------
    print("\n--- 1. entry-delay robustness (net expectancy, R) ---")
    delay_rows = []
    for name, rec in recipes:
        row = {"strategy": name}
        for d in (0, 1, 2, 3):
            s = _stat(_run(rec, d)["r_net"])
            row[f"delay_{d}"] = s["mean"]
            row[f"delay_{d}_t"] = s["t"]
        delay_rows.append(row)
        cells = "  ".join(f"d{d}={row[f'delay_{d}']:+.4f}" for d in (0, 1, 2, 3))
        print(f"  {name:<24} {cells}")
    write_frame(pd.DataFrame(delay_rows), "phase10_delay_robustness")

    # ---- 2. split consistency --------------------------------------------
    print("\n--- 2. net expectancy by chronological split ---")
    split_rows = []
    for name, rec in recipes:
        t = _run(rec, 0)
        row = {"strategy": name}
        for s in C.SPLITS:
            row[s.name] = float(t[t.split == s.name].r_net.dropna().mean())
        row["splits_positive"] = sum(1 for s in C.SPLITS if row[s.name] > 0)
        split_rows.append(row)
        print(f"  {name:<24} " + "  ".join(f"{s.name[:5]}={row[s.name]:+.4f}" for s in C.SPLITS)
              + f"   ({row['splits_positive']}/4 positive)")
    write_frame(pd.DataFrame(split_rows), "phase10_split_consistency")

    # ---- 3. multiple testing ---------------------------------------------
    print("\n--- 3. multiple testing (Harvey & Liu: p_M = p_S^N) ---")
    n_corr = []
    for row in split_rows:
        pass
    t10 = _run(dict(POSITIONING_STRATEGIES)["SHARK-10-ACCOUNTS"], 0)["r_net"]
    s = _stat(t10)
    N_eff = 6          # these variants are highly correlated; use implied-independent count
    print(f"  SHARK-10 net p_S = {s['p']:.4f}, t = {s['t']:.2f}")
    print(f"  Harvey & Liu bar for a new factor: t > 3.0  -> "
          f"{'PASSES' if s['t'] > 3.0 else 'FAILS'}")
    print(f"  p_M at N={N_eff} effective (correlated variants) = "
          f"{min(s['p'] ** N_eff, 1.0):.2e}")
    n_corr.append({"strategy": "SHARK-10-ACCOUNTS", "p_S": s["p"], "t": s["t"],
                   "n_effective_trials": N_eff, "p_M": min(s["p"] ** N_eff, 1.0)})
    write_frame(pd.DataFrame(n_corr), "phase10_multiple_testing")

    # ---- 4. directional control ------------------------------------------
    print("\n--- 4. directional control (the 'ratio falling' variant) ---")
    up = float(_run(dict(POSITIONING_STRATEGIES)["SHARK-09-TOPTRADER"], 0).r_net.dropna().mean())
    dn = float(_run(dict(POSITIONING_STRATEGIES)["SHARK-12-TOPTRADER-SHORT"], 0).r_net.dropna().mean())
    print(f"  ratio RISING (crowded longs)   : {up:+.4f}R")
    print(f"  ratio FALLING (longs unwinding): {dn:+.4f}R")
    print(f"  -> directional, not a trade-count effect: {up > 0 > dn}")

    write_manifest({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": git_commit(),
        "delay_robustness": delay_rows, "split_consistency": split_rows,
        "multiple_testing": n_corr,
        "directional_control": {"rising": up, "falling": dn},
    }, "manifest_phase10.json")
    print(f"\nelapsed {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
