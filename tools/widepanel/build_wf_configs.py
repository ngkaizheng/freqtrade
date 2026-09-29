"""Build the two walk-forward slices for every ladder rung.

`PREREG_WALKFORWARD_SELECTION_2026-09-28.md`: DEVELOPMENT 2023-01-01 to
2024-12-31 may be the ONLY data any choice uses; OOS 2025-01-01 to 2026-08-31 is
evaluated once, after the choice is frozen.

The splits are by TIMERANGE, not by slicing the trade export, so each side is a
normal backtest with the same engine, the same costs and the same liquidation
book. Slicing the export would silently keep the full-sample equity curve and
make every P&L wrong.

Run:
    .venv\\Scripts\\python.exe tools\\widepanel\\build_wf_configs.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "user_data" / "config_wf"
BASE = ROOT / "user_data" / "config_perp_short_deploy.json"
RUNGS = [25, 40, 50, 60, 75, 100, 125, 150, 200, 300, 515]
SLICES = {
    "dev": "20230101-20241231",     # DEVELOPMENT - the only data a choice may use
    "oos": "20250101-20260928",     # OOS - evaluated once
}


def main() -> int:
    liq = pd.read_csv(ROOT / "user_data" / "perp_short_out" / "liquidity_515.csv")
    base = json.load(open(BASE))
    OUT.mkdir(parents=True, exist_ok=True)
    for n in RUNGS:
        sub = liq.head(n) if n <= len(liq) else liq
        pairs = [s[:-4] + "/USDT:USDT" for s in sub["symbol"]]
        for sl, tr in SLICES.items():
            cfg = dict(base)
            cfg["pair_whitelist"] = pairs
            cfg["exchange"] = dict(base["exchange"])
            cfg["exchange"]["pair_whitelist"] = pairs
            cfg["max_open_trades"] = 24
            cfg["datadir"] = str(ROOT / "user_data" / "data" / "wide526").replace("\\", "\\\\")
            cfg["timerange"] = tr
            cfg["logfile"] = f"user_data/logs/wf_{sl}_{n}.log"
            json.dump(cfg, open(OUT / f"wf_{sl}_{n}.json", "w"), indent=2)
        sub[["symbol", "cohort", "med_quote"]].to_csv(OUT / f"wf_{n}_cohorts.csv",
                                                      index=False)
        a = int((sub["cohort"] == "A").sum())
        print(f"  N={n:<4} pairs={len(pairs):<4} A={a:<4} ({a/len(sub)*100:4.1f}%)")
    print(f"\nDEVELOPMENT: {SLICES['dev']}")
    print(f"OOS        : {SLICES['oos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
