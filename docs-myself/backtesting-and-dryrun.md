# Backtesting, Dry-run and Downloading Historical Data

This page shows quick commands and examples to: activate the environment, download historical data, run backtests, and run dry-run trading sessions.

## Prerequisites
- Python 3.11+ and project dependencies installed.
- A valid config file (e.g., `user_data/config.json` or one under `config_examples/`).
- A strategy file or use one of the bundled strategies.

## Activate virtual environment
- PowerShell (Windows):

```powershell
.\.venv\Scripts\Activate.ps1
```

- CMD (Windows):

```cmd
.\.venv\Scripts\activate.bat
```

- Unix / WSL / Git Bash:

```bash
source .venv/bin/activate
```

## Download historical OHLCV data
Use `download-data` to fetch candles for the exchange/pairs configured in your config file.

Basic form:

```bash
freqtrade download-data -c <config.json> --timerange <YYYYMMDD>-<YYYYMMDD> --timeframes <tf1> <tf2> ...
```

Examples:

```bash
freqtrade download-data -c user_data/config.json --timerange 20230101- --timeframes 5m 15m 1h

freqtrade download-data -c config_examples/config_freqai.example.json --timerange 20240501-20250701 --timeframes 3m 15m 1h

freqtrade download-data -c config_examples/config_binance.example.json --timerange 20240501-20250701 --timeframes 3m 5m 15m 1h
```

Notes:
- `--timerange 20230101-` downloads from 2023-01-01 until now.
- Timeframe examples: `1m`, `3m`, `5m`, `15m`, `1h`, `4h`, `1d`.

## Backtesting
Run backtests using a strategy and optional strategy path.

Basic form:

```bash
freqtrade backtesting --strategy <StrategyName> [--strategy-path <path>] --config <config.json> --timerange <YYYYMMDD>-<YYYYMMDD>
```

Examples:

```bash
freqtrade backtesting --strategy FreqaiExampleStrategy --strategy-path freqtrade/templates --config config_examples/config_freqai.example.json --freqaimodel LightGBMRegressor --timerange 20240501-20250701

freqtrade backtesting --strategy AlwaysTradeStrategy --timerange 20251109-20251110

freqtrade backtesting --strategy TrendFollowingStrategy --strategy-path user_data/strategies --config config_examples/config_binance.example.json --timerange 20240501-20250701
```

Tips:
- Use `--strategy-path` to point to custom strategy files (e.g., `user_data/strategies`).
- `--freqaimodel` applies only to freqAI-integrated strategies.

## Dry-run trading (paper trading)
Run the bot in `--dry-run` mode to simulate live trading without real funds.

Basic form:

```bash
freqtrade trade --strategy <StrategyName> --config <config.json> --strategy-path <path> --dry-run
```

Examples:

```bash
freqtrade trade --strategy FreqaiExampleStrategy --strategy-path freqtrade/templates --freqaimodel LightGBMRegressor --dry-run

freqtrade trade --strategy AlwaysTradeStrategy --dry-run

freqtrade trade --strategy TrendFollowingStrategy --config config_examples/config_binance.example.json --dry-run
```

Notes:
- Dry-run simulates orders using exchange paper balance; real orders are not sent.
- Ensure your config has `dry_run` options and paper balances set as desired.

## Other useful commands
- List available exchanges, markets, pairs, strategies:

```bash
freqtrade list-exchanges
freqtrade list-markets --exchange Binance
freqtrade list-pairs --exchange Binance
freqtrade list-strategies
```

- Convert or migrate databases:

```bash
freqtrade convert-db --help
```

- Plot profit or dataframes:

```bash
freqtrade plot-profit --strategy <StrategyName> --timerange 20240101-20241231
freqtrade plot-dataframe --strategy <StrategyName> --timerange 20240101-20241231
```

## Timerange formats
- `YYYYMMDD-YYYYMMDD` (inclusive range).
- `YYYYMMDD-` (from date until now).
- Single-day: `YYYYMMDD-YYYYMMDD` with same start and end.

## Config tips
- Use `config_examples/` for sample configs. Copy to `user_data/config.json` and adapt API keys, pairs, stake, and exchange settings.
- Ensure the `pairlists` and `timeframe` settings match data you downloaded.

## Quick checklist before running a backtest or dry-run
- Activate venv: `.\.venv\Scripts\Activate.ps1` (PowerShell).
- Confirm `config.json` path and `--strategy-path`.
- Download required timeframes for the timerange.
- Run `freqtrade backtesting ...` or `freqtrade trade --dry-run ...`.

If you'd like, I can:
- add this page to the table of contents, or
- create a short troubleshooting section for common errors (auth, rate-limits, missing data).
