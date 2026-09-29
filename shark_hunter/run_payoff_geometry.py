"""Why the signal-to-noise ratio is what it is: an algebraic decomposition.

The 4h strategy's per-trade dispersion is 1.454R.  That number looks like a
data problem, so it was checked first.  It is not: it is arithmetic.

For a bracket that wins `2R` and loses `1R` with hit rate `p`:

    E[X]  =  3p - 1
    Var   =  9p(1-p)
    sd    =  3 * sqrt(p(1-p))

At p = 0.406 that is 1.47R, against a measured 1.454R.  The dispersion is
fully explained by the bracket, so no gap risk, time stop or funding
correction is inflating it.

That has a consequence worth stating plainly, because it changes where the
leverage is supposed to come from:

    SNR = edge / (3 * sqrt(p(1-p)))

The dispersion is bounded near 1.5R for ANY 1:2 bracket at any plausible hit
rate -- sqrt(p(1-p)) is at most 0.5, and a 30-45% hit rate already sits close
to that.  So a 1R/2R bracket is a low-SNR machine by construction, and the
only way to raise SNR is a larger edge per trade: a wider stop with a higher
payoff ratio, or a materially higher hit rate.

This is the quantitative backing for the phase-4 recommendation to change the
payoff geometry rather than to gather more data.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import config as C
from .runner import git_commit, write_frame, write_manifest

HIT_RATES = np.round(np.arange(0.30, 0.56, 0.01), 2)
TARGETS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)


def main() -> int:
    t0 = time.time()
    rows = []
    for target in TARGETS:
        for p in HIT_RATES:
            # Win = target*R, lose = 1R.
            mean = target * p - 1.0 * (1 - p)
            var = (target ** 2) * p + 1.0 * (1 - p) - mean ** 2
            sd = float(np.sqrt(max(var, 0.0)))
            breakeven = 1.0 / (1.0 + target)
            rows.append({
                "target_r": target, "hit_rate": p,
                "breakeven_hit_rate": breakeven,
                "mean_r": mean, "sd_r": sd,
                "edge_over_sd": mean / sd if sd else np.nan,
                # SNR for a modest 0.10R real edge at this bracket:
                "snr_if_edge_0.10R": 0.10 / sd if sd else np.nan,
            })
    df = pd.DataFrame(rows)
    write_frame(df, "phase6_payoff_geometry_snr")

    print("=" * 76)
    print("PAYOFF GEOMETRY: where the signal-to-noise ratio actually comes from")
    print("=" * 76)
    print(f"\nmeasured 4h: hit rate 40.6%, target 2R -> predicted sd "
          f"{3 * np.sqrt(0.406 * 0.594):.3f}R vs measured 1.454R")
    print("The dispersion is arithmetic, not a data artefact.\n")

    print("--- SNR by target multiple, at the 4h hit rate of 40.6% ---")
    sub = df[np.isclose(df["hit_rate"], 0.41)].copy()
    for _, r in sub.iterrows():
        print(f"  target {r['target_r']:.1f}R  breakeven {r['breakeven_hit_rate']:.1%}  "
              f"mean {r['mean_r']:+.3f}R  sd {r['sd_r']:.3f}R  "
              f"SNR {r['edge_over_sd']:+.3f}   "
              f"SNR if a 0.10R edge existed: {r['snr_if_edge_0.10R']:.3f}")

    print("\n--- dispersion is near-maximal for any 1:2 bracket ---")
    for p in (0.30, 0.35, 0.40, 0.45, 0.50):
        print(f"  hit rate {p:.0%} -> sd {3 * np.sqrt(p * (1 - p)):.3f}R")
    print("\n  sqrt(p(1-p)) is maximised at p=0.5, so sd <= 1.5R for ANY 1:2")
    print("  bracket. A tight bracket cannot produce a high SNR, whatever the")
    print("  hit rate. The leverage has to come from a larger edge per trade.")

    write_manifest({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "git_commit": git_commit(),
        "measured_sd_r": 1.454, "predicted_sd_r": float(3 * np.sqrt(0.406 * 0.594)),
        "note": "dispersion is explained by the 1R/2R bracket and the hit rate",
    }, "manifest_phase6.json")
    print(f"\nelapsed {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
