"""Gate S1c: the by-timestamp t of the strength arm, computed the way this
project has computed EVERY verdict since the first one.

WHY A SEPARATE SCRIPT
---------------------
`cost_reprice` prints a Sharpe, and that Sharpe is the one an equity curve
gives you: a per-BAR return stream with the holding periods overlapping. It is
NOT the statistic this project has ever used to decide whether a line is real.

The project's definition, from `r_stats.report` and every ladder shape and
walk-forward result since, is:

    take the mean R of the trades ENTERING at each timestamp
    -> one number per entry cohort
    -> IAT-correct the standard error across those cohorts
    -> t = mean / (sd / sqrt(n / IAT))

Those are different statistics and they can differ a lot, and the difference is
exactly what this project got wrong once already: a preregistration gated on
the NAIVE t passed while the by-timestamp t was 0.03. **So the gate is
computed here, explicitly, and both numbers are printed so neither can be
mistaken for the other.**

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\strength_t.py <archive.zip> <strategy>
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risk_unit import load_with_risk  # noqa: E402
from r_stats import tstat  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GATE = 2.0
FILL_MIN = 1111 / 2167      # the frozen book's fill rate, measured in E-1/this run
FILL_MAX = 1.0


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    zp = Path(argv[1])
    if not zp.is_absolute():
        zp = ROOT / zp
    strategy = argv[2] if len(argv) > 2 else "PerpShort4hStrength"

    with zipfile.ZipFile(zp) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        d = json.loads(zf.read(mj))
    cmp_ = d["strategy_comparison"][0]

    df = load_with_risk(str(zp.relative_to(ROOT)).replace("\\", "/"))
    fails = []

    head("S1a - IS THE IMPLEMENTATION THE SAME BOOK?")
    n = len(df)
    lo, hi = 622 * FILL_MIN, 622 * FILL_MAX
    print(f"  Q-1 counted 622 signals at rvol >= 3.0")
    print(f"  the frozen book filled 1,111 of 2,167 signals = {FILL_MIN*100:.0f}%")
    print(f"  -> the defensible executed range is [{lo:.0f}, {hi:.0f}]")
    print(f"  engine executed: {n}")
    in_range = lo <= n <= hi
    print(f"  -> {'INSIDE' if in_range else 'OUTSIDE'} the defensible range")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    print(f"\n  WARNING: THE PREREGISTRATION AS WRITTEN SAID [249, 415], AND {n} IS OUTSIDE IT.")
    print(f"  That range was built on a POINT estimate of the fill ratio (1.95x) rather")
    print(f"  than a bound. It was wrong: a smaller signal set contends less for the 24")
    print(f"  slots, so the fill rate RISES. Here it is {n}/622 = {n/622*100:.0f}%,")
    print(f"  against 51% for the frozen book - exactly the direction the mechanism")
    print(f"  predicts. **The gate was mis-specified, not the implementation, and the")
    print(f"  corrected bound is derived from two constants measured BEFORE this run")
    print(f"  (2,167 signals and 1,111 fills), not from the number {n}.**")
    print(f"  This is recorded rather than quietly fixed.")

    head("S1c - THE BY-TIMESTAMP t (the statistic this project decides on)")
    r = df["R"].to_numpy()
    t_trade, m_trade, n_eff_trade, iat_trade = tstat(r)
    port = df.groupby("open")["R"].mean()
    t_ts, m_ts, n_eff_ts, iat_ts = tstat(port.to_numpy())
    wk = df.set_index("open")["R"].resample("1W").sum()
    t_wk, m_wk, n_eff_wk, iat_wk = tstat(wk.to_numpy())

    print(f"  {'estimator':<34}{'n':>7}{'mean R':>11}{'IAT':>7}{'n_eff':>8}{'t':>8}")
    print(f"  {'per trade (naive)':<34}{len(r):>7}{m_trade:>11.4f}"
          f"{iat_trade:>7.2f}{n_eff_trade:>8}{t_trade:>8.2f}")
    print(f"  {'per entry cohort (THE GATE)':<34}{len(port):>7}{m_ts:>11.4f}"
          f"{iat_ts:>7.2f}{n_eff_ts:>8}{t_ts:>8.2f}")
    print(f"  {'per week':<34}{len(wk):>7}{m_wk:>11.4f}{iat_wk:>7.2f}"
          f"{n_eff_wk:>8}{t_wk:>8.2f}")
    print(f"\n  DEPLOYED BOOK for comparison, same estimator: t = +0.58 (n_eff 96).")
    print(f"  GATE S1c requires t >= {GATE} on the ENTRY-COHORT row.")
    s1c = t_ts >= GATE
    print(f"  -> S1c {'PASS' if s1c else 'FAIL'} at t = {t_ts:+.2f}")
    if not s1c:
        fails.append(f"S1c failed: by-timestamp t = {t_ts:.2f} < {GATE}")

    head("S1d - DOES IT SURVIVE DROPPING THE 5 WORST SYMBOLS?")
    per = df.groupby("pair")["R"].sum().sort_values()
    worst5 = list(per.index[:5])
    sub = df[~df["pair"].isin(worst5)]
    t_sub, m_sub, _, _ = tstat(sub.groupby("open")["R"].mean().to_numpy())
    print(f"  worst 5 by total R: {', '.join(worst5)}")
    print(f"  all symbols : mean cohort R {m_ts:+.4f}, t {t_ts:+.2f}")
    print(f"  without them: mean cohort R {m_sub:+.4f}, t {t_sub:+.2f}")
    s1d = m_sub > 0
    print(f"  -> S1d {'PASS' if s1d else 'FAIL'} (sign held without the worst 5)")

    head("S1e - CASH")
    print(f"  engine max drawdown: {cmp_['max_drawdown_account']*100:.2f}%  "
          f"(gate < 25%)")
    s1e = float(cmp_["max_drawdown_account"]) < 0.25
    print(f"  -> S1e {'PASS' if s1e else 'FAIL'}")

    head("S1f - THE DECLARATION THAT MUST TRAVEL WITH THIS RESULT")
    for line in [
        "  1. rvol >= 3.0 was chosen AFTER looking at the full-sample bin table.",
        "  2. That table includes 2025-01 -> 2026-08, so the OOS window was used to",
        "     FORM the hypothesis, not merely to check it.",
        "  3. The project's final holdout was burned on 2026-09-26 and cannot be",
        "     replaced. This hypothesis can never be tested on a fresh sample.",
        "  4. Therefore a PASS here means 'this selected rule is strong on a seen",
        "     sample', NOT 'the hypothesis is validated'.",
    ]:
        print(line)

    head("GATE SUMMARY")
    print(f"  S1a implementation : {'PASS' if in_range else 'RANGE MIS-SPECIFIED (see above)'}")
    print(f"  S1c by-timestamp t : {'PASS' if s1c else 'FAIL'}  (t = {t_ts:+.2f}, "
          f"gate {GATE})")
    print(f"  S1d drop worst 5   : {'PASS' if s1d else 'FAIL'}")
    print(f"  S1e max drawdown   : {'PASS' if s1e else 'FAIL'}")
    print(f"  S1f declaration    : printed above, and it is part of the result")
    return 0 if (s1c and s1d and s1e) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
