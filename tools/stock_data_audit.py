"""Data-availability audit for the user's stock tickers.

Two separate questions that must not be conflated:

  A. Can we RESEARCH these names?  -> need years of history.
  B. Can we EXECUTE on Binance?    -> need the TradFi perps, which exist but are new.

If A is possible and B is possible but short, the honest structure is:
research on the long history, execute on Binance, and treat the perp history
length as an execution/validation constraint rather than a research one.

Also documents the instrument type and its risks, because TRADIFI_PERPETUAL is
NOT the same as holding a stock.
"""

import glob
import json
import os
import urllib.request
import datetime as dt

HDRS = {"User-Agent": "Mozilla/5.0 (research)"}
FAPI = "https://fapi.binance.com/fapi/v1"
CACHE = "quant-research-handoff/data/cache"

WANTED = ["MU", "NVDA", "SNDK", "SPCX", "TSLA", "AAPL", "META", "AMD",
          "GOOGL", "MSFT", "AMZN", "NFLX", "INTC", "AVGO", "QCOM", "SPY", "QQQ"]


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    print("=" * 94)
    print("# STOCK DATA AUDIT — research history vs Binance execution history")
    print("=" * 94)

    # ---------- A. Local research history ----------
    print(f"\n{'=' * 94}")
    print("# A. LOCAL RESEARCH HISTORY (handoff cache, yfinance daily)")
    print(f"{'=' * 94}\n")
    print(f"  {'ticker':<8} {'in cache':<10} {'from':<12} {'to':<12} {'years':>7} "
          f"{'rows':>7}")
    have, missing = [], []
    for t in WANTED:
        p = os.path.join(CACHE, f"{t}.csv")
        if not os.path.exists(p):
            print(f"  {t:<8} {'NO':<10}")
            missing.append(t)
            continue
        import pandas as pd
        d = pd.read_csv(p, parse_dates=["Date"])
        d = d.dropna(subset=["Close"]).sort_values("Date")
        yrs = (d["Date"].max() - d["Date"].min()).days / 365.25
        print(f"  {t:<8} {'yes':<10} {str(d['Date'].min().date()):<12} "
              f"{str(d['Date'].max().date()):<12} {yrs:>7.1f} {len(d):>7}")
        have.append((t, yrs))
    print(f"\n  available: {len(have)}/{len(WANTED)}   missing: {missing or 'none'}")
    if have:
        print(f"  median history: {sorted(y for _, y in have)[len(have)//2]:.1f} years")

    # ---------- B. Binance execution history ----------
    print(f"\n{'=' * 94}")
    print("# B. BINANCE TradFi PERPETUAL HISTORY (execution venue)")
    print(f"{'=' * 94}\n")
    info = get(f"{FAPI}/exchangeInfo")
    tradifi = [s for s in info["symbols"]
               if s.get("contractType") == "TRADIFI_PERPETUAL"]
    print(f"  total TRADIFI_PERPETUAL instruments: {len(tradifi)}")

    rows = []
    for s in tradifi:
        sym = s["symbol"]
        base = s["baseAsset"]
        if base not in WANTED:
            continue
        try:
            k0 = get(f"{FAPI}/klines?symbol={sym}&interval=1d&startTime=0&limit=1")
            k1 = get(f"{FAPI}/klines?symbol={sym}&interval=1d&limit=2")
        except Exception as e:
            rows.append((base, sym, "ERR", "", "", 0, 0))
            continue
        if not k0 or not k1:
            continue
        first = dt.datetime.utcfromtimestamp(k0[0][0] / 1000).date()
        last = dt.datetime.utcfromtimestamp(k1[-1][0] / 1000).date()
        days = (last - first).days
        qv = float(k1[-1][7])
        rows.append((base, sym, str(first), str(last), days, qv,
                     s.get("status")))

    print(f"\n  {'ticker':<8} {'symbol':<12} {'from':<12} {'to':<12} "
          f"{'days':>6} {'last qvol':>14}  status")
    for r in sorted(rows, key=lambda x: x[0]):
        if r[2] == "ERR":
            print(f"  {r[0]:<8} {r[1]:<12} ERROR")
            continue
        print(f"  {r[0]:<8} {r[1]:<12} {r[2]:<12} {r[3]:<12} {r[4]:>6} "
              f"{r[5]:>14,.0f}  {r[6]}")

    if rows:
        dmax = max((r[4] for r in rows if r[2] != "ERR"), default=0)
        print(f"\n  longest perp history: {dmax} days = {dmax/365:.2f} years")
        print(f"  SE(Sharpe) at that length: {1/ (dmax/365)**0.5:.2f}")
        print(f"\n  -> ANY backtest on the perps alone is statistically useless,")
        print(f"     but that is an EXECUTION-venue limit, not a research limit.")

    # ---------- C. Instrument risk disclosure ----------
    print(f"\n{'=' * 94}")
    print("# C. WHAT A TRADIFI_PERPETUAL ACTUALLY IS")
    print(f"{'=' * 94}")
    print("""
  These are NOT tokenized shares and NOT the stock itself. They are perpetual
  futures that TRACK a US equity price. That changes the risk profile:

  * Leverage: perps are margin products. You can lose more than a spot holder,
    and liquidation is possible.
  * Funding: perpetuals charge a periodic funding payment between longs and
    shorts. A spot stockholder pays nothing. Over months this is a real drag or
    credit, and it is NOT in any equity backtest.
  * Trading hours: perps trade 24/7 while the underlying only trades US session.
    Overnight/weekend gaps mean the perp price can move when the stock cannot,
    and the perp can diverge from the stock around earnings or halts.
  * Settlement/regulatory: a Binance product, with counterparty and
    jurisdictional risk that a brokerage account does not have.
  * Short history: these are new; there is no multi-year track record to
    validate execution quality, funding behaviour, or divergence.

  Practical consequence: the user's premise ("less risk than crypto") is right
  about the UNDERLYING (equity vol ~15-20% vs crypto ~75%), but the perp
  wrapper reintroduces leverage, funding and counterparty risk. Spot brokerage
  would be lower risk than a Binance perp for the same underlying.
""")

    # ---------- D. The research question this raises ----------
    print(f"\n{'=' * 94}")
    print("# D. IMPORTANT PRIOR RESULT")
    print(f"{'=' * 94}")
    print("""
  I already tested this exact idea in round 4: the frozen SMA-50 exposure rule
  on 109 US equities (2010-2026, 5bps). It FAILED 0/4 gates:

      beats buy & hold Sharpe : 22/109 (20%)
      mean dSharpe vs flat    : -0.065
      correlation-aware p     : 0.793

  Mechanism (round 4): US equities MEAN-REVERT — VR(20) = 0.84 — so trend rules
  lose there by construction. Crypto trends (VR 1.19), which is why the same
  rule works there and not here.

  So moving to stocks does NOT rescue the strategy; it removes the mechanism
  that makes it work. Lower risk, but the edge is also gone.

  What remains genuinely open for equities is different: the handoff's OWN
  validated finding is MA200 exposure management on SPY (33.6y, drawdown
  -55% -> -30%), where the benefit is explicitly RISK REDUCTION rather than
  return. That is the one equity result with real evidence behind it, and it
  targets the user's actual stated concern (risk), not return.
""")


if __name__ == "__main__":
    main()
