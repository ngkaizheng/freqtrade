"""Build the D-1 risk-frontier configs: one file per risk level, nothing else changed."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "user_data" / "config_perp_forward_dry.json")
                  .read_text(encoding="utf-8"))
GRID = [0.0025, 0.0040, 0.0050, 0.0075, 0.0100, 0.0150]


def main() -> int:
    for r in GRID:
        c = dict(BASE)
        c["risk_per_trade"] = r
        tag = f"n40_r{int(round(r * 10000)):05d}"
        # its own database and log, for the reason this project has already
        # paid for once: a second process pointed at the forward collector's
        # database is how a stale-DB bug started once already.
        c["db_url"] = f"sqlite:///user_data/risk_{tag}.dryrun.sqlite"
        c["logfile"] = f"user_data/logs/risk_{tag}.log"
        c["exportfilename"] = f"user_data/risk_out/{tag}"
        p = ROOT / "user_data" / f"config_risk_{tag}.json"
        p.write_text(json.dumps(c, indent=2), encoding="utf-8")
        os.makedirs(ROOT / "user_data" / "risk_out" / tag, exist_ok=True)
        print(f"{tag}  risk={r}  N={len(c['exchange']['pair_whitelist'])}  "
              f"strategy={c['strategy']}  atr_stop={c['atr_stop']}  "
              f"max_open={c['max_open_trades']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
