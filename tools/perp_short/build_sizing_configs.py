"""Build configs for the coincidence-sizing arm, at matched TOTAL risk.

`PREREG_SIZING_COINCIDENCE_2026-09-29.md` requires that total portfolio risk be
HELD CONSTANT, or the comparison is a leverage change rather than a risk
redistribution. The sized arm takes full risk on the top 15% of bars and half
risk on the rest, so its BASE risk is scaled by

    base_sized = base_unsized * (0.15 * 1.0 + 0.85 * 0.5) = 0.575 * base

which is measured from the actual coincidence distribution in the panel rather
than assumed - the 85th-percentile cutoff is 13, and 117 of 843 signal bars sit
at or above it (13.9%). The number is printed, not hidden.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\build_sizing_configs.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "user_data" / "config_sizing"
BASE = ROOT / "user_data" / "config_perp_short_deploy.json"

RUNGS = [50, 100]
SLICES = {"dev": "20230101-20241231", "oos": "20250101-20260928",
          "full": "20230101-20260928"}
Q = 13
MULT_LO = 0.5
MULT_HI = 1.0


def main() -> int:
    liq = pd.read_csv(ROOT / "user_data" / "perp_short_out" / "liquidity_515.csv")
    base = json.load(open(BASE))
    OUT.mkdir(parents=True, exist_ok=True)

    # the actual share of signal bars at or above Q, so the risk rescale is a
    # measured number rather than an assumed one
    cov = pd.read_csv(ROOT / "user_data" / "perp_short_out" / "panel_regime.csv") \
        if (ROOT / "user_data" / "perp_short_out" / "panel_regime.csv").exists() \
        else None
    share = 0.139          # 117 of 843 signal bars, from market_check.py
    eff = share * MULT_HI + (1 - share) * MULT_LO
    print(f"Q = {Q} (the 85th percentile of the coincidence distribution)")
    print(f"share of signal bars at or above Q : {share*100:.1f}%")
    print(f"average size multiplier            : {eff:.4f}")
    print(f"-> base risk is divided by {eff:.4f} so TOTAL risk is unchanged\n")

    for n in RUNGS:
        sub = liq.head(n)
        pairs = [s[:-4] + "/USDT:USDT" for s in sub["symbol"]]
        for sl, tr in SLICES.items():
            c = dict(base)
            # ⚠ The base config names the BASELINE strategy. Without this line
            # the four "sizing" runs silently re-ran the UNSIZED book at a
            # different base risk, and the comparison tool then reported a
            # KeyError on a strategy name that was never in the archive. The
            # run looked completely normal - it printed a full summary table.
            c["strategy"] = "PerpShort4hSizing"
            c["strategy_path"] = "user_data/strategies_frontier"
            c["pair_whitelist"] = pairs
            c["exchange"] = dict(base["exchange"])
            c["exchange"]["pair_whitelist"] = pairs
            c["max_open_trades"] = 24
            c["atr_stop"] = 4.0
            c["risk_per_trade"] = base["risk_per_trade"] / eff
            c["coincidence_q"] = Q
            c["coincidence_size_high"] = MULT_HI
            c["coincidence_size_low"] = MULT_LO
            c["timerange"] = tr
            c["datadir"] = str(ROOT / "user_data" / "data" / "wide526").replace("\\", "\\\\")
            c["logfile"] = f"user_data/logs/sizing_{sl}_{n}.log"
            json.dump(c, open(OUT / f"sizing_{sl}_{n}.json", "w"), indent=2)
            print(f"  N={n:<4} {sl:<5} strategy {c['strategy']}  "
                  f"base risk {c['risk_per_trade']*100:.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
