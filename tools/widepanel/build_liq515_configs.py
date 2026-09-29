"""Build the liquidity ladder configs on the 515-symbol universe, WITH cohort tags.

The cohort map has to travel with the universe, because gate L2 - the decisive
one - asks what the NON-cohort-A portion of each rung did. A ladder that ships
only a pair list cannot answer that, and a ladder that answers it only by
joining afterwards risks joining on a name that got dropped.

Run:
    .venv\\Scripts\\python.exe tools\\widepanel\\build_liq515_configs.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "user_data" / "config_liq515"
BASE = ROOT / "user_data" / "config_perp_short_deploy.json"
RANKS = [50, 100, 200, 515]


def main() -> int:
    liq = pd.read_csv(ROOT / "user_data" / "perp_short_out" / "liquidity_515.csv")
    base = json.load(open(BASE))
    OUT.mkdir(parents=True, exist_ok=True)
    for n in RANKS:
        sub = liq.head(n) if n <= len(liq) else liq
        pairs = [s[:-4] + "/USDT:USDT" for s in sub["symbol"]]
        cfg = dict(base)
        cfg["pair_whitelist"] = pairs
        cfg["exchange"] = dict(base["exchange"])
        cfg["exchange"]["pair_whitelist"] = pairs
        cfg["max_open_trades"] = 24
        cfg["datadir"] = str(ROOT / "user_data" / "data" / "wide526").replace("\\", "\\\\")
        cfg["logfile"] = f"user_data/logs/liq515_{n}.log"
        p = OUT / f"liq515_{n}.json"
        json.dump(cfg, open(p, "w"), indent=2)
        # the cohort map travels WITH the rung, so gate L2 needs no later join
        sub[["symbol", "cohort", "med_quote"]].to_csv(
            OUT / f"liq515_{n}_cohorts.csv", index=False)
        a = int((sub["cohort"] == "A").sum())
        print(f"  N={n:<4} pairs={len(pairs):<4} cohort A={a:<4} ({a/len(sub)*100:4.1f}%)"
              f"  med quote ${sub['med_quote'].median():,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
