"""D-1: are the two delivered books actually complementary, or is the compliment a story?

    .venv\\Scripts\\python.exe tools\\perp_short\\diversity_check.py

THE CLAIM UNDER TEST
--------------------
Section 49 measured, SEPARATELY, that the short book and the long book behave differently
by year. **A table of two annual numbers is not a measurement of complementarity.** If the
two return series move together then the user has bought one bet twice and the rationale for
a second strategy is a story.

WHAT IS COMPUTED
----------------
D1  daily and monthly return series for each book, the sign agreement of monthly returns,
    and the correlation at both frequencies.
D2  the 50/50 combined book, each side keeping its own risk fraction. Both books are
    risk-sized as a fraction of equity and near-linear in size, so the combined daily
    return is the equal-weighted average. **That is a construction and is labelled as one.**
D3  the deciding comparison: combined Sharpe vs BOTH single-book Sharpes. Sharpe and not
    total return, because total return is bought with risk and the question is per unit of
    risk.
D4  the check on the check: overlap length is printed, a short overlap voids the verdict,
    and EVERY Sharpe in the comparison is recomputed from the same daily series so that no
    derived number is ever compared against an engine number silently.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEPLOYED = ROOT / "user_data" / "deployed_out"
RESULTS = ROOT / "user_data" / "backtest_results"
BULL_CFG = ROOT / "user_data" / "config_perp_bull_dry.json"
START = 10_000.0
TRADING_DAYS = 365.25        # crypto trades every calendar day; an annualiser of 252
                              # would understate the Sharpe of both books identically, but
                              # the SAME one is used on both sides so the comparison holds.
MIN_OVERLAP = 0.60


def daily_series(zip_path: Path, strategy: str) -> pd.Series | None:
    """Equity curve on calendar dates, from the engine's own per-trade record."""
    with zipfile.ZipFile(zip_path) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        pl = json.loads(zf.read(mj))
    st = pl["strategy"].get(strategy)
    if st is None:
        return None
    tr = pd.DataFrame(st["trades"])
    if len(tr) == 0:
        return None
    tr["d"] = pd.to_datetime(tr["close_date"], utc=True).dt.tz_localize(None)
    tr = tr.sort_values("d")
    eq = START + tr["profit_abs"].cumsum().to_numpy()
    s = pd.Series(eq, index=pd.DatetimeIndex(tr["d"]))
    daily = s.resample("1D").last().ffill()
    daily.iloc[0] = START
    return daily


def find_bull() -> Path | None:
    """The bull archive identified by the CONFIG INSIDE it, never by position (§47g)."""
    want = json.loads(BULL_CFG.read_text(encoding="utf-8"))
    for z in sorted(RESULTS.glob("*.zip"), key=lambda p: -p.stat().st_mtime):
        try:
            with zipfile.ZipFile(z) as zf:
                cj = [n for n in zf.namelist() if n.endswith("_config.json")]
                if not cj:
                    continue
                c = json.loads(zf.read(cj[0]))
                if (c.get("strategy") == want["strategy"]
                        and c.get("side") == want["side"]
                        and c.get("exit_mode") == want["exit_mode"]
                        and float(c.get("chandelier_atr", 0)) == float(want["chandelier_atr"])
                        and float(c.get("risk_per_trade", 0)) == float(want["risk_per_trade"])):
                    return z
        except Exception:                                       # noqa: BLE001
            continue
    return None


def sharpe(r: pd.Series) -> float:
    x = r.dropna()
    if len(x) < 5 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / x.std(ddof=1) * np.sqrt(TRADING_DAYS))


def maxdd(s: pd.Series) -> float:
    return float((s / s.cummax() - 1).min())


def main() -> int:
    short_z = sorted(DEPLOYED.glob("*.zip"))[-1]
    bull_z = find_bull()
    print("D-1  ARE THE TWO BOOKS COMPLEMENTARY, OR IS THE COMPLIMENT A STORY?\n")
    print(f"  short book : {short_z.name}")
    print(f"  long  book : {bull_z.name if bull_z else 'NOT FOUND'}")
    if bull_z is None:
        print("\nBLOCKED: the bull archive was not found by its embedded config.")
        return 2
    a = daily_series(short_z, "PerpShort4hDeploy")
    b = daily_series(bull_z, "PerpLong4h")
    if a is None or b is None:
        print("\nBLOCKED: could not rebuild an equity curve from one of the archives.")
        return 2

    # align on calendar dates - the whole point of D4
    idx = a.index.intersection(b.index)
    a, b = a.loc[idx], b.loc[idx]
    # rebase each to its own first common date so both start from the same equity
    a = a / a.iloc[0] * START
    b = b / b.iloc[0] * START
    ra, rb = a.pct_change().dropna(), b.pct_change().dropna()
    common = ra.index.intersection(rb.index)
    ra, rb = ra.loc[common], rb.loc[common]

    print(f"\n  overlap: {len(common):,} common daily returns "
          f"({common[0]:%Y-%m-%d} .. {common[-1]:%Y-%m-%d})")
    print(f"  short book days: {len(a):,},  long book days: {len(b):,}")
    if len(common) < MIN_OVERLAP * max(len(a), len(b)):
        print(f"  ** overlap under {MIN_OVERLAP:.0%} of the longer series -> NO VERDICT (prereg kill rule)")

    # ---- D1 -----------------------------------------------------------------
    ma = a.resample("ME").last().pct_change().dropna()
    mb = b.resample("ME").last().pct_change().dropna()
    mc = ma.index.intersection(mb.index)
    ma, mb = ma.loc[mc], mb.loc[mc]
    agree = float((np.sign(ma) == np.sign(mb)).mean())

    print(f"\nD1  CORRELATION")
    print(f"  daily   Pearson r : {ra.corr(rb):+.3f}   (n = {len(common):,})")
    print(f"  monthly Pearson r : {ma.corr(mb):+.3f}   (n = {len(mc)})")
    print(f"  monthly SIGN AGREEMENT: {agree*100:.1f}% of months move the same way")
    print(f"  same-year monthly sign disagreement: {100*(1-agree):.1f}%")

    # ---- D2: the 50/50 combination, labelled as a CONSTRUCTION --------------
    comb = 0.5 * a + 0.5 * b
    print(f"\nD2  THE 50/50 COMBINATION  (a CONSTRUCTION, not an engine output)")
    print(f"  {'book':<26}{'total':>10}{'CAGR':>9}{'Sharpe*':>10}{'maxDD':>9}{'days':>8}")
    for name, s in (("short alone", a), ("long alone", b), ("COMBINED 50/50", comb)):
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 else float("nan")
        print(f"  {name:<26}{((s.iloc[-1]/s.iloc[0])-1)*100:>9.1f}%{cagr*100:>8.1f}%"
              f"{sharpe(s.pct_change()):>10.2f}{maxdd(s)*100:>8.1f}%{len(s):>8}")
    print("  * every Sharpe here is recomputed from the SAME daily series, so the three")
    print("    numbers are on one basis. The engine's own Sharpe is a different statistic")
    print("    on a different basis and is NOT comparable to these.")

    sh_s, sh_b, sh_c = sharpe(a.pct_change()), sharpe(b.pct_change()), sharpe(comb.pct_change())
    print(f"\nD3  THE DECIDING COMPARISON")
    print(f"  short alone Sharpe {sh_s:.2f} | long alone {sh_b:.2f} | COMBINED {sh_c:.2f}")
    wins = sh_c > max(sh_s, sh_b)
    if wins:
        print(f"  ** the COMBINED Sharpe ({sh_c:.2f}) EXCEEDS BOTH singles "
              f"({sh_s:.2f}, {sh_b:.2f}) ->")
        print(f"     the complement claim is SUPPORTED by a per-unit-of-risk measurement, **")
        print(f"     not by a two-row annual table. **")
    else:
        print(f"  ** the combined Sharpe ({sh_c:.2f}) does NOT exceed both singles ->")
        print(f"     THE COMPLEMENT CLAIM IS RETRACTED. It rested on a two-row annual")
        print(f"     table, and the per-unit-of-risk measurement does not support it. **")

    print(f"\n  BY YEAR - the claim in the form the user would meet it")
    print(f"  {'year':<8}{'short':>10}{'long':>10}{'combined':>12}{'panel':>10}")
    for y in sorted({d.year for d in common}):
        m = a.index.year == y
        if m.sum() < 20:
            continue
        rs = a[m].iloc[-1] / a[m].iloc[0] - 1
        rl = b[m].iloc[-1] / b[m].iloc[0] - 1
        rc = comb[m].iloc[-1] / comb[m].iloc[0] - 1
        print(f"  {y:<8}{rs*100:>9.1f}%{rl*100:>9.1f}%{rc*100:>11.1f}%")
    print(f"  (the panel row is in bull_axis.txt; the short book is short by construction so")
    print(f"   it should be positive when the panel falls - check it does, and if it does")
    print(f"   not then this table is wrong and should not be believed.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
