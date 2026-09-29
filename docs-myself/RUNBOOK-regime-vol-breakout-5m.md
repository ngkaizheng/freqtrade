# Runbook — `RegimeVolBreakout5m`

Config + CLI for the 1h-regime / 5m-breakout hypothesis in
`user_data/strategies/RegimeVolBreakout5m.py`.

Every command below was **executed in this workspace** on freqtrade **2026.8**
(`.venv\Scripts\freqtrade.exe`, Python 3.11.9, Windows/PowerShell). Anything
not executed is marked **[UNVERIFIED]**.

| File | Purpose |
|---|---|
| `user_data/strategies/RegimeVolBreakout5m.py` | the strategy (installed from your attachment, unmodified) |
| `user_data/config_regime_breakout_backtest.json` | research/backtest environment |
| `user_data/config_regime_breakout_dryrun.json` | paper trading environment |
| `user_data/config_lookahead_override.json` | one-key fragment, only ever passed as a **second** `--config`; see §3.4 |

> Both full configs were checked with `validate_config_schema` against the
> 2026.8 schema. **The override fragment fails a standalone schema check** — the
> schema requires `exchange`, `dry_run`, `dataformat_ohlcv` and `dataformat_trades`
> — and that is expected: it is a fragment, it is never used on its own, and the
> lookahead run in §3.4 is the proof that it works. Do not "fix" it by pasting the
> base config into it.

Keep the two configs separate. A backtest config is an *experiment definition*; a
dry-run config is a *deployment target*. Merging them is how a research setting
leaks into something that places orders.

---

## 0. Activate

```powershell
.\.venv\Scripts\Activate.ps1
```

If execution policy blocks that, call the binary directly — every example below
assumes you have:

```powershell
& ".\.venv\Scripts\freqtrade.exe" --version
```

---

## 1. Four things in the source md that would have failed, and what I changed

The md is mostly right about the *layering* (Strategy / config / CLI / data) and
right about `config > strategy`. Four specifics did not survive contact with
freqtrade 2026.8 or with the data actually on this disk.

### 1.1 The proposed 10-pair whitelist does not exist here — 6 of 10 have no 5m data

The md proposes BTC/ETH/SOL/BNB/XRP/DOGE/ADA/AVAX/LINK/SUI. On this machine:

```
pairs with 5m futures data : 9   (BTC ETH XRP TRX ADA DOT LTC ETC XLM)
pairs with 1h futures data : 28
pairs with BOTH            : 8
```

**SOL, BNB, DOGE, AVAX, LINK, SUI have 1h candles but no 5m candles.** The
strategy's base timeframe is 5m, so they cannot be traded at all.

**XLM is the dangerous one: it has 5m but no 1h.** That matters more than it
looks. Freqtrade does **not** resample for informative pairs — in backtesting
`DataProvider.historic_ohlcv` calls `load_pair_history` straight off disk for the
requested timeframe (`dataprovider.py:328-335`). A missing 1h file therefore
merges as all-NaN, `data_valid` is False on every bar, and the pair contributes
**exactly zero trades, with no error and no warning**. That is the `&=`-from-
all-False failure class in `AGENTS.md` §3, reached by a missing file instead of a
bad mask. The config whitelists only the 8 pairs that have both.

### 1.2 `datadir` in a config file is silently ignored

`Configuration._process_datadir_options` unconditionally overwrites
`config["datadir"]`, and `create_datadir` never reads it
(`configuration.py:212`, `directory_operations.py:20-25`). This repo has already
been bitten — see `RESEARCH_STATE.md` §1 and `tools/matrix/run_leverage_matrix.py`
lines 12-15.

> **Always pass `--datadir user_data\data\binance` explicitly.** The commands
> below all do.

### 1.3 `max_open_trades` is silently capped at the number of pairs

`optimize_reports.py:577`:

```python
max_open_trades = min(config["max_open_trades"], len(pairlist))
```

This wrecks the md's §14 phase-3 ladder ("BTC ETH SOL, then +BNB XRP, then 10
assets"). **That ladder changes the universe *and* the concurrency at the same
time**, so a difference between rungs is uninterpretable. Verified: the 2-pair
run below printed `Max open trades : 2` while the config said 5.

Fix: hold concurrency fixed when you change the universe. Either always run all 8
pairs, or pass `--max-open-trades` explicitly to pin it.

### 1.4 `perp_leverage` is a repo convention, not a freqtrade key — and this strategy ignores it

`perp_leverage` appears in this repo's other futures configs, but **freqtrade
2026.8 never reads it**. It is a convention that individual strategies opt into
via `self.config.get("perp_leverage", ...)` inside their own `leverage()` method
(`PerpTrendBreakout.py:182`, `WideBreakoutMatrix.py:90`, `ShortBreakout4hLev.py:118`).

`RegimeVolBreakout5m` does not read it. Its `leverage()` is:

```python
return min(1.0, max_leverage)
```

**Leverage is 1x and nothing in the config can change it.** I left
`"perp_leverage": 1.0` in both configs so the intended value is written down and
matches the strategy — but editing that number will do nothing. The only lever is
the `leverage()` method, which is a Strategy change and therefore invalidates
every comparison run so far (see `RESEARCH_STATE.md` §1, the
`stoploss`/leverage bug row: two independent sessions hit that footgun).

---

## 2. The config, key by key

Only the keys that this strategy actually depends on are explained. The rest is
house style from `user_data/config_perp_backtest.json`.

| Key | Value | Why this value, for THIS strategy |
|---|---|---|
| `trading_mode` | `futures` | **Load-bearing.** `can_short = True`. In spot mode the long branch of the entry never runs. |
| `margin_mode` | `isolated` | Matches the research design; keeps one blown position from taking the account. |
| `stake_amount` | `100` (fixed) | Not `unlimited`. Fixed stake makes per-trade R comparable across cells; `unlimited` lets the trade *set* change with the wallet (`RESEARCH_STATE.md` §1 leverage-matrix row). The question here is "does the signal have an edge", not "what would the account do". |
| `dry_run_wallet` | `10000` | 5 slots × 100 = 500 USDT max exposure, 5% of wallet. Capital is close to inert at this size (measured: 500/1k/5k differ <2.7pp), so it is a denominator, not a lever. |
| `max_open_trades` | `5` | A **research variable**, not a truth. It gates entries, so it changes the trade set. See §1.3. |
| `fee` | `0.0006` | **6 bps per side = 12 bps round trip**, the repo's floor. Freqtrade applies it twice. See §4 for why this is the *calm-day* number, not a bound. |
| `timeframe_detail` | `1m` | **Load-bearing, and easy to miss.** The custom stop is `3 × ATR(5m)`, which is a small fraction of a percent. On 5m granularity the stop fills are coarse and the backtest flatters itself. All 8 pairs have 1m futures data covering the window, so this costs runtime, not accuracy. |
| `liquidation_buffer` | `0.1` | 1x leverage never liquidates here. Present so it is a declared assumption if leverage is ever raised. |
| `perp_leverage` | `1.0` | Inert for this strategy — see §1.4. Documented, not functional. |
| `pairlists` | `StaticPairList` | Mandatory. `backtesting.py:250` **rejects** `VolumePairList` outright. Static also keeps the universe reproducible, which is the point of the pre-registration discipline. |
| `pair_whitelist` | the 8 pairs with 5m **and** 1h | See §1.1. |
| `entry_pricing` / `exit_pricing` | order book, same side, top 1 | Binance futures order-book pricing is the upstream recommendation, and in backtesting `use_order_book` is inert — these matter for dry-run/live parity. |
| `api_server` | disabled, `127.0.0.1` | The API can start and stop trades. `RUNBOOK.md` §6 already flags `0.0.0.0` + `YourPassword123!` in `user_data/config.json`; do not copy that. |

### Things deliberately **not** in the config

- `data_directory` — not a real key. The real one is `datadir`, and it is
  ignored in config (§1.2). Use the CLI flag.
- `exportfilename` — deprecated for backtesting in 2026.8
  (`cli_options.py:239-254`). Use `--backtest-directory`.
- `futures_funding_rate` — this is the *fake* funding fallback for when funding
  data is missing. **It is not needed and must not be set here**: all 8 pairs
  have real 1h funding-rate and mark files covering the window, and
  `_load_bt_data_detail` loads them with `fail_without_data=True`
  (`backtesting.py:422-432`). Real funding is charged. Setting this key would
  silently substitute a constant and understate the cost.
- `db_url` in the backtest config — backtesting does not use a persistent DB.
  It is set in the dry-run config only.

---

## 3. The command sequence

### 3.1 Sanity — does the strategy load and is the config valid?

```powershell
& ".\.venv\Scripts\freqtrade.exe" list-strategies
& ".\.venv\Scripts\freqtrade.exe" show-config --config user_data\config_regime_breakout_backtest.json
```

✅ **Verified 2026-09-27.** `RegimeVolBreakout5m` → `OK`. Config passes the
2026.8 schema.

### 3.2 Confirm the data is where the config will look

```powershell
& ".\.venv\Scripts\freqtrade.exe" list-data --config user_data\config_regime_breakout_backtest.json --datadir user_data\data\binance
```

You are looking for, per pair, **5m + 1h + 1h funding_rate + 1h mark**, and 1m
if `timeframe_detail` is on. A pair missing funding or mark **crashes** the
backtest with `No data found. Terminating.` — that one is loud, which is why
only the silent all-NaN 1h case (§1.1) is dangerous.

### 3.3 Baseline backtest

```powershell
& ".\.venv\Scripts\freqtrade.exe" backtesting `
    --config user_data\config_regime_breakout_backtest.json `
    --datadir user_data\data\binance `
    --strategy RegimeVolBreakout5m `
    --timerange 20230101-20251118 `
    --export trades
```

- `--timerange 20230101-20251118` is the **common** window. BTC/ETH/XRP/TRX
  start 2021-01-01; ADA/DOT/LTC/ETC start 2023-01-01. Using 2021 for all 8
  silently gives 4 pairs ~2.9 years and 4 pairs nothing.
- `--timeframe 5m` is unnecessary — it is already the strategy's timeframe.
  Adding it is harmless but it is an *override*, and per the md's own
  `config > strategy` rule an override you did not mean to set is a bug waiting.
- No `--strategy-path`: `user_data/strategies` is already a default lookup path
  and passing it makes every strategy report `DUPLICATE NAME` (`RUNBOOK.md` §2).

Results land in `user_data\backtest_results\backtest-result-<ts>.zip` + `.meta.json`.

```powershell
& ".\.venv\Scripts\freqtrade.exe" backtesting-show --config user_data\config_regime_breakout_backtest.json
& ".\.venv\Scripts\freqtrade.exe" backtesting-analysis --config user_data\config_regime_breakout_backtest.json
```

### 3.4 Lookahead check — run this before believing anything

The md §15 is right that this should be run, and the reason is stronger than the
md gives: **backtesting hands `populate_indicators()` the entire dataframe at
once**, so any operation that reaches forward — a centred rolling window, a
`.max()` without `.shift(1)`, a bfill, a `df.iloc[-1]` inside a vectorised
column — produces a clean, confident, wrong backtest. The `.shift(1)` discipline
in this strategy is correct by inspection; this verifies it.

> **⚠ The documented command does not work on Binance futures, and neither
> workaround the upstream docs offer works either. Three separate failures, all
> found by running it. This is the single most important operational note in
> this file.**

**Failure 1 — the default invocation dies on config validation.**
`lookahead_helpers.py:157-163` forces `order_types` to market to avoid late
entries, then `config_validation._validate_price_config` (line 117) rejects the
config because market entry orders require `entry_pricing.price_side = "other"`
and ours is `"same"`:

```
Configuration error: Market entry orders require entry_pricing.price_side = "other".
```

**Failure 2 — the obvious fix dies on a second check.** Overriding both
`price_side` to `"other"` and turning the order book off passes check 1 and then
fails `Exchange.validate_pricing` (line 846-849), because **Binance futures
tickers carry no price**:

```
Configuration error: Ticker pricing not available for Binance.
```

`binance.py:61` sets `"tickers_have_price": False` in `_ft_has_futures`. So on
Binance futures there is **no pricing configuration that satisfies both rules** —
`price_side` must be `"other"` and the order book must be off, and the second
requires tickers this venue does not have.

**Failure 3 — the documented escape hatch is a no-op in 2026.8.** The docs say
`--lookahead-allow-limit-orders` skips the override. It does not:
`lookahead_allow_limit_orders` is **never copied from `args` into the config**
(`configuration.py:444-456` lists `targeted_trade_amount`,
`minimum_trade_amount`, `lookahead_analysis_exportfilename` — but not this one),
while `lookahead_helpers.py:157` reads it from the config. The flag parses, is
accepted, and changes nothing. Verified: the run with the flag still logged
`Forced order_types to market orders.`

**What actually works** — set the key in a config file instead. Upstream's own
test does this (`tests/optimize/test_lookahead_analysis.py:144`), which is how the
disconnect is visible. `user_data/config_lookahead_override.json` is provided:

```json
{ "lookahead_allow_limit_orders": true }
```

```powershell
& ".\.venv\Scripts\freqtrade.exe" lookahead-analysis `
    --config user_data\config_regime_breakout_backtest.json `
    --config user_data\config_lookahead_override.json `
    --datadir user_data\data\binance `
    --strategy RegimeVolBreakout5m `
    --timerange 20250101-20250701 `
    --pairs BTC/USDT:USDT ETH/USDT:USDT `
    --minimum-trade-amount 20 --targeted-trade-amount 25
```

Later `--config` files win (`load_config.py:116`, `deep_merge_dicts`).

> **Caveat on the result, stated because the docs warn about it.** Upstream says
> limit orders "has shown to eventually produce false positives" in this command.
> That risk is specifically about limit orders combined with
> `custom_entry_price()` / `custom_exit_price()` callbacks. **This strategy
> defines neither** — its only callbacks are `custom_exit` (an exit *reason*)
> and `custom_stoploss`. So for this strategy the override is the low-risk path.
> A positive bias finding here would still need confirming; a negative one is
> meaningful.

**✅ Verified result 2026-09-27** (2 pairs, 6 months, 431 trades found,
25 checked):

| filename | strategy | has_bias | total_signals | biased_entry | biased_exit | biased_indicators |
|---|---|---|---:|---:|---:|---|
| RegimeVolBreakout5m.py | RegimeVolBreakout5m | **No** | 25 | 0 | 0 | *(none)* |

The `.shift(1)` usage in this strategy is clean.

`--minimum-trade-amount` / `--targeted-trade-amount` bound the work; without
them this is hours on 5m data.

### 3.5 Universe ladder — with concurrency pinned

See §1.3. This is the version of the md's phase-3 ladder that is actually
interpretable:

```powershell
# 3 pairs, concurrency pinned at 3
& ".\.venv\Scripts\freqtrade.exe" backtesting --config user_data\config_regime_breakout_backtest.json --datadir user_data\data\binance --strategy RegimeVolBreakout5m --timerange 20230101-20251118 --max-open-trades 3 --pairs BTC/USDT:USDT ETH/USDT:USDT XRP/USDT:USDT

# 5 pairs, SAME concurrency of 3
& ".\.venv\Scripts\freqtrade.exe" backtesting --config user_data\config_regime_breakout_backtest.json --datadir user_data\data\binance --strategy RegimeVolBreakout5m --timerange 20230101-20251118 --max-open-trades 3 --pairs BTC/USDT:USDT ETH/USDT:USDT XRP/USDT:USDT ADA/USDT:USDT DOT/USDT:USDT

# all 8, concurrency back to 5
& ".\.venv\Scripts\freqtrade.exe" backtesting --config user_data\config_regime_breakout_backtest.json --datadir user_data\data\binance --strategy RegimeVolBreakout5m --timerange 20230101-20251118 --max-open-trades 5
```

Only the first two rungs are comparable. The third changes two things at once and
must be reported as such.

### 3.6 Cost stress

Per the md §14 phase 2 — strategy untouched, only cost moves. This is the
single most informative experiment available, because this repo has already
measured that cost here is **not** a constant: 12.0 bps calm, 15.6 cascade,
22.8 volatile, **34.9 COVID** (`RESEARCH_STATE.md` §1b).

| `--fee` | round trip | which regime |
|---:|---:|---|
| `0.0005` | 10 bps | Binance futures taker, BNB discount (`user_data/fee_fut_bnb.json`) |
| `0.0006` | **12 bps** | baseline — the repo's calm-day floor |
| `0.0008` | 16 bps | repo modelled |
| `0.0010` | 20 bps | between calm and volatile |
| `0.0015` | 30 bps | near the COVID measurement |
| `0.0030` | 60 bps | ruin check |

```powershell
foreach ($f in 0.0006, 0.0008, 0.0010, 0.0015, 0.0030) {
    & ".\.venv\Scripts\freqtrade.exe" backtesting `
        --config user_data\config_regime_breakout_backtest.json `
        --datadir user_data\data\binance `
        --strategy RegimeVolBreakout5m `
        --timerange 20230101-20251118 `
        --fee $f --export trades `
        --export-directory "user_data\backtest_results\fee_$f"
}
```

**`--fee` on the CLI beats the config** — it is in `ARGS_COMMON_OPTIMIZE`, and
`Configuration` overwrites the config value. `backtesting.py:268-281` then uses
`config["fee"]` ahead of the exchange default. Without it, freqtrade silently
uses `max(taker, maker)` from the exchange's lowest tier, which is **not**
6 bps and not what this repo assumes.

**Publish the whole curve, never the best cell.** A frontier that is positive at
12 bps and negative at 30 bps is a cost-bound result; a curve that is negative
everywhere is a null. They are different findings and only one of them is final.

### 3.7 Dry-run

```powershell
& ".\.venv\Scripts\freqtrade.exe" trade `
    --config user_data\config_regime_breakout_dryrun.json `
    --strategy RegimeVolBreakout5m
```

`initial_state` is `"stopped"`, so the bot loads and connects but does not open
positions until you start it from the API or change it. That is deliberate.

Dry-run still needs to load Binance markets, so it is subject to the same
network reachability as everything else (`RUNBOOK.md` §1 — VPN on, or
`api.binance.com` is unreachable and the bot dies in `reload_markets`).

### 3.8 If you need the md's SOL/BNB/DOGE/AVAX/LINK/SUI

```powershell
& ".\.venv\Scripts\freqtrade.exe" download-data `
    --config user_data\config_regime_breakout_backtest.json `
    --datadir user_data\data\binance `
    --exchange binance --futures `
    --pairs SOL/USDT:USDT BNB/USDT:USDT DOGE/USDT:USDT AVAX/USDT:USDT LINK/USDT:USDT SUI/USDT:USDT `
    --timeframes 5m 1h 1m `
    --timerange 20230101- `
    --prepend
```

Then add them to `pair_whitelist`. **Re-run `list-data` (§3.2) afterwards** —
a pair added to the whitelist without its 5m file is the §1.1 silent-zero case.
Note this widens the universe and changes concurrency at the same time (§1.3).

---

## 4. What the first full run showed

**Run (✅ verified 2026-09-27):** 8 pairs, 2023-01-01 → 2025-11-18 (1,052 days),
`--fee 0.0006` from config, `timeframe_detail: 1m`, max_open_trades 5, wallet
10,000 USDT, fixed 100 USDT stake.

| | |
|---|---:|
| Trades | **9,236** (8.78/day) |
| Total profit | **−12.33%** (−1,233 USDT) |
| Profit factor | 0.68 |
| Win rate | 30.6% |
| Sharpe (closed trades) | −24.54 |
| Mean profit p-value | 1.96e−44 |
| Max drawdown | 12.50% over **1,042 days** |
| Total trade volume | **1,807,023 USDT** |
| **Market change over the same window** | **+207.14%** |

Three things in that table matter more than the headline.

**1. It lost money in a window the market gained 207% in.** Not "flat" — down
12% while the underlying rose. And the drawdown runs 1,042 of the 1,052 days:
the equity curve never recovered.

**2. Turnover is the story, and the gross edge is *already* negative.** I first
read the 1.8M USDT of traded notional as "fees explain the loss" and inferred a
positive gross. **That inference was wrong, and measuring it is why.** Re-running
with the fee at ~zero:

| `--fee` | round trip | Total profit % | Profit factor | Sharpe | Abs profit | Trades |
|---:|---:|---:|---:|---:|---:|---:|
| `0.000001` | ~0 (**gross**) | **−1.51%** | 0.95 | −3.01 | −151.24 | 9,236 |
| `0.0006` | 12 bps (baseline) | **−12.33%** | 0.68 | −24.54 | −1,233.00 | 9,236 |
| `0.0030` | 60 bps (stress) | **−55.67%** | 0.22 | −110.61 | −5,567.25 | 9,236 |

✅ All three verified 2026-09-27. **The trade count is identical in every row** —
the fee does not change which trades are taken, only what they are worth. That
makes this a controlled experiment on cost alone, and the identity is clean:

```
net ≈ gross(−151) − volume(1.81M) × fee
      −151 − 1,084 = −1,235  (measured −1,233)
      −151 − 5,434 = −5,585  (measured −5,567)
```

**The curve starts negative at zero cost.** There is no fee level at which this
configuration is profitable, and removing all costs does not rescue it — the
gross edge is −1.51% with a profit factor of 0.95, i.e. flat-to-slightly-negative
before a single fee.

This is the distinction `RESEARCH_STATE.md` §1b draws for E#6, and this line
lands on the *other* side of it. E#6's failure was sample size, not cost. **This
one fails on both: the signal has no gross edge, and 181× capital turnover on a
43-minute average hold then hands 1,084 USDT to the exchange on top.**

> **Rule, restated because this run earned it: do not infer a gross number from
> a net one.** "The loss is mostly fees" looked obvious from a 1.8M notional
> figure and was wrong in the reassuring direction — it implied a hidden positive
> edge that does not exist. The gross series has to be run.

**3. The exit model, not the entry, is where it goes.** Exit-reason stats:

| Exit reason | Exits | share | Win% | Total USDT | Avg hold |
|---|---:|---:|---:|---:|---:|
| `trailing_stop_loss` | 4,856 | 52.6% | 20.0% | **−1,842.87** | 0:30 |
| `exit_signal` | 2,182 | 23.6% | **1.3%** | **−1,387.99** | 0:47 |
| `tp_1_8pct` | 895 | 9.7% | 100% | **+1,657.51** | 0:37 |
| `time_stop` | 1,222 | 13.2% | 76.4% | **+418.09** | 1:30 |
| `stop_loss` | 81 | 0.9% | 0% | −77.74 | 0:15 |

The two exits that let a trade run — the 1.8% target and the 90-minute time stop
— make **+2,076 USDT across 2,117 trades**. The three that cut a trade short lose
**−3,309 USDT across 7,119**.

Specifically: `exit_signal` closed 2,182 trades and won **28 of them (1.3%)**.
Its condition is `close < ema_21` **or** `close < ema_50_1h` — any 5m close below
EMA21 trips it, so it fires on ordinary noise and truncates the average hold to
47 minutes against a 90-minute time stop. And the 3×ATR trailing stop fires on
**more than half of all trades** at a 30-minute average hold, re-anchored to the
latest price every candle: a stop too tight to let a 1.8% target be reached.

### What this is, and what it is not

It is a clear and highly significant negative result **for this configuration**,
and both the mechanism and the cost decomposition are measured rather than
inferred. It is **not** proof that the *hypothesis* is false, for one reason
that is about method rather than about the strategy:

- The whole thing is **in-sample on one parameterisation**. "Which exits lose" is
  exactly the kind of observation that invites a fix, and fixing it now is
  selection. Per §1 of the md and this repo's pre-registration rule, if the exit
  model is going to change, that has to be a *pre-registered* change with a fresh
  OOS window, not a patch informed by this run.

What can be said without hedging: **this configuration has no gross edge, so no
cost assumption rescues it, and no parameter search over its entry filters will
either** — the entry is the 5m breakout family, which is already closed (§ below).

### Prior art this run reproduces

This hypothesis is a recombination of three families this repository has already
tested and closed. `RESEARCH_STATE.md` §1, §1c, §1d:

- **5m breakout** — `PerpTrendBreakout`, 4,916 trades over 2024-01-01 →
  2025-11-18: gross ≈ 0, **99.2% of the loss was fees**. **This run reproduces
  that on an independent implementation and a different filter stack: gross
  −1.51%, PF 0.95.** Two engines, two entry variants, the same answer. Verdict on
  the family: *"do not optimize this same signal family by parameter search or
  deploy."*
- **Volume expansion** — the 5m factor scan: RVOL's best gross edge is
  **2.47 bps against a 12.0 bps round trip, short by 5×**. CVD, the factor this
  hypothesis leans on hardest, is null at t_adj 0.54. The `volume_expansion`
  filter here is the same RVOL construction and cannot be expected to add what the
  scan measured.
- **1h directional regime filter** — no peer-reviewed support in any asset class;
  Hurst, Ooi & Pedersen (2017, JPM, peer-reviewed) tested prospective regime
  timing directly and it failed. The one filter with an empirical result behind it
  is **low** volatility — the opposite of this hypothesis, which requires
  volatility expansion. `RESEARCH_STATE.md` §1d's counter-example is the WIDE
  PANEL result, where the **low-vol** filter added +38–43% gross; the same
  direction, inverted, is untested here.
- **5m cost arithmetic** — `cost_R = round_trip_bps / (stop_multiple × atr_pct ×
  10,000)`. At 5m, `atr_pct` is small, so cost per R is **0.62–0.75R** against a
  gross edge this hypothesis has to beat before fees are counted at all. The
  measured 5m gross is ≈ 0. **A 5m strategy with 3×ATR stops needs a gross edge
  well above 0.75R just to reach breakeven, and this family has never produced
  one.** The measured gross above is −1.51%, which is the other side of that
  hurdle from where it needs to be.

None of that was re-derived for this run; it is quoted from existing artifacts.
The one genuinely new item is the exit-reason decomposition, and it points at a
mechanism (a stop too tight to reach the target, firing on half the trades) that
the prior work never isolated because those lines used different exit models.

**If this line continues**, the honest next step is not a parameter sweep. It is
to decide, pre-registered, whether the exit model is the thing being tested — and
if so, freeze it, and re-test on a window not used here.

---

## 5. Trap list for this specific strategy

1. **`lookahead-analysis` does not run on Binance futures with a normal config.**
   Three separate failures; see §3.4. Use `user_data/config_lookahead_override.json`.
2. **XLM has 5m but no 1h** → silent all-NaN informative merge → zero trades, no
   error. Keep it out of the whitelist, or download 1h for it.
3. **`--datadir` is mandatory**; `datadir` in config is ignored.
4. **`max_open_trades` is silently `min(setting, n_pairs)`** — changing the
   universe changes the concurrency unless you pin it.
5. **`perp_leverage` does nothing here.** Only `leverage()` does. And see
   `RESEARCH_STATE.md` §1: a flat `stoploss` is a *margin* stop, so
   `LocalTrade.adjust_stop_loss` divides it by leverage. **At 1x that is a
   non-issue** — but if you ever raise leverage, a `stoploss = -0.009` becomes a
   0.045% *price* stop at 20x while the 1.8% target stays fixed. That bug
   produced a fake "leverage destroys returns" curve twice in this repo.
6. **Without `--fee`, the cost is the exchange's worst tier**, not 6 bps. The
   log line `Using fee 0.0600% from config.` is the confirmation — if you do not
   see it, the assumption is not in force.
7. **The strategy returns 1x from `leverage()` unconditionally**, so `--futures-leverage`
   / leverage experiments are a Strategy edit, not a CLI experiment.
8. **`timeframe_detail: 1m` changes the fills.** Turning it off to "go faster"
   silently changes the result, not just the runtime.
9. **The `entry_pricing`/`exit_pricing` order-book settings are inert in
   backtesting** and only matter for dry-run/live parity. Do not read them as
   validated by a backtest.
10. **`--export-filename` is deprecated and does nothing** for backtesting in
    2026.8; use `--backtest-directory` or `--notes`.
