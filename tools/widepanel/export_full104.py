"""Export the FULL 104-perp panel into freqtrade's datadir layout.

WHY THIS EXISTS
---------------
`export_for_freqtrade.py` deliberately took a 24-symbol subset: freqtrade's
backtester is far slower than the vectorised shark engine and the cross-check's
job was to falsify, not to re-derive. That job is done, and the 24-symbol result
is in `docs-myself/PREREG_104_FT_COSTS_2026-09-28.md` §0: it cannot confirm or
refute a 104-symbol panel claim.

This exports all 104 so the panel claim itself can be tested inside the engine,
with the repo's measured costs.

THE DATA LAYOUT TRAP, WRITTEN DOWN SO IT IS NOT RE-DISCOVERED
-------------------------------------------------------------
`freqtrade/data/history/datahandlers/idatahandler.py:354-371` builds the path as
`{datadir}/{pair_to_filename(pair)}-{timeframe}{candle}.{ext}` with a `futures/`
subdirectory added for non-spot candle types. So:

    4h futures     -> {datadir}/futures/BTC_USDT_USDT-4h-futures.feather
    1h funding     -> {datadir}/futures/BTC_USDT_USDT-1h-funding_rate.feather
    1h mark        -> {datadir}/futures/BTC_USDT_USDT-1h-mark.feather

`pair_to_filename("BTC/USDT:USDT")` is `BTC_USDT_USDT` - pair FIRST, then
timeframe. Get that backwards and the engine reports "No data found", or worse,
loads a different file. AND: futures backtesting loads funding and mark with
`fail_without_data=True` (backtesting.py:428, 441), so a missing one CRASHES
rather than silently returning nothing - that part at least is loud.

THE MARK-PRICE APPROXIMATION - READ BEFORE USING AT LEVERAGE
------------------------------------------------------------
1h mark klines are not downloaded for the full panel (that is ~7,000 files from
Binance Vision). Instead each symbol's 4h klines are resampled to 1h and
written as the mark series. At **1x leverage this is safe**: the mark price only
feeds the LIQUIDATION price, and at 1x liquidation sits ~100% away while the
stop is ~3.6% away, so every trade is closed by the stop first. **At leverage
> 1x this data is invalid** and must be re-downloaded.

Funding is NOT approximated - the real per-symbol history is in
`shark_data/wide/funding/`, taken from the same download as the panel.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEAT = ROOT / "shark_data" / "wide" / "features"
FUND = ROOT / "shark_data" / "wide" / "funding"
DEST = ROOT / "user_data" / "data" / "wide104"
TF = "4h"


def main() -> int:
    syms = pd.read_csv(FEAT / "universe.csv")["symbol"].tolist()
    ex = DEST / "futures"
    if ex.exists():
        shutil.rmtree(ex)
    ex.mkdir(parents=True, exist_ok=True)

    n_ok = n_drop = 0
    dropped: list[tuple[str, str]] = []

    for s in syms:
        fp = FEAT / f"{s}.parquet"
        if not fp.exists():
            n_drop += 1
            dropped.append((s, "no features parquet"))
            continue
        f = pd.read_parquet(fp)[["open_time", "open", "high", "low", "close", "volume"]]
        if f.empty:
            n_drop += 1
            dropped.append((s, "empty features"))
            continue

        out = pd.DataFrame({
            "date": f["open_time"].dt.tz_convert("UTC"),
            "open": f["open"].astype("float32"),
            "high": f["high"].astype("float32"),
            "low": f["low"].astype("float32"),
            "close": f["close"].astype("float32"),
            "volume": f["volume"].astype("float32"),
        })
        base = s[:-4] if s.endswith("USDT") else s
        fname = f"{base}_USDT_USDT"
        out.to_feather(ex / f"{fname}-{TF}-futures.feather")

        # ---- 1h mark, approximated from the 4h klines (see module docstring)
        # ⚠ `reset_index()` is REQUIRED, and this is a real defect that was
        # shipped. `set_index("date").resample(...).to_feather(...)` writes the
        # timestamp as the frame's INDEX, and read_feather does not restore the
        # index name, so freqtrade's loader saw a FIVE-column file and logged
        # "Unexpected column count 5 - expected 6" for most symbols. The
        # backtest then CONTINUED on partial data - a full run printed a normal
        # equity curve with an ERROR line nobody reads. Same silent-degradation
        # family as the rest of this repo's history.
        m = (out.set_index("date")
                .resample("1h")
                .agg({"open": "last", "high": "last", "low": "last",
                      "close": "last", "volume": "sum"})
                .ffill()
                .dropna(subset=["close"])
                .reset_index())
        m.to_feather(ex / f"{fname}-1h-mark.feather")

        # ---- 1h funding, the real per-symbol history
        fpath = FUND / f"{s}.csv.gz"
        if fpath.exists():
            fd = pd.read_csv(fpath)
            # pandas 3 will not infer a single format across mixed rows, and this
            # file HAS mixed rows: Binance writes some settlements as
            # "2023-01-01 00:00:00+00:00" and others as
            # "2023-01-01 08:00:00.008000+00:00" (a stray millisecond field on
            # the 08:00 settlement). format="ISO8601" parses both; the default
            # raises ValueError on the first microsecond row it meets.
            fd["calc_time"] = pd.to_datetime(fd["calc_time"], utc=True,
                                            format="ISO8601")
            fr = pd.DataFrame({
                "date": fd["calc_time"],
                "funding_rate": fd["last_funding_rate"].astype("float64"),
            }).sort_values("date").reset_index(drop=True)
            fr.to_feather(ex / f"{fname}-1h-funding_rate.feather")
        else:
            n_drop += 1
            dropped.append((s, "no funding file"))
            continue

        n_ok += 1

    print(f"exported {n_ok} symbols, dropped {n_drop}")
    for s, why in dropped:
        print(f"   DROPPED {s}: {why}")
    print(f"-> {ex}")
    if n_drop:
        print("\n⚠ futures backtesting loads funding and mark with "
              "fail_without_data=True, so any dropped symbol must ALSO come out "
              "of the pair whitelist or the run crashes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
