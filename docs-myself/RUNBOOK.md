# FreqTrader Runbook (verified on this machine)

All commands below were actually executed in this workspace on 2026-09-19.
Anything not verified is marked **[UNVERIFIED]**.

Interpreter: `.venv\Scripts\python.exe` — Python 3.11.9
Freqtrade: **2026.8** (branch `stable`, tag `2026.8`, `9f10e357a`) — upgraded 2026-09-19
Platform: Windows / PowerShell

> **Superseded sections:** §1 describes Binance as geo-blocked. That was true
> before the VPN was enabled; with the VPN up, `api.binance.com` is reachable
> and plain `user_data/config.json` works for `download-data` / `backtesting`.
> The mirror config remains useful as a fallback. See
> `findings-ma200-and-momentum.md` for current work.

---

## Findings & studies index

> **START HERE:** `TERMINAL-FINDING.md` — **no strategy survives** to the project's
> own standard. It links every rejection, the decisive tests, and the 13-entry
> lessons ledger. Read `LESSONS.md` before starting new research.
>
> **Before any NEW hypothesis:** `GATE-0-POWER-CHECK.md` — reject underpowered
> studies at design time. **New long US-equity data (33–57y) is downloaded and
> verified** in `user_data/data/us_long/`; see `findings-round-freeze-and-audit.md`.
>
> `FINAL-DECISION.md` is the earlier, more optimistic record; its correction box
> supersedes it.

Research artifacts produced on this machine. Read the findings before writing
new strategies — most studies ended in **rejection**, and knowing why saves
repeating the work.

| Study | Verdict | Findings | Script |
|---|---|---|---|
| **TERMINAL FINDING** | 🏁 **no strategy survives** — DSR 0.9435, 8 tests converge, selection inflated p by 4–6× | `TERMINAL-FINDING.md` | `tools/reality_check_generalized.py` |
| **Round freeze & env audit** | 📦 crypto search **terminated**; Binance stocks = perps not spot; **US long history obtained (33–57y)**; WeChat note assessed non-transferable | `findings-round-freeze-and-audit.md` | `tools/download_us_long.py` |
| **GATE 0 — power pre-check** | 🚦 **run before any new hypothesis**; required-years vs available-years | `GATE-0-POWER-CHECK.md` | — |
| **LESSONS LEDGER** | 📋 **read before new research** — 13 errors and the rules preventing recurrence | `LESSONS.md` | — |
| **H-D: VR predictive?** | ❌ **NOT SUPPORTED** (3/4; strict prediction failed) — pre-registered, not re-tuned | `findings-hD-vr-predictive.md` | `tools/hD_vr_predictive.py` |
| **Forward validation (H-A)** | 🔄 **active** — protocol frozen, checker verified 6/6; currently INSUFFICIENT_DATA (1 day, needs 90) | `findings-forward-protocol.md` + `FORWARD-PROTOCOL.md` | `tools/forward_criteria_check.py` |
| **Power analysis (CORRECTION)** | ⚠️ **my "~271 years" claim was wrong** — wrong statistic. Paired comparison needs **~10–20y** (autocorr-adjusted ~18y) | `findings-power-analysis.md` | `tools/power_analysis.py`, `tools/power_which_is_right.py` |
| **Binance tokenized stocks** | ⚠️ **data exists (199 TradFi perps) but mechanism absent** — your tickers VR(20)=0.903 < 1, edge −0.031, beats flat 5/13 | `findings-stocks.md` | `tools/stock_tickers_test.py` |
| **Fragility & selection** | ⚠️ edge is **temporally stable** (jackknife +0.154…+0.237) but its **window cannot be chosen in advance** (BTC: in-sample-best gave positive OOS edge 0/6 splits) | `findings-fragility-and-selection.md` | `tools/fragility_analysis.py`, `tools/rho_stability.py` |
| **H-E / H-F parameter-free** | ❌ **both fail** — ensemble gives stability without positive OOS edge (pool E2 fail); expanding-mean is degenerate (~zero edge). Selection-transfer question left **unresolved** | `findings-hE-parameter-free.md` | `tools/hE_parameter_free.py` |
| MA200 exposure management | ❌ placebo cannot distinguish from random de-risking | `findings-ma200-and-momentum.md` | `tools/ma200_exposure_study.py` |
| Cross-sectional momentum (47 pairs) | ⚠️ beats random (p<0.001) but -89% DD + unmeasured survivorship bias | `findings-ma200-and-momentum.md` | `tools/crypto_momentum_study.py` |
| Drawdown control (20 majors) | ❌ drawdown falls -81%→-46% but almost entirely **mechanical** | `findings-drawdown-control.md` | `tools/drawdown_control_study.py` |
| **Volume signals** | ❌ volume adds **0.017 Sharpe** — nothing. But found SMA-50 | `findings-volume-signals.md` | `tools/volume_vs_speed.py` |
| **SMA-50 (best candidate so far)** | ❌ **fails** — walk-forward passes, anchored OOS fails, cross-asset replication collapses to p=0.142 under correlation adjustment | `findings-volume-signals.md` | `tools/sma50_walkforward.py`, `tools/sma_cross_asset_wf.py`, `tools/correlation_adjusted_test.py` |
| **Funding rate (orthogonal)** | ❌ refuted — contrarian -0.335 ΔSharpe; momentum fails Bonferroni; **negative incremental** over SMA-50 | `findings-funding-rate.md` | `tools/funding_sign_test.py` |
| **SMA-50 on 15y BTC** | ✅ **CANDIDATE — passes all gates** (see `FINAL-DECISION.md`) | `findings-sma-15year.md` | `tools/objective_gate_check.py` |
| **Equal-weight pool + execution** | ✅ 5th control closed (pool p=0.003); found & fixed 2 live-only defects (24% order churn, stale DB) | `findings-execution-layer.md` | `tools/equal_weight_pool_test.py`, `tools/dryrun_db_analysis.py` |
| **Domain specificity** | ⚠️ **frozen SMA-50 fails 0/4 on 109 US equities** but passes on crypto — mechanism: crypto VR(20)=1.19 (trending) vs equities VR(20)=0.84 (mean-reverting) | `findings-domain-specificity.md` | `tools/equity_out_of_domain.py`, `tools/trend_mechanism_test.py` |
| **Train/test split (CORRECTION)** | ⚠️ **weakens the candidate** — train-only selection picks SMA-20 not SMA-50; pool train edge +0.402 → test −0.001; per-asset +0.197 → −0.031 | `findings-train-test-split.md` | `tools/train_test_2025_2026.py`, `tools/decay_significance.py` |

**The one-line lesson across all six:** CAGR can be manufactured, drawdown
cannot be reduced by timing. The only reliable way to a smaller drawdown is to
hold a smaller position — no signal required.

**Two orthogonal information sources (volume, funding rate) have been tested and
both failed.** The binding constraint is statistical power, not ideas: 6.7–7.7
years of daily data gives SE(Sharpe) ≈ 0.36–0.39, which cannot separate a
Sharpe of 1.07 from 0.82.

**Best candidate status (SMA-50 on 15y BTC/USD): PASSES all gates.** The fix was
statistical power, not another signal — Lo (2002) SE ≈ 1/√YEARS, so I extended
BTC history back to 2011 via Bitstamp (15.1y, SE 0.36→0.257). Result: Sharpe
1.45 vs buy & hold 1.26, placebo p=0.002, 2011-2019 holdout (never searched)
beats both benchmarks, and it **survives realistic fixed-units execution**
(+0.168 ΔSharpe vs flat, CI [+0.017, +0.340]). Deployed as
`user_data/strategies/BTCSmaTrend.py` + `user_data/config_btcsma.json`.

**Honest limits:** MaxDD is still **-74%**; one asset; the edge is ~+0.17 Sharpe
(real but modest); ~5 market cycles means independence is overstated; no funding
cost modelled. **Not a green light for real money** — needs dry-run/forward
validation first.

**Key methodology added:** measure **effective** independent bets, not nominal
ones. 20 correlated crypto majors ≈ 2.6 independent trials. Naive significance
tests on correlated panels overstate evidence by roughly √(N/N_eff). See
`tools/correlation_adjusted_test.py`.

**Lo (2002) corollary:** finer granularity (4h/1h) buys NO statistical power —
only more calendar years do. Do not add intraday data expecting significance.

Key methodology enforced in every script (from `quant-research-handoff/`):
- **Single lag point** (`shift(1)`) — decide on close[t], hold from t+1
- **Explicit NaN masks** for indicator warm-up
- **Equal-weight same-pool benchmark**, never a single index or coin
- **Matched-exposure flat control** — a rule that only holds less risk proves nothing
- **Wildcard/circular-shift placebo** — matched mean AND run structure
- **One-bar shift test** — graceful degradation means no look-ahead

Other tools:

| Tool | Purpose |
|---|---|
| `tools/_smoke_strategies.py` | Runs every strategy's indicator pipeline offline — survives dependency upgrades without exchange access |
| `tools/test_strategy_signals.py` | Strategy signal checks |

Data on disk: **47 Binance USDT pairs, daily, 2018–2026** in
`user_data/data/binance/*-1d.feather` (3.7 MB). Download command in §3.

---

## 0. Activate the environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation is blocked by execution policy, or you prefer not to activate,
call the executables directly (all examples below use this form):

```powershell
& ".\.venv\Scripts\freqtrade.exe" --version
```

---

## 1. ⚠️ Read this first: Binance reachability

**Status as of 2026-09-19: reachable via VPN.** With the VPN enabled,
`api.binance.com` responds and the mirror config is no longer required.

**Without the VPN**, `api.binance.com`, `dapi.binance.com` and
`fapi.binance.com` are **unreachable** (DNS resolves `api.binance.com` to
`175.139.142.25`; TCP 443 times out) and every freqtrade command that touches
the exchange dies while loading markets:

```
freqtrade.exceptions.TemporaryError: Error in reload_markets due to RequestTimeout.
Message: binance GET https://dapi.binance.com/dapi/v1/exchangeInfo
```

This is a **network/geography problem, not a freqtrade bug**, and it breaks
`download-data`, `backtesting` and `trade` even though your candles are already
on disk — freqtrade always loads markets before it will start.

**Diagnostic gotcha:** don't use PowerShell's `Invoke-WebRequest` to test this.
It reports `The SSL connection could not be established` even when the network
is fine, which sends you chasing a firewall that isn't there. Test with Python:

```powershell
.\.venv\Scripts\python.exe -c "import urllib.request; print(urllib.request.urlopen('https://api.binance.com/api/v3/ping', timeout=15).read())"
```

Reachability measured from here (VPN off):

| Endpoint | Status |
|---|---|
| `api.binance.com` | BLOCKED (no VPN) / REACHABLE (VPN) |
| `dapi.binance.com` | BLOCKED |
| `fapi.binance.com` | BLOCKED |
| `data-api.binance.vision` | REACHABLE |
| `api.kraken.com`, `www.okx.com`, `api.gateio.ws`, `api.bitget.com`, `api.coinbase.com` | REACHABLE |
| `api.bybit.com`, `api.kucoin.com` | BLOCKED |

### Workaround (verified working)

`user_data/config_binance_vision.json` points ccxt at Binance's public
data mirror and restricts market fetching to spot. It loads markets and
backtests fine.

The two parts that matter — note that a plain `"hostname"` override is
**not** enough, because ccxt still hits `fapi.binance.com` for exchangeInfo:

```json
"exchange": {
  "name": "binance",
  "ccxt_config": {
    "urls": {
      "api": {
        "public":  "https://data-api.binance.vision/api/v3",
        "private": "https://data-api.binance.vision/api/v3",
        "v3":      "https://data-api.binance.vision/api/v3"
      }
    },
    "options": { "fetchMarkets": ["spot"], "defaultType": "spot" }
  },
  "ccxt_async_config": { "...same as ccxt_config..." }
}
```

Limitations: this mirror only serves **public spot market data**. It cannot
place orders or read a private balance, so this config is for
`download-data` / `backtesting` / `list-*` only — **not** for live trading.

### Alternative: use a reachable exchange

`user_data/config_okx.json` is a plain OKX spot dry-run config. Verified
end-to-end (download → backtest). Use this if you want a smoothly working
pipeline without mirror tricks.

---

## 2. List strategies

```powershell
& ".\.venv\Scripts\freqtrade.exe" list-strategies
```

Verified output — 7 strategies in `user_data/strategies`, all `OK`:

| Strategy | Hyperoptable |
|---|---|
| `AlwaysTradeStrategy` | No |
| `FreqaiExampleHybridStrategy` | Yes |
| `MA200Exposure` | No |
| `SampleStrategy` | Yes |
| `Strategy002` | No |
| `Strategy005` | Yes |
| `TrendFollowingStrategy` | No |

**Tip:** do *not* pass `--strategy-path user_data/strategies`.
`user_data/strategies` is already a default lookup path, so adding it
explicitly makes every strategy show up as `DUPLICATE NAME`.
Use `--strategy-path` only for strategies kept *outside* `user_data/strategies`.

---

## 3. Download historical data

```powershell
# Verified 2026-09-19: 47 pairs, daily, 2018->now, via the vision mirror.
# Result: 1,646-3,182 rows per pair in user_data\data\binance\*-1d.feather
& ".\.venv\Scripts\freqtrade.exe" download-data `
    --config user_data\config_binance_vision.json `
    --timeframes 1d --timerange 20190101- `
    --pairs BTC/USDT ETH/USDT BNB/USDT XRP/USDT ADA/USDT SOL/USDT ...

# OKX (reachable without VPN) — verified
& ".\.venv\Scripts\freqtrade.exe" download-data `
    --config user_data/config_okx.json `
    --pairs BTC/USDT ETH/USDT XRP/USDT `
    --timeframes 5m --timerange 20240401-20241001
```

Result: ~52,799 candles per pair, written to `user_data\data\okx\`.

For Binance-with-mirror, same form but `--config user_data/config_binance_vision.json`.
Market loading succeeds; actual candle availability depends on the mirror.

**Note on `--pairs`:** you must pass pairs explicitly. Pairs listed in a config's
`pair_whitelist` are not always picked up by `download-data`.

Timeframe notes: `1m 3m 5m 15m 1h 4h 1d`.
`--timerange 20230101-` means "from 2023-01-01 until now".

---

## 4. Backtest

```powershell
# Verified: OKX, 39 trades
& ".\.venv\Scripts\freqtrade.exe" backtesting `
    --config user_data/config_okx.json `
    --strategy TrendFollowingStrategy `
    --timerange 20240401-20240901

# Verified: Binance via mirror, 63 trades
& ".\.venv\Scripts\freqtrade.exe" backtesting `
    --config user_data/config_binance_vision.json `
    --strategy TrendFollowingStrategy `
    --timerange 20240601-20250101 --timeframe 1h
```

Results are written to `user_data\backtest_results\` as
`backtest-result-<timestamp>.zip` plus a `.meta.json`.

Useful follow-ups:

```powershell
& ".\.venv\Scripts\freqtrade.exe" backtesting-show          # re-print last result
& ".\.venv\Scripts\freqtrade.exe" backtesting-analysis      # per-tag / per-pair breakdown
& ".\.venv\Scripts\freqtrade.exe" plot-profit  --strategy TrendFollowingStrategy --timerange 20240401-20240901
& ".\.venv\Scripts\freqtrade.exe" plot-dataframe --strategy TrendFollowingStrategy --timerange 20240401-20240901
```

**Bias checks** — these map directly onto the research project's regression
suite (look-ahead and off-by-one bugs):

```powershell
& ".\.venv\Scripts\freqtrade.exe" lookahead-analysis  --strategy TrendFollowingStrategy
& ".\.venv\Scripts\freqtrade.exe" recursive-analysis  --strategy TrendFollowingStrategy
```

---

## 5. Dry-run (paper trading) — verified

```powershell
& ".\.venv\Scripts\freqtrade.exe" trade `
    --config user_data/config_okx.json `
    --strategy TrendFollowingStrategy `
    --strategy-path user_data/strategies `
    --dry-run
```

Smoke-tested for 45s: the bot started, heartbeated
(`state='RUNNING'`), detected an ROI exit on `ETH/USDT`, and wrote it to
`tradesv3.dryrun.sqlite`. Ctrl-C to stop.

Notes:
- `--dry-run` overrides the config, but `user_data/config.json` already has
  `"dry_run": true`.
- Dry-run uses a simulated wallet (`dry_run_wallet`).
- Dry-run still needs markets loaded → still subject to the Binance block.

---

## 6. Real trading **[UNVERIFIED]**

Not executed here — requires real API keys and real funds.

```powershell
# 1. Put real keys in the config (exchange.key / exchange.secret)
# 2. Set "dry_run": false
# 3. Then:
& ".\.venv\Scripts\freqtrade.exe" trade --config user_data/config.json --strategy <StrategyName>
```

Before doing this, at minimum:
- Run the strategy through **dry-run for weeks first** — upstream's own
  disclaimer says exactly this.
- Replace the placeholder credentials and the weak default password.
- Set `api_server.listen_ip_address` to `127.0.0.1` (see security note below).
- Decide on Telegram/webhook alerting so you learn about fills.

### ⚠️ Security issue in the current `user_data/config.json`

It ships with values you should not expose:

| Setting | Current value | Risk |
|---|---|---|
| `api_server.listen_ip_address` | `0.0.0.0` | API reachable from the whole LAN |
| `api_server.enabled` | `true` | endpoint is live |
| `api_server.password` | `YourPassword123!` | guessable; controls the bot |
| `jwt_secret_key` / `ws_token` | literal values in the file | forgeable sessions |
| `exchange.key` / `secret` | empty | fine for now, must be set for live |

The API server can start/stop trades and read balances. Bind it to
`127.0.0.1` and rotate the password/token before any live run.

---

## 7. Where the strategy file goes

Strategies are Python classes subclassing `IStrategy` (interface version 3),
placed in **`user_data/strategies/`**.

A strategy defines:

| Piece | Purpose |
|---|---|
| `timeframe` | candle size, e.g. `"5m"`, `"1h"`, `"1d"` |
| `startup_candle_count` | warm-up bars needed before signals are valid |
| `populate_indicators()` | add indicator columns |
| `populate_entry_trend()` | set `enter_long` / `enter_short` = 1 |
| `populate_exit_trend()` | set `exit_long` / `exit_short` = 1 |
| `minimal_roi` | ROI exit table |
| `stoploss` | stop loss (e.g. `-0.10`) |
| `custom_stake_amount()` | per-trade position sizing |
| `adjust_trade_position()` | scale in/out (needs `position_adjustment_enable = True`) |

Scaffold a new one with:

```powershell
& ".\.venv\Scripts\freqtrade.exe" new-strategy --strategy MyStrategy
```

The bundled strategies in this workspace:

- `always_trade.py` — trivial smoke-test bot (enters on every candle, exits on ROI)
- `TrendFollowingStrategy.py` — EMA20 cross + OBV confirmation, 5m
- `sample_strategy.py`, `Strategy002.py`, `Strategy005.py` — upstream samples
- `FreqaiExampleHybridStrategy.py` — FreqAI/ML example (needs `--freqaimodel`)

---

## 8. Reproducing the research handoff

From `quant-research-handoff/`:

```powershell
cd quant-research-handoff

# Regression suite for the 6 "runs fine, wrong answer" bug classes — 12/12 PASSED
& "..\.venv\Scripts\python.exe" methodology\test_regressions.py

# Backtest engine self-check (no look-ahead / no leverage / no off-by-one) — 7/7 PASSED
& "..\.venv\Scripts\python.exe" code\quant\engine.py

# Hypothesis scripts (reproductions)
& "..\.venv\Scripts\python.exe" code\run_h1.py
& "..\.venv\Scripts\python.exe" code\run_h2.py
& "..\.venv\Scripts\python.exe" code\run_h3.py
```

`yfinance` is **not installed** in this venv. That is fine — all 113 CSVs ship
with the handoff, so every reproduction above runs fully offline.
You only need `yfinance` to re-pull fresh data.

If you fetch data, `yf.set_tz_cache_location()` must point at a writable
directory or you get `sqlite3.OperationalError: unable to open database file`.

---

## 9. Quick reference

```powershell
& ".\.venv\Scripts\freqtrade.exe" --help                    # all 40+ subcommands
& ".\.venv\Scripts\freqtrade.exe" list-exchanges
& ".\.venv\Scripts\freqtrade.exe" list-pairs --exchange okx
& ".\.venv\Scripts\freqtrade.exe" list-data --config user_data/config_okx.json
& ".\.venv\Scripts\freqtrade.exe" show-config -c user_data/config.json   # merged config
& ".\.venv\Scripts\freqtrade.exe" new-config                             # scaffold a config
& ".\.venv\Scripts\freqtrade.exe" hyperopt --strategy <S> --hyperopt-loss SharpeHyperOptLoss
```

Full upstream docs: `README.md`, `docs/` (48 files), and https://www.freqtrade.io.
A shorter command cheat-sheet already existed at `docs-myself/backtesting-and-dryrun.md`.

---

## 10. Corpus of what was verified

### Platform (verified 2026-09-19, freqtrade 2026.8)

| Action | Status |
|---|---|
| `pip check` | ✅ No broken requirements |
| `--version` | ✅ freqtrade 2026.8, CCXT 4.5.76, Python 3.11.9 |
| `list-strategies` | ✅ **7 strategies, all OK** |
| `download-data` (Binance mirror, 1d, 47 pairs) | ✅ 1,646–3,182 rows/pair |
| `download-data` (OKX, 5m, 3 pairs) | ✅ 52,799 candles/pair |
| `backtesting` (Binance, Strategy005, 1h) | ✅ 18 trades |
| `backtesting` (Binance, SampleStrategy, 1h) | ✅ 27 trades |
| `backtesting` (MA200Exposure, 1d) | ✅ 1 trade / 63 resize orders |
| `show-config` on all 5 user configs | ✅ valid against 2026.8 schema |
| Strategy indicator pipelines on pandas 3.0.5 | ✅ 5/5 non-FreqAI strategies |
| `trade --dry-run` (OKX) | ✅ started, heartbeated, exited a trade |
| Research regression suite | ✅ 12/12 |
| Research engine self-test | ✅ 7/7 |
| `trade` live | ❌ not attempted (no keys/funds) |

### Research findings

| Study | Result |
|---|---|
| MA200 exposure (BTC/ETH/XRP) | ❌ DD improved 3/3 but placebo indistinguishable (BTC p=0.435) |
| Cross-sectional momentum (47 pairs) | ⚠️ p<0.001 vs random, no look-ahead, but -89% DD + survivorship bias |
| Drawdown control (20 majors) | ❌ DD -81%→-46% but all bootstrap CIs straddle zero; flat control matches it |

Configs added while verifying: `user_data/config_binance_vision.json`,
`user_data/config_okx.json`, `user_data/config_ma200.json`.
Strategies added: `user_data/strategies/MA200Exposure.py`.

**Known environment quirk:** PowerShell's `Invoke-WebRequest` reports
`SSL connection could not be established` on this machine even when the network
is fine. Use Python `urllib` to test connectivity — see §1.
