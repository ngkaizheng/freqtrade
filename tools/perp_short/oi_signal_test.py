"""OI-1 measurement instrument: Gate 1 (coverage), Gate 2 (does OI predict?),
Gate 3 (is it better than volume and price, or the same information?).

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\oi_signal_test.py

THE ORDER THIS IS BUILT IN MATTERS
----------------------------------
`docs-myself/PREREG_OI_2026-09-30.md` was written BEFORE the download finished and
before any OI number was seen. The pass lines live there and are NOT restated here
with different numbers. This file is the instrument those rules are applied by, so
there is exactly one copy of the rule.

CAUSALITY, AND THE SECTION 39 TRAP
----------------------------------
Section 39 cost this project a 13 % error: two computations averaged 7 years and 3.7
years and called the difference a disagreement. Two rules follow and both are enforced
here:
  * each symbol's 4h panel is restricted to THAT symbol's own OI date range, so both
    sides always cover one period;
  * OI is merged onto the 4h frame with `merge_asof(direction="backward")`, so a 4h bar
    only ever sees OI observed at or before it. A forward merge here would be
    look-ahead, and it is the easiest way to make this whole experiment lie.

NEWEY-WEST
----------
4h crypto returns are strongly autocorrelated, so an ordinary t on overlapping forward
returns is wildly overstated. Every IC becomes a Newey-West t with a Bartlett kernel and
lag `floor(4*(n/100)^(2/9))`. The lag used is printed, because a test that does not
report its own correction cannot be checked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
OI = ROOT / "user_data" / "data" / "oi"
DATA4 = ROOT / "user_data" / "data" / "wide526" / "futures"
PREREG = ROOT / "docs-myself" / "PREREG_OI_2026-09-30.md"

MIN_SYMBOLS = 30           # Gate 1, from the preregistration
IC_PASS = 0.02             # Gate 2
NW_T_PASS = 2.5            # Gate 2
HORIZONS = [4, 12, 24]      # forward 4h bars = 16h, 48h, 96h
REPAIRS: list[int] = []       # non-positive OI values neutralised, summed and reported



def archive_symbol(pair: str) -> str:
    base, _, rest = pair.partition("/")
    return f"{base}{rest.split(':')[0]}"


def nw_lag(n: int) -> int:
    return int(np.floor(4 * (max(n, 2) / 100) ** (2 / 9))) or 1


def nw_t(x: np.ndarray, lags: int) -> float:
    """Newey-West t for the MEAN of x, Bartlett kernel.

    ⚠ THE FIRST VERSION OF THIS FUNCTION WAS STRUCTURALLY WRONG AND WOULD HAVE
    CLOSED THE OI LINE ON A BUG. It did `x = x - x.mean()` to build the
    autocovariance, and then returned `x.mean() / sqrt(var/n)` - the mean AFTER
    centring, which is zero by construction. **Every t came out 0.00**, every
    Gate 2 feature "failed", and the printed verdict would have been "OI carries no
    information" - a confident negative that was pure arithmetic error.

    It was caught by `check_ic_t.py`, which runs this exact function on synthetic
    data where the right answer is known (a null must fire ~5 % at |t|>1.96, and
    here it fired 0.0 %).

    The fix is to KEEP the sample mean and only centre for the autocovariance.
    """
    x = x[np.isfinite(x)]
    n = x.size
    if n < 50:
        return float("nan")
    mu = float(x.mean())
    xc = x - mu
    if xc.std(ddof=1) == 0:
        return float("nan")
    g0 = float(xc @ xc) / n
    var = g0
    for L in range(1, min(lags, n - 1) + 1):
        w = 1.0 - L / (lags + 1.0)
        var += 2.0 * w * float(xc[L:] @ xc[:-L]) / n
    if var <= 0:
        return float("nan")
    return float(mu / np.sqrt(var / n))



def ic_and_t(x: pd.Series, y: pd.Series) -> tuple[float, float, int, int]:
    """Spearman IC and its Newey-West t, on the correct statistic.

    ⚠⚠ TWO WRONG VERSIONS WERE CAUGHT HERE BY `check_ic_t.py`, AND THE FIRST WOULD
    HAVE CLOSED THE OI LINE ON PURE ARITHMETIC ERROR.

      v1: `x = x - x.mean()` then `return x.mean() / sqrt(var/n)` - the mean AFTER
          centring, which is zero by construction. **Every t was 0.00.** Every Gate 2
          feature would have "failed" and the printed verdict would have been "OI
          carries no information". A confident negative that was a divide-by-zero
          wearing a p-value.
      v2: using the raw product of the two RANK series as the test series. Under the
          null `E[rank_x*rank_y] ~ ((n+1)/2)^2 ~ 1.6e7`, so the statistic came out
          at +101 and fired on 100 % of pure noise.

    The correct statistic is the Fisher transform of the standardised-rank product:
    standardise each rank series to mean 0 / sd 1, take `arctanh(rx*ry)`, and take a
    Newey-West t of THAT series. Under independence it is ~N(0,1), and the NW step
    is what pays for autocorrelation in 4h crypto returns.
    """
    j = pd.concat([x, y], axis=1).dropna()
    n = len(j)
    if n < 200:
        return float("nan"), float("nan"), n, 0
    rx = j.iloc[:, 0].rank()
    ry = j.iloc[:, 1].rank()
    ic = float(rx.corr(ry))
    rx = (rx - rx.mean()) / rx.std(ddof=1)
    ry = (ry - ry.mean()) / ry.std(ddof=1)
    z = np.arctanh((rx * ry).clip(-0.999999, 0.999999)).to_numpy(dtype=float)
    lag = nw_lag(n)
    return ic, nw_t(z, lag), n, lag



def build_symbol(arch: str, flat: str) -> pd.DataFrame | None:
    f, f4 = OI / f"{arch}-oi.parquet", DATA4 / f"{flat}-4h-futures.feather"
    if not f.exists() or not f4.exists():
        return None
    o = pd.read_parquet(f)
    if o.empty:
        return None
    # `set_index(<array>)` sets the index from the array but LEAVES the column in
    # place, so the later `reset_index()` hits "cannot insert create_time, already
    # exists". Set the index BY COLUMN NAME, which consumes it.
    o["create_time"] = pd.to_datetime(o["create_time"], utc=True).dt.tz_localize(None)
    o = o.set_index("create_time").sort_index()
    p = pd.read_feather(f4)
    p["date"] = pd.to_datetime(p["date"], utc=True).dt.tz_localize(None)
    p = p[(p["date"] >= o.index[0]) & (p["date"] <= o.index[-1])]
    p = p.sort_values("date").set_index("date")
    if len(p) < 300:
        return None
    m = pd.merge_asof(p.reset_index(),
                      o.reset_index().rename(columns={"create_time": "date"}),
                      on="date", direction="backward")       # CAUSAL: backward only
    return m.set_index("date")


def features(m: pd.DataFrame) -> pd.DataFrame:
    d = m
    c = d["close"]
    r = np.log(c).diff()
    # ⚠ MEASURED 2026-09-30 on the real files: 97 of ~450,000 `sum_open_interest`
    # values are exactly ZERO and none are NaN. Open interest on a live perpetual
    # cannot be zero, so these are data glitches, not events - and they must be
    # treated as MISSING **before** differencing, because a single zero in
    # `pct_change(k)` poisons k bars AFTER it, not just its own. Found by
    # `check_oi_pipeline.py`, which reported `inf` in every dOI feature; the raw
    # rate is 0.02 % of rows, so this is a repair, not a structural problem - and
    # it is recorded rather than silently absorbed.
    oi = pd.to_numeric(d["sum_open_interest"], errors="coerce")
    n_bad = int((oi <= 0).sum())
    oi = oi.where(oi > 0)
    if n_bad:
        REPAIRS.append(n_bad)
    out = pd.DataFrame(index=d.index)
    for k in (1, 4, 12):
        out[f"dOI_{k}"] = oi.pct_change(k)

    # the INTERACTION: was the move up or down while positioning expanded? This is
    # the part genuinely unavailable from price and volume.
    out["dOI_x_sign"] = out["dOI_4"] * np.sign(r)
    out["dOI_x_ret"] = out["dOI_4"] * r
    for col, tag in (("count_long_short_ratio", "retail_ls"),
                     ("count_toptrader_long_short_ratio", "top_ls"),
                     ("sum_taker_long_short_vol_ratio", "taker")):
        if col in d:
            mu = d[col].rolling(365 * 6, min_periods=200).mean()
            sd = d[col].rolling(365 * 6, min_periods=200).std()
            out[f"z_{tag}"] = (d[col] - mu) / sd.replace(0.0, np.nan)
    # CONTROLS (Gate 3) built identically so the comparison is like for like
    out["dVol_4"] = d["volume"].pct_change(4).replace([np.inf, -np.inf], np.nan)
    out["mom_4"] = c.pct_change(4)
    for h in HORIZONS:
        out[f"fwd_{h}"] = np.log(c.shift(-h) / c)
    return out


def main() -> int:
    print("OI-1  DOES OPEN INTEREST CARRY INFORMATION THE TWO BOOKS DO NOT HAVE?\n")
    print(f"rules live in {PREREG.name}; this file only applies them\n")
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    names = [(archive_symbol(p), p.replace("/", "_").replace(":", "_"))
             for p in cfg["exchange"]["pair_whitelist"]]

    frames, cov = [], []
    for arch, flat in names:
        m = build_symbol(arch, flat)
        if m is None:
            continue
        cov.append((m.index[0], m.index[-1], len(m)))
        frames.append(features(m))

    n = len(frames)
    print("GATE 1  COVERAGE")
    print(f"  symbols with usable OI + 4h overlap: {n} of {len(names)}"
          f"   (prereg needs >= {MIN_SYMBOLS})")
    if cov:
        print(f"  date range: {min(c[0] for c in cov):%Y-%m-%d} .. "
              f"{max(c[1] for c in cov):%Y-%m-%d}")
        print(f"  4h bars/symbol: min {min(c[2] for c in cov):,} "
              f"median {int(np.median([c[2] for c in cov])):,} "
              f"max {max(c[2] for c in cov):,}")
    if n < MIN_SYMBOLS:
        print(f"  ** INSUFFICIENT_DATA. No OI number is published and the line is not")
        print(f"     judged. Move to Tier 2 (volatility signals, zero download). **")
        return 2

    d = pd.concat(frames).replace([np.inf, -np.inf], np.nan)
    print(f"  pooled 4h observations: {len(d):,}")
    if REPAIRS:
        print(f"  data repairs: {sum(REPAIRS):,} non-positive `sum_open_interest` "
              f"values set to NaN (0.02 % of rows;\n                  open interest "
              f"cannot be zero on a live perp, so these are glitches, not events)")


    oi_feats = [c for c in d.columns if c.startswith(("dOI", "z_"))]
    ctl_feats = ["dVol_4", "mom_4"]

    print("GATE 2  DOES OI PREDICT FORWARD RETURNS?")
    print(f"  {'feature':<14}" + "".join(f"{'h='+str(h):>21}" for h in HORIZONS))
    best = None
    for f in oi_feats:
        line = f"  {f:<14}"
        for h in HORIZONS:
            ic, t, k, lag = ic_and_t(d[f], d[f"fwd_{h}"])
            line += f"{ic:>12.4f}/t{t:>6.2f}"
            if np.isfinite(t) and (best is None or abs(t) > best["t"]):
                best = {"f": f, "h": h, "ic": ic, "t": t, "n": k, "lag": lag}
        print(line)
    if best is None:
        print("  no OI feature produced a testable statistic")
        return 3
    print(f"\n  best OI: {best['f']} @ {best['h']}h  IC={best['ic']:+.4f}  "
          f"NW-t={best['t']:+.2f}  n={best['n']:,}  nw_lag={best['lag']}")
    g2 = abs(best["ic"]) >= IC_PASS and abs(best["t"]) >= NW_T_PASS
    print(f"  GATE 2 {'PASS' if g2 else 'FAIL'}  (needs |IC| >= {IC_PASS} and "
          f"|NW-t| >= {NW_T_PASS})")

    print("\nGATE 3  IS IT BETTER THAN THE CONTROLS, OR THE SAME INFORMATION?")
    print(f"  {'control':<14}" + "".join(f"{'h='+str(h):>21}" for h in HORIZONS))
    bc = None
    for f in ctl_feats:
        line = f"  {f:<14}"
        for h in HORIZONS:
            ic, t, k, lag = ic_and_t(d[f], d[f"fwd_{h}"])
            line += f"{ic:>12.4f}/t{t:>6.2f}"
            if np.isfinite(t) and (bc is None or abs(t) > bc["t"]):
                bc = {"f": f, "h": h, "ic": ic, "t": t, "n": k, "lag": lag}
        print(line)
    print(f"\n  best control: {bc['f']} @ {bc['h']}h  IC={bc['ic']:+.4f}  "
          f"NW-t={bc['t']:+.2f}")
    g3 = g2 and abs(best["t"]) > abs(bc["t"])
    print(f"  GATE 3 {'PASS' if g3 else 'FAIL'}  (OI must beat the BEST control on "
          f"|NW-t|, not merely be non-zero)")

    print("\nVERDICT")
    if not g2:
        big = abs(best["ic"]) >= 0.08
        if big:
            print("  Gate 2 did not pass AND the measured |IC| is large (>= 0.08),")
            print("  which is well above the ~0.035-0.04 this test detects reliably.")
            print("  That makes this a genuine NEGATIVE: OI does not predict here.")
            print("  DIRECTION CLOSED on a measurement.")
        else:
            print("  Gate 2 did not pass. Per PREREG appendix A.3 this is ** INCONCLUSIVE,")
            print("  NOT a negative result. The test fires ~5 % under the null, so a pass")
            print("  would have been real - but a FAIL at |IC| = "
                  f"{abs(best['ic']):.4f} is what a 10-38 %-power test does when the")
            print("  true effect is small. It does NOT establish that OI carries no")
            print("  information, and it must not be reported as if it did.")
            print(f"  The measured |IC| = {abs(best['ic']):.4f} is far below the ~0.08 this")
            print("  test could have detected.")
            print("  INCONCLUSIVE. Do not close the direction; do not build a strategy.")
    elif not g3:

        print("  OI predicts, but NOT better than volume change or price momentum.")
        print("  ** It is the same information wearing a different feed. ** A third book")
        print("  on it would be the same bet the two already held, which is the exact")
        print("  thing this line was opened to avoid. DIRECTION CLOSED.")
    else:
        print("  OI passes Gates 2 and 3: it predicts, and it beats volume and price")
        print("  momentum on the same test. That is the first evidence of a genuinely")
        print("  third source of information in this project.")
        print("  NEXT: a Freqtrade strategy, then the full chain - backtest -> realistic")
        print("  cost -> lookahead-analysis -> recursive-analysis -> OOS -> stress ->")
        print("  correlation (Gate 4, daily r < 0.30) -> holdout.")
        print("  Gate 2/3 is a FEATURE-layer test, not a backtest, and must not be")
        print("  reported as a strategy result.")
    out = ROOT / "user_data" / "perp_short_out"
    out.mkdir(parents=True, exist_ok=True)
    d.to_parquet(out / "oi_features.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
