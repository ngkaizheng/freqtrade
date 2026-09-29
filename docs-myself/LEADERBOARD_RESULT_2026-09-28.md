# The leaderboard strategy, taken apart — result and verdict

**Date:** 2026-09-27/28
**Object:** `NotAnotherSMAOffsetStrategy`
(`davidzr/freqtrade-strategies`, SHA `4d2d11e0`) — the most-cloned entry in the
freqle.org public top 20 (ranks 10, 12, 20, 31).
**Question asked:** is there a freqtrade community strategy worth copying?
**Answer:** not as a strategy. Its **entry signal** is a real, reproducible,
cost-surviving effect; its **exit model is what destroys it**. That decomposition is
the deliverable, and it is this repo's own recurring finding reproduced on an
independently-sourced strategy.

---

## 0. VERDICT FIRST

| question | answer |
|---|---|
| Is there a validated, deployable strategy? | **NO.** Evidence is marginal and does not survive multiple-testing correction. |
| Did the registered prediction hold? | **NO — it was falsified.** I predicted the curve starts at/below zero; it starts at **+351.68%**. |
| Is the entry signal real? | **Probably yes.** Out-of-sample lift **+48.04 bps**, dependence-adjusted **t = 2.08, p = 0.019**, still **+13 bps** after this repo's measured 35 bps COVID round trip. |
| Is it deployable at t=2.08? | **Not yet.** This is the max of a 5,330-strategy field, times 3 horizons I tried ⇒ ~16,000 effective trials. That bar is t ≈ 4.4. |
| Sample needed? | **~2.4 years** more forward data on the portfolio series (120 → ~390 trades); **~12 years** to clear the fully-deflated bar. |

---

## 1. The fee frontier (the registered experiment) — PREDICTION FALSIFIED

Freqle's exact published harness, 33 Binance spot pairs, 5m, 1825 days,
1,000 USDT wallet, 10×100 slots, `--fee` the only thing that changes:

| fee/side | round trip | trades | total profit | Sharpe | max DD |
|---|---|---:|---:|---:|---:|
| 0.000001 | ~0 | 2,777 | **+351.68%** | 3.90 | 2.55% |
| 0.001 (Freqle's charge) | 20 bps | 2,756 | +295.50% | 3.60 | 2.94% |
| 0.00175 (this repo's COVID regime) | 35 bps | 2,743 | +253.64% | 3.33 | 3.30% |

**The curve does not start at or below zero. It starts at +351.68% and falls gently.**
Linear extrapolation puts break-even at **~62.7 bps/side = ~125 bps round trip**, versus
this repo's measured 12.0–34.9 bps. **Cost was never this strategy's problem.**

Both prior 5m nulls in this repo (`PerpTrendBreakout`, `RegimeVolBreakout5m`) reported
gross ≈ 0. **They do not generalise to this family**, and that is a real correction to the
record: the "5m is always ~zero gross" pattern is not a property of 5m.

---

## 2. What I got wrong on the way, and said so

**(a) The trailing-stop artefact I asserted, then disproved.** From the first run's
exit-reason table, `trailing_stop_loss` fired 849 times at a **100% win rate**, +3.07%
average, 11-minute hold. I attributed that to `docs/backtesting.md:577`
("High happens first — adjusting stoploss") and wrote that ~3/4 of the headline was an
intra-candle-ordering artefact. **I tested it with `--timeframe-detail 1m` and it did not
collapse:** 455 trades/+62.98% → 467 trades/+64.00%, Sharpe 2.75 → 2.79. The 1m-detail
run is also rejected by the engine for 15m (`Detail timeframe must be smaller than
strategy timeframe`).

**The reasoning itself was wrong:** a trailing stop is by construction a move-to-breakeven
device, so it *always* exits profitable. A 100% win rate there is a tautology, not an
artefact. The magnitude (not the rate) was the thing to test, and it held up. **This
turned out to be a point in the engine's favour, and it is why the effect survived.**

**(b) "150 EMA columns / ~20 GB" was false.** `parameters.py:210-222`: `range` returns a
**1-item** list outside hyperopt mode, *"to avoid calculating 100ds of indicators."*
Measured: upstream and a slimmed copy are both 18 columns / 5.8 MB. I built the slim copy
on the false premise, proved equivalence, and then **deleted it** once the measurement
contradicted me.

**(c) The decisive one: my own block bootstrap was invalid, twice.** My first
dependence-adjusted entry-power number was **t = 2.81, p = 0.004**, which read as a
clean pass. It was wrong: the moving blocks ran over a **pair-major concatenation** of the
33 pairs' signals, which is not a time-ordered series, so the blocks straddled unrelated
instants and the dependence correction was destroyed. Sorting by time first gives
**t = 2.08, p = 0.019**. The naive version is t = 4.48. So the same quantity is
**4.48 / 2.08 / 1.11** depending on which dependence structure you assume, and only the
middle one is defensible. This is §3.1 of `AGENTS.md` happening a third time, to me.

---

## 3. The finding that matters: the exit model spends the entry

### 3.1 The upstream exit model, out-of-sample (2026, never seen by the selection)

| exit reason | exits | mean | total | win% |
|---|---:|---:|---:|---:|
| trailing_stop_loss | 24 | +2.815% | +67.57% | 100.0% |
| roi | 6 | +1.383% | +8.30% | 83.3% |
| **exit_signal** | **90** | **−0.416%** | **−37.48%** | **46.7%** |
| TOTAL | 120 | +0.320% | +38.39% | 59.2% |

t_naive 1.536 → **t_block 1.043, p = 0.161. Not significant.**

**75% of the exits lose money.** All profit came from 30 trailing/roi exits. This is the
identical finding this repo already recorded for `RegimeVolBreakout5m` — *"the exit model,
not the entry"* — now reproduced on a strategy from an entirely different source and
engine session.

### 3.2 The entry signal alone, dependence-adjusted

Conditional forward return of the entry minus the same pair's unconditional forward
return ("lift"), all 33 pairs, block bootstrap on the **time-sorted** signal sequence:

| window | horizon | n | lift | t_naive | **t_BLOCK** | **p** | after 20bps | after 35bps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| in-sample 2021-25 | 15m | 6,880 | +89.89 bps | 20.75 | 9.02 | 0.000 | +69.89 | +54.89 |
| in-sample | 1h | 6,880 | +154.80 bps | 24.22 | 9.87 | 0.000 | +134.80 | +119.80 |
| in-sample | 3h | 6,880 | +226.03 bps | 22.39 | 8.78 | 0.000 | +206.03 | +191.03 |
| **OOS 2026** | 15m | 443 | +29.02 bps | 4.09 | 1.86 | 0.039 | +9.02 | −5.98 |
| **OOS 2026** | **1h** | **443** | **+48.04 bps** | 4.48 | **2.08** | **0.019** | **+28.04** | **+13.04** |
| OOS 2026 | 3h | 443 | +22.62 bps | 1.83 | 0.92 | 0.219 | +2.62 | −12.38 |

**The 1h lift is real at the signal level and survives the worst measured cost.** It decays
69% from in-sample to out-of-sample — which is exactly the decay the backtest showed
(1.07% → 0.32% per trade), so the decay is in the **entry**, not the exit.

### 3.3 Replacing the exit with the measured horizon

`LeaderboardEntry1hHold` keeps the entry byte-for-byte and replaces only the exit with a
fixed 1h hold — the horizon the lift was measured at, not a tuned parameter. Trailing stop,
ROI ladder and the −35% stop are all disabled.

**Out-of-sample 2026, same 33 pairs, fee 0.001/side:**

| | upstream exit model | 1h hold | change |
|---|---:|---:|---:|
| trades | 120 | 120 | — |
| avg profit/trade | +0.320% | **+0.483%** | **+51%** |
| total profit | +3.84% | **+5.79%** | **+51%** |
| win rate | 59.2% | 51.7% | −7.5pp |
| max drawdown | 2.70% | **2.59%** | better |
| Sharpe (daily wallet) | 1.11 | 1.07 | ~flat |
| t_block | 1.043 | **1.110** | still not significant |

The per-trade mean **+0.483% matches the independently-measured 1h forward return
+0.4830% exactly** — the exit model was indeed the leak. But the win rate falls (the
trailing exit was donating free wins) and the portfolio t stays at ~1.1, because **96 of
443 signals were rejected by the 10-slot cap**, and the executed subset is not the
measured population.

---

## 4. Why this is still not deployable

1. **t = 2.08 is below this repo's bar.** The strategy is the maximum of a 5,330-strategy
   leaderboard, and I tried 3 horizons ⇒ ~16,000 effective trials. Deflating for that
   needs t ≈ 4.4, not 2.08. Bailey et al. 2016 (*JC*, peer-reviewed) is the citation: on a
   **random walk**, an 8,800-grid search produced IS Sharpe 1.27 / PSR 2.83 with
   **PBO 55%**.
2. **The portfolio-level t is 1.11, p = 0.138** on the series that would actually be
   traded. Signal-level and portfolio-level disagree because of the slot cap's selection
   effect, and the portfolio is what gets paid.
3. **120 trades in 9 months.** At the measured signal rate (~161/yr) the portfolio needs
   **~2.4 more years** to reach t = 2.0, and ~12 years to clear the fully-deflated bar.
   **State that now, not in two years.**
4. **The engine still has no slippage or impact model** (`docs/backtesting.md:562`). The
   35 bps used here is this repo's own measured book cost, not a simulated fill.
5. **The universe is survivorship-selected**: 7 of 33 pairs are late-listed (POL from
   2024-09-13, SEI 2023-08-15, SUI 2023-05-03, ARB 2023-03-23, APT 2022-10-19, OP
   2022-06-01, ICP 2021-05-11) — **8.7% of the window is simply absent.**

---

## 5. What survives as usable

- **The entry rule and its measured horizon.** A 1h hold on that entry beat the upstream
  exit model by 51% per trade on data the strategy was never selected on. That is a real,
  reproducible, documented improvement, and the decomposition is the generalisable lesson:
  *measure the entry's conditional lift separately, because a backtest cannot tell you
  whether the entry or the exit is carrying the P&L.*
- **The measurement scripts** (`tools/leaderboard/`): `coverage.py`, `test_causality.py`
  (truncation-based, this repo's own stronger-than-engine causality gate),
  `entry_power2.py`, `forward_stats.py`, `run_capped.ps1`.

---

## 6. Four engine traps found and fixed, worth keeping

1. **`custom_exit` is gated behind `use_exit_signal`** —
   `freqtrade/strategy/interface.py:1469` puts the `custom_exit` call *inside*
   `if self.use_exit_signal:`. Setting `use_exit_signal = False` to silence `exit_long`
   **silently disables `custom_exit` too**. Symptom: the strategy holds for **months**
   (avg duration 80 days) and leaves only via the stoploss. To use `custom_exit` alone
   you must leave `use_exit_signal = True` and make `populate_exit_trend` return nothing.
2. **A v2 strategy on a v3 engine produces ZERO trades and no error.** The most-cloned
   strategy on the leaderboard is `INTERFACE_VERSION = 2`; it had to be converted first.
3. **Freqtrade 2026.8 uses a flat datadir** (`idatahandler.py:354-371` — no exchange
   subdirectory). **All spot data in this repo is under `<datadir>/binance/` and is
   invisible to the engine**; `list-data` returns 0 pairs against 12 existing files.
4. **`strategy-updater` rewrote 10 of this repo's research strategies** (unconditional
   `write_text`, `strategyupdater.py:82`), despite `--strategy-path`. All 10 restored
   byte-identically from its own backup (`:70-77`).
