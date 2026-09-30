"""REGIME ROBUSTNESS for the F-1 Gate B result, before any strategy is written.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\volflow_by_regime.py

WHY THIS IS A SEPARATE FILE AND WHY IT COMES FIRST
----------------------------------------------------
`volflow_test.py`'s `incremental()` was wrong three times and every wrong version looked
like a finding. This file therefore **imports** it and re-implements nothing: the
statistic, the guards, the pass bar and the power caveat all live in one place.

And it runs BEFORE a strategy, for a reason this project has already paid for.
Section 41: **a result that wins only in the regime that selected it is one data point.**
The F-1 Gate B test passed on the pooled 2023-2026 sample. The panel rose +198.6 % in 2023
and +103.6 % in 2024, then fell. If the incremental volume effect exists only in the up
years, a strategy built on it is a bet on which regime arrives - not a diversifying third
book, but a disguised timing overlay.

Same test, same controls, same bars, recomputed inside each calendar year. Every cell is
printed; none is selected.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "perp_short"))
from volflow_test import features, incremental, T_PASS  # noqa: E402

DATA4 = ROOT / "user_data" / "data" / "wide526" / "futures"
FEATURES = ROOT / "user_data" / "perp_short_out" / "volflow_features.parquet"
CANDIDATES = ["dVol_12", "vol_z", "vol_trend"]
HORIZON = 12


def main() -> int:
    print("REGIME ROBUSTNESS of the F-1 incremental result\n")
    print("The F-1 test passed on the pooled sample. This asks whether it holds inside")
    print("each regime - the cheapest guard against a regime artefact.\n")

    if FEATURES.exists():
        d = pd.read_parquet(FEATURES)
        print(f"  loaded cached features: {len(d):,} rows")
    else:
        cfg = json.loads((ROOT / "user_data" / "config_perp_forward_dry.json")
                         .read_text(encoding="utf-8"))
        frames = []
        for p in cfg["exchange"]["pair_whitelist"]:
            k = p.replace("/", "_").replace(":", "_")
            f4 = DATA4 / f"{k}-4h-futures.feather"
            if not f4.exists():
                continue
            x = pd.read_feather(f4)
            x["date"] = pd.to_datetime(x["date"], utc=True).dt.tz_localize(None)
            x = x.sort_values("date").drop_duplicates("date").set_index("date")
            if len(x) >= 1000:
                frames.append(features(x))
        d = pd.concat(frames)
        print(f"  built from {len(frames)} symbols: {len(d):,} rows")

    yrs = sorted(pd.Index(d.index).year.unique())
    print(f"\n  {'feature':<11}{'year':<7}{'n':>11}{'inc t':>9}{'partial r':>11}   verdict")
    bad, tot, held = [], 0, 0
    for f in CANDIDATES:
        for y in yrs:
            sub = d[pd.Index(d.index).year == y]
            if len(sub) < 5000:
                continue
            t, r, n, _cond = incremental(sub[f"fwd_{HORIZON}"],
                                         [sub["mom_4"], sub["dVol_4"], sub[f]])
            if not np.isfinite(t):
                print(f"  {f:<11}{y:<7}{'-':>11}{'degenerate':>9}{r:>11.4f}   n/a")
                continue
            ok = abs(t) >= T_PASS
            tot += 1
            held += ok
            if not ok:
                bad.append(f"{f}@{y}")
            print(f"  {f:<11}{y:<7}{n:>11,}{t:>9.2f}{r:>11.4f}   "
                  f"{'holds' if ok else 'DOES NOT HOLD'}")
    print(f"\n  cells holding the incremental bar: {held}/{tot}")
    up = [y for y in yrs if y in (2023, 2024)]
    dn = [y for y in yrs if y in (2025, 2026)]
    print(f"  up regimes {up} · down regimes {dn}")
    print("  (panel: 2023 +198.6 %, 2024 +103.6 %, 2025 -56.8 %, 2026 -17.6 %)")
    if bad:
        print(f"\n  NOT UNIFORM - fails: {', '.join(bad)}")
        print("  A strategy on this would be a bet on which regime arrives, not a rule")
        print("  that diversifies. That is exactly what this project must not ship.")
    else:
        print("\n  uniform across all four regimes -> not a regime artefact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
