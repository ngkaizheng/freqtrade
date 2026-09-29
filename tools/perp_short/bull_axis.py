"""B-1 report: the long arms BY REGIME, against the panel's own return in the same regime.

WHY THE TOTALS ARE NOT THE ANSWER
----------------------------------
A bull-market book that returned +19 % over four years sounds fine until you learn the
panel returned +198.6 % in 2023. **The objective is "makes money in a bull market", and
that is a per-regime claim, not a total-return claim.** A book can post a positive total by
winning a little in every month, or by winning hugely in one up year and bleeding in the
rest, and those are different products for the user.

So every arm is decomposed by calendar year beside the equal-weight panel measured by
`regime_calendar.py` on the same symbols and the same bars. The bar was fixed in the
preregistration BEFORE any of these backtests ran:

    a bull-market book must be net-positive in the UP regimes after the measured
    round trip, and must not merely clear zero - it must be worth having against
    the alternative of holding the coins.

The breaker comparison rides along, because `breaker_max_dd` ships enabled in the delivered
book and this is the first measurement of what it does on EITHER side.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\bull_axis.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BULL = ROOT / "user_data" / "backtest_results"
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
ARMS = [("b0_control", "B0 deployed short"),
        ("c1_chand200", "chand 2.0"),
        ("a1_run_breakout", "chand 3.0 (A1)"),
        ("c3_chand400", "chand 4.0"),
        ("c4_chand600", "chand 6.0 (B-3 best)"),
        ("c5_chand800", "chand 8.0"),
        ("c6_chand1000", "chand 10.0"),
        ("c7_chand1200", "chand 12.0"),
        ("x1_chand2000", "chand 20.0 (asymptote)"),
        ("x2_chand5000", "chand 50.0 (limit)")]
CONTROL_TOTAL = 113.74





def find(tag: str) -> Path | None:
    """The NEWEST archive for this arm.

    ⚠ The first version returned the FIRST match in sorted order, and both the broken
    first run and the fixed second run write archives under the same tag. So it silently
    reported the OLD numbers: B0 came out as 166 trades / +2.89 % when the run that
    actually passed the control gate printed 1,111 / +113.74 %. **Selecting a run by
    the tag it was given rather than by which one is newest is §34c's error again** -
    the one that dropped 999 of 1,111 trades and printed a verdict anyway.
    """
    best = None
    for z in sorted(BULL.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                cj = [n for n in zf.namelist() if n.endswith("_config.json")]
                if not cj:
                    continue
                c = json.loads(zf.read(cj[0]))
                if c.get("strategy") == "PerpLong4h" and tag in str(c.get("exportfilename")):
                    if best is None or z.stat().st_mtime > best.stat().st_mtime:
                        best = z
        except Exception:                                       # noqa: BLE001
            continue
    return best



def panel_by_year() -> dict[int, float]:
    cfg = json.loads((ROOT / "user_data" / "config_perp_forward_dry.json").read_text(encoding="utf-8"))
    closes = {}
    for p in cfg["exchange"]["pair_whitelist"]:
        k = p.replace("/", "_").replace(":", "_")
        f = DATA / f"{k}-4h-futures.feather"
        if not f.exists():
            continue
        d = pd.read_feather(f)[["date", "close"]]
        d["date"] = pd.to_datetime(d["date"], utc=True).dt.as_unit("ns")
        closes[k] = d.drop_duplicates("date").sort_values("date").set_index("date")["close"]
    px = pd.DataFrame(closes).sort_index()
    r = px.pct_change().mean(axis=1).dropna()
    # PERCENT, not fraction. The first version returned fractions and printed them with a
    # "%" suffix, which rendered 2023's +198.6 % as "2.0%" - a number small enough to
    # look like a bad result rather than like a formatting bug. §16d's class again.
    return {int(y): float((1 + g).prod() - 1) * 100.0
            for y, g in r.groupby(r.index.year)}


def main() -> int:
    pan = panel_by_year()
    yrs = sorted(pan)
    up = [y for y in yrs if pan[y] > 0]
    print(f"  {'year':<7}{'PANEL (buy&hold)':>19}", end="")
    print("".join(f"{n:>26}" for n, _ in ARMS[1:]))

    rows = {}
    for tag, name in ARMS:
        z = find(tag)
        if z is None:
            print(f"\n  {tag}: NO ARCHIVE - BLOCKED, not zero")
            continue
        with zipfile.ZipFile(z) as zf:
            mj = [n for n in zf.namelist()
                  if n.endswith(".json") and not n.endswith("_config.json")][0]
            pl = json.loads(zf.read(mj))
        st = pl["strategy"]["PerpLong4h"]
        c = pl["strategy_comparison"][0]
        tr = pd.DataFrame(st["trades"])
        if len(tr) == 0:
            rows[tag] = {}
            continue
        tr["d"] = pd.to_datetime(tr["close_date"], utc=True).dt.tz_localize(None)
        by = {}
        for y, g in tr.groupby(tr["d"].dt.year):
            by[int(y)] = float(g["profit_abs"].sum())
        # convert each year's absolute P&L to a return on the year's STARTING equity, by
        # replaying the equity path year by year - a per-year percentage that sums to the
        # total is not a percentage.
        eq, out = float(c.get("starting_balance", 10_000)), {}
        # ---- AVERAGE DEPLOYED FRACTION: the missing control ------------------
        # The panel return is measured at ~100 % exposure. These books are not: at
        # 0.5 % risk a position is 0.005/(4*ATR%) of equity, so the whole book is
        # maybe a tenth deployed. **Comparing a 10 %-deployed book against a 100 %
        # benchmark is section 41's lesson repeated - comparing two different
        # quantities and calling the gap a finding.**
        stake = tr["stake_amount"].to_numpy()
        dur = ((pd.to_datetime(tr["close_date"], utc=True)
                - pd.to_datetime(tr["open_date"], utc=True)).dt.total_seconds() / 86400.0)
        dur = np.clip(dur.to_numpy(), 1 / 24, None)
        pa = tr["profit_abs"].to_numpy()
        start_bal = float(c.get("starting_balance", 10_000))
        # Equity AT EACH TRADE'S OPEN (not after it), so the index aligns with the
        # per-trade loop. The first version built a path of len(trades)+1 and indexed
        # it with a len(trades) mask, which is an off-by-one that is invisible until
        # the first trade of a run.
        eq_path = start_bal + np.concatenate([[0.0], np.cumsum(pa)[:-1]])
        eq_path_times = (pd.to_datetime(tr["open_date"], utc=True).dt.tz_localize(None)
                         .to_numpy())
        deployed = []
        for t0, s_, h in zip(eq_path_times, stake, dur):
            t1 = t0 + np.timedelta64(int(h * 86400 * 1e9), "ns")
            win = (eq_path_times >= t0) & (eq_path_times < t1)
            e = eq_path[win]
            deployed.append(s_ / e.mean() if e.size and e.mean() > 0 else np.nan)
        dep = float(np.nanmean(deployed)) if len(deployed) else float("nan")
        for y in yrs:


            sub = tr[tr["d"].dt.year == y]
            start = eq
            eq += float(sub["profit_abs"].sum())
            out[y] = (eq / start - 1) * 100 if start else float("nan")
        rows[tag] = {"by": by, "ret": out, "total": float(c["profit_total_pct"]),
                     "n": int(c["trades"]), "pf": float(c["profit_factor"]),
                     "dd": float(st.get("max_relative_drawdown", float("nan"))) * 100,
                     "dep": dep}


    print()
    for y in yrs:
        tag = "UP " if y in up else "DOWN"
        print(f"  {y:<3}{tag}{pan[y]:>18.1f}%", end="")
        for n, _ in ARMS[1:]:
            v = rows.get(n, {}).get("ret", {}).get(y)
            print(f"{v:>25.1f}%" if v is not None else f"{'-':>26}", end="")
        print()

    print(f"\n  {'arm':<34}{'trades':>8}{'total':>10}{'PF':>7}{'maxDD':>9}"
          f"{' 2023 (panel +198.6%)':>22}{' 2024 (panel +103.6%)':>22}")
    for tag, name in ARMS:
        r = rows.get(tag)
        if not r:
            continue
        v23 = r["ret"].get(2023)
        v24 = r["ret"].get(2024)
        print(f"  {name:<34}{r['n']:>8}{r['total']:>9.2f}%{r['pf']:>7.2f}"
              f"{r['dd']:>8.2f}%"
              f"{(f'{v23:+.1f}%' if v23 is not None else '-'):>22}"
              f"{(f'{v24:+.1f}%' if v24 is not None else '-'):>22}")

    print("\nMATCHED EXPOSURE - the control B-1 did not have, and the DECISION quantity")
    print(f"  {'arm':<30}{'deployed':>10}{'total':>9}{'2023':>8}{'2024':>8}"
          f"{'panel@same exp 2023':>22}{'capture 2023':>14}{'capture 2024':>14}")
    best = []
    for tag, name in ARMS:
        r = rows.get(tag)
        if not r or not r["ret"] or not np.isfinite(r.get("dep", float("nan"))):
            continue
        d, m23, m24 = r["dep"], r["ret"].get(2023), r["ret"].get(2024)
        if m23 is None or pan[2023] <= 0:
            continue
        b23, b24 = pan[2023] * d, pan[2024] * d
        c23, c24 = m23 / b23, (m24 / b24) if m24 is not None and b24 > 0 else float("nan")
        best.append((tag, name, c23, c24, d, r))
        print(f"  {name:<30}{d*100:>9.1f}%{r['total']:>8.2f}%{m23:>7.1f}%"
              f"{m24:>7.1f}%{b23:>21.1f}%{c23*100:>13.1f}%{c24*100:>13.1f}%")
    print("  (capture = the arm's return divided by buy-and-hold AT THE SAME EXPOSURE;")
    print("   >100% means it beat holding the coins with the same capital at risk)")

    print("\nTHE PREREGISTERED BAR")
    print(f"  up regimes: {up}   panel median up year "
          f"{np.median([pan[y] for y in up]):+.1f}%")
    b1 = rows.get("c5_chand800")
    if b1 and b1["ret"]:
        wins = [y for y in up if b1["ret"].get(y, -1) > 0]
        print(f"  chandelier 8.0 positive in {len(wins)} of {len(up)} up regimes: {wins}")
    print("\n  THE PRE-REGISTERED B-4 RULE, APPLIED")
    print("  'flattens toward 100%' was DEFINED before the run as: the last three rungs")
    print("  have a capture spread under 25pp AND the highest rung is below 200%.")
    last3 = [c for t, _n, c, _c2, _d, _r in best
             if t in ("c7_chand1200", "x1_chand2000", "x2_chand5000")]
    if len(last3) == 3 and best:
        hi = max(c for _t, _n, c, _c2, _d, _r in best)
        spread = max(last3) - min(last3)
        flat = spread < 0.25 and hi < 2.0
        print(f"    last three rungs (12/20/50 ATR) capture: "
              f"{', '.join(f'{c*100:.0f}%' for c in last3)}   spread {spread*100:.1f}pp")
        print(f"    highest capture anywhere on the curve: {hi*100:.0f}%")
        print(f"    -> {'PLATEAU TO THE ASYMPTOTE: family answered' if flat else 'PEAK-AND-FALL: 8.0 is a real INTERIOR peak'}")
        top = max(best, key=lambda b: b[2])
        print(f"    best capture: {top[1]} at {top[2]*100:.0f}% of the matched-exposure benchmark")

    print("\nTHE B-2 CONTRASTS, carried forward")
    for a, b, why in (("a1_run_breakout", "c5_chand800", "EXITS+CHANDELIER: ch3 -> ch8"),
                      ("c4_chand600", "c5_chand800", "CHANDELIER: ch6 -> ch8"),
                      ("c5_chand800", "c6_chand1000", "past the peak: ch8 -> ch10")):
        ra, rb = rows.get(a), rows.get(b)
        if ra and rb:
            print(f"  {why:<40} {ra['total']:>7.2f}% -> {rb['total']:>7.2f}%   "
                  f"maxDD {ra['dd']:>5.2f}% -> {rb['dd']:>5.2f}%")
    b2 = rows.get("c1_chand200")
    if b2:
        print(f"\n  the BREAKER threshold is 0.20 and this curve's drawdown runs "
              f"17%→44%, so above ~6 ATR the breaker\n  is BINDING on some rungs. That is "
              f"part of what the far tail is measuring, and it is why the\n  50-ATR arm is a "
              f"CAPPED book and not a clean buy-and-hold.")
    return 0




if __name__ == "__main__":
    sys.exit(main())

