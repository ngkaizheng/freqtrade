"""The CORRECT risk unit, and the trap that made the wrong one look right.

WHY THIS FILE EXISTS
--------------------
Three scripts written on 2026-09-29 (funding_decomp, variance_decomp,
leverage_geometry) computed

    R = profit_abs / (stake_amount * abs(initial_stop_loss_ratio))

and got **`initial_stop_loss_ratio == 0.3` for all 1,253 trades, to six decimal
places, across 50 symbols.** That is not a coincidence and it is not the 4xATR
stop. It is the CLASS BACKSTOP.

`freqtrade/persistence/trade_model.py:871-879` sets `initial_stop_loss_pct` the
FIRST time a stop is assigned, from the `stoploss` passed at that moment, and
never re-derives it. On entry that value is the class attribute
`stoploss = -0.30` (`PerpShort4h.py:142`). `custom_stoploss` only runs on
subsequent candle updates and can only TIGHTEN the stop, so the recorded
`initial_stop_loss_abs` is the wide backstop and the 4xATR anchor shows up in
`stop_loss_abs` (e.g. CRV: initial 1.19990 -> final 1.06838).

So the correct risk unit is the one this repo's own validated path has always
used (`r_stats.build`, line 168):

    risk_usd = stake_amount * atr_stop * (ATR(entry bar) / entry_price)

and the wrong one overstates risk by `0.30 / (4 * atr_pct)`, which is symbol- and
date-dependent. On a symbol with 2 % ATR that is a 3.75x error; on one with 7.5 %
it is 1.0x - i.e. the error partially CANCELS for high-ATR names and is large
for low-ATR ones, so it is not even a uniform scale factor.

WHAT SURVIVES THE CORRECTION
----------------------------
`gross / cost` is a ratio of two quantities on the SAME trade, so `risk_usd`
cancels and the headline "the edge clears its costs by 9.8x" is unaffected. The
absolute R levels, the t-statistics and the variance decomposition are NOT, and
must be recomputed.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\risk_unit.py      # self-check
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
ATR_STOP = 4.0          # the frozen multiple, from the validated configs
ATR_PERIOD = 14         # freqtrade/TA-Lib default, which is what the strategy uses


def _atr_frame(path: Path) -> pd.DataFrame:
    d = pd.read_feather(path)[["date", "high", "low", "close"]].copy()
    d["date"] = pd.to_datetime(d["date"], utc=True)
    d = d.sort_values("date").reset_index(drop=True)
    prev = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"], (d["high"] - prev).abs(),
                    (d["low"] - prev).abs()], axis=1).max(axis=1)
    # Wilder's smoothing, matching TA-Lib's ATR that the strategy's dataframe uses
    atr = tr.ewm(alpha=1.0 / ATR_PERIOD, adjust=False, min_periods=ATR_PERIOD).mean()
    d["atr"] = atr
    return d.set_index("date")


def load_with_risk(zip_rel: str, atr_mult: float = ATR_STOP,
                   frames: dict | None = None) -> pd.DataFrame:
    """Per-trade ledger with the CORRECT 4xATR risk unit, plus the wrong one
    side by side so the size of the error is never invisible again."""
    if frames is None:
        frames = {}
    with zipfile.ZipFile(ROOT / zip_rel) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        d = json.loads(zf.read(mj))
    (name,) = d["strategy"].keys()
    rows, missing = [], 0
    for t in d["strategy"][name]["trades"]:
        if t.get("is_open"):
            continue
        entry = float(t["open_rate"])
        stake = float(t["stake_amount"])
        if not (entry > 0 and stake > 0):
            raise AssertionError(f"bad trade fields in {t.get('pair')}")
        pair = t["pair"]
        if pair not in frames:
            f = DATA / f"{pair.replace('/', '_').replace(':', '_')}-4h-futures.feather"
            if not f.exists():
                missing += 1
                continue
            frames[pair] = _atr_frame(f)
        df = frames[pair]
        ts = pd.Timestamp(t["open_date"])
        atr = np.nan
        # the strategy reads the ENTRY bar; the fallback is the previous bar only
        for cand in (ts, ts - pd.Timedelta(hours=4)):
            try:
                v = df.at[cand, "atr"]
            except KeyError:
                continue
            if np.isfinite(v) and v > 0:
                atr = float(v)
                break
        if not np.isfinite(atr) or atr <= 0:
            continue
        atr_pct = atr / entry
        risk_usd = stake * atr_mult * atr_pct
        assert risk_usd > 0, f"risk_usd collapsed to {risk_usd}"
        rows.append({
            "pair": pair, "open": ts, "close": pd.Timestamp(t["close_date"]),
            "is_short": bool(t["is_short"]), "stake": stake, "entry": entry,
            "atr_pct": atr_pct, "risk_usd": risk_usd,
            "risk_usd_WRONG": stake * abs(float(t["initial_stop_loss_ratio"])),
            "backstop_ratio": abs(float(t["initial_stop_loss_ratio"])),
            "profit": float(t["profit_abs"]),
            "fees": (float(t["fee_open"]) + float(t["fee_close"])) * stake,
            "funding": float(t["funding_fees"]),
            "dur_h": (pd.Timestamp(t["close_date"])
                      - pd.Timestamp(t["open_date"])).total_seconds() / 3600.0,
        })
    if missing:
        print(f"  [data] {missing} symbols had no 4h file and were skipped")
    df = pd.DataFrame(rows)
    assert len(df) > 100, f"only {len(df)} trades - wrong archive or wrong panel"
    df["R"] = df["profit"] / df["risk_usd"]
    df["fee_R"] = df["fees"] / df["risk_usd"]
    df["funding_R"] = df["funding"] / df["risk_usd"]
    df["gross_R"] = df["R"] + df["fee_R"] - df["funding_R"]
    return df.sort_values("open").reset_index(drop=True)


def selfcheck() -> None:
    print("RISK-UNIT SELF-CHECK\n")
    df = load_with_risk("user_data/sizing_out/full/n50/"
                        "backtest-result-2026-09-28_21-44-27.zip")
    print(f"  trades {len(df)}, symbols {df['pair'].nunique()}")
    n_back = int((df["backstop_ratio"].round(6) == 0.3).sum())
    print(f"  trades whose recorded initial_stop_loss_ratio is exactly 0.300000: "
          f"{n_back}/{len(df)}  <- the class backstop, not the ATR anchor")
    print(f"\n  the real risk unit (4 x ATR at entry):")
    for q in (0.5, 0.75, 0.9, 0.95, 0.99, 1.0):
        print(f"    p{int(q*100):<3} ATR% = {np.percentile(df['atr_pct'], q*100)*100:6.2f}%"
              f"   ->  stop = {np.percentile(df['atr_pct'], q*100)*400:6.2f}%")
    err = (df["risk_usd_WRONG"] / df["risk_usd"])
    print(f"\n  how wrong the backstop denominator was: "
          f"median {err.median():.2f}x, p90 {np.percentile(err,90):.2f}x, "
          f"max {err.max():.2f}x")
    print(f"    (1.0x means 4*ATR happened to equal 30% for that trade)")

    # The quantity that must NOT move: gross/cost is a same-trade ratio.
    g = df["gross_R"].mean()
    c = (df["fee_R"] + df["funding_R"]).mean()
    print(f"\n  invariant check - gross R {g:.4f}, cost R {c:.4f}, "
          f"ratio {g/c:.2f}x  (the risk unit cancels, so the '9.8x' headline is "
          f"unaffected)")
    gw = df["profit"].mean() / (df["risk_usd_WRONG"]).mean() + \
        df["fee_R"].mean() - df["funding_R"].mean()
    print(f"    and with the WRONG unit it would have read "
          f"{gw/c:.2f}x - close, because it is also a same-trade ratio.")


if __name__ == "__main__":
    selfcheck()
