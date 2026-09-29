"""Build the C-1 slot-cap configs: risk x max_open_trades, nothing else changed."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = json.loads((ROOT / "user_data" / "config_perp_forward_dry.json")
                  .read_text(encoding="utf-8"))
# (risk_per_trade, max_open_trades)
GRID = [(0.0050, 96), (0.0075, 96), (0.0100, 96), (0.0150, 96)]


def main() -> int:
    for risk, slots in GRID:
        c = dict(BASE)
        c["risk_per_trade"] = risk
        c["max_open_trades"] = slots
        tag = f"cap{slots}_r{int(round(risk * 10000)):05d}"
        c["db_url"] = f"sqlite:///user_data/{tag}.dryrun.sqlite"
        c["logfile"] = f"user_data/logs/{tag}.log"
        c["exportfilename"] = f"user_data/slotcap_out/{tag}"
        p = ROOT / "user_data" / f"config_{tag}.json"
        p.write_text(json.dumps(c, indent=2), encoding="utf-8")
        os.makedirs(ROOT / "user_data" / "slotcap_out" / tag, exist_ok=True)
        print(f"{tag}  risk={risk}  max_open_trades={slots}  "
              f"N={len(c['exchange']['pair_whitelist'])}  "
              f"strategy={c['strategy']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
