# Community / official strategy review — is there anything worth copying?

**Date:** 2026-09-27
**Asked by:** user, pointing at <https://www.freqtrade.io/en/stable/> — *"Look into freqtrade
official or community, have any good strategy exist that can be copy / refer / enhance from?"*
**Nature of this work:** research only. No strategy was written, no backtest was run, no code
in `user_data/` was touched.

> **Environment limitation, stated up front.** The file sandbox failed this session with
> `SetNamedSecurityInfoW failed (Win32 5): grantWrite(E:\FreqTrader\freqtrade)` — the same
> failure recorded in `RESEARCH_STATE.md` §1c. **No shell command ran**, so nothing here was
> recomputed in code, and the one proposed experiment (below) was **not** executed. Everything
> load-bearing is quoted from a primary source: the freqtrade docs in this checkout, the
> freqtrade GitHub organisation, and the two sites' own published text.

---

## 0. The answer, in one paragraph

**No alpha to copy. Three things worth reusing, none of them a strategy.** The freqtrade
maintainer *himself deleted* the community strategy results table in August 2026, calling it
"missleading statistics". The one serious community leaderboard is better built than the table
it replaced — it publishes its own config, its own flags, and its own caveats, several of which
are more honest than most published quant results — but its headline numbers are bounded by
`docs/backtesting.md`, which states that the backtester fills every order at the requested
price with no slippage, and fills every stoploss *exactly at the stop price even if the low was
lower*. A −1.5% five-year maximum drawdown on 33 crypto spot pairs is not a skill; it is that
sentence. Every alpha family the leaderboard is built from — SMA/RSI/Bollinger/Supertrend trend,
mean reversion, and a BTC regime filter — is a family this repository has already measured to a
null, most of them twice, on two engines. What is worth taking is **execution**
(`AlmgrenChrissStrategy`, `TWAPStrategy`), **exit/risk machinery** (`BreakEven`,
`FixedRiskRewardLoss`), and **the diagnostics** — which in two cases are better than ours.

---

## 1. Official: the maintainer removed the results

`freqtrade/freqtrade-strategies` README, commit [`e5e1791`](https://github.com/freqtrade/freqtrade-strategies/commit/e5e1791c09b6ead0cf7d422d62bcf9f78d5db317),
**2026-08-05, by `xmatthias`** (the project's maintainer):

> `docs: clarify Repository purpose, remove missleading statistics` — *closes #337*

The current README says:

> "They also mostly should serve as **a starting point for your own strategies, not as
> 'ready to use' strategies**."

The table it removed (readable at the parent commit
[`dbd5b0b`](https://raw.githubusercontent.com/freqtrade/freqtrade-strategies/dbd5b0b21cfbf5ee80588d37458ace2467b7f8a4/README.md))
is the entire official performance claim, and it is:

| strategy | buy count | AVG profit % | backtest period |
|---|---:|---:|---|
| Strategy001 | 55 | 0.05 | 2018-01-10 → 2018-01-30 |
| Strategy002 | 9 | 3.21 | 2018-01-10 → 2018-01-30 |
| Strategy003 | 14 | 1.47 | 2018-01-10 → 2018-01-30 |
| Strategy004 | 37 | 0.69 | 2018-01-10 → 2018-01-30 |
| Strategy005 | 180 | 1.16 | 2018-01-10 → 2018-01-30 |

**A 20-day window. Nine trades in the best-looking row.** The strategies' own README said
"Most of them were designed from Hyperopt calculations" — so the numbers are the output of a
search, reported on a window the search never saw, which is the maximum-of-N construction
`RESEARCH_STATE.md` §1d already cites Sullivan, Timmermann & White (1999, *JF*) demolishing.

**Why the table was removed.** [Issue #337](https://github.com/freqtrade/freqtrade-strategies/issues/337)
asked for an exit-reason split, and made the point that the published ROI ladder plus a
`-10%` stoploss implies a break-even win rate of **92.73%** if wins close on the bottom rung
(`10.20 / (10.20 + 0.80)`). The maintainer closed it `not_planned` and removed the table.

> **This repository had already answered #337, more thoroughly, and independently.** The
> `RegimeVolBreakout5m` exit-reason decomposition measured that the `exit_signal` closed
> **2,182 trades, of which 28 won (1.3%)**, and the 3×ATR trail fired on **52.6% of all trades
> at a 30-minute average hold** — i.e. the exit model, not the entry, was where the money went.
> The community issue asks for one number; this repo measures the whole exit distribution.

**The official docs are explicit, twice:**

- `docs/strategy-101.md:187` — *"**most public strategies are not good performers** due to the
  time and effort to make a strategy work profitably in multiple scenarios."*
- `docs/strategy-101.md:145-147` — *"**Some websites that list and rank Freqtrade strategies
  show impressive backtest results. Do not assume these results are achieveable or realistic.**"*
- `docs/strategy-customization.md:1256` — *"these strategies should be considered **only for
  learning purposes, not real world trading**."*
- `docs/strategy-customization.md:34` — *"`new-strategy` generates starting examples which will
  not be profitable out of the box."*

The official `SampleStrategy` is RSI-crosses-30/70 plus a Bollinger and TEMA guard on **5m** —
the canonical momentum-reversion indicator stack. §4 below maps it to a closed line.

---

## 2. The one serious community leaderboard: Freqle

`https://freqle.org` — 5,330 ranked strategies, 2021–2025, 33 Binance spot pairs. It is a
commercial product (Supporter/Premium tiers via GitHub Sponsors). **Give it its due first:**

**What it does that is genuinely better than the official table:**

- **A published, common harness.** Same 33 pairs, same wallet (1,000 USDT), same stake
  (100), 10 slots, 0.1% fee, `--enable-protections`, `--cache none`, fixed timerange
  `20210101-20260101`. The sandbox command is printed on their FAQ. Comparability across
  strategies is real, and this is the one thing the official table never had.
- **A clone-blind ranking is NOT claimed — and should be.** (§2.3)
- **It states its own selection problem and corrects for it**: *"with 1,000 strategies, about
  50 will look 'significant at p < 0.05' by chance alone"*, and applies Benjamini-Hochberg
  across the board, reporting how many of the top 20 are expected false positives. That is the
  same correction this repo's §1d and §3.1 insist on, arrived at independently.
- **Eleven "artifact flags" for results that are impossible rather than merely good** — e.g.
  `edge_below_fee` ("the fee at which the edge reaches zero is below the fee the run was
  charged: **this strategy loses money at real costs**"), `dca_capital_fiction`, `held_to_end`,
  `losers_left_open`, `liquidated`, `profit_concentration`.
- **It excludes ML/FreqAI strategies from the League entirely** (no compute), and says so.
- **Its own closing rule:** *"A backtest is the best case. It fills every order, pays no
  slippage, and knows the pair list survived. Treat a good number as a reason to look closer,
  never as a reason to deploy."*
- Its FAQ check #1 is the exact footgun this repo has now paid for **twice** (§4.3):
  *"freqtrade's `stoploss` is a **price** move, not a margin move… if you get past 100%, the
  stoploss is decorative."*

**Their own `edge_below_fee` flag fires on 4,041 of 8,118 backtests — 49.8%.** Half of
everything they ran loses money at the fee they charged. The leaderboard is the other half.

### 2.1 The numbers are bounded by `docs/backtesting.md`, not by skill

Top of the table (fetched 2026-09-27):

| # | strategy | profit | CAGR | maxDD | win | Sharpe | trades |
|---|---|---:|---:|---:|---:|---:|---:|
| 01 | `DS_BNC_EV1E_5m` | +309.2% | +32.5% | **−1.47%** | 88.5% | **7.578** | 897 |
| 02 | `DivergenceStrategy` | +252.4% | +28.6% | **−1.07%** | 83.7% | **10.2** | 1,979 |
| 10 | `NotAnotherSMAOffsetStrategy` | +296.1% | +31.7% | −3.94% | 76.0% | 9.031 | 2,761 |
| 23 | `NASOSv6` | +505.6% | +43.3% | −7.89% | 94.0% | 11.377 | 4,747 |

Their harness: 1,000 USDT wallet, 10 slots of 100 USDT, **5m candles**, spot. So **−1.47% of
equity is −14.7 USDT — one slot losing 14.7%** — as the *worst* peak-to-trough over five years
and 897 trades.

**The engine cannot produce anything worse, and says so:**

> `docs/backtesting.md:571` — *"Stoploss exits happen **exactly at stoploss price, even if low
> was lower**"*
> `docs/backtesting.md:573` — *"Low happens before high for stoploss, protecting capital first"*
> `docs/backtesting.md:562` — *"All orders are filled at the requested price (**no slippage**)"*
> `docs/backtesting.md:567-568` — ROI: *"Exits are never 'below the candle', so a ROI of 2% may
> result in an exit at 2.4%"*

A real stop is a *trigger*; the fill is the next tradeable price. In 2021–2022, on SOL/AVAX/BNB
at 5m, that is routinely 20–30% past the level. **The backtester prices that at exactly the
level, every time, forever.** A −1.5% drawdown is a statement about `backtesting.md:571`, not
about the strategy. The 88.5% win rate and the Sharpe of 7.578 follow from the same sentence.

An internal consistency check on row 01, assuming their "profit %" is on starting balance
(their own definition) and reading the published PF of 10.36 with the published 88.5% win rate:
average win ≈ **+4.3%**, average loss ≈ **−3.2%**. *An average losing trade of 3.2% on a 5m
crypto spot pair, 897 times, over 2021–2025.* Every one of those 103 losses is a fill the engine
placed at exactly the stop. Freqle's own MAE/MFE page invites the reader to look for "a wall of
dots pinned at MAE ≈ 0… suspicious" — this is the aggregate form of the same signature.

### 2.2 An unresolved internal inconsistency in the Calmar column

Freqle's FAQ defines Calmar as *"CAGR ÷ max drawdown"*. On the five rows I checked, the
**Calmar column is not CAGR ÷ the Max DD column shown beside it**:

| # | CAGR | Max DD | CAGR ÷ MaxDD | Calmar shown | ratio |
|---|---:|---:|---:|---:|---:|
| 01 | 32.5 | 1.47 | 22.1 | 219.556 | 9.9× |
| 02 | 28.6 | 1.07 | 26.7 | 296.548 | 11.1× |
| 03 | 30.0 | 1.53 | 19.6 | 185.232 | 9.4× |
| 05 | 28.7 | 1.58 | 18.2 | 168.259 | 9.2× |
| 10 | 31.7 | 3.94 | 8.0 | 105.644 | 13.1× |

The ratio is consistently 9–13×, never 1. Either the Calmar column is computed on a different
drawdown basis than the adjacent "Max DD" column, or one of the two is wrong. **I did not
resolve it** — a strategy page may document a different drawdown definition. Recorded because
it is exactly `RESEARCH_STATE.md` §3.32b's defect class (*the same signal carrying several
values because several bases were used*) in a third-party table, and it is checkable in thirty
seconds from their own public page.

### 2.3 The leaderboard is a max over clones, not over 5,330 independent bets

The public table contains **byte-identical metric rows from different repositories**:

- Rows 03/04 — `binance` (vaskosmihaylov) and `E0V1E` (XinuxC): both +271.5%, +30.0%, −1.53%,
  87.3%, 5.967, 6.606, 185.232, pf 11.59, **757 trades**.
- Rows 06/07 — `E0V1E` (cyberjunky) and `OptimalStrategy` (freqle/uploads): both +248.0%,
  +28.3%, −1.59%, 80.1%, 7.49, 7.489, 163.548, pf 9.27, **868 trades**.
- Rows 27/28 — `NASOSv4_SMA` (remiotore) and `DS_SOS_5m` (Danson77): both +561.3%, +45.9%,
  −8.91%, 93.9%, 10.545, 17.156, 85.809, **5,639 trades**.
- Rows 14/15 — `ElliotV8` and `ElliotV8_original`: **2,166 trades each**.

Identical trade counts to the unit are not a coincidence. `NotAnotherSMAOffsetStrategy` and
`E0V1E` appear four times each inside the top 20. **"5,330 ranked" is therefore not 5,330
independent bets**, and the BH correction is applied over a field far larger than the number of
distinct strategies in it — which makes the correction *anti*-conservative, not conservative.
This is `RESEARCH_STATE.md` §3.5 (counting correlated observations as independent) in a new
place, and it is the single most important structural fact about the leaderboard.

### 2.4 The pair list is a survivorship-selected present-day universe

Their fixed universe is 33 pairs that are *currently* listed, backtested from 2021-01-01. Several
of those did not exist at the start of the window. Freqtrade's own FAQ documents the
consequence: *"Freqtrade will fill up these candles with 'empty' candles, where open, high, low
and close are set to the previous candle close."* Freqle's own FAQ concedes the check *"Does not
prove: live behaviour. No slippage, no partial fills, **no pair delisting**."*

**Flagged, not asserted:** I did **not** verify per-symbol listing dates this session —
Binance's public `exchangeInfo` no longer returns `onboardDate` (queried 2026-09-27, field
absent). The structural point stands from the two disclosures above; the exact count of
later-listed pairs is unverified. This repo has already been bitten by exactly this shape
(`PREREG_CROSS_SECTION_2026-09-26.md`, survivorship handling as a frozen protocol item).

### 2.5 `--timeframe-detail` is off

Freqle's printed command omits it, and their FAQ concedes the consequence for coarse
timeframes. At 5m the exposure is small, so this is **not** a major driver for the top of their
table — but this repo used `timeframe_detail 1m` for exactly the reason
(`RegimeVolBreakout5m`), and it changed the exit-reason decomposition materially.

---

## 3. Mapping the leaderboard's alphas onto this repo's closed lines

The most common single "trick" across the whole field is `btc_regime_filter` — **2,873 of
5,330** strategies. The rest of the leaders cluster on `time_exit` (2,751), `trailing`,
`deadfish_exit` (209), `risk_sizing` (520).

| leaderboard family | this repo's status |
|---|---|
| SMA/EMA/RSI/Bollinger/Supertrend trend-following (`MultiMa`, `Supertrend`, `ElliotV8`, `NotAnotherSMAOffsetStrategy`, `TrendRider`, `GodStra`) | **CLOSED.** `PerpTrendSlow` +12.79% / Sharpe 0.21 vs buy-and-hold +177.09%. 111 of 170 trades were stop-outs, none profitable. `PREREG_MULTI_STRATEGY` re-ran SMA-200 and Donchian 55/20 through freqtrade: all four variants landed within 1/6th–1/27th of the 0.54 detection floor of each other. |
| `btc_regime_filter` (2,873 strategies) | **CLOSED, and by the canonical paper.** §1d: Hurst, Ooi & Pedersen (2017, *JPM* 44(1), peer-reviewed) tested prospective regime timing directly — recession, inflation, war/peace, bull/bear, S&P vol quintiles, T-bill yield — and found it null: *"the performance of trend following was similar across groups."* §1d also records §1c's law: a filter raises net-per-trade only by raising **gross** expectancy; trading less does not make the kept trades cheaper. |
| 5m mean reversion | **CLOSED, twice.** `PerpTrendBreakout` (4,916 trades, 7.16/day): gross ≈ −$3, fees $452 of the $456 loss. `RegimeVolBreakout5m` (9,236 trades): the cost frontier **starts negative at zero cost** — −1.51% at fee 1e-6 — so it is a signal failure *and* a cost failure, and no fee assumption rescues it. |
| `funding_rate` (214 strategies) | **CLOSED.** Funding excess is −0.88 to −1.56 %/yr; the switch is re-armed but the trade is off. §2. |
| cross-sectional ranking (`PercentRankPairList`) | **CLOSED, pre-registered.** E#3 trend FAIL 2/8, E#4 reversal null at portfolio level, E#6 FAIL 5/8. Corroborated by Arefev (SSRN 7404139) on the same venue/instrument/period. |
| FreqAI / ML | **Three independent priors against.** Fayez Junior: rank IC +0.0243 (t=3.55) → **net Sharpe −2.91, −95.6% maxDD**. Freqtrade's own docs: `continual_learning` *"has a high probability of overfitting."* Bailey et al. 2016 (*JC*): IS Sharpe 1.27 / PSR 2.83 on a **random walk**, PBO 55%. Freqle **excludes ML from its own League.** |

**The modal configuration of the leaderboard is 5m** — 2,325 of 5,330 (44%). By this repo's
closed-form cost law (`RESEARCH_STATE.md` §1c, `cost_R = round_trip_bps / (stop_multiple ×
atr_pct × 10,000)`), 5m costs **0.416R per trade against 4h's 0.092R** — 4.5× more expensive per
unit of risk — and the 5m gross edge has been measured at zero twice.

---

## 4. What IS worth copying, referring to, or enhancing

### 4.1 Execution algorithms — the one class this repo has never touched

`AlmgrenChrissStrategy.py` and `TWAPStrategy.py` in the official collection. Both are
**execution** strategies, not alpha: the AC one ships with a placeholder signal
(`rsi < 45` / `rsi > 55`) and says so in its own docstring — *"The entry and exit signals are
examples and should be adapted to your strategy."*

The reusable part is the machinery: `position_adjustment_enable` + `adjust_trade_position` +
`custom_stake_amount` to slice a single parent order into timed child orders. The AC
implementation is a correct textbook one — κ from `arccosh(½κ̃²τ² + 1)/τ`, slice fractions from
`1 − sinh(κ(m−1))/sinh(κm)`, and it **reduces exactly to plain TWAP at κ = 0**, which is a
self-check worth copying on its own.

**Why it maps onto a real gap here.** `RESEARCH_STATE.md` §1b measures Binance `bookDepth` and
§1 notes the standing defect: *"The cost model in this repository has **no market-impact
term**."* Granting the entire 16 bps budget to the thinnest measured name caps gross book
notional at **$0.8M/day** (0.2% band) to **$3.9M/day** (1% band). TWAP/AC is the mechanism that
spends *time* instead of paying impact for it.

**The honest caveat, and it is decisive:** `docs/backtesting.md:562` — the backtester has **no
slippage and no market-impact model at all**. A TWAP strategy cannot be evaluated by backtesting
in this engine, because the engine cannot express the cost TWAP exists to avoid. Testing it
requires the repo's own measured depth (`tools/cost/measure_impact.py`, `shark_data/costs/`),
not a freqtrade number. That converts it from "a strategy to run" into "an execution model to
validate against a cost model we already measured" — real work, but **not an alpha claim**, and
it must not be reported as one.

### 4.2 Exit and risk machinery

`BreakEven.py` (empty signals, `minimal_roi = {"0": 0.01, "10": 0}` — close everything at
profit, let losers come to break-even) and `FixedRiskRewardLoss.py`. Small, correct, and they
attack the part of the P&L this repo has actually located: the exit model, not the entry.
`RegimeVolBreakout5m` measured the `exit_signal` closing 2,182 trades of which 28 won (1.3%).
Worth reading and adapting; not an edge.

### 4.3 The diagnostics — two of them are better than ours

`freqle.org/faq` and `docs/strategy-customization.md:1225-1252` contain checks worth importing
into the repo's own gate. In descending order of value:

1. **OHLC-overwrite realism.** Assigning over `open`/`high`/`low`/`close` in `populate_*` —
   almost always the Heikin-Ashi swap. *"It isn't random either — `HA_open` is the midpoint of
   the previous synthetic body, so it lags below the real open in an uptrend and above it in a
   downtrend. **Longs fill cheap, shorts fill rich, on every single trade.**"* A free directional
   bias from a strictly causal transformation. **Not recorded in this repo.**
2. **Dead v2 signals.** Writing `buy`/`sell` from a v3 `populate_entry_trend` never fires —
   *"the backtest isn't inflated, it's measuring a strategy that doesn't trade."* This is the
   `RESEARCH_STATE.md` §3 silent-signal family reached through a version mismatch: a strategy
   that produces **exactly zero trades with no error**. Same family as the informative-timeframe
   NaN trap and the `&=`-from-all-False rule. **Not recorded.**
3. **Colliding tags and signals.** `.loc` blocks run in source order, so a candle matching two
   conditions keeps only the **last** tag; and if a long and a short condition both fire,
   `check_for_trade_entry` takes **no trade at all** — *"signals vanish silently, in backtest
   and live alike."* `docs/strategy-customization.md:1245-1252` documents the second half; the
   first half is a per-tag-measurement error. **Not recorded.**
4. **`startup_candle_count` defaults to 0** and *"freqtrade trims no warmup, so the backtest
   opens with indicator values that could never exist live."* **Not recorded here** — and the
   repo's own `RegimeVolBreakout5m` work implies this repo does set it.
5. **`exit_profit_only` does nothing when `use_exit_signal = False`** — *"settings that look
   like risk management but never execute… tell you the author wasn't testing what they thought
   they were."*

**In the other direction — and this matters for honesty:** the repo's own
**truncation-based causality assertion** (recompute features on truncated history, assert the
shared bars are bit-identical) is **strictly stronger** than freqtrade's `lookahead-analysis`,
which Freqle itself concedes only *"identifies most common problems"* and which freqtrade's docs
caveat: *"A negative result of each does not guarantee that there are none of the above errors
included."* **Do not replace the repo's test with the engine's.**

### 4.4 Not worth it: FreqAI, pairlists, hyperopt

- **FreqAI/ML** — three independent priors against, and the leaderboard excludes it from its own
  ranking (§3).
- **`PercentRankPairList` and friends** — this is the freqtrade-native cross-sectional rank,
  i.e. E#3/E#4/E#6, already pre-registered and closed. *Worth recording* that the ecosystem's
  version is the same construction, so nobody re-frames it as new.
- **Hyperopt** — `RESEARCH_STATE.md` §1d's Bailey et al. 2016 (*JC*, peer-reviewed) result is the
  answer, and it is on a **random walk**: 8,800-node grid, IS Sharpe 1.27, PSR 2.83 (*"less
  than 1% probability the true SR is below 0"*), and **PBO = 55%**. The official repo's five
  `Strategy00x` files were themselves "designed from Hyperopt calculations."

---

## 5. The one experiment worth running (NOT run — sandbox blocked)

**`AGENTS.md` §1a: this design can conclude, and here is why.** The question is a
gross-versus-net decomposition at a fixed trade count. It is the same construction that
produced this repo's two cleanest negatives (`RegimeVolBreakout5m`'s three-point cost frontier,
trade count **identical in all three cells**, and `PerpTrendBreakout`'s $452-of-$456
attribution). Nothing here needs a significance test, a power calculation, or a new dataset.

**Design.** Take the single most-cloned entry in the leaderboard — `E0V1E` /
`NotAnotherSMAOffsetStrategy`, four clones in the top 20 — into `user_data/strategies/`, and
run it at fee `1e-6`, `0.0006`, and `0.00175`, holding **pairs, timerange and stake fixed** so
the trade count is identical at all three points. Then compare each against this repo's measured
book: 12.0 bps calm → 34.9 bps COVID round trip (§1b).

**Falsifiable prediction, stated in advance** (this repo's law, §1c, applied to a 5m book):
the curve **starts at or below zero at zero cost**, exactly as both previous 5m implementations
did. If instead it starts strongly positive, the prediction is wrong, the two prior nulls do not
generalise to this family, and the WIDE_PANEL short leg (§1, t_adj 1.8746 vs a 2.0 bar) becomes
a materially more interesting candidate. **Either outcome is worth an hour.**

**Preconditions, carried from this repo's own traps:**

- **Pass `--datadir` explicitly** — a `datadir` key in any config is silently ignored
  (`RESEARCH_STATE.md` §1, "Freqtrade `datadir` config trap").
- **Pin `--max-open-trades 10`** to match their harness, and beware the silent
  `min(max_open_trades, len(pairlist))` cap.
- **Set `startup_candle_count` honestly** and run `recursive-analysis` (Freqle's check #4).
- **Add `--timeframe-detail 1m`** if the strategy leans on `custom_exit` / trailing — Freqle
  does not, and this repo has been bitten by the exit model before.
- **Run the exit-reason split** (`--export trades`). It is the number issue #337 asked for, and
  this repo already has the tooling pattern.
- **State the selection trap in the write-up**: a max-of-5,330 leaderboard position is an
  in-sample upper bound, whatever it prints. Report the frontier, never the chosen cell.

**What NOT to do:** do not backtest the top 20. It is a max-of-5,330 selection on an engine
with no slippage model, and the arithmetic above already bounds what it can prove.

---

## 6. Verdict

- **Official freqtrade alphas: nothing to copy.** The maintainer removed the performance table
  as misleading; the docs say most public strategies are not good performers and warn
  specifically about ranking sites.
- **Community leaderboard: nothing to copy.** Sharpes of 5–11 with drawdowns of −1.0 to −1.5%
  over five years of 5m crypto are produced by `backtesting.md:571`, not by an edge. The field
  contains at least four cloned files in its top 20, so the effective N is far below 5,330.
- **Three reusable things, none of them alpha:** Almgren–Chriss/TWAP execution scaffolding (§4.1),
  exit/risk machinery (§4.2), and five backtest-integrity checks (§4.3) — of which three are
  not currently recorded in this repo and one of which would improve it.
- **One cheap experiment** (§5) that would convert all of this from an argument into a
  measurement, with a prediction registered in advance.

**A negative result is a valid result, and this is mostly one** — but the two things it leaves
open (execution cost, exit geometry) are the two this repo's own measurements point at, which
is a more useful place to be than a third null on a fourth indicator stack.
