"""GATE: is the delivered LONG config the same book as the MEASURED long rung?

WHY THIS FILE EXISTS
--------------------
The short book has eleven gates and a one-command release check. The long book,
delivered on 2026-09-30 as `user_data/config_perp_bull_dry.json`, had **none** - it
was a config file and a claim. Nothing compared it to the config that actually
produced the published +95.43 %, and nothing checked the keys whose absence is
silent.

That gap is not hypothetical. This gate was written to find out, and on its first
run it found a real defect: the delivered long config is **missing `initial_state`**.
`DELIVERABLE_SPEC_2026-09-30.md` §3 lists that key as one of four whose absence
produces NO error and NO number - the process heartbeats every 60 seconds in state
STOPPED and looks perfectly healthy. It is the single most dangerous failure mode
this project has documented, and the long delivery had exactly that hole.

THE THREE QUESTIONS
-------------------
  A. FIELD-FOR-FIELD vs THE MEASURED RUNG. `config_bull_c5_chand800.json` is the run
     that produced 1,000 trades / +95.43 % / PF 1.37. If the delivered config differs
     from it in ANY field that can change a backtest, the published number describes a
     different book. Only three fields are allowed to differ - they name where output
     goes and cannot change a single trade.
  B. THE WHITELIST, INCLUDING ITS ORDER. Trap 8: the same universe in alphabetical
     order returned +4.14 % against -17.52 % in liquidity order. Order is a decision,
     not formatting, so it is compared as a sequence and not as a set.
  C. IS EVERY KEY LOAD-BEARING. A key that sits in the config and equals the strategy's
     class default is decoration; a key that DIFFERS from it is the only thing stopping
     the class from silently running a different book. `DELIVERABLE_SPEC` §3 says of
     `atr_stop`: *"class default is 1.5. Omit it and you silently collect a completely
     different strategy."* That is a testable claim and this gate tests it: each
     performance key must be present AND must differ from the class default. If one
     ever equals the default, this file says so, because a reader would then believe
     the config is protecting them when it is not.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\bull_config_gate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELIVERED = ROOT / "user_data" / "config_perp_bull_dry.json"
# The run that produced the published number. bull_axis.py `find()` resolves this to
# user_data/backtest_results/backtest-result-2026-09-29_13-23-42.zip, whose embedded
# config carries exportfilename=user_data/bull_out/c5_chand800 and chandelier_atr=8.0.
MEASURED = ROOT / "user_data" / "config_bull_c5_chand800.json"

# Fields that name WHERE OUTPUT GOES. None of them can change a trade: the engine
# reads candles, the strategy, the sizing inputs and the fee. Everything else must
# match exactly, and this allowlist is deliberately tiny so that adding a field to
# one config and not the other is a FAILURE rather than a silent divergence.
RUNTIME_ONLY = {
    "logfile",            # a dry-run writes to a different file than a backtest
    "db_url",             # the long book MUST NOT share the short book's dry-run DB
    "exportfilename",     # the delivery exports to its own directory
    # `initial_state` was added to the delivered long config on 2026-09-30, AFTER this
    # gate found it missing. It is a runtime key - backtesting never reads it - so it
    # is allowed to differ from the measured rung, but section C still REQUIRES it to
    # be present. Being in this allowlist does not make it optional.
    "initial_state",
}

# Keys whose absence produces no error, from DELIVERABLE_SPEC_2026-09-30.md §3.
# `database_url` is the trap's mirror image: freqtrade does not reject unknown keys,
# so the typo silently opens a stale DB somewhere else entirely.
MUST_BE_PRESENT = {
    "db_url": "the key is db_url; database_url is silently ignored and opens a stale DB",
    "initial_state": "without it the process heartbeats in state STOPPED and produces nothing",
    "timeframe": "the class default happens to also be 4h, so drift would be silent",
    "atr_stop": "the class default is 1.5; omitting it silently runs a different strategy",
}
MUST_NOT_BE_PRESENT = {
    "database_url": "freqtrade does not reject unknown keys; this typo opens a stale DB",
}

# key -> (value the docs publish, the class default it must differ from)
PUBLISHED = {
    "strategy": ("PerpLong4h", None),
    "timeframe": ("4h", None),
    "atr_stop": (4.0, 1.5),
    "risk_per_trade": (0.005, None),
    "breaker_max_dd": (0.20, None),
    "breaker_cooldown_bars": (42, None),
    "side": ("long", "long"),
    "exit_mode": ("run", "fixed"),
    "chandelier_atr": (8.0, 3.0),
    "startup_candle_count": (420, None),
}

fails: list[str] = []
notes: list[str] = []


def flat(obj, prefix: str = "") -> dict:
    """Dotted paths. Lists are VALUES, not containers - the whitelist must compare
    element by element, in order, which it would not if it were flattened."""
    out: dict = {}
    for k, v in (obj or {}).items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flat(v, f"{key}."))
        else:
            out[key] = v
    return out


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def class_defaults() -> dict:
    """Read the real defaults off the real classes.

    Hard-coding them in this file would make the gate a restatement of my memory,
    and this project has been bitten by a wrong-but-plausible constant more than
    once. `PerpShort4hStop.atr_stop` is a PROPERTY, so the class attribute is the
    property object and not a number - the 1.5 lives on the frozen grandparent.
    """
    for d in (ROOT / "user_data" / "strategies_frontier", ROOT / "user_data" / "strategies"):
        sys.path.insert(0, str(d))
    from freqtrade.strategy import IStrategy
    from PerpLong4h import PerpLong4h
    from PerpShort4h import PerpShort4h

    return {
        "atr_stop": float(PerpShort4h.atr_stop),
        "target_r": float(PerpShort4h.target_r),
        "rvol_threshold": float(PerpShort4h.rvol_threshold),
        "time_stop_bars": int(PerpShort4h.time_stop_bars),
        "stoploss": float(PerpShort4h.stoploss),
        "side": str(PerpLong4h.side),
        "exit_mode": str(PerpLong4h.exit_mode),
        "chandelier_atr": float(PerpLong4h.chandelier_atr),
        "startup_candle_count": int(IStrategy.startup_candle_count),
    }


def main() -> int:
    if not DELIVERED.exists():
        print(f"FAIL - {DELIVERED} does not exist")
        return 1
    cfg = json.loads(DELIVERED.read_text(encoding="utf-8"))

    # ---- A. field-for-field against the measured rung -----------------------
    head("A. DELIVERED CONFIG vs THE MEASURED RUNG (chandelier 8.0, the published run)")
    if not MEASURED.exists():
        fails.append(f"measured rung config {MEASURED.name} is missing - "
                     f"the gate cannot establish that the delivery is the measured book")
        print(f"  [FAIL] {MEASURED.name} is missing")
    else:
        ref = json.loads(MEASURED.read_text(encoding="utf-8"))
        a, b = flat(cfg), flat(ref)
        only_cfg = sorted(set(a) - set(b))
        only_ref = sorted(set(b) - set(a))
        for k in only_cfg:
            tag = "ok - runtime" if k in RUNTIME_ONLY else "FAIL"
            print(f"  [{tag}] only in delivered : {k} = {a[k]!r}")
            if k not in RUNTIME_ONLY:
                fails.append(f"{k} exists only in the delivered config")
        for k in only_ref:
            tag = "ok - runtime" if k in RUNTIME_ONLY else "FAIL"
            print(f"  [{tag}] only in measured  : {k} = {b[k]!r}")
            if k not in RUNTIME_ONLY:
                fails.append(f"{k} exists only in the measured config")
        diff = [k for k in sorted(set(a) & set(b)) if a[k] != b[k]]
        for k in diff:
            tag = "ok - runtime" if k in RUNTIME_ONLY else "FAIL"
            print(f"  [{tag}] differs           : {k}  delivered={a[k]!r}  measured={b[k]!r}")
            if k not in RUNTIME_ONLY:
                fails.append(f"{k}: delivered {a[k]!r} vs measured {b[k]!r}")
        n_same = len(set(a) & set(b)) - len(diff)
        print(f"  {n_same} field(s) identical, {len(diff)} differing, "
              f"{len(only_cfg) + len(only_ref)} one-sided")

    # ---- B. the whitelist, in order ----------------------------------------
    head("B. THE UNIVERSE, INCLUDING ITS ORDER")
    wl = cfg.get("exchange", {}).get("pair_whitelist", [])
    print(f"  N = {len(wl)}")
    if len(wl) != 40:
        fails.append(f"whitelist has {len(wl)} pairs, the delivery is specified as 40")
        print("  [FAIL] N != 40")
    else:
        print("  [PASS] N = 40")
    dupes = {p for p in wl if wl.count(p) > 1}
    if dupes:
        fails.append(f"whitelist contains duplicates: {sorted(dupes)}")
        print(f"  [FAIL] duplicates: {sorted(dupes)}")
    print(f"  order: {', '.join(wl[:6])} ...")
    if MEASURED.exists():
        refwl = json.loads(MEASURED.read_text(encoding="utf-8"))["exchange"]["pair_whitelist"]
        if wl == refwl:
            print("  [PASS] byte-identical to the measured rung, IN THE SAME ORDER")
        elif set(wl) == set(refwl):
            fails.append("whitelist is the same SET as the measured rung but a different "
                         "ORDER - trap 8 measured 21.7 points on exactly this")
            print("  [FAIL] same pairs, DIFFERENT ORDER (trap 8)")
        else:
            fails.append("whitelist is not the measured rung's universe")
            print("  [FAIL] different universe")

    # ---- C. the keys whose absence is silent -------------------------------
    head("C. THE KEYS WHOSE ABSENCE IS SILENT")
    for k, why in MUST_BE_PRESENT.items():
        if k not in cfg:
            fails.append(f"config is MISSING `{k}` - {why}")
            print(f"  [FAIL] {k:<20} absent. {why}")
        else:
            print(f"  [PASS] {k:<20} = {cfg[k]!r}")
    for k, why in MUST_NOT_BE_PRESENT.items():
        if k in cfg:
            fails.append(f"config contains `{k}` - {why}")
            print(f"  [FAIL] {k:<20} present. {why}")
        else:
            print(f"  [PASS] {k:<20} absent (as it must be)")

    # ---- D. no credentials, ever -------------------------------------------
    head("D. CREDENTIALS")
    ex = cfg.get("exchange", {})
    if ex.get("key") or ex.get("secret"):
        fails.append("THE LONG CONFIG CONTAINS API CREDENTIALS")
        print("  [FAIL] credentials present - this must never ship")
    else:
        print("  [PASS] no API credentials")
    if cfg.get("dry_run") is True:
        print("  [PASS] dry_run = true")
    else:
        fails.append(f"dry_run is {cfg.get('dry_run')}, not True")
        print(f"  [FAIL] dry_run = {cfg.get('dry_run')}")

    # ---- E. is every published key load-bearing? ---------------------------
    head("E. IS EVERY KEY LOAD-BEARING (config value vs the CLASS default)")
    try:
        cd = class_defaults()
    except Exception as e:                                   # noqa: BLE001
        fails.append(f"could not read the class defaults: {e}")
        print(f"  [FAIL] could not import the strategy classes: {e}")
        cd = {}
    if cd:
        for k, (want, _declared_default) in PUBLISHED.items():
            if k not in cfg:
                fails.append(f"published key `{k}` is not in the delivered config at all")
                print(f"  [FAIL] {k:<20} absent entirely")
                continue
            got = cfg[k]
            ok_val = got == want
            dflt = cd.get(k)
            if dflt is None:
                verdict = "PASS" if ok_val else "FAIL"
                extra = ""
            elif got == dflt:
                # present, correct, and redundant: deleting it changes nothing.
                verdict = "NOTE"
                extra = f"  <- EQUALS the class default {dflt!r}: this key is DECORATIVE"
                notes.append(f"{k}={got!r} equals the class default, so it is not what "
                             f"makes the book what it is")
            else:
                verdict = "PASS" if ok_val else "FAIL"
                extra = f"  (class default {dflt!r}, so the key IS load-bearing)"
            print(f"  [{verdict}] {k:<20} = {got!r}  published {want!r}{extra}")
            if not ok_val:
                fails.append(f"{k} is {got!r}, the docs publish {want!r}")
        print(f"\n  frozen constants inherited: " + ", ".join(
            f"{k}={v!r}" for k, v in cd.items() if k not in PUBLISHED))

    # ---- verdict -----------------------------------------------------------
    head("BULL CONFIG GATE")
    if notes:
        print("  notes, not failures:")
        for n in notes:
            print(f"    - {n}")
    if fails:
        print(f"\n  {len(fails)} FAILURE(S):")
        for f in fails:
            print(f"    - {f}")
        print("\n  VERDICT: the delivered long config is NOT the book that was measured.")
        return 1
    print("\n  VERDICT: PASS - the delivered long config is field-for-field the")
    print("  measured chandelier-8.0 rung on every field that can change a backtest,")
    print("  the universe and its order are identical, the silent keys are present,")
    print("  and there are no credentials.")
    print("\n  WHAT THIS DOES NOT ESTABLISH: that the long book makes money. It")
    print("  establishes that the config you would run is the config that was")
    print("  measured. The number is a separate claim with its own gates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
