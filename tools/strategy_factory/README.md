# Strategy Factory MVP

This directory contains an isolated, read-only research harness for the four
pre-registered short-horizon hypotheses. It does not modify Freqtrade core,
migrate market data, place orders, or claim that a backtest survivor is
profitable.

## Entry points

```powershell
# Read-only data and protocol audit
.\.venv\Scripts\python.exe -m tools.strategy_factory audit `
  --data-dir user_data\data\binance\futures

# Fast diagnostic smoke run; output is explicitly marked truncated
.\.venv\Scripts\python.exe -m tools.strategy_factory smoke `
  --data-dir user_data\data\binance\futures `
  --output user_data\strategy_factory_runs\smoke-YYYYMMDD `
  --start 2024-01-01 --end 2024-04-01

# Full 400-configuration pre-registered run
.\.venv\Scripts\python.exe -m tools.strategy_factory run `
  --data-dir user_data\data\binance\futures `
  --output user_data\strategy_factory_runs\full-YYYYMMDD
```

`run` refuses a non-empty output directory unless `--overwrite` is explicitly
provided. Results are assembled in a temporary sibling directory and promoted
only after the manifest and report have been written.

## Frozen scope

- BTC/USDT:USDT and ETH/USDT:USDT.
- Stored 1m futures candles for execution and stored 5m futures candles for
  the informative regime.
- Four families: VWAP pullback, EMA retest, UTC opening-range breakout, and
  ATR compression.
- 400 deterministic parameter configurations.
- One completed-candle signal, next-1m-open entry, ATR stop, fixed-R target,
  adverse per-side fee/slippage scenarios, and adverse-payer funding.
- Rolling 365-day train / 90-day validation / 90-day step with a 4-hour
  embargo and forced-flat boundaries.
- Calendar-time block Monte Carlo, DSR-style selection deflation, and a
  block-bootstrap max-statistic Reality Check sensitivity test.

See [`PREREGISTRATION.md`](PREREGISTRATION.md) for the frozen rules and gates.
The manifest records source/data hashes, the exact trial universe, folds,
diagnostic truncations, and statistical settings.

## Important local-data limitations

- The local futures files use legacy 8h funding/mark names. Current Freqtrade
  2026.8 parity expects canonical 1h funding/mark files, so a later parity
  backtest must use an isolated staged data directory.
- Stored 1m and 5m data are audited independently. The tool records a small
  number of cross-timeframe discrepancies and never rewrites either source.
- Funding credits are ignored by design. The research result therefore does
  not claim exact exchange funding cashflows or mark-notional settlement.
- BTC and ETH are equal-weight standalone sleeves. Families do not compete for
  one shared cash account; the output is not an executable portfolio backtest.
- A result that passes the historical gates still requires a separately
  exported Freqtrade strategy, lookahead/recursive analysis, and forward
  dry-run before any consideration of real capital.
