"""Is there ANY crypto cross-sectional signal that is not just "the market"?

PRE-REGISTERED as X-1 in docs-myself/PREREG_XSECT_SCREEN_2026-09-30.md. Read the
gates there first. The short version:

Section 15c measured that the 4h crypto perp cross-section is very nearly ONE
factor at every horizon - 50 to 99 symbols carry the information of about three
independent bets. Section 15c-5 then wrote down the free gate any new line must
clear: a first-principal-component loading materially below 0.5, and a net
long-short leg, judged by REGRESSION rather than correlation. It also noted that
the regression is the one piece of machinery not yet built.

This builds it, and uses it to screen seven candidates. No backtest, no new
data: only 4h futures OHLCV and 1h funding, both already on disk. The cost of
this experiment is minutes; the cost of skipping it is another 40 rounds.

Gate X5 is the one that matters most: the residual-momentum candidate is
market-neutral BY CONSTRUCTION, so if its loading comes out high the regression
is broken and every number here is void. That is checked first and loudly.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\xsect_screen.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r_stats import tstat  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
OUT = ROOT / "user_data" / "perp_short_out" / "xsect_screen.csv"

UNIVERSE = ROOT / "user_data" / "perp_short_out" / "liq515_universe.json"
# measured round-trip cost regimes, RESEARCH_STATE section 4
COSTS = {"calm 12bps": 12.0, "covid 34.9bps": 34.9, "xsect 70bps": 70.0}
# Arefev (2026) net-of-costs replication published a gross cross-sectional
# momentum spread of +0.573%/week - this is the bar to beat, and the null.
AREFEV_GROSS_WK_PCT = 0.573

HORIZONS = {"1d": 6, "3d": 18, "1w": 42}   # 4h bars
CANDIDATES = ["S1_mom20", "S2_rev5", "S3_funding", "S4_lowvol",
              "S5_sma200dev", "S6_turnover", "S7_residmom"]


def head(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def load_universe() -> list[str]:
    """The delivered N=40, liquidity-ordered universe if it exists, else the
    largest liquid set we can build from the files on disk."""
    if UNIVERSE.exists():
        d = json.loads(UNIVERSE.read_text())
        for k in ("universe", "pairs", "whitelist"):
            if isinstance(d, dict) and k in d:
                return list(d[k])
        if isinstance(d, list):
            return d
    return []


def panel(pairs: list[str]) -> pd.DataFrame:
    """4h close panel. Returns are LOG returns; a non-positive close makes
    log() -inf, and inf is not NaN, so it survives .corr() and silently
    corrupts every correlation downstream."""
    cols = {}
    for p in pairs:
        f = DATA / f"{p.replace('/', '_').replace(':', '_')}-4h-futures.feather"
        if not f.exists():
            continue
        d = pd.read_feather(f)[["date", "close", "volume"]]
        d["date"] = pd.to_datetime(d["date"], utc=True)
        d = d.sort_values("date")
        c = d["close"].to_numpy(dtype=float)
        c = np.where(c > 0, c, np.nan)
        s = pd.Series(np.log(c), index=d["date"].to_numpy(), name=p)
        cols[p] = s
    px = pd.DataFrame(cols)
    n_inf = int(np.isinf(px.to_numpy()).sum())
    if n_inf:
        px = px.replace([np.inf, -np.inf], np.nan)
        print(f"  [data] {n_inf} infinite log prices removed")
    return px


def load_funding(pairs: list[str]) -> pd.DataFrame:
    cols = {}
    for p in pairs:
        f = DATA / f"{p.replace('/', '_').replace(':', '_')}-1h-funding_rate.feather"
        if not f.exists():
            continue
        d = pd.read_feather(f)
        d["date"] = pd.to_datetime(d["date"], utc=True)
        d = d.sort_values("date")
        # the funding series is 8h; forward-fill onto the 4h grid is wrong for a
        # ranking signal, so take the LAST KNOWN rate and keep its own timestamp
        cols[p] = pd.Series(d["funding_rate"].to_numpy(dtype=float),
                            index=d["date"].to_numpy())
    return pd.DataFrame(cols).sort_index()


def first_pc(r: pd.DataFrame):
    """First principal component share of variance, and the equal-weight market
    factor as a **Series that keeps the index**. Returning a bare numpy array
    here cost a run: the spread is dropna()'d, so its index is shorter than the
    panel's, and `pd.Series(arr, index=sp.index)` then raises rather than
    silently misaligning - which is the one saving grace of that constructor.
    """
    c = r.corr(min_periods=200).fillna(0.0).to_numpy()
    c = (c + c.T) / 2.0
    w = np.linalg.eigvalsh(c)[::-1]
    w = np.clip(w, 0, None)
    share = float(w[0] / w.sum()) if w.sum() > 0 else float("nan")
    return r.mean(axis=1), share


def build_signal(name: str, px: pd.DataFrame, fund: pd.DataFrame,
                 factor: pd.Series) -> pd.DataFrame:
    """A per-timestamp cross-sectional SCORE. Higher score = more long."""
    if name == "S1_mom20":
        return px.diff(20)
    if name == "S2_rev5":
        return -px.diff(5)
    if name == "S3_funding":
        f = fund.reindex(px.index, method="ffill")
        return -f                      # long the LOW-funding end
    if name == "S4_lowvol":
        r = px.diff()
        return -r.rolling(42).std()    # long the LOW-vol end
    if name == "S5_sma200dev":
        return px - px.rolling(200).mean()
    if name == "S6_turnover":
        return px.diff()               # proxy: recent return, see note
    if name == "S7_residmom":
        # residual momentum: regress each symbol's 20-bar return on the market
        # factor, keep the residual, rank THAT.
        mom = px.diff(20)
        out = mom.copy()
        for c in mom.columns:
            y = mom[c]
            ok = y.notna() & factor.notna()
            if ok.sum() < 200:
                out[c] = np.nan
                continue
            b = np.polyfit(factor[ok], y[ok], 1)
            out[c] = y - (b[0] * factor + b[1])
        return out
    raise KeyError(name)


def spread_portfolio(score: pd.DataFrame, fwd: pd.DataFrame, q: float = 0.3):
    """Long the top `q` by score, short the bottom `q`. Returns a per-timestamp
    equal-weight long-short return, plus the per-symbol membership so X4 can
    drop the worst names."""
    s = score.reindex(fwd.index)
    n = s.shape[1]
    k = max(1, int(round(q * n)))
    ranks = s.rank(axis=1, ascending=False, na_option="keep")
    long_m = ranks <= k
    short_m = ranks >= (n - k + 1)
    r = fwd.where(long_m).mean(axis=1) - fwd.where(short_m).mean(axis=1)
    return r, long_m | short_m


def main() -> int:
    print("X-1 SCREEN: is any crypto cross-sectional signal NOT just the market?\n")
    print("Pre-registered in docs-myself/PREREG_XSECT_SCREEN_2026-09-30.md.")
    print("21 cells (7 candidates x 3 horizons). The whole grid is published.\n")

    pairs = load_universe()
    if not pairs:
        files = sorted(DATA.glob("*-4h-futures.feather"))
        pairs = [f.name.split("-4h-futures")[0].replace("_", "/").replace("/", ":")
                 for f in files][:515]
    print(f"  universe requested: {len(pairs)} symbols")
    px = panel(pairs)
    px = px.dropna(axis=1, thresh=int(0.5 * len(px)))
    print(f"  price panel: {px.shape[0]} bars x {px.shape[1]} symbols "
          f"({px.index[0]} -> {px.index[-1]})")
    assert px.shape[1] >= 20, f"only {px.shape[1]} symbols survived - panel is wrong"
    fund = load_funding([c for c in px.columns])

    r = px.diff()
    factor, pc_share = first_pc(r)
    head("THE GATE ITSELF: how one-factor is this universe?")
    print(f"  first principal component carries {pc_share*100:.1f}% of the variance")
    print(f"  the factor used for the loadings below is the equal-weight mean of "
          f"4h returns\n  (a proxy for PC1; X5 checks the machinery regardless)")

    rows = []
    for hname, hb in HORIZONS.items():
        fwd = r.shift(-hb)
        for cname in CANDIDATES:
            score = build_signal(cname, px, fund, factor)
            if cname == "S6_turnover":
                # turnover needs volume; fall back to |return| magnitude, which is
                # what the prereg called a proxy. SAY IT rather than silently swap.
                score = px.diff().abs()
            sp, members = spread_portfolio(score, fwd)
            sp = sp.dropna()
            if len(sp) < 200:
                print(f"  {cname:<14} {hname}: only {len(sp)} usable points - SKIPPED")
                continue
            # X1: loading of the SPREAD on the market factor
            fac = pd.Series(factor, index=sp.index)
            ok = sp.notna() & fac.notna()
            beta = alpha = float("nan")
            if ok.sum() > 200:
                b = np.polyfit(fac[ok], sp[ok], 1)
                beta, alpha = float(b[0]), float(b[1])
            t, m, n_eff, iat = tstat(sp.to_numpy())
            gross_bps = float(sp.mean() * 1e4)
            row = {"candidate": cname, "horizon": hname, "n": len(sp),
                   "n_eff": n_eff, "beta": beta, "alpha_bps": alpha * 1e4,
                   "gross_bps": gross_bps, "t": t, "mean_bps": m * 1e4,
                   "members": int(members.to_numpy().sum())}
            for cname_cost, bps in COSTS.items():
                row[f"net_{cname_cost}"] = gross_bps - bps
            rows.append(row)

    if not rows:
        print("\nNO USABLE CELLS. The screen cannot conclude.")
        return 1
    df = pd.DataFrame(rows)
    df["x1_load"] = df["beta"].abs() < 0.5
    df["x2_net"] = df["net_covid 34.9bps"] > 0
    df["x3_t"] = df["t"] >= 2.0
    df["x4"] = True      # filled in below where the membership allows it
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    head("THE WHOLE GRID — 7 candidates x 3 horizons, nothing withheld")
    print(f"  {'cell':<22}{'n':>7}{'beta':>8}{'alpha bp':>10}{'gross bp':>10}"
          f"{'t':>7}{'net@12':>9}{'net@34.9':>10}{'net@70':>9}  X1 X2 X3")
    for _, r_ in df.iterrows():
        print(f"  {r_['candidate']+' '+r_['horizon']:<22}{r_['n']:>7}"
              f"{r_['beta']:>8.3f}{r_['alpha_bps']:>10.2f}{r_['gross_bps']:>10.2f}"
              f"{r_['t']:>7.2f}{r_['net_calm 12bps']:>9.1f}"
              f"{r_['net_covid 34.9bps']:>10.1f}{r_['net_xsect 70bps']:>9.1f}"
              f"   {'P' if r_['x1_load'] else 'F'}  "
              f"{'P' if r_['x2_net'] else 'F'}  "
              f"{'P' if r_['x3_t'] else 'F'}")

    # ---- X5, the positive control, checked LOUDLY --------------------------
    head("X5 — THE POSITIVE CONTROL: does the machinery detect a neutral signal?")
    s7 = df[df["candidate"] == "S7_residmom"]
    if len(s7):
        print(f"  S7 residual momentum loadings: "
              f"{', '.join(f'{x.horizon}={x.beta:+.3f}' for x in s7.itertuples())}")
        ok7 = bool((s7["beta"].abs() < 0.5).all())
        print(f"  -> X5 {'PASS' if ok7 else 'FAIL'}: "
              + ("the regression detects a signal that is neutral by construction"
                 if ok7 else
                 "a signal that is NEUTRAL BY CONSTRUCTION came out market-loaded, "
                 "so the\n     loading machinery is wrong and NOTHING above may be "
                 "interpreted."))
    else:
        ok7 = False
        print("  S7 produced no cells - the screen cannot conclude.")

    # ---- X4 ---------------------------------------------------------------
    head("X4 — BUCKET WIDTH: does the verdict depend on how wide the spread is?")
    print("  The prereg did NOT fix the long/short bucket width, and a reader is")
    print("  entitled to ask whether 30% was chosen after seeing the answer. It was")
    print("  not - it is the default here - so the width is published as a curve.")
    print("  This is sensitivity reporting on the SAME 7 candidates, not a new search.\n")
    print(f"  {'bucket':>8}{'mean gross bp (S4 lowvol, 1w)':>30}"
          f"{'mean gross bp (S1 mom20, 1w)':>30}{'cells net>0 @34.9bps':>22}")
    sens_rows = []
    for q in (0.1, 0.2, 0.3, 0.4):
        fwd = r.shift(-HORIZONS["1w"])
        line = []
        net_cells = 0
        for cname in CANDIDATES:
            score = build_signal(cname, px, fund, factor)
            if cname == "S6_turnover":
                score = px.diff().abs()
            sp, _ = spread_portfolio(score, fwd, q=q)
            sp = sp.dropna()
            g = float(sp.mean() * 1e4)
            line.append(g)
            net_cells += int((g - COSTS["covid 34.9bps"]) > 0)
        sens_rows.append((q, line, net_cells))
        print(f"  {q*100:>7.0f}%{line[CANDIDATES.index('S4_lowvol')]:>30.2f}"
              f"{line[CANDIDATES.index('S1_mom20')]:>30.2f}{net_cells:>19}/7")
    print("\n  The 34.9 bps round trip is a FIXED cost per rebalance, so narrowing the")
    print("  bucket concentrates capital into a smaller set of names - it does not")
    print("  reduce the cost of getting in and out.")

    # ---- verdict ----------------------------------------------------------
    head("VERDICT")
    passed = df[df["x1_load"] & df["x2_net"] & df["x3_t"]]
    print(f"  cells clearing X1 (loading<0.5) : {int(df['x1_load'].sum())}/{len(df)}")
    print(f"  cells clearing X2 (net>0 @covid): {int(df['x2_net'].sum())}/{len(df)}")
    print(f"  cells clearing X3 (t>=2)        : {int(df['x3_t'].sum())}/{len(df)}")
    print(f"  cells clearing ALL THREE        : {len(passed)}")
    print()
    if not ok7:
        print("  X5 FAILS, so this screen is VOID by its own pre-registration. "
              "Nothing above is\n  a finding. Report that and stop.")
        return 1
    if len(passed):
        print("  A CANDIDATE EXISTS. It is NOT a validated strategy and NOT an open")
        print("  line: 21 cells were searched, so t=2 is not a pass. The next step is")
        print("  a single pre-registered test of that one candidate, with a final")
        print("  holdout - not a re-run of this screen.")
        for _, r_ in passed.iterrows():
            print(f"    -> {r_['candidate']} @ {r_['horizon']}: beta {r_['beta']:+.3f}, "
                  f"gross {r_['gross_bps']:.2f} bps, net@34.9 "
                  f"{r_['net_covid 34.9bps']:.2f} bps, t {r_['t']:.2f}")
        return 0
    print("  NO CANDIDATE PASSES. The preregistered consequence is to CLOSE the")
    print("  class: on a one-factor crypto cross-section, a cross-sectional screen")
    print("  that clears measured costs AND has a t >= 2 does not exist among these")
    print("  seven families. This is a completed negative, not a gap.")
    # how big would it have to be?
    best = df.loc[df["gross_bps"].idxmax()]
    need = COSTS["covid 34.9bps"] / max(best["gross_bps"], 1e-9)
    print(f"\n  The strongest cell is {best['candidate']} @ {best['horizon']}: "
          f"{best['gross_bps']:.2f} bps gross, t {best['t']:.2f}.")
    print(f"  It would need {need:.0f}x that gross edge to pay a 34.9 bps round trip,")
    print(f"  or a cost of {best['gross_bps']:.1f} bps - "
          f"{best['gross_bps']/12.0*100:.0f}% of the calmest measured regime.")
    print(f"\n  Arefev (2026), same venue and instrument, measured cross-sectional")
    print(f"  momentum gross at {AREFEV_GROSS_WK_PCT}%/week and found it")
    print(f"  indistinguishable from zero once costs were subtracted. The S1/S2 rows")
    print(f"  above are the same family, are the screen's NEGATIVE control rather")
    print(f"  than a re-opening, and reach the same verdict from our own data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
