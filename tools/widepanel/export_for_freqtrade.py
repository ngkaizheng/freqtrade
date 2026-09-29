"""Export the wide panel into freqtrade's datadir layout for the cross-check.

A SUBSET, not all 104: freqtrade's backtester is far slower than the vectorised
shark engine, and the cross-check's job is to falsify, not to re-derive. The
subset is chosen by a RULE written in advance (largest median quote volume in
the first 500 bars, the names most likely to be liquid in BOTH engines), never
by whether a symbol's result looked good.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEAT = ROOT / "shark_data" / "wide" / "features"
DEST = ROOT / "user_data" / "data" / "wide_ft"
TF = "4h"
N_SYMBOLS = 24


def main() -> int:
    syms = pd.read_csv(FEAT / "universe.csv")["symbol"].tolist()
    stats = []
    for s in syms:
        d = pd.read_parquet(FEAT / f"{s}.parquet")
        stats.append({"symbol": s,
                      "med_quote": float((d["volume"] * d["close"]).median())})
    rank = pd.DataFrame(stats).sort_values("med_quote", ascending=False)
    pick = rank.head(N_SYMBOLS)["symbol"].tolist()

    # freqtrade's own convention, read off FeatherDataHandler._pair_data_filename:
    #   pair_to_filename("BTC/USDT:USDT") -> "BTC_USDT_USDT"
    #   _pair_data_filename -> {datadir}/futures/{pair_s}-{timeframe}-{candle}.{ext}
    # so the file is  {datadir}/futures/BTC_USDT_USDT-4h-futures.feather
    # (pair FIRST, then timeframe — the reverse is silently "no data found").
    ex = DEST / "futures"
    if ex.exists():
        shutil.rmtree(ex)
    ex.mkdir(parents=True, exist_ok=True)

    for s in pick:
        f = pd.read_parquet(FEAT / f"{s}.parquet")[
            ["open_time", "open", "high", "low", "close", "volume"]]
        out = pd.DataFrame({
            # futures candles must stay tz-aware UTC: stripping the zone raises
            # "can't compare offset-naive and offset-aware datetimes" deep
            # inside the backtester.
            "date": f["open_time"].dt.tz_convert("UTC"),
            "open": f["open"].astype("float32"),
            "high": f["high"].astype("float32"),
            "low": f["low"].astype("float32"),
            "close": f["close"].astype("float32"),
            "volume": f["volume"].astype("float32"),
        })
        base = s[:-4] if s.endswith("USDT") else s
        out.to_feather(ex / f"{base}_USDT_USDT-{TF}-futures.feather")

    (DEST / "pairs.json").write_text(
        pd.Series(pick, name="symbol").to_json(orient="values"))
    print(f"exported {len(pick)} symbols to {ex}")
    print(",".join(f'"{s}"' for s in pick))
    return 0


if __name__ == "__main__":
    sys.exit(main())
