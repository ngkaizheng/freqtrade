"""Open interest, long/short positioning, and taker flow for the event-trade names.

Offered to the user and now pulled, because it is the only direct read on the
one question the cost table could not answer: if a short thesis is right but the
shorts are already crowded, the negative carry break-even does not save you.
Squeeze risk is a positioning fact, not a price fact.

All endpoints are public Binance USD-M futures:
  /fapi/v1/openInterest                     current OI
  /futures/data/openInterestHist            OI history (5m granularity, 30d)
  /futures/data/globalLongShortAccountRatio account ratio (retail, by account)
  /futures/data/topLongShortPositionRatio  top-trader position ratio
  /futures/data/takerlongshortRatio        taker buy/sell volume ratio

Read the ratio family carefully - they disagree with each other constantly, and
the disagreement is itself the signal. Accounts are retail-dominated and lazy;
top-trader positions are the ones that can liquidate.
"""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
UA = {"User-Agent": "freqtrade-oi/1.0"}
FAPI = "https://fapi.binance.com"
FDATA = "https://fapi.binance.com/futures/data"

SYMBOLS = ["ENAUSDT", "AEROUSDT", "SEIUSDT", "2ZUSDT", "LITUSDT", "AVAUSDT",
           "BTCUSDT"]


def get(url: str, tries: int = 3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(str(last))


def pct(a, b):
    return (a / b - 1) * 100 if b else float("nan")


def measure(sym: str) -> dict:
    r = {"symbol": sym}

    # --- current OI and mark price ----------------------------------------
    # /fapi/v1/openInterest returns ONLY {symbol, openInterest, time} - no price.
    # The first version read markPrice off it and produced a well-formed table
    # of nothing. Price comes from premiumIndex, which does return markPrice.
    try:
        oi = get(f"{FAPI}/fapi/v1/openInterest?symbol={sym}")
        r["oi_contracts"] = float(oi["openInterest"])
        prem = get(f"{FAPI}/fapi/v1/premiumIndex?symbol={sym}")
        px = float(prem["markPrice"])
        r["mark"] = px
        # Binance OI is in base-asset units for USD-M perps.
        r["oi_usd"] = r["oi_contracts"] * px
    except Exception as exc:  # noqa: BLE001
        r["err_oi"] = str(exc)
        return r

    # --- OI history: is positioning building or unwinding? ----------------
    try:
        hist = get(f"{FDATA}/openInterestHist?symbol={sym}&period=1h&limit=168")
        if isinstance(hist, list) and len(hist) > 24:
            # sumOizValue is the USD notional series - the comparable measure
            s = [float(x["sumOizValue"]) for x in hist]
            r["oi_1h_ago_usd"] = s[0]
            r["oi_24h_ago_usd"] = s[min(24, len(s) - 1)]
            r["oi_7d_ago_usd"] = s[0]
            r["oi_now_usd"] = s[-1]
            r["oi_chg_24h_pct"] = pct(s[-1], s[min(24, len(s) - 1)])
            r["oi_chg_7d_pct"] = pct(s[-1], s[0])
            r["oi_max_7d_usd"] = max(s)
            r["oi_vs_7d_high_pct"] = pct(s[-1], max(s))
    except Exception as exc:  # noqa: BLE001
        r["err_oihist"] = str(exc)

    # --- account long/short ratio ----------------------------------------
    try:
        ls = get(f"{FDATA}/globalLongShortAccountRatio?symbol={sym}&period=1h&limit=24")
        if isinstance(ls, list) and ls:
            r["ls_accounts_now"] = float(ls[-1]["longShortRatio"])
            r["ls_accounts_24h_ago"] = float(ls[0]["longShortRatio"])
    except Exception as exc:  # noqa: BLE001
        r["err_ls"] = str(exc)

    # --- top-trader POSITION ratio (the ones who can liquidate) -----------
    try:
        tp = get(f"{FDATA}/topLongShortPositionRatio?symbol={sym}&period=1h&limit=24")
        if isinstance(tp, list) and tp:
            r["ls_toptrader_pos_now"] = float(tp[-1]["longShortRatio"])
            r["ls_toptrader_pos_24h_ago"] = float(tp[0]["longShortRatio"])
    except Exception as exc:  # noqa: BLE001
        r["err_tp"] = str(exc)

    # --- taker buy/sell flow ---------------------------------------------
    try:
        tk = get(f"{FDATA}/takerlongshortRatio?symbol={sym}&period=1h&limit=24")
        if isinstance(tk, list) and tk:
            r["taker_ratio_now"] = float(tk[-1]["buySellRatio"])
            r["taker_ratio_24h_ago"] = float(tk[0]["buySellRatio"])
    except Exception as exc:  # noqa: BLE001
        r["err_tk"] = str(exc)
    return r


def main() -> None:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(measure, SYMBOLS))

    L = []
    L.append("=" * 104)
    L.append("OPEN INTEREST & POSITIONING — Binance USD-M perpetuals")
    L.append(f"  {stamp}")
    L.append("=" * 104)
    L.append("")
    L.append(f"{'symbol':<10s}{'OI now $M':>12s}{'OI 24h%':>10s}{'OI 7d%':>9s}"
             f"{'vs 7d hi%':>11s}{'LS accts':>10s}{'LS top pos':>12s}{'taker':>8s}")
    L.append("-" * 104)
    for r in rows:
        if "err_oi" in r:
            L.append(f"{r['symbol']:<10s}  ERROR {r['err_oi'][:60]}")
            continue
        def g(k, f="{:.3f}"):
            v = r.get(k)
            return f.format(v) if isinstance(v, (int, float)) else "n/a"
        L.append(
            f"{r['symbol']:<10s}{r['oi_usd']/1e6:>11.1f}M"
            f"{g('oi_chg_24h_pct', '{:+.2f}'):>10s}{g('oi_chg_7d_pct', '{:+.2f}'):>9s}"
            f"{g('oi_vs_7d_high_pct', '{:+.1f}'):>11s}"
            f"{g('ls_accounts_now'):>10s}{g('ls_toptrader_pos_now'):>12s}"
            f"{g('taker_ratio_now'):>8s}")
    L.append("")
    L.append("  OI 24h/7d  = open interest change. RISING OI + rising price = new longs")
    L.append("                 (fuel for a squeeze). FALLING OI + rising price = short cover")
    L.append("                 (the move is spent).")
    L.append("  vs 7d hi    = how far below the 7-day OI peak. Near 0% = crowded now.")
    L.append("  LS accts    = LONG/SHORT by ACCOUNT count (retail). >1 = more long accounts.")
    L.append("  LS top pos  = LONG/SHORT by POSITION size at top traders. The liquidation risk.")
    L.append("  taker       = taker BUY / SELL volume ratio. >1 = aggressive buying.")
    L.append("  'n/a' = endpoint unavailable for that symbol; NOT the same as zero.")

    txt = "\n".join(L)
    (OUT / "oi_positioning.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
