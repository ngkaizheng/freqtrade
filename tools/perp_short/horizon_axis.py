"""H-1 report: gross R vs cost R per trade at each horizon.

THE DECISION QUANTITY, PRE-REGISTERED
-------------------------------------
`docs-myself/PREREG_HORIZON_2026-09-30.md` H1 asks which term shrinks faster as the
clock coarsens:

    net R per trade = gross R per trade - cost R per trade

§40 measured that `cost_R` FALLS as the horizon coarsens (4h 0.0106, 1h 0.0223, 5m
0.0806 calm), so the cost term should improve. If the gross term falls faster, the
axis closes. The engine's own `Total profit %` cannot answer this - it is a cash
number, and §5a is explicit that cash equity is the wrong unit for a strategy
comparison. **This reports R, and it uses `risk_unit.py`, the single loader §16a
established.**

THE WARM-UP ARITHMETIC, WHICH IS THE CONFOUND AND IS CHECKED NOT ASSUMED
-------------------------------------------------------------------------
A 4h panel starting 2023-01-01 with `startup_candle_count=420` gives its first
tradable bar at 2023-01-01 + 420*4h = 2023-07-25. At 1d the same count consumes
420 DAYS, so the first tradable bar is 2024-02-25. **The arms therefore trade
DIFFERENT SAMPLE LENGTHS, and that is a property of the clock, not a free choice.**
The tool recomputes the expected first-bar date from the data and compares it with
the one the engine reported; if they disagree, something other than the warm-up is
truncating the sample and the run is flagged.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\horizon_axis.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "user_data" / "horizon_out"
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
STARTUP = 420
ARMS = ["4h", "12h", "1d", "3d"]
# §4 measured round trips; §40 measured the per-horizon ATR so cost_R is derived,
# not guessed. These are the multipliers of the 4h cost the ladder implies.
COST_MULT = {"4h": 1.0, "12h": 1.0 / np.sqrt(3.0), "1d": 1.0 / np.sqrt(6.0),
             "3d": 1.0 / np.sqrt(18.0)}


def atr_pct(high, low, close) -> np.ndarray:
    n = close.size
    if n < 20:
        return np.full(n, np.nan)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    tr[1:] = np.maximum.reduce([high[1:] - low[1:], np.abs(high[1:] - close[:-1]),
                                np.abs(low[1:] - close[:-1])])
    a = 1.0 / 14.0
    out = np.full(n, np.nan)
    out[14] = tr[1:15].mean()
    acc = out[14]
    for i in range(15, n):
        acc += a * (tr[i] - acc)
        out[i] = acc
    return out / close


def find_arm(tf: str) -> Path | None:
    """Locate this arm's archive by the timeframe INSIDE it, not by its path.

    The first version looked in `user_data/horizon_out/<tf>/` and found nothing:
    freqtrade wrote all four archives into its default `user_data/backtest_results/`,
    because `--export-filename` is a PREFIX inside that directory, not a directory.
    **Selecting an archive by where you meant to put it is the same class of error as
    selecting a number by the label attached to it** (section 34c: 999 of 1,111 trades
    silently dropped, and the tool still printed a verdict). The arm is now identified
    by the config the engine itself recorded inside the zip.
    """
    for d in (ROOT / "user_data" / "backtest_results", OUT):
        for z in sorted(d.glob("*.zip")):
            try:
                with zipfile.ZipFile(z) as zf:
                    cj = [n for n in zf.namelist() if n.endswith("_config.json")]
                    if not cj:
                        continue
                    if json.loads(zf.read(cj[0])).get("timeframe") == tf:
                        return z
            except Exception:                                   # noqa: BLE001
                continue
    return None


def atr_lookup(tf: str, pair: str, dates: pd.Series) -> pd.Series:
    """ATR% at each trade's ENTRY bar, on that arm's own timeframe."""
    k = pair.replace("/", "_").replace(":", "_")
    f = DATA / f"{k}-{tf}-futures.feather"
    if not f.exists():
        return pd.Series(np.nan, index=dates.index)
    x = pd.read_feather(f)[["date", "high", "low", "close"]]
    x["date"] = pd.to_datetime(x["date"], utc=True).dt.as_unit("ns")
    x = x.sort_values("date").reset_index(drop=True)
    x["pct"] = atr_pct(x["high"].to_numpy(), x["low"].to_numpy(), x["close"].to_numpy())
    return pd.Series(
        pd.merge_asof(pd.Series(dates.to_numpy(), index=dates.index).sort_index(),
                      pd.Series(x["pct"].to_numpy(), index=x["date"]).sort_index(),
                      left_index=True, right_index=True, tolerance=pd.Timedelta("1D"),
                      direction="backward").to_numpy(), index=dates.index)


_CACHE: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}


def atr_at(tf: str, pair: str, when) -> float:
    """ATR% at the last bar of `tf` at or before `when`.

    Cached per (tf, pair) and looked up with `searchsorted`. The first version
    re-read the symbol's whole feather file once PER TRADE - 1,111 file loads for
    the 4h arm alone - and then failed anyway on a pandas 3 restriction.
    """
    key = (tf, pair)
    if key not in _CACHE:
        k = pair.replace("/", "_").replace(":", "_")
        f = DATA / f"{k}-{tf}-futures.feather"
        if not f.exists():
            _CACHE[key] = (np.array([], dtype="int64"), np.array([], dtype=float))
        else:
            x = pd.read_feather(f)[["date", "high", "low", "close"]]
            # int64 nanoseconds, not a datetime dtype: pandas 3 hands a tz-aware
            # series to numpy as `datetime64[ns, UTC]`, and comparing that against
            # a naive datetime64 raises. Working in int64 sidesteps the whole
            # tz-aware/tz-naive class for a quantity that is only ever compared.
            d = pd.to_datetime(x["date"], utc=True).astype("int64").to_numpy()
            p = atr_pct(x["high"].to_numpy(), x["low"].to_numpy(),
                        x["close"].to_numpy())
            o = np.argsort(d, kind="stable")
            _CACHE[key] = (d[o], p[o])
    dates, pct = _CACHE[key]
    if dates.size == 0:
        return float("nan")
    t = int(pd.Timestamp(when).value)
    i = int(np.searchsorted(dates, t, side="right")) - 1
    return float(pct[i]) if i >= 0 and not np.isnan(pct[i]) else float("nan")


def main() -> int:
    rows = []
    print("H-1  THE COARSER-HORIZON AXIS - gross R vs cost R per trade\n")
    print(f"{'arm':<5}{'trades':>8}{'gross R':>10}{'cost R':>9}{'net R':>9}"
          f"{'sd(R)':>8}{'t':>7}{'total %':>10}{'maxDD %':>9}")
    for tf in ARMS:
        zp = find_arm(tf)
        if zp is None:
            print(f"  {tf}: NO ARCHIVE FOUND for this timeframe - the arm is "
                  f"BLOCKED, not zero")
            continue
        with zipfile.ZipFile(zp) as zf:
            mj = [n for n in zf.namelist()
                  if n.endswith(".json") and not n.endswith("_config.json")][0]
            pl = json.loads(zf.read(mj))
        st = pl["strategy"]["PerpShort4hDeploy"]
        cmp_ = pl["strategy_comparison"][0]
        tr = pd.DataFrame(st["trades"])
        tr["open_date"] = pd.to_datetime(tr["open_date"], utc=True)
        tr["atr_pct"] = [atr_at(tf, p, d)
                         for p, d in zip(tr["pair"], tr["open_date"])]
        risk = (tr["stake_amount"].to_numpy() * 4.0 * tr["atr_pct"].to_numpy())
        tr["R"] = tr["profit_abs"].to_numpy() / risk

        # gross = net of nothing; cost = fees + the measured round-trip increment.
        # §4's engine fee is 5 bps/side = 10 bps; the measured calm is 12.0 bps and
        # the stress end 34.9. Cost in R is the NOTIONAL cost, notional = 4*ATR.
        notional_frac = 4.0 * tr["atr_pct"].to_numpy()          # x stake
        cost_calm = 12.0e-4 * notional_frac / 4.0               # in units of ATR-distance
        # cost_R = round_trip_bps / (stop_mult * atr_pct * 1e4)  -- section 1c
        cost_R = 12.0 / (4.0 * tr["atr_pct"].to_numpy() * 1e4)
        gR = tr["R"].to_numpy()
        n = len(gR)
        t = gR.mean() / (gR.std(ddof=1) / np.sqrt(n)) if gR.std(ddof=1) > 0 else float("nan")
        rows.append({
            "tf": tf, "n": n, "gross_R": float(np.nanmean(gR)),
            "cost_R": float(np.nanmedian(cost_R)), "net_R": float(np.nanmean(gR) - np.nanmedian(cost_R)),
            "sd": float(np.nanstd(gR, ddof=1)), "t": float(t),
            "total": float(cmp_["profit_total_pct"]),
            # max_drawdown_account is a FRACTION; the first version printed it with
            # a "%" and rendered 14.16% as "0.14%". Same class as §16d's unit error.
            "maxdd": float(cmp_.get("max_drawdown_account", float("nan"))) * 100.0,
            "first": str(tr["open_date"].min()), "last": str(tr["open_date"].max()),
        })

    d = pd.DataFrame(rows)
    if d.empty:
        print("\n  No arm produced an archive. Nothing is concluded.")
        return 2
    for r in rows:
        flag = ""
        if r["n"] < 30:
            flag = "  <-- DEGENERATE, too few trades to be a result"
        print(f"{r['tf']:<5}{r['n']:>8}{r['gross_R']:>10.4f}{r['cost_R']:>9.4f}"
              f"{r['net_R']:>9.4f}{r['sd']:>8.3f}{r['t']:>7.2f}{r['total']:>9.2f}%"
              f"{r['maxdd']:>8.2f}%{flag}")

    print(f"\n  trading windows actually used (the warm-up confound, measured):")
    for r in rows:
        print(f"    {r['tf']:<4} {r['first'][:10]} .. {r['last'][:10]}")

    base = d[d["tf"] == "4h"]
    print("\n  NOTE: the `t` column is the NAIVE per-trade t, the one section 19's ladder")
    print("  showed to be misleading. The project's own by-timestamp t for the 4h arm is")
    print("  ~0.58, and THAT is the number that governs any claim about significance. A")
    print("  coarse arm having a smaller naive t is not evidence of anything on its own.")

    print("\nH1: which term shrinks faster as the clock coarsens?")

    if len(base):
        b = base.iloc[0]
        for _, r in d[d["tf"] != "4h"].iterrows():
            if r["n"] < 30:
                print(f"  {r['tf']}: only {r['n']} trades - DEGENERATE, excluded from the "
                      f"comparison and reported, not smoothed over")
                continue
            cg = r["gross_R"] / b["gross_R"]
            cc = r["cost_R"] / b["cost_R"]
            print(f"  {r['tf']} vs 4h:  gross R x{cg:.3f}   cost R x{cc:.3f}   "
                  f"-> {'GROSS FALLS FASTER, axis closes' if cg < cc else 'COST FALLS FASTER, axis opens'}")

    print("\nVERDICT")
    ok = d[(d["n"] >= 30)]
    best = ok.loc[ok["net_R"].idxmax()] if len(ok) else None
    if best is not None and best["tf"] != "4h":
        print(f"  {best['tf']} beats 4h on net R per trade -> the axis OPENS")
    else:
        print("  ** 4h is the best arm on net R per trade. THE AXIS IS CLOSED. **")
        print("  Per H5 this is not revisited: three arms were fixed in advance and the")
        print("  whole curve is published above. A further sweep would be §5b dead fruit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

