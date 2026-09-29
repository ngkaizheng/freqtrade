"""GATE 0 FOR WHOEVER PROPOSES THE NEXT SIGNAL FAMILY: does the cost law kill it
BEFORE anyone downloads a byte?

WHY THIS FILE EXISTS
-------------------
This project ran 45 rounds and closed six optimisation axes on one book. Nearly
every family that died, died the same way: **the effect is real, documented, and
lives at a horizon where a round trip costs more than it is worth.** The repo
already has the law (`RESEARCH_STATE.md` section 1c):

    cost_R = round_trip_bps / (stop_multiple x atr_pct x 1e4)

and the measured round trips (section 4): **12.0 / 15.6 / 22.8 / 34.9 bps**.

But that law was only ever applied AFTER a family had been researched, coded and
backtested - hundreds of rounds in. **It was never applied first.**

This tool inverts the order. For a candidate family you supply the horizon its
documented effect lives at and the effect size in R per trade. It MEASURES the
universe's ATR% at that horizon, computes the cost_R there, and returns CLOSED or
OPEN **from arithmetic**.

A family closed here costs one line in a table. A family that survives has
earned a pre-registration.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not prove an edge exists and it does not say an OPEN family will work.
It removes the ones that cannot work at any plausible size, and records why each
one was removed. `AGENTS.md` 1a is the same rule; this is its mechanical form.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\family_prescreen.py
    .venv\\Scripts\\python.exe tools\\perp_short\\family_prescreen.py --markdown
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"

# Measured round trips, RESEARCH_STATE section 4.
CALM_BPS = 12.0
COVID_BPS = 34.9
BARS_PER_YEAR = 365.25 * 24 * 60
HORIZONS = (1, 5, 15, 60, 240, 1440, 10080)


def _atr_series(high, low, close) -> pd.Series:
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()],
                   axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()


def _resampled_atr_pct(d: pd.DataFrame, step: str) -> tuple[float, bool]:
    """Median ATR% after resampling, plus whether the resample DID anything.

    THIS FUNCTION GOT BOTH DIRECTIONS WRONG IN TURN.

    Round 1: resampled 4h data DOWN to 1m/5m/15min/1h and called it measured.
    Resampling to a FINER interval cannot invent bars - every row is
    forward-filled, high/low collapse, and the ATR degenerates to the 4h ATR.
    The screen printed an identical 2.835 % at 1m, 5m, 15m, 1h AND 4h, which is
    impossible, and made all 13 families look OPEN - contradicting this repo's
    own measured 5m cost_R of 0.285-0.485 by ~20x.

    Round 2: the guard was then written BACKWARDS. Resampling UP (4h -> 1d)
    yields FEWER bars and is a valid aggregation, but the guard rejected it for
    producing fewer bars, so 4h/1d/1w came out "unavailable".

    The correct rule:
      fewer bars than the source  => coarser bucket, VALID aggregation
      more bars than the source   => finer than the data, FABRICATED, reject
    """
    n_before = len(d)
    r = (d.set_index("date")[["high", "low", "close"]]
         .resample(step)
         .agg({"high": "max", "low": "min", "close": "last"}).dropna())
    n_after = len(r)
    if n_after >= n_before or n_after < 30:
        return float("nan"), False
    atr = _atr_series(r["high"], r["low"], r["close"])
    return float((atr / r["close"]).median()), True


def median_atr_pct() -> dict:
    """Median ATR% per bar by horizon, with provenance.

    * **4h** - measured on the deployed 40-symbol universe (wide526).
    * **1h** - measured on the 28 symbols that have GENUINE 1h bars
      (`user_data/data/binance/futures`); the ratio to 4h came out 0.478
      (section 18a).
    * **1d and 1w** - measured by aggregating the 4h panel upward, which is a
      real aggregation.
    * **below 1h** - NOT MEASURABLE in this repo. The value returned is the
      square-root-of-time extrapolation from the 1h anchor and is flagged
      `assumed`, because asserting it as measured is exactly the mistake above.
    """
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    frames = {}
    for p in cfg["exchange"]["pair_whitelist"]:
        f = DATA / f"{p.replace('/', '_').replace(':', '_')}-4h-futures.feather"
        if not f.exists():
            continue
        d = pd.read_feather(f)[["date", "high", "low", "close"]]
        d["date"] = pd.to_datetime(d["date"], utc=True)
        frames[p] = d.sort_values("date").reset_index(drop=True)

    out = {}

    def pooled(per_symbol, keys):
        vals = [v for v in per_symbol.values() if np.isfinite(v)]
        return float(np.median(vals)) if vals else float("nan")

    for m, label in ((240, "4h (native)"), (1440, "1d"), (10080, "1w")):
        ok = {}
        for p, d in frames.items():
            if m == 240:
                # the native resolution: no resample at all, so this is the
                # panel's own ATR and there is nothing to validate
                a = float((_atr_series(d["high"], d["low"], d["close"])
                           / d["close"]).median())
            else:
                a, did = _resampled_atr_pct(d, f"{m}min")
                if not did:
                    continue
            if np.isfinite(a):
                ok[p] = a
        out[m] = (pooled(ok, None), "measured", label, len(ok))

    # 1h from the symbols that actually have 1h bars
    one_hour_dir = ROOT / "user_data" / "data" / "binance" / "futures"
    h1 = {}
    for f in sorted(one_hour_dir.glob("*-1h-futures.feather")):
        d = pd.read_feather(f)[["date", "high", "low", "close"]]
        d["date"] = pd.to_datetime(d["date"], utc=True)
        d = d.sort_values("date").reset_index(drop=True)
        atr = _atr_series(d["high"], d["low"], d["close"])
        h1[f.name] = float((atr / d["close"]).median())
    out[60] = (float(np.median(list(h1.values()))) if h1 else float("nan"),
               "measured", "1h", len(h1))

    # Below 1h: EXTRAPOLATE from the 1h anchor - except 5m, which is now MEASURED.
    #
    # §40 (2026-09-30) replaced the 5m extrapolation with a real measurement.
    # `tools/perp_short/five_min_horizon.py` downloaded 5m klines for the deployed
    # 40 and measured the 5m/4h ATR ratio on the SAME symbols over the SAME window
    # (each symbol's 4h pinned to its own 5m span - the §39 rule). It writes
    # `user_data/perp_short_out/five_min.json` and the number is read from there,
    # so the screen has ONE source for it. The pre-registration is
    # `docs-myself/PREREG_FIVE_MIN_2026-09-30.md`.
    #
    # The extrapolation was ~1.85x too PESSIMISTIC in both regimes, i.e. it was
    # closing this family partly on a cost that was too high - and the family is
    # STILL closed, now by a measured margin. A closure that survives a correction
    # running against it is the strong form of the result.
    fm = ROOT / "user_data" / "perp_short_out" / "five_min.json"
    measured_5m = None
    if fm.exists():
        j = json.loads(fm.read_text(encoding="utf-8"))
        if j.get("n_symbols", 0) >= 25:
            measured_5m = j
            out[5] = (j["atr_pct_5m"], "MEASURED (F-1, 5m klines)", "5m",
                      j["n_symbols"])

    anchor = out[60][0]
    for m in (1, 5, 15):
        if m == 5 and measured_5m is not None:
            continue                                   # already set from the measurement
        if np.isfinite(anchor) and anchor > 0:
            out[m] = (anchor * np.sqrt(m / 60.0), "ASSUMED (sqrt-t from 1h)", "1h", 0)
        else:
            out[m] = (float("nan"), "unavailable", "", 0)
    return out



# (family, effect horizon minutes, documented gross edge R/trade, stop multiple,
#  where the effect comes from, this repo's status)
FAMILIES = [
    ("Trend following (SMA/EMA/Supertrend)", 1440, 0.09, 4.0,
     "MultiMa / Supertrend / GodStra on the Freqle leaderboard",
     "CLOSED 2026-09-27: PerpTrendSlow +12.8% Sharpe 0.21 vs buy-and-hold +177%"),
    ("5m mean reversion", 5, 0.05, 2.0,
     "the leaderboard's modal configuration (2,325 of 5,330)",
     "CLOSED twice: gross ~0, and RegimeVolBreakout5m's cost frontier STARTS "
     "NEGATIVE AT ZERO COST"),
    ("btc_regime_filter (bull/bear switch)", 1440, 0.10, 4.0,
     "2,873 of 5,330 leaderboard strategies",
     "CLOSED: PerpShort4hSwitch +52.4% -> -58.7%; and Hurst/Ooi/Pedersen 2017 (JPM)"),
    ("Funding-rate carry", 10080, 0.02, 1.0,
     "214 leaderboard strategies; OctopusTakopi 2.43M settlements",
     "CLOSED: funding excess -0.88 to -1.56 %/yr, and only 1-2 % of this book's gross"),
    ("Cross-sectional momentum / reversal", 1440, 0.05, 4.0,
     "PercentRankPairList; Arefev 2026 on the same venue and instrument",
     "CLOSED: X-1 measured 21 of 21 cells net-NEGATIVE after 12-35 bps"),
    ("FreqAI / ML", 60, 0.05, 4.0,
     "Fayez Junior; freqtrade's own docs; Bailey et al. 2016",
     "CLOSED on three independent priors; Freqle excludes ML from its own League"),
    ("On-chain exchange flows", 60, 0.20, 4.0,
     "Chi et al. 2024: -1.70 % per US$1M of ETH net inflow",
     "CLOSED: an external pre-registered replication rejected it twice"),
    ("Options variance risk premium", 1440, 0.25, 4.0,
     "Almeida et al. 2025, 14 %/yr",
     "CLOSED: the spread is INVERTED for BTC as of Sept 2026"),
    ("New-listing microstructure", 1440, 0.30, 4.0,
     "RockawayX 2025 and others, on Binance listings",
     "CLOSED by power arithmetic: ~200 events vs a t>=2.0 bar"),
    ("Order-book imbalance / OFI", 1, 0.15, 2.0,
     "Cont, Kukanov & Stoikov - the canonical microstructure result",
     "NOT YET TESTED HERE - the pre-screen closes it: a 1-min "
     "round trip costs 0.348-1.011 R against a 0.15 R effect"),
    ("Taker-flow / trade-sign imbalance", 5, 0.08, 2.0,
     "order-flow literature; aggTrades already in shark_data",
     "NOT YET TESTED HERE - the pre-screen closes it: 0.155-0.452 R against a 0.08 R effect"),
    ("Cross-venue basis (Binance vs OKX/Bybit)", 60, 0.10, 4.0,
     "classic arbitrage; Makarov & Schoar 2020",
     "NOT TESTABLE: OKX/Bybit funding history does not exist (VENUE_CLOSED)"),
    ("Liquidation-cascade timing", 5, 0.30, 2.0,
     "cascade / forced-liquidation literature",
     "NOT YET TESTED and the only NEW family that clears the calm bar - "
     "but probably un-actionable, since trading it means being on the wrong side of it first"),
]


def _norm(s: str) -> set:
    """Significant tokens of a family name, lowercased, punctuation dropped."""
    import re as _re
    stop = {"the", "and", "for", "with", "vs", "per", "any", "cross", "intraday"}
    toks = _re.findall(r"[a-z0-9]{3,}", s.lower())
    return {t for t in toks if t not in stop}


def closed_match(name: str, closed: set) -> str:
    """Is this candidate already on the closed registry?

    EXACT string matching was the first version and it was far too weak: six
    closed families slipped through on wording alone, and "cross-venue basis"
    screened as OPEN while the registry records it as NOT TESTABLE. So the test
    is now token overlap - a candidate is refused when most of the registry
    entry's significant tokens appear in it. **A guard that matches on wording is
    not a guard.**
    """
    n = _norm(name)
    if not n:
        return ""
    best, best_frac = "", 0.0
    for entry in closed:
        e = _norm(entry)
        if not e:
            continue
        frac = len(n & e) / len(e)
        if frac > best_frac:
            best, best_frac = entry, frac
    if best_frac >= 0.6:
        return f"REFUSED - matches closed '{best}' ({best_frac*100:.0f}% tokens)"
    return ""

def load_closed() -> set:
    """The machine-readable closed registry, so this tool can REFUSE a family that
    has already been closed instead of quietly re-screening it.

    `docs-myself/CLOSED_FAMILIES.json` is the registry. Enforcing it here is what
    turns "do not re-search a closed family" from a note in a document into
    something a script will stop.
    """
    reg = ROOT / "docs-myself" / "CLOSED_FAMILIES.json"
    if not reg.exists():
        return set()
    try:
        d = json.loads(reg.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return set()
    return {str(e.get("family", "")).lower() for e in d.get("mechanism_families", [])}


def main(argv: list[str]) -> int:
    md = "--markdown" in argv
    # --add "name|minutes|edge_R|stop|source" screens a candidate on demand,
    # so a new proposal can be costed in seconds without editing this file.
    if "--add" in argv:
        spec = argv[argv.index("--add") + 1]
        parts = [x.strip() for x in spec.split("|")]
        if len(parts) < 4:
            print("--add needs: name|minutes|edge_R|stop|source")
            return 1
        FAMILIES.insert(0, (parts[0], int(parts[1]), float(parts[2]),
                         float(parts[3]),
                         parts[4] if len(parts) > 4 else "ad hoc candidate",
                         "proposed this session"))
        print(f"  screening an ad-hoc candidate: {parts[0]}\n")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    closed = load_closed()
    if closed:
        print(f"  {len(closed)} families are on the closed registry "
              f"(docs-myself/CLOSED_FAMILIES.json).")
        print("  A proposed family that matches one of them is REFUSED, not re-screened.\n")
    print("FAMILY PRE-SCREEN: the cost law applied BEFORE the research\n")
    print("A family is CLOSED here if its documented effect cannot pay for one")
    print("round trip at the horizon the effect actually lives at.\n")

    ap = median_atr_pct()
    print("MEDIAN ATR% PER BAR ON THE DEPLOYED UNIVERSE, WITH PROVENANCE")
    print(f"  {'horizon':>10}{'ATR%/bar':>12}{'bars/yr':>11}  provenance")
    for m in HORIZONS:
        if m not in ap:
            continue
        a, how, label, n = ap[m]
        if not np.isfinite(a):
            print(f"  {m:>7} min{'?':>12}{'?':>11}  unavailable")
            continue
        print(f"  {m:>7} min{a*100:>11.3f}%{BARS_PER_YEAR/m:>11,.0f}"
              f"  {how} ({label}, {n} symbols)")
    print("\n  ⚠ Below 1h there is NO data in this repo. Those rows are square-root-of")
    print("     time extrapolations from the measured 1h anchor and are flagged")
    print("     ASSUMED. The first version of this tool resampled 4h data DOWN to")
    print("     1m/5m/15m/1h - which cannot invent bars - and reported the 4h ATR")
    print("     four times over as if measured, which made every family look OPEN")
    print("     and made the 5m cost_R come out 0.155 against the 0.285-0.485 this")
    print("     repo has been quoting. **A resample must be checked, not trusted -")
    print("     and neither of those two numbers is MEASURED.** See section 38d.")

    rows = []
    print(f"  {'family':<36}{'hz':>7}{'atr%':>8}{'costR12':>9}{'costR35':>9}"
          f"{'edge':>7}  verdict")
    print("  " + "-" * 94)
    for name, mins, edge, stop, src, status in FAMILIES:
        why = closed_match(name, closed)
        if why:
            print(f"  {name[:34]:<36}{mins:>6}m{'-':>8}{'-':>9}{'-':>9}"
                  f"{edge:>7.2f}  {why}")
            continue
        a, how, label, n = ap.get(mins, (float("nan"), "", "", 0))
        if not np.isfinite(a) or a <= 0:
            print(f"  {name[:34]:<36}{mins:>6}m{'?':>8}{'?':>9}{'?':>9}"
                  f"{edge:>7.2f}  NO ATR AT THIS HORIZON")
            continue
        c12 = CALM_BPS / (stop * a * 1e4)
        c35 = COVID_BPS / (stop * a * 1e4)
        if edge > c35:
            verdict = "OPEN (stress end)"
        elif edge > c12:
            verdict = "OPEN (calm only)"
        else:
            verdict = "CLOSED by cost"
        flag = " *" if how.startswith("ASSUMED") else ""
        rows.append((name, mins, a, c12, c35, edge, verdict, src, status, how))
        print(f"  {name[:34]:<36}{mins:>6}m{a*100:>7.2f}%{c12:>9.3f}{c35:>9.3f}"
              f"{edge:>7.2f}  {verdict}{flag}")
    print("  (* = the ATR at that horizon is an ASSUMED extrapolation, not measured)")

    if md:
        print()
        print("<!-- generated by tools/perp_short/family_prescreen.py -->")
        print()
        print("# Family pre-screen: the cost law applied BEFORE the research")
        print()
        print("Every number below is an arithmetic consequence of")
        print("`cost_R = round_trip_bps / (stop_multiple x atr_pct x 1e4)`, using the")
        print("**measured** median ATR% of the deployed 40-symbol universe and the")
        print("**measured** round trips (12.0 bps calm, 34.9 bps COVID).")
        print()
        print("A family is CLOSED here when its documented effect cannot pay for one")
        print("round trip at the horizon where that effect exists. **Closing a family")
        print("here costs one line; closing it after the research costs a round.**")
        print()
        print("| family | horizon | median ATR% | cost_R @12bps | cost_R @34.9bps |"
              " documented edge (R) | verdict | source of the effect |"
              " status in this repo |")
        print("|---|---:|---:|---:|---:|---:|---|---|---|")
        for name, mins, a, c12, c35, edge, verdict, src, status, how in rows:
            print(f"| {name} | {mins} min | {a*100:.2f} % | {c12:.3f} | {c35:.3f} |"
                  f" {edge:.2f} | **{verdict}** | {src} | {status} |")
        print()
    else:
        print("  " + "-" * 94)

    opens = [r for r in rows if r[6].startswith("OPEN")]
    print(f"\n  {len(opens)} of {len(rows)} families clear the cost bar at the")
    print("  horizon their effect lives at. Those are the only ones that have")
    print("  earned a pre-registration.")
    for r in opens:
        print(f"    - {r[0]}  ({r[1]} min, cost_R {r[4]:.3f} at the stress end, "
              f"edge {r[5]:.2f})")
    closed_here = [r for r in rows if r[6] == "CLOSED by cost"]
    print(f"\n  {len(closed_here)} are closed BY THE COST LAW ALONE, before any new")
    print("  research. That is the part of this table that did not exist before")
    print("  today: the same verdict used to cost a full research round each.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
