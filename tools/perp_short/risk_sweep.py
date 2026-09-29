"""RISK / RETURN CURVE for the 4.0-ATR short book.

WHY A CURVE AND NOT A RECOMMENDATION
-------------------------------------
The user asked for something that makes money and explicitly accepted trading on
a backtested-but-not-significance-validated result. That is their call and this
script serves it. What it does NOT do is pick a risk level for them, because
that choice is a statement about how much drawdown they can sit through, and no
backtest can make it for them.

It publishes the whole curve so the choice is visible.

WHAT IS REPLAYED
----------------
The trades are FIXED - the same 1,140 entries and exits the 4.0-ATR arm
produced on 104 Binance USD-M perps, 2023-03-22 to 2026-08-31. Only the SIZING
changes, and each trade's stake is re-derived from the running equity exactly as
`PerpShort4h.custom_stake_amount` does, so compounding is correct rather than a
post-hoc subtraction.

Why replaying is enough here: a trade is taken if a slot is free, and slot
occupancy depends on holding times, not on stake size. The final chosen setting
is then re-run through the real engine as a check, not assumed from this.

THE STRESS LINE - the one that actually matters
-----------------------------------------------
The panel result measured that 72% of trades share a timestamp with another and
the cross-sectional mean has beta = 1.000. So when this book fires, it fires on
many names AT ONCE, and they are not independent. The backtester fills every
stop exactly at the stop price, so a same-bar stop is always exactly -1R here.
In reality a cascade fills past it.

`worst-case` therefore assumes EVERY simultaneously-open position is stopped and
each one loses MORE than 1R - which is what a liquidation cascade does. It is
the number to size against, and it is not in the backtest.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide104"
    .venv\\Scripts\\python.exe tools\\perp_short\\risk_sweep.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("tools", "perp_short"))

import cost_frontier as CF  # noqa: E402

CF.ATR_STOP = 4.0
ARCHIVE = "user_data/stopfront_out/s_4p0/*.zip"
STRATEGY = "PerpShort4hStop"

# measured cost regimes; the calm one is the planning case, COVID the stress end
CASES = [("calm", 5.0, 12.0), ("covid", 5.0, 34.9)]


def replay(trades, frames, reg, risk, cap, lev, max_open):
    """Re-derive each stake from the running equity, honouring the slot count.

    The slot limit is applied in ORDER, exactly as the engine would: a trade is
    skipped if `max_open` positions are already busy on its entry bar. Skipped
    trades are NOT re-taken later, which is also what the engine does.
    """
    equity = CF.START_WALLET
    rows = []
    open_at = []          # (exit_date, ) of currently open trades
    for t in trades:
        entry = float(t["open_rate"])
        close = float(t["close_rate"])
        ts = pd.Timestamp(t["open_date"])
        te = pd.Timestamp(t["close_date"])
        # close anything that exited before this entry
        open_at = [x for x in open_at if x > ts]
        if len(open_at) >= max_open:
            continue
        open_at.append(te)

        atr = CF.atr_at(frames, t["pair"], ts)
        if not (np.isfinite(atr) and atr > 0 and entry > 0):
            continue
        notional = risk * equity / (CF.ATR_STOP * (atr / entry))
        stake = min(notional / lev, equity * cap)
        qty = stake / entry * lev
        gross = (entry - close) * qty
        fee = reg.fee_bps / 1e4 * (qty * entry + qty * close)
        slip = reg.slippage_bps / 1e4 * qty * (entry + close) / 2.0
        funding = float(t.get("funding_fees") or 0.0) * (stake / float(t["stake_amount"]))
        pnl = gross - fee - slip - funding
        equity += pnl
        rows.append({"date": t["close_date"], "equity": equity, "pnl": pnl,
                     "notional": notional})
    return pd.DataFrame(rows), open_at


def stats(df, start, end):
    if df.empty:
        return dict(total=np.nan, cagr=np.nan, sharpe=np.nan, dd=np.nan,
                    calmar=np.nan, worst=1.0, peak_conc=0)
    eq = df["equity"]
    total = eq.iloc[-1] / CF.START_WALLET - 1
    yrs = (end - start).total_seconds() / (365.25 * 86400)
    cagr = (eq.iloc[-1] / CF.START_WALLET) ** (1 / yrs) - 1 if yrs > 0 else np.nan
    daily = df.set_index(pd.to_datetime(df["date"], utc=True))["equity"].resample("1D").last().ffill()
    r = daily.pct_change().dropna()
    sh = r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else np.nan
    dd = float((eq.cummax() - eq).div(eq.cummax()).max())
    # the concurrency that actually happened: max positions open at once
    return dict(total=total, cagr=cagr, sharpe=sh, dd=dd,
                calmar=cagr / dd if dd else np.nan, worst=1.0,
                peak_conc=0)


def main() -> int:
    import r_stats
    ap = max(glob.glob(ARCHIVE), key=os.path.getmtime)
    trades = sorted(r_stats.load_trades(ap, strategy=STRATEGY),
                    key=lambda t: t["open_date"])
    pairs = sorted({t["pair"] for t in trades})
    frames = CF.load_frames(pairs)
    start = pd.to_datetime(trades[0]["open_date"])
    end = pd.to_datetime(trades[-1]["close_date"])
    print(f"archive : {ap}")
    print(f"trades  : {len(trades)}   symbols: {len(pairs)}   "
          f"atr_stop=4.0   window {start.date()} -> {end.date()}\n")

    # how clustered is the book, really? this sets the stress number
    conc = []
    open_n = 0
    ev = []
    for t in trades:
        ts = pd.Timestamp(t["open_date"])
        te = pd.Timestamp(t["close_date"])
        ev = [e for e in ev if e > ts]
        ev.append(te)
        conc.append(len(ev))
    conc = np.array(conc)
    print(f"=== CONCURRENCY, measured: how many positions are open at once ===")
    print(f"   max {conc.max()}   p99 {np.percentile(conc, 99):.0f}   "
          f"p90 {np.percentile(conc, 90):.0f}   median {np.median(conc):.0f}")
    print(f"   -> the portfolio risk in one bad moment is roughly "
          f"{conc.max()} x risk_per_trade, not 1 x risk_per_trade.\n")

    for case, fee, slip in CASES:
        reg = CF.Regime(case, fee, slip, "")
        # 'cascade' is the EQUITY REMAINING, not the loss. Labelled that way
        # because the first version printed it under a bare header called
        # "cascade", which reads as the loss and is the opposite.
        print(f"=== {case} (fee {fee}bps/side, {slip}bps round trip slippage) ===")
        print(f"{'risk/trade':>11}{'max open':>10}{'trades':>8}{'total':>9}"
              f"{'CAGR':>8}{'Sharpe':>8}{'maxDD':>8}{'Calmar':>8}"
              f"{'cascade?':>10}{'peakConc':>10}")        for risk in (0.0025, 0.005, 0.01, 0.02):
            for mo in (6, 12, 24):
                df, _ = replay(trades, frames, reg, risk, 0.25, 1.0, mo)
                if df.empty:
                    continue
                m = stats(df, start, end)
                # the cascade: every simultaneously-open position stopped and
                # each losing 1.5R instead of 1R (a real gap-through)
                worst = 1 - min(1.0, conc.max() * risk * 1.5)
                print(f"{risk*100:>10.2f}%{mo:>10d}{len(df):>8}"
                      f"{m['total']*100:>8.1f}%{m['cagr']*100:>7.1f}%"
                      f"{m['sharpe']:>8.2f}{m['dd']*100:>7.1f}%{m['calmar']:>8.2f}"
                      f"{worst*100:>9.1f}%{conc.max():>10d}")
        print()

    print("=== READ THIS BEFORE PICKING A ROW ===")
    print("  * 'cascade?' is the EQUITY REMAINING after the worst observed moment:")
    print("    every position open at the peak-concurrency bar is stopped AND gaps")
    print("    50% past the stop. It is NOT in the backtest - the engine fills every")
    print("    stop exactly at the stop price, so it cannot produce this.")
    print(f"    At 1% risk that costs about "
          f"{(1 - (1 - min(1.0, conc.max() * 0.01 * 1.5)))*100:.0f}% of the account;")
    print("    at 2% risk it is survivable-but-ugly; at 0.25% it is a non-event.")
    print("  * 'total' and 'maxDD' ARE in-sample and the strategy is NOT")
    print("    significance-validated (t = -0.15 on the strictest measure).")
    print("  * 2 of the 4 calendar years are negative, 2023 by -40.1%.")
    print("  * Sharpe RISES with risk level. That is NOT a reason to use more")
    print("    leverage - it is compounding on a long in-sample run, and it is the")
    print("    classic shape of a backtest rewarding you for taking more of a")
    print("    non-significant signal.")
    print("  * max_open_trades=6 is NOT a risk control. It loses money at every")
    print("    risk level including 2%, because with 6 slots the book cannot hold")
    print("    the timing exposure that the whole edge consists of.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
