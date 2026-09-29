"""Build one config per cohort for the widened-universe test.

U0 IS THE GATE THAT MATTERS FIRST: cohort A must REPLICATE the delivered book.
If it does not, the newer cohorts are uninterpretable, because the only way to
know the new data is being read the same way as the old data is the old data
reproducing.

Each config pins `max_open_trades` to 24 - the state file records that freqtrade
silently applies `min(setting, len(pairlist))`, so leaving it to float would make
rungs differ in two ways at once. Here the universe is 41-515 symbols so 24 is
below the cap everywhere, but it is pinned rather than assumed.

Run:
    .venv\\Scripts\\python.exe tools\\widepanel\\build_widened_configs.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "user_data" / "config_widened"
BASE = ROOT / "user_data" / "config_perp_short_deploy.json"

COHORTS = {
    "A": ["A"],                 # replication arm
    "BCDE": ["B", "C", "D", "E"],   # the independent test set
    "ALL": ["A", "B", "C", "D", "E"],
    "D": ["D"],                 # 2025 cohort alone, most numerous
    "E": ["E"],                 # 2026 cohort alone, expected inconclusive
}


def main() -> int:
    import glob
    uni = json.loads((ROOT / "shark_data" / "widened" / "universe.json").read_text())
    co = {u["symbol"]: u["cohort"] for u in uni}
    syms = []
    for f in glob.glob(str(ROOT / "user_data" / "data" / "wide526" / "futures"
                           / "*-4h-futures.feather")):
        stem = os.path.basename(f).split("-4h-futures")[0]
        sym = stem[:-len("_USDT_USDT")] + "USDT"
        syms.append(sym)
    syms = sorted(set(syms))
    print(f"symbols on disk: {len(syms)}")

    OUT.mkdir(parents=True, exist_ok=True)
    base = json.load(open(BASE))
    for name, cs in COHORTS.items():
        pairs = [s[:-4] + "/USDT:USDT" if s.endswith("USDT") else s + "/USDT:USDT"
                 for s in syms if co.get(s) in cs]
        cfg = dict(base)
        cfg["pair_whitelist"] = pairs
        cfg["exchange"] = dict(base["exchange"])
        cfg["exchange"]["pair_whitelist"] = pairs
        cfg["max_open_trades"] = 24
        cfg["datadir"] = str(ROOT / "user_data" / "data" / "wide526").replace("\\", "\\\\")
        cfg["logfile"] = f"user_data/logs/widened_{name}.log"
        p = OUT / f"widened_{name}.json"
        json.dump(cfg, open(p, "w"), indent=2)
        print(f"  {name:<6} {len(pairs):>4} pairs -> {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
