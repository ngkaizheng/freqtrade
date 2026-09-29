"""
E#9 -- Part A: is a stop loss information, or noise?

Run before the strategy, and the strategy is not run if this fails. A stop that
fires before a fall is worth something; a stop that fires before a rally is a
cost, and leverage turns a cost into a ruin.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e9_stop_diagnostic.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 240)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
TOP_N = 50
STOPS = (0.10, 0.15, 0.20, 0.30)
FWD = 20
REBASE = -0.90


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    closes, vols = {}, {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        d = d[d["quote_volume"] > 0]
        if (d["close"].pct_change() < REBASE).any():
            continue
        closes[sym] = d["close"]
        vols[sym] = d["quote_volume"]
    return (pd.concat(closes, axis=1).sort_index(),
            pd.concat(vols, axis=1).sort_index())


def main() -> None:
    px, qv = load()
    uni = list(qv.median().nlargest(TOP_N).index)
    px = px[uni]
    eq = px.mean(axis=1).ffill()
    r = eq.pct_change(fill_method=None).fillna(0.0)
    n = len(eq)
    print(f"basket: top {TOP_N} liquid names, {n} daily bars, "
          f"{eq.index[0].date()} -> {eq.index[-1].date()}")
    print(f"daily vol {r.std()*100:.2f}%  (annualised {r.std()*math.sqrt(365)*100:.0f}%)\n")

    fwd = (eq.shift(-FWD) / eq - 1.0).dropna()

    print("=" * 104)
    print(f"PART A -- after a trailing stop fires, what does the basket do over {FWD} days?")
    print("=" * 104)
    print("""
  Re-entry is a fixed COOLDOWN, not "wait for a new high". An earlier version
  used new-high-only and the stop fired 2-3 times in six years -- this basket
  makes new all-time highs so rarely that the rule sits out of the market almost
  permanently. That is informative about the basket but useless as a
  diagnostic, and the cooldown is the structure Part B actually specifies, so
  the diagnostic has to measure that.
""")
    print(f"{'stop':>6} {'cool':>5} {'fires':>7} {'fwd mean%':>11} {'fwd t':>8} "
          f"{'placebo%':>10} {'placebo t':>10} {'diff t':>8}")
    print("-" * 70)

    results = {}
    rng = np.random.default_rng(20260926)
    for stop in STOPS:
        for cool in (5, 20):
            in_pos = True
            peak = eq.iloc[0]
            wait = 0
            fires = []
            for i in range(1, n):
                if in_pos:
                    peak = max(peak, eq.iloc[i])
                    if eq.iloc[i] / peak - 1.0 <= -stop:
                        in_pos = False
                        fires.append(eq.index[i])
                        wait = cool
                elif wait > 0:
                    wait -= 1
                else:
                    in_pos = True
                    peak = eq.iloc[i]
            if len(fires) < 20:
                print(f"{stop:>6.0%} {cool:>5} {len(fires):>7}   too few events")
                continue
            after = fwd.reindex(fires).dropna()
            pool = fwd.index[:-1]
            placebo_idx = rng.choice(pool, size=min(len(fires), len(pool)), replace=False)
            pl = fwd.reindex(placebo_idx).dropna()
            t_after = after.mean() / after.std(ddof=1) * math.sqrt(len(after))
            t_pl = pl.mean() / pl.std(ddof=1) * math.sqrt(len(pl))
            se = math.sqrt(after.var(ddof=1) / len(after) + pl.var(ddof=1) / len(pl))
            t_diff = (after.mean() - pl.mean()) / se
            results[(stop, cool)] = {"fires": len(fires), "fwd_mean": float(after.mean()),
                                     "t_after": float(t_after), "placebo": float(pl.mean()),
                                     "t_diff": float(t_diff)}
            print(f"{stop:>6.0%} {cool:>5} {len(fires):>7} {after.mean()*100:>11.2f} "
                  f"{t_after:>8.2f} {pl.mean()*100:>10.2f} {t_pl:>10.2f} {t_diff:>8.2f}")

    print()
    print("=" * 104)
    print("GATES (pre-registered)")
    print("=" * 104)
    any_pass = False
    for (stop, cool), res in results.items():
        a1 = res["t_after"] <= -1.645
        a2 = res["t_diff"] <= -1.645
        ok = a1 and a2
        any_pass = any_pass or ok
        print(f"  stop {stop:.0%} cool {cool:>2}d   A1 forward negative "
              f"{'PASS' if a1 else 'FAIL'} (t={res['t_after']:+.2f})    "
              f"A2 beats placebo  {'PASS' if a2 else 'FAIL'} (t={res['t_diff']:+.2f})"
              f"{'   <-- BOTH' if ok else ''}")
    print(f"\n  PART A VERDICT: "
          f"{'PASS -- Part B may be run' if any_pass else 'FAIL -- DO NOT RUN PART B'}")
    if not any_pass:
        print("""
  A stop that is not followed by a fall is a cost, and leverage converts a cost
  into a ruin. This is the specific mechanism by which "high leverage plus a
  tight stop" loses money steadily in crypto, and on this evidence it should
  not be levered at all.""")


if __name__ == "__main__":
    main()
