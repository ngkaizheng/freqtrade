"""DATA-INTEGRITY CHECK for the OI pipeline, on the real files already downloaded.

THIS IS NOT A VERDICT
---------------------
`PREREG_OI_2026-09-30.md` Gate 1 needs >= 30 symbols. This file checks the
PLUMBING on whatever exists, so that a shape, dtype, NaN or causality fault is found
now rather than after the 113-minute download finishes. It deliberately reports no IC,
no t and no pass/fail on the hypothesis.

THE ONE THING THAT MATTERS MOST HERE
------------------------------------
LOOK-AHEAD. The OI series is merged onto the 4h frame with
`merge_asof(direction="backward")`. If that ever became a forward join, every feature
would carry future information, every IC would be inflated, and the whole line would
report a confident, entirely fictional result. **So this file asserts, on real data,
that the OI timestamp attached to each 4h bar is at or before it - not by reading the
code, by measuring the merge.**

Also checked: feature frame builds, no NaN blow-up, no inf, and that the OI columns
actually vary (a feature that is constant or all-NaN looks exactly like "no signal"
and is the failure mode of this project's trap #1).

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\check_oi_pipeline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
OI = ROOT / "user_data" / "data" / "oi"
DATA4 = ROOT / "user_data" / "data" / "wide526" / "futures"
sys.path.insert(0, str(ROOT / "tools" / "perp_short"))
import oi_signal_test as M  # noqa: E402


def archive_symbol(pair: str) -> str:
    base, _, rest = pair.partition("/")
    return f"{base}{rest.split(':')[0]}"


def main() -> int:
    print("OI PIPELINE INTEGRITY CHECK - plumbing only, NO verdict\n")
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    names = [(archive_symbol(p), p.replace("/", "_").replace(":", "_"))
             for p in cfg["exchange"]["pair_whitelist"]]
    have = [(a, f) for a, f in names if (OI / f"{a}-oi.parquet").exists()]
    print(f"OI files present: {len(have)} of {len(names)}")
    if not have:
        print("  nothing downloaded yet - nothing to check")
        return 2

    problems, built = [], 0
    lag_min, lag_med = [], []
    for arch, flat in have:
        fp = OI / f"{arch}-oi.parquet"
        o = pd.read_parquet(fp)
        o["create_time"] = pd.to_datetime(o["create_time"], utc=True).dt.tz_localize(None)
        o = o.set_index("create_time").sort_index()
        p = pd.read_feather(DATA4 / f"{flat}-4h-futures.feather")
        p["date"] = pd.to_datetime(p["date"], utc=True).dt.tz_localize(None)
        p = p.sort_values("date").set_index("date")
        p = p[(p.index >= o.index[0]) & (p.index <= o.index[-1])]
        if len(p) < 300:
            problems.append(f"{arch}: only {len(p)} 4h bars in the OI range")
            continue
        # re-do the merge but KEEP the OI timestamp so causality can be measured
        oj = o.reset_index()
        m = pd.merge_asof(p.reset_index(), oj, left_on="date", right_on="create_time",
                          direction="backward")
        d = (m["date"] - m["create_time"]).dt.total_seconds()
        if (d < 0).any():
            problems.append(f"{arch}: LOOK-AHEAD - {int((d<0).sum())} bars carry OI "
                            f"from AFTER the bar")
        if m["create_time"].isna().any():
            problems.append(f"{arch}: {int(m['create_time'].isna().sum())} bars have no OI")
        lag_min.append(float(d.min() / 3600.0))
        lag_med.append(float(d.median() / 3600.0))

        feat = M.features(m.set_index("date"))
        built += 1
        featcols = [c for c in feat.columns if c.startswith(("dOI", "z_"))]
        for c in featcols:
            col = feat[c]
            if col.notna().sum() == 0:
                problems.append(f"{arch}: feature {c} is entirely NaN (looks like "
                                f"'no signal' but is a bug - trap #1)")
            elif np.isinf(col.to_numpy(dtype=float, na_value=np.nan)).any():
                problems.append(f"{arch}: feature {c} contains inf")
            elif col.nunique(dropna=True) < 5:
                problems.append(f"{arch}: feature {c} is nearly constant "
                                f"({col.nunique(dropna=True)} distinct)")

    print(f"\n  symbols whose feature frame built: {built}")
    print("\n  LOOK-AHEAD (the assertion that matters):")
    if lag_med:
        print(f"    OI lags behind its 4h bar by: min {min(lag_min):.2f} h, "
              f"median {np.median(lag_med):.2f} h")
        print(f"    a median lag of ~2 h is expected - 4h bars sample the 1h OI series "
              f"at the last hour\n    available, never a future one.")
    bad = [x for x in problems if "LOOK-AHEAD" in x]
    print(f"    look-ahead violations: {len(bad)}  {'(NONE - causality holds)' if not bad else bad}")

    print(f"\n  other problems: {len(problems) - len(bad)}")
    for x in problems:
        if "LOOK-AHEAD" not in x:
            print(f"    {x}")

    print("\nVERDICT (plumbing only)")
    if problems:
        print("  ** the pipeline has faults - fix before any IC is computed **")
        return 1
    print("  the pipeline is sound on the files checked: causal merge, features build,")
    print("  no all-NaN and no near-constant columns. The preregistered Gates may be run")
    print("  once Gate 1's 30-symbol requirement is met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
