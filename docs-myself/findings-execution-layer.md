# Findings: Execution Layer — Defects the Backtest Could Not See

Run 2026-09-19, freqtrade 2026.8. Scripts: `tools/equal_weight_pool_test.py`,
`tools/dryrun_db_analysis.py`. Strategy: `user_data/strategies/BTCSmaTrend.py`.

This round closed the two gaps left open by `findings-sma-15year.md`:
the objective's **equal-weight same-pool benchmark**, and the handoff's
**execution-layer questions** that research cannot answer.

---

## 1. Equal-weight same-pool benchmark — the objective's missing control

The objective names five controls. Four were already satisfied for SMA-50
(matched-exposure, placebo, one-bar shift, survivorship disclosure). The fifth
is the handoff's explicit stage-0 rule:

> 与 SPY 比较是**假的测试**（池子偏差）→ 必须用**等权同池**

The 15-year study compared BTC against BTC buy & hold — natural for a
single-asset timing rule, but **not** a same-pool test. So I built the
equal-weight portfolio of the Bitstamp majors, with a point-in-time universe
(a member joins only when it actually lists):

| pair | lists |
|---|---|
| BTC/USD | 2011-08-18 |
| XRP/USD | 2016-12-16 |
| LTC/USD | 2017-06-16 |
| ETH/USD | 2017-08-16 |
| BCH/USD | 2017-12-04 |

Pool window: **2016-12-17 → 2026-09-19 (9.8y)**, SE(Sharpe) ≈ 0.320.

### Result — it holds on the pool too

| rule | avgExp | CAGR | MaxDD | Sharpe |
|---|---:|---:|---:|---:|
| equal-weight buy & hold | 100% | 72.58% | -90.71% | 1.05 |
| **SMA-50 on pool** | 76.4% | **89.87%** | **-78.42%** | **1.30** |
| flat @ 76% | 76.4% | 62.05% | -82.22% | 1.05 |

| gate | result |
|---|---|
| wildcard placebo (300 draws) | **p = 0.003** ✅ |
| bootstrap vs flat | +0.252, **CI [+0.04, +0.44]**, p=0.009 ✅ |
| bootstrap vs equal-weight B&H | +0.252, **CI [+0.05, +0.45]**, p=0.010 ✅ |
| one-bar shift | 1.30 → 1.25 → 1.24 (graceful) ✅ |

Window grid on the pool: 10→1.12, 20→1.16, 30→1.22, **50→1.30**, 75→1.17,
100→1.23, 150→1.13, 200→1.06. Still a plateau, with 50 at the peak — but the
spread (1.06–1.30) is wider than on BTC alone, so the pool result is somewhat
more parameter-sensitive than the single-asset one.

## 2. Survivorship bias — stated, and why it partly cancels

The pool is 5 coins that **still trade in 2026**. Everything that delisted or
went to zero between 2011 and 2026 is absent, which is an upward bias on
buy & hold.

**How it affects this result:** the strategy is *relative* — it holds 50% or
100% of the **same** asset. Because both legs of every comparison use the
**identical universe**, the survivorship bias largely **cancels** in the
relative comparison. The absolute CAGRs (72%, 90%) are inflated and should not
be quoted; the *edge* (+0.25 Sharpe vs both benchmarks) is the part that
carries information.

A true fix needs point-in-time listing/delisting data, which Bitstamp's public
API does not provide. **Not corrected** — disclosed.

---

## 3. Execution layer — two real defects found by dry-run

`freqtrade trade --dry-run` surfaced problems **invisible to any backtest**,
exactly the questions the handoff says the research track cannot answer.

### Defect 1 — stale database carried foreign trades

The first dry-run logged:

```
Found open trade: Trade(id=44, pair=BTC/USDT, ... open_since=2026-05-03)
```

That trade came from an **earlier Binance session** in the shared
`tradesv3.dryrun.sqlite`. The new Bitstamp run adopted it and began emitting
orders for it — mixing two exchanges in one database.

**Fix:** dedicated `"db_url": "sqlite:///tradesv3.btcsma.dryrun.sqlite"` in
`config_btcsma.json`. Never share a dry-run DB across configs.

### Defect 2 — order churn from callback cadence

Logs showed the same order created, cancelled and replaced every ~5 seconds:

```
Position adjust: about to create a new order ... stake_amount: 24.4271
Buy order cancelled to be replaced by new limit order ...
Order dry_run_buy_BTC/USD_45239c7b... was created ... status is open
(repeating)
```

Measured churn in the shared DB: **119 orders, 28 cancelled = 24%**.

**Root cause:** `adjust_trade_position` fires on *every process throttle*
(~5s) in live/dry-run, but only *once per candle* in backtesting. Acting on
every call therefore produces live behaviour the backtest never models.

**Fix:** two guards in `BTCSmaTrend.adjust_trade_position`, both safe because
the signal is a daily-candle state so at most one action per candle is correct:

1. act only once per known candle (tracked in trade custom data)
2. never act while the trade already has an open order

### Verified fix

Fresh 90-second dry-run on a clean DB:

| metric | before fix | after fix |
|---|---:|---:|
| orders | 119 | **2** |
| cancelled | 28 | **0** |
| cancel rate | **24%** | **0%** |
| exchanges in DB | binance (polluted) | **bitstamp only** |
| `Position adjust` calls | 11 for one trade | **1** |

Backtest is unchanged (1 trade, +2443.59%, Sharpe 0.92 wallet-balance) —
the guards do not alter historical behaviour, they only stop live over-trading.

### Restart / state recovery — verified clean

Second run against the existing DB:

```
Found open trade: Trade(id=1, pair=BTC/USD, amount=0.06147427, open_rate=81334.83)
Bot heartbeat ... state='RUNNING'
```

One trade recovered, **zero new orders**, no churn. State recovery works.

---

## Where this leaves the objective

| objective control | status |
|---|---|
| equal-weight same-pool benchmark | ✅ this round (p=0.003, CI excludes 0) |
| matched-exposure control | ✅ flat at same avg exposure |
| placebo / permutation test | ✅ p=0.002 (BTC), p=0.003 (pool) |
| one-bar shift test | ✅ graceful, no look-ahead |
| survivorship bias honestly reported | ✅ disclosed + why it cancels relatively |
| **do not deploy real money until all controls pass** | ✅ controls pass; **still not deployed** |

Two objective-level caveats remain, unchanged from round 2:

* **MaxDD is still -74% (-78% on the pool).** Better than buy & hold, not "safe".
* **The edge is ~+0.17–0.25 Sharpe** — real but modest.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\equal_weight_pool_test.py   # objective's 5th control
.\.venv\Scripts\python.exe tools\dryrun_db_analysis.py       # churn evidence

# fresh dry-run (use a dedicated DB; do NOT reuse tradesv3.dryrun.sqlite)
.\.venv\Scripts\freqtrade.exe trade --config user_data\config_btcsma.json `
    --strategy BTCSmaTrend --dry-run
```

**Not a green light for real money.** The controls pass and the execution
defects are fixed, but this has never traded forward on live data. That —
not more backtesting — is the remaining step.
