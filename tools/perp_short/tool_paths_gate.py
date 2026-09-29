"""GATE: does every tool still point at a data panel that EXISTS?

WHY THIS FILE EXISTS
--------------------
On 2026-09-30 `verify_stop.py` was found to have been crashing on every run for
some time, because it pointed at `user_data/data/wide_ft` - a panel that had
been replaced by `wide526` - and it is one of the four gates `HOW_TO_RUN` tells a
reader to execute. Nobody noticed, because a tool only fails when someone runs
it, and nothing in the output said "this is a stale path" as opposed to "this is
a bug".

A grep the same day found **19 files under `tools/` still naming `wide_ft`**,
including `cost_frontier.py` and `r_stats.py` - both in the live perp_short
toolchain, both broken in the identical way. That is the third instance of the
same failure in three rounds, so the class, not the instance, is what needs
guarding.

This gate greps every Python file under `tools/` for a datadir-shaped string
literal, resolves it against the repository, and reports the ones that do not
exist. It is deliberately dumb: it does not try to understand what a tool does,
it only asks whether the path it will open is there.

The limitation is stated rather than hidden: this catches MISSING DIRECTORIES
in string literals. A tool that builds a path at runtime from parts, or that
reads a datadir out of a JSON config, is not covered.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\tool_paths_gate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
# A datadir-shaped literal: user_data/data/<something>, optionally with a
# trailing "futures". Matched on the repo-relative form used in these files.
PAT = re.compile(r"""["'](user_data[\\/]data[\\/][A-Za-z0-9_\-]+)["']""")

# Directories that are legitimately absent and are NOT data panels.
# ⚠ THE FIRST VERSION OF THIS GATE WAS A FALSE PASS, AND IT IS WORTH RECORDING WHY.
# It checked only "does this directory exist". `user_data/data/wide_ft` EXISTS - it
# holds 97 files - but it does not contain 1000BONK_USDT_USDT-4h-futures, which is
# the file `cost_frontier.py` actually failed to open. A directory check is therefore
# NOT the question. The question is whether the panel can READ THE UNIVERSE THE
# DEPLOYED CONFIG RUNS, so that is what this gate asks.
DEPLOYED = ROOT / "user_data" / "config_perp_forward_dry.json"
TIMEFRAMES = ("4h-futures",)

# SCOPE, STATED RATHER THAN GUESSED. "Can this panel read the deployed N=40?" is
# the right question for the tools that operate on the DELIVERED book and the
# wrong question for everything else: beta_check, market_check, test_causality
# and friends deliberately study the 104-symbol panel, and the carry tools
# deliberately study funding. Failing those would be the gate crying wolf, and a
# gate that cries wolf gets ignored.
#
# So this gate HARD-FAILS only for the declared live chain below, and REPORTS
# everything else. Adding a tool to the live chain means adding it here.
# An explicit list is honest; a heuristic that guesses is not.
LIVE_CHAIN = {
    "verify_stop.py", "verify_collector.py", "collector_fidelity.py",
    "risk_unit.py", "funding_decomp.py", "variance_decomp.py",
    "leverage_geometry.py", "horizon_factor.py",
    "verify_factor_structure.py", "xsect_screen.py", "intraday_gate0.py",
    "cost_reprice.py", "state_gate.py",
}

def deployed_symbols() -> list[str]:
    if not DEPLOYED.exists():
        return []
    import json
    wl = json.loads(DEPLOYED.read_text(encoding="utf-8"))["exchange"]["pair_whitelist"]
    return [f"{p.replace(chr(47), chr(95)).replace(chr(58), chr(95))}-{tf}.feather"
            for p in wl for tf in TIMEFRAMES]


def coverage(panel: Path, wanted: list[str]):
    have = 0
    for f in wanted:
        if (panel / "futures" / f).exists() or (panel / f).exists():
            have += 1
    return have, len(wanted)


def main() -> int:
    print("TOOL PATHS GATE: can each tool's data panel read the deployed universe?\n")
    print("The third instance of this failure was a tool crashing on a panel that no")
    print("longer held the data, while being documented as a working gate.\n")
    hits = {}
    for p in sorted(TOOLS.rglob("*.py")):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in PAT.finditer(txt):
            rel = m.group(1).replace(chr(92), "/")
            hits.setdefault(rel, []).append(str(p.relative_to(ROOT)))
    if not hits:
        print("  no datadir literals found - is the pattern still right? FAIL.")
        return 1
    wanted = deployed_symbols()
    print(f"  reference universe: {len(wanted)} files from {DEPLOYED.name}")
    print()
    print(f"  {'panel':<28}{'tools':>7}{'feathers':>10}{'reads N=40?':>16}")
    broken, thin = [], []
    for rel, files in sorted(hits.items()):
        d = ROOT / rel
        if not d.is_dir():
            print(f"  {rel:<28}{len(files):>7}{chr(45)*3:>10}{'NO - no dir':>16}")
            broken.append((rel, files))
            continue
        n = sum(1 for _ in d.rglob("*.feather"))
        have, tot = coverage(d, wanted)
        ok = (tot == 0) or (have == tot)
        if tot and have < tot:
            thin.append((rel, files))
        mark = ("YES " + str(have) + "/" + str(tot)) if ok else ("NO  " + str(have) + "/" + str(tot))
        print(f"  {rel:<28}{len(files):>7}{n:>10}{mark:>16}")
    print()
    # Split the thin panels by whether the tool belongs to the declared live chain.
    live_bad, other_thin = [], []
    for rel, files in thin:
        live = [f for f in files if Path(f).name in LIVE_CHAIN]
        rest = [f for f in files if Path(f).name not in LIVE_CHAIN]
        if live:
            live_bad.append((rel, live))
        if rest:
            other_thin.append((rel, rest))
    for rel, files in broken:
        print(f"  BROKEN  {rel}  ({len(files)} tools) - the directory does not exist")
    for rel, files in live_bad:
        print(f"  LIVE-THIN  {rel} - a LIVE-CHAIN tool cannot read the deployed N=40:")
        for f in files:
            print(f"            {f}")
    if other_thin:
        print("\n  reported, NOT failed - these tools deliberately target another panel")
        print("  (the 104-symbol studies, or funding, or the exchange downloads):")
        for rel, files in other_thin:
            print(f"    {rel}: {len(files)} tool(s)")
        print("  If one of these IS meant to run the delivered book, move it into")
        print("  LIVE_CHAIN above and it will start failing.")

    if broken or live_bad:
        print("\n  VERDICT: FAIL. A tool in the live chain that cannot open the data it")
        print("  is documented against is not a tool, it is a crash waiting to be")
        print("  mistaken for a finding.")
        return 1
    print("\n  VERDICT: PASS - every tool's panel exists, and every LIVE-CHAIN tool can")
    print("  read the deployed N=40 universe.")
    print("  LIMIT: string literals and the deployed whitelist only. A path built at")
    print("  runtime, or a panel needing symbols outside it, is not covered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
