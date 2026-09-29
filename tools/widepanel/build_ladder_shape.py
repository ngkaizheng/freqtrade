"""Build the DENSE ladder rungs for the shape test, with cohort maps.

Rungs are FROZEN in `PREREG_LADDER_SHAPE_2026-09-28.md`: {25, 40, 50, 60, 75,
100, 125, 150, 200, 300, 515}. The cohort map travels with each config so gate
L2-style decomposition needs no later join and nothing can be dropped in one.

Run:
    .venv\\Scripts\\python.exe tools\\widepanel\\build_ladder_shape.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "user_data" / "config_laddershape"
BASE = ROOT / "user_data" / "config_perp_short_deploy.json"
RUNGS = [25, 40, 50, 60, 75, 100, 125, 150, 200, 300, 515]


def main() -> int:
    liq = pd.read_csv(ROOT / "user_data" / "perp_short_out" / "liquidity_515.csv")
    base = json.load(open(BASE))
    OUT.mkdir(parents=True, exist_ok=True)
    for n in RUNGS:
        sub = liq.head(n) if n <= len(liq) else liq
        pairs = [s[:-4] + "/USDT:USDT" for s in sub["symbol"]]
        cfg = dict(base)
        cfg["pair_whitelist"] = pairs
        cfg["exchange"] = dict(base["exchange"])
        cfg["exchange"]["pair_whitelist"] = pairs
        cfg["max_open_trades"] = 24
        cfg["datadir"] = str(ROOT / "user_data" / "data" / "wide526").replace("\\", "\\\\")
        cfg["logfile"] = f"user_data/logs/lshape_{n}.log"
        json.dump(cfg, open(OUT / f"lshape_{n}.json", "w"), indent=2)
        sub[["symbol", "cohort", "med_quote"]].to_csv(
            OUT / f"lshape_{n}_cohorts.csv", index=False)
        a = int((sub["cohort"] == "A").sum())
        print(f"  N={n:<4} pairs={len(pairs):<4} A={a:<4} ({a/len(sub)*100:4.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
