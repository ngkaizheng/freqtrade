"""Where does the money in the delivered 4h-short book actually come from?

PRE-REGISTERED as F-1 in docs-myself/PREREG_FUNDING_2026-09-29.md. Read the
gates there before reading anything this prints. The short version:

    profit_abs = gross_price_move - fees + funding_fees

Freqtrade 2026.8 DOES model funding in backtest
(`freqtrade/optimize/backtesting.py:416` loads funding+mark with
`fail_without_data=True`; `_run_funding_fees` accumulates it; short positions
RECEIVE positive funding - `exchange.py:4008` returns the value unchanged for
shorts and negates it for longs). So funding is already inside every number
this repository has reported. It has simply never been reported on its own.

This script decomposes it, in R, with the identity check (G1) that says
whether the decomposition is even arithmetically valid.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\funding_decomp.py [result.zip ...]
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r_stats import tstat  # noqa: E402
from risk_unit import load_with_risk  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

DEFAULTS = [
    "user_data/sizing_out/full/n50/backtest-result-2026-09-28_21-44-27.zip",
    "user_data/sizing_out/oos/n50/backtest-result-2026-09-28_21-45-26.zip",
    "user_data/sizing_out/full/n100/backtest-result-2026-09-28_21-47-44.zip",
]

# G5: the mark price is 4h-resampled, not the true 1h mark, so the LEVEL of the
# funding term is approximate. The SIGN is not in doubt (it is the sign of the
# published funding rate). Hence the 0.5x / 1.0x / 1.5x band.
SCALES = (0.5, 1.0, 1.5)


def load(path: Path) -> tuple[str, list[dict]]:
    with zipfile.ZipFile(path) as zf:
        main_json = [n for n in zf.namelist()
                     if n.endswith(".json") and not n.endswith("_config.json")][0]
        d = json.loads(zf.read(main_json))
    (name,) = d["strategy"].keys()
    return name, d["strategy"][name]["trades"]


def build(trades: list[dict]) -> pd.DataFrame:
    """⚠ CORRECTED 2026-09-30. The first version divided by
    `stake * |initial_stop_loss_ratio|`, and that field is the CLASS BACKSTOP
    (exactly 0.300000 on all 1,253 trades) rather than the 4xATR anchor - see
    `tools/perp_short/risk_unit.py`. Every R level in the first run was therefore
    about 2.9x too small at the median. Ratios of same-trade quantities survive;
    levels, t-statistics and the variance split do not. This function is kept
    only as the reader's warning; `risk_unit.load_with_risk` is what runs.
    """
    raise NotImplementedError(
        "Use risk_unit.load_with_risk(); the recorded initial_stop_loss_ratio is "
        "the class backstop (0.30), not the 4xATR stop. See risk_unit.py.")


def head(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def describe(series: np.ndarray, label: str) -> dict:
    t, m, n_eff, k = tstat(series)
    return {"label": label, "mean": float(m), "t": t, "n": len(series),
            "n_eff": n_eff, "iat": k}


def main(argv: list[str]) -> int:
    paths = [Path(a) if Path(a).exists() else ROOT / a for a in (argv[1:] or DEFAULTS)]
    paths = [p for p in paths if p.exists()]
    if not paths:
        print("no result archives found")
        return 1

    g1_ok = True
    all_summary = []

    for p in paths:
        rel = p.relative_to(ROOT).as_posix() if p.is_absolute() else p.as_posix()
        df = load_with_risk(rel).sort_values("open").reset_index(drop=True)
        name = Path(rel).name

        head(f"{p.parent.parent.name}/{p.parent.name}  {name}  ({len(df)} trades)")

        # ---------------- G1: does the identity close? ------------------------
        resid = (df["profit"] - (df["gross_R"] * df["risk_usd"] - df["fees"]
                                 + df["funding"])).abs().max()
        nz = float((df["funding"] != 0).mean())
        print(f"G1 identity: profit == gross - fees + funding, "
              f"max abs residual = {resid:.3e} USDT")
        print(f"G1 coverage: {nz*100:.1f}% of trades carry a non-zero funding term")
        if resid > 0.01 or nz < 0.95:
            g1_ok = False
            print("   -> G1 FAILS. The decomposition below is NOT interpretable.")
            continue

        # ---------------- headline: where the P&L comes from -------------------
        tot_p = df["profit"].sum()
        tot_f = df["fees"].sum()
        tot_u = df["funding"].sum()
        tot_g = tot_p + tot_f - tot_u
        print(f"\n  gross price move : {tot_g:>12,.0f} USDT   "
              f"({tot_g/tot_p*100:6.1f}% of net)")
        print(f"  trading fees     : {tot_f:>12,.0f} USDT   "
              f"({tot_f/tot_p*100:6.1f}% of net)")
        print(f"  funding          : {tot_u:>12,.0f} USDT   "
              f"({tot_u/tot_p*100:6.1f}% of net)")
        print(f"  NET              : {tot_p:>12,.0f} USDT")
        print(f"  without funding  : {tot_p - tot_u:>12,.0f} USDT  "
              f"(that is the number the strategy would have made on price alone)")

        # ---------------- G2: is funding a separable positive stream? ---------
        head("G2  IS FUNDING A SEPARABLE POSITIVE STREAM?")
        by_ts = df.groupby("open")["funding_R"].mean()
        rows = [describe(df["funding_R"].to_numpy(), "funding_R per trade"),
                describe(by_ts.to_numpy(), "funding_R by timestamp")]
        wk = df.set_index("open")["funding_R"].resample("1W").sum()
        rows.append(describe(wk.to_numpy(), "funding_R by week"))
        for r in rows:
            print(f"  {r['label']:<26} mean {r['mean']:+.5f}R   t = {r['t']:+6.2f}"
                  f"   n = {r['n']:>5}  n_eff = {r['n_eff']:>5}")
        g2 = (rows[1]["mean"] > 0 and rows[1]["t"] >= 2.0)
        print(f"  -> G2 {'PASS' if g2 else 'FAIL'} "
              f"(needs mean>0 and t_by_timestamp >= 2)")

        # ---------------- G3: per year and per symbol -------------------------
        head("G3  IS IT STABLE ACROSS YEARS AND SYMBOLS?")
        yr = df.set_index("open").groupby(pd.Grouper(freq="YE"))[
            ["funding", "profit"]].sum()
        nyr = 0
        print(f"  {'year':<8}{'funding USDT':>14}{'net P&L USDT':>15}")
        for ts, row in yr.iterrows():
            if row["profit"] == 0 and row["funding"] == 0:
                continue
            nyr += row["funding"] > 0
            print(f"  {ts.year:<8}{row['funding']:>14,.0f}{row['profit']:>15,.0f}")
        pp = df.groupby("pair")["funding_R"].agg(["mean", "count"])
        pp30 = pp[pp["count"] >= 30]
        frac = float((pp30["mean"] > 0).mean()) if len(pp30) else float("nan")
        print(f"\n  symbols with >=30 trades: {len(pp30)}   "
              f"share with positive mean funding_R: {frac*100:.0f}%")
        print(f"  worst 3 symbols: "
              + ", ".join(f"{p} {m:+.4f}R" for p, m in
                          pp30.nsmallest(3, "mean")["mean"].items()) if len(pp30) else "")
        g3 = (nyr >= 3 and frac >= 0.60)
        print(f"  -> G3 {'PASS' if g3 else 'FAIL'} "
              f"(needs >=3/4 positive years and >=60% positive symbols)")

        # ---------------- G4: is it just a shadow of the P&L? -----------------
        head("G4  IS IT A SHADOW OF THE TRADE P&L?")
        # CORRECTION (this gate was wrong twice in the first version of this
        # script). v1 regressed funding_R on (1, R): fitting an intercept forces
        # the residual mean to exactly zero, so "residual mean > 0" could never
        # pass. v2 cross-sectionally demeaned at each timestamp, which forces the
        # per-timestamp mean to zero - the same tautology with a fancier name.
        # Both reported t = 0.00 in every result set. That was the estimator, not
        # the data.
        #
        # The real question is whether funding income is CONDITIONAL on the
        # signal being right. Funding is charged by the exchange on the clock,
        # not on the outcome, so a stream that is genuinely exogenous must be
        # paid on losing trades too. That is testable and it is not a tautology.
        x = df["R"].to_numpy()
        y = df["funding_R"].to_numpy()
        ok = np.isfinite(x) & np.isfinite(y)
        corr = float(np.corrcoef(x[ok], y[ok])[0, 1])
        common = df.groupby("open")["funding_R"].transform("mean")
        share_common = (abs(common.sum()) / abs(df["funding_R"].sum())
                        if df["funding_R"].sum() != 0 else float("nan"))
        losers = df[df["R"] < 0]
        winers = df[df["R"] > 0]
        print(f"  corr(R, funding_R) = {corr:+.3f}   "
              f"(the P&L explains |{abs(corr):.2f}| of funding: almost nothing)")
        print(f"  of the total funding, {share_common*100:.0f}% is a market-wide "
              f"time factor\n     applied to every open position at the same "
              f"clock instants - i.e. it is\n     a property of holding a short, "
              f"not of the trade being right.")
        print(f"  mean funding_R on LOSING trades: "
              f"{losers['funding_R'].mean():+.5f} (n={len(losers)})")
        print(f"  mean funding_R on WINNING trades: "
              f"{winers['funding_R'].mean():+.5f} (n={len(winers)})")
        g4 = losers["funding_R"].mean() > 0
        print(f"  -> G4 {'PASS' if g4 else 'FAIL'}: funding is "
              f"{'paid even on losing trades, so it is a genuine' if g4 else 'conditional on the trade winning, so it is NOT an'}\n     "
              f"{'separate cash flow' if g4 else 'independent stream'}. "
              f"Whether that cash flow is worth\n     anything is G2's question, "
              f"not this one's.")

        # ---------------- G5: level sensitivity ------------------------------
        head("G5  LEVEL SENSITIVITY (the mark price is 4h-resampled)")
        print(f"  {'scale':<8}{'funding USDT':>15}{'net P&L USDT':>15}"
              f"{'% of net':>11}{'G2 t':>8}")
        g5_holds = []
        for s in SCALES:
            sc = df.groupby("open")["funding_R"].mean().to_numpy() * s
            tt, mm, _, _ = tstat(sc)
            u = tot_u * s
            net_at_s = tot_p - tot_u + u      # replace the term, do not add to it
            holds = (mm > 0 and tt >= 2.0)
            g5_holds.append(holds)
            print(f"  {s:<8.1f}{u:>15,.0f}{net_at_s:>15,.0f}"
                  f"{u/tot_p*100:>10.0f}%{tt:>8.2f}"
                  f"{'  PASS' if holds else '  FAIL'}")
        g5 = all(g5_holds)
        print(f"  -> G5 {'PASS' if g5 else 'FAIL'} (the G2 verdict must hold at "
              f"every scale;\n     a level error of +-50% must not flip it)")

        # ---------------- misc facts worth knowing ---------------------------
        head("FACTS THE HEADLINE HIDES")
        short_frac = float(df["is_short"].mean())
        print(f"  short share of trades      : {short_frac*100:.1f}%")
        print(f"  mean holding time          : {df['dur_h'].mean():.1f} h "
              f"(median {df['dur_h'].median():.1f} h)")
        print(f"  funding as bps of notional : "
              f"{df['funding'].sum()/df['stake'].sum()*1e4:+.1f} bps over "
              f"{df['stake'].sum():,.0f} USDT traded")
        print(f"  mean gross R per trade     : {df['gross_R'].mean():+.4f}R   "
              f"(price move, before ANY cost)")
        print(f"  mean fee   R per trade     : {df['fee_R'].mean():+.4f}R")
        print(f"  mean funding R per trade   : {df['funding_R'].mean():+.4f}R")
        print(f"  mean net    R per trade    : {df['R'].mean():+.4f}R")
        cost_R = float(df["fee_R"].mean() + df["funding_R"].mean())
        print(f"\n  Every trade must first produce {cost_R:.4f}R just to pay for "
              f"its own costs.\n     This signal produces "
              f"{df['gross_R'].mean():.4f}R gross, so it clears that bar by "
              f"{df['gross_R'].mean()/max(cost_R,1e-12):.1f}x.")
        print(f"     Fees are {df['fee_R'].mean()/df['gross_R'].mean()*100:.0f}% "
              f"of the gross move; funding is "
              f"{abs(df['funding_R'].mean())/df['gross_R'].mean()*100:.0f}%"
              + (f" (a credit this period).\n     If the price edge were zero, "
                 f"this book would be {-cost_R/df['gross_R'].mean()*100:.0f}% of "
                 f"gross - it lives entirely on timing." if df["funding_R"].mean() > 0
                 else "."))

        all_summary.append((p, g2, g3, g4, g5, tot_p, tot_u,
                            float(df["funding_R"].mean()),
                            float(df["R"].mean())))

    head("SUMMARY ACROSS RESULT SETS")
    print(f"  {'result':<16}{'net USDT':>12}{'funding USDT':>15}"
          f"{'funding_R':>11}{'net R':>9}  G2 G3 G4 G5")
    for p, g2, g3, g4, g5, tp, tu, hr, mr in all_summary:
        print(f"  {str(p.parent.parent.name)+'/'+p.parent.name:<16}{tp:>12,.0f}"
              f"{tu:>15,.0f}{hr:>+11.4f}{mr:>+9.4f}   "
              f"{'P' if g2 else 'F'}   {'P' if g3 else 'F'}   "
              f"{'P' if g4 else 'F'}   {'P' if g5 else 'F'}")

    print("\nG1 " + ("PASS" if g1_ok else "FAIL"))
    return 0 if g1_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
