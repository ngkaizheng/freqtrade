# Strategy Factory MVP — frozen pre-registration

**Spec version:** `2026-09-25-mvp-v1`

This document is written before the MVP search is executed. Result-driven
changes require a new spec version and must not rewrite an earlier run.

## Scope

- Binance USDT perpetual futures.
- BTC/USDT:USDT and ETH/USDT:USDT.
- Base execution timeframe: completed 1-minute candles.
- Informative execution regime: completed 5-minute candles.
- No SOL, intrabar tick reconstruction, LOB queue simulation, or live trading.

## Hypotheses

### H1 — VWAP pullback continuation

A completed 5-minute EMA trend must agree with the side. On 1-minute data, price
must touch the UTC-session VWAP within the pre-specified tolerance, close back
on the trend side, print an expansion candle, and satisfy both contraction of
pullback volume and current-volume confirmation. Entry is the next 1-minute
open. Exits use ATR stop, fixed R target, and a time stop.

### H2 — EMA retest continuation

A completed 5-minute EMA regime must agree with the side. The completed
1-minute candle must touch EMA-fast while fast remains on the correct side of
EMA-slow, and print a strict bullish/bearish engulfing candle. Entry is the next
1-minute open. Exits use ATR stop, fixed R target, and a time stop. No crossover
entry is used.

### H3 — UTC opening-range breakout

The opening range is built only from completed UTC-day candles. Breakouts are
allowed after the range closes and only inside the pre-specified post-UTC-open
window. Confirmation requires current volume above the shifted median of the
previous 20 candles. Entry is the next 1-minute open.

### H4 — ATR compression expansion

ATR must be below a pre-specified fraction of its shifted rolling median. A
breakout of the shifted lookback high/low plus volume confirmation is required,
with the completed 5-minute trend agreeing. Entry is the next 1-minute open.

## Frozen execution assumptions

- One position per pair; signals while occupied are ignored.
- Entry and exit use adverse slippage in the configured scenario.
- Fee and slippage are charged on both sides.
- Funding charges only periods in which the position is a funding payer; funding
  credits and maker rebates are ignored. This is deliberately conservative.
- If stop and target are both touched in one candle, the stop fills first.
- A gap through a stop fills at the worse candle open; a favourable target gap
  fills at the candle open.
- Leverage is fixed at 1x so liquidation cannot manufacture or hide alpha.
- Signals are formed only from completed candles and fill at the next open.
- At every train/validation boundary the simulator is forced flat; trades
  crossing a boundary are excluded from both adjacent evaluation windows.
- The stored 5m file is authoritative for informative features. A 1m-to-5m
  aggregation is audited for provenance but never substituted.
- The local legacy 8h funding/mark files are research inputs only; exact
  mark-notional settlement and canonical 1h Freqtrade parity are out of scope.

## Frozen search and selection

- Complete cartesian product of each parameter table in
  `preregistration.py`; no adaptive early stopping.
- Rolling folds: 365 training days, 90 validation days, 90-day step, 4-hour
  embargo.
- One configuration per hypothesis is selected in each fold by training net
  Sharpe, then net expectancy as a deterministic tie-breaker.
- Validation results do not affect the selected parameters of that fold.

## Frozen acceptance gates

A hypothesis is called a survivor only if its walk-forward-selected OOS result
passes all gates:

1. at least 100 OOS trades;
2. positive net expectancy in at least 60% of validation folds;
3. baseline profit factor >= 1.05;
4. stressed profit factor >= 1.00;
5. Deflated Sharpe Ratio >= 0.95;
6. block-bootstrap Reality Check p-value <= 0.05;
7. at least 25% of the family's OOS configurations have positive expectancy;
8. positive OOS expectancy independently for both BTC and ETH.

“No survivor” is a valid and complete result. Backtest survival is not a green
light for real capital; a survivor only advances to a separate Freqtrade parity
backtest, lookahead audit, and forward dry-run.
