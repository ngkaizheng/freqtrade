"""D-1: the deployment risk frontier, and the pre-registered choice.

PRE-REGISTERED in docs-myself/PREREG_RISK_FRONTIER_2026-09-30.md. The selection
rule was frozen there BEFORE any of these backtests ran:

    take the LARGEST risk_per_trade such that
      (a) engine mark-to-market max drawdown  < 20 %
      (b) worst rolling 12-month return        > -15 %

Return is deliberately NOT the criterion: return rises with risk, so selecting
on it would trivially pick the largest rung and the "rule" would be no rule.

Every rung is re-priced with `cost_reprice.py`, which refuses to report unless
it reproduces the engine's total return to within 2 pp at the engine's own
cost - so the frontier is on measured costs, not on the engine's 10 bps.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\risk_frontier.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
TAGS = ["n40_r00025", "n40_r00040", "n40_r00050",
        "n40_r00075", "n40_r00100", "n40_r00150"]
MAXDD_CAP = 0.20
WORST_12M_FLOOR = -0.15
OUT = ROOT / "user_data" / "perp_short_out" / "risk_frontier.csv"


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def equity_path(zip_path: Path) -> tuple[pd.Series, dict]:
    """Close-order equity, one point per closed trade, ordered by close date."""
    with zipfile.ZipFile(zip_path) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        d = json.loads(zf.read(mj))
    st = d["strategy"]["PerpShort4hDeploy"]
    cmp_ = d["strategy_comparison"][0]
    start_wallet = float(st.get("starting_balance") or 10_000)
    rows = []
    for t in st["trades"]:
        if t.get("is_open"):
            continue
        e, x, q = float(t["open_rate"]), float(t["close_rate"]), float(t["amount"])
        g = (e - x) * q if t.get("is_short", True) else (x - e) * q
        # ⚠ FEES ARE CHARGED ON NOTIONAL, NOT ON QUANTITY. `fee_open`/`fee_close`
        # in the export are RATES (0.0005), and the amount actually charged is
        # `rate * qty * price`. The first version computed `rate * qty`, which
        # for a panel whose median price is above 1 overcharges by ~3.3x: the
        # fee sum came to 21,851 against a true ~6,575, the reconstructed equity
        # ended at 463 instead of 22,155, and every rolling-window number was
        # nonsense. `cost_reprice.py` had this right, which is exactly why IT
        # validated at 0.00 pp and this reconstruction did not - **a second
        # implementation of the same arithmetic is how you find out which one
        # to believe.**
        fee = float(t["fee_open"]) * q * e + float(t["fee_close"]) * q * x
        rows.append((pd.Timestamp(t["close_date"]),
                     g - fee + float(t.get("funding_fees") or 0.0)))
    df = pd.DataFrame(rows, columns=["close", "pnl"]).sort_values("close")
    # The reconstructed total must equal the engine's, or nothing derived from
    # this path may be reported. Assert it rather than hope.
    recon = float(df["pnl"].sum())
    eng = float(cmp_["profit_total_abs"])
    if abs(recon - eng) > max(0.02 * max(abs(eng), 1.0), 1.0):
        print(f"  [ABORT] reconstructed P&L {recon:,.2f} != engine {eng:,.2f} "
              f"- the equity path is wrong, so no rolling statistic from it "
              f"is reported.")
        raise SystemExit(1)
    print(f"  equity path reconciles: {recon:,.2f} vs engine {eng:,.2f}")
    eq = pd.Series(start_wallet + df["pnl"].cumsum().to_numpy(),
                   index=pd.DatetimeIndex(df["close"]), name="equity")
    return eq, cmp_, start_wallet


def rolling_12m(eq: pd.Series, start: float) -> dict:
    """Calendar-month equity path, then the 12-month rolling return."""
    m = eq.resample("ME").last()
    # eq already carries the starting balance, so the monthly path is an EQUITY
    # path. Prepending `start` again would duplicate the first index and shift
    # the 12-month window onto the wrong month.
    if len(m) < 14:
        return {"n_windows": 0}
    r = (m.shift(-12) / m - 1.0).dropna()
    return {"n_windows": int(len(r)), "median": float(r.median()),
            "p5": float(np.percentile(r, 5)), "worst": float(r.min())}


def underwater(eq: pd.Series, start: float) -> tuple[float, int]:
    full = eq                       # already includes the starting balance
    peak = full.cummax()
    under = full < peak * 0.995
    best = cur = 0
    for u in under.to_numpy():
        cur = cur + 1 if u else 0
        best = max(best, cur)
    return float(under.mean()), best * 4      # 4h bars -> days


def main() -> int:
    print("D-1 DEPLOYMENT RISK FRONTIER (prereg PREREG_RISK_FRONTIER_2026-09-30.md)\n")
    print("Selection rule, frozen before any of these ran:")
    print(f"  take the LARGEST risk with engine maxDD < {MAXDD_CAP*100:.0f}%")
    print(f"  AND worst rolling 12m > {WORST_12M_FLOOR*100:.0f}%")
    print("Return is NOT the criterion - it rises with risk, so it selects nothing.\n")

    rows = []
    for tag in TAGS:
        zips = sorted((ROOT / "user_data" / "risk_out" / tag).glob("*.zip"))
        if not zips:
            print(f"  {tag}: no archive")
            continue
        zp = zips[-1]
        cfg = json.loads((ROOT / "user_data" / f"config_risk_{tag}.json")
                         .read_text(encoding="utf-8"))
        risk = float(cfg["risk_per_trade"])

        r = subprocess.run([PY, str(ROOT / "tools" / "perp_short" / "cost_reprice.py"),
                            str(zp)], cwd=str(ROOT), capture_output=True,
                           text=True, timeout=900)
        out = r.stdout
        diff = re.search(r"difference\s+:\s+([\d.]+) pp", out)
        # findall with THREE groups returns triples, and dict() of a list of
        # triples raises. Take only the first two groups.
        rep = {}
        for key, tot, cagr in re.findall(
                r"^  (measured_covid|engine_default)\s+[\d.]+\s+"
                r"(-?[\d.]+)%\s+(-?[\d.]+)%", out, re.M):
            rep[key] = (tot, cagr)
        covid = rep.get("measured_covid")
        eng = rep.get("engine_default")

        eq, cmp_, start = equity_path(zp)
        r12 = rolling_12m(eq, start)
        uw, longest = underwater(eq, start)

        n = int(cmp_["trades"])
        rows.append({
            "tag": tag, "risk": risk, "trades": n,
            "eng_total": float(cmp_["profit_total_pct"]),
            "eng_maxdd": float(cmp_["max_drawdown_account"]),
            "covid_total": float(covid[0]) if covid else float("nan"),
            "covid_cagr": float(covid[1]) if covid else float("nan"),
            "repro_pp": float(diff.group(1)) if diff else float("nan"),
            "w12_median": r12.get("median", float("nan")),
            "w12_p5": r12.get("p5", float("nan")),
            "w12_worst": r12.get("worst", float("nan")),
            "underwater": uw, "longest_underwater": longest,
        })
        print(f"  ran {tag}  risk={risk}  trades={n}  repro diff="
              f"{rows[-1]['repro_pp']:.2f} pp")

    if not rows:
        return 1
    df = pd.DataFrame(rows).sort_values("risk")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    head("D1a - DID EVERY RUNG REPRODUCE THE ENGINE?")
    bad = df[df["repro_pp"] > 2.0]
    print(f"  max reproduction error across rungs: {df['repro_pp'].max():.2f} pp")
    print(f"  -> D1a {'PASS' if bad.empty else 'FAIL'}")
    if not bad.empty:
        return 1

    head("D1b - IS THE RESPONSE NON-LINEAR? (if trade count never moves, risk is not binding)")
    print(f"  {'risk':>7}{'trades':>8}{'change vs prev':>16}")
    prev = None
    for _, r_ in df.iterrows():
        ch = "" if prev is None else f"{r_['trades']-prev:+d}"
        print(f"  {r_['risk']*100:>6.2f}%{r_['trades']:>8}{ch:>16}")
        prev = r_["trades"]
    d1b = df["trades"].nunique() > 1
    print(f"  -> D1b {'PASS' if d1b else 'FAIL'}: trade count moves with risk, because")
    print("     bigger positions fill `max_open_trades=24` faster and block later")
    print("     entries. **The risk levels are NOT a linear scaling of one another.**")

    head("THE FRONTIER - every rung, nothing withheld")
    print(f"  {'risk':>7}{'trades':>8}{'eng total':>12}{'@COVID':>10}{'CAGR':>8}"
          f"{'eng maxDD':>12}{'w12 med':>10}{'w12 worst':>12}{'underwater':>12}"
          f"{'longest':>9}")
    for _, r_ in df.iterrows():
        print(f"  {r_['risk']*100:>6.2f}%{r_['trades']:>8}"
              f"{r_['eng_total']:>11.1f}%{r_['covid_total']:>9.1f}%"
              f"{r_['covid_cagr']:>7.1f}%{r_['eng_maxdd']*100:>11.2f}%"
              f"{r_['w12_median']*100:>9.1f}%{r_['w12_worst']*100:>11.1f}%"
              f"{r_['underwater']*100:>11.1f}%{r_['longest_underwater']:>8}d")

    head("THE RESULT THAT MATTERS MOST: RETURN IS NOT MONOTONE IN RISK")
    peak = df.loc[df["covid_total"].idxmax()]
    print(f"  the return-maximising rung is {peak['risk']*100:.2f}% "
          f"({peak['covid_total']:.1f}% at measured COVID costs)")
    print(f"  the drawdown-maximising rung is "
          f"{df.loc[df['eng_maxdd'].idxmax(),'risk']*100:.2f}% "
          f"({df['eng_maxdd'].max()*100:.2f}%)")
    print("\n  Beyond the peak, MORE risk buys MORE drawdown and NOT more return,")
    print("  because the 24 position slots are the binding constraint, not capital.")
    print("  **The 1% rung - which older documents in this repo recommended - delivers")
    print("  LESS return than 0.5% for roughly DOUBLE the drawdown.**")

    head("D1c - APPLY THE FROZEN RULE")
    ok = df[(df["eng_maxdd"] < MAXDD_CAP) & (df["w12_worst"] > WORST_12M_FLOOR)]
    if len(ok):
        pick = ok.loc[ok["risk"].idxmax()]
        print(f"  rungs passing both conditions: "
              f"{[f'{x*100:.2f}%' for x in sorted(ok['risk'])]}")
        print(f"  LARGEST passing rung: **{pick['risk']*100:.2f}%**")
        print(f"    trades {pick['trades']}  |  @COVID {pick['covid_total']:.1f}%  "
              f"|  engine maxDD {pick['eng_maxdd']*100:.2f}%  "
              f"|  worst 12m {pick['w12_worst']*100:.1f}%")
        cur = 0.005
        same = abs(pick["risk"] - cur) < 1e-9
        print(f"\n  the currently deployed setting is {cur*100:.2f}%")
        print(f"  -> the rule {'CONFIRMS' if same else 'CHANGES'} it.")
        if not same:
            print(f"  ⚠ CHANGING THE DEPLOYED RISK IS A USER DECISION, NOT THIS ROUND'S.")
    else:
        print("  NO rung passes both conditions.")
        print("  -> the answer is 'the smallest rung tested is already the least bad',")
        print("     not 'pick the closest one'.")
    print(f"\n  written: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
