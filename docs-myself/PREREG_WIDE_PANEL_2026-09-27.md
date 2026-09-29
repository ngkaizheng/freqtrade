# PRE-REGISTRATION — the frozen rule on a wide perp panel, and the one regime filter

**Date frozen:** 2026-09-27, **before any wide-panel result is computed.**
**Author:** agent session, at the user's request to "go in the direction that can
make this work" and to "test using freqtrade's own backtest".
**Supersedes the execution plan in** `docs-myself/PREREG_1P5ATR_2026-09-27.md`
**only in its sample-size assumption.** That file's Gate 0 arithmetic stands: its
"untestable" branch was computed *at 9 symbols*. Widening the universe is a
**power fix for a frozen signal**, not a parameter change, and it is registered
here as such.

---

## 0. The one thing that was actually broken

The 4h signal's problem was never "the effect is too small to exist". It was
**that σ (per-trade dispersion) is a property of the trade, while n was measured
on 9 symbols.**

```
t = (m/σ) · sqrt(n_eff)
```

Measured: m/σ = 0.0294 (full sample, 1.0 ATR), n = 1,690, lag-1 AC = **−0.004**,
i.e. **the 4h trades are already effectively independent** (`phase3_effective_sample_size.csv`,
inflation factor 1.0). At independence, **every additional symbol is an
independent observation**, and t scales as `sqrt(N)`.

This is the opposite of the cross-sectional and carry lines in this repo, where
adding names bought almost nothing (§3.9: 5→200 names = **1.21×**). Here it
buys `sqrt(N)`, because trades — not a portfolio of correlated returns — are the
observation unit.

**Power target.** At 104 symbols ≈ 19,500 trades:

| bar | required m/σ |
|---|---:|
| t ≥ 2.0, no selection deflation | 0.0143 |
| **deflated, framing A (4.1954 / sqrt(n), 41,472 trials)** | **0.0300** |
| measured today, full sample @1.0 ATR | 0.0294 |
| × the 1.5 ATR gross gain (×1.29) | **0.0379** |

**So on a wide panel the frozen 1.5 ATR cell clears even the harsh deflated
bar — if, and only if, the effect generalises beyond the 9 majors.**
That is a real test with a real chance of a real answer. It is not a
guarantee, and a null here is a null.

## 1. Universe — frozen by rule, not by result

**All Binance USD-M USDT perpetuals with `onboardDate ≤ 2023-01-01` and status
TRADING at download time.** Measured 2026-09-27: **105 symbols.**

- **Exclude** `BTCDOMUSDT` (a dominance **index** contract, not a crypto price).
  → **104 symbols.**
- No liquidity filter, no volume screen, no ranking, no "top N". §3.25 rule 1
  forbids filtering a cross-section in place of weighting it.
- Symbols that 404 on download are **dropped and the drop is reported with its
  reason** — a silent drop is the §3.10 failure shape.

> **⚠ SURVIVORSHIP, DISCLOSED NOT CORRECTED.** `exchangeInfo` returns only
> currently-listed contracts; there is no public registry of delisted USD-M
> perps (§3.8). **Every number below is an upper bound.** Ammann et al. measure
> the equal-weighted bias at **62.19%/yr** against value-weighted **0.93%/yr**
> (§3.25). Mitigation is therefore **weighting, not filtering**:
> **inverse-vol weighted is the pre-registered primary; equal-weight is
> reported as the diagnostic only.**

## 2. Signal — frozen, unchanged from SHARK-01

- Entry: **relative volume ≥ 2.0** and **20-bar breakout**, per
  `shark_hunter.strategies.recipes.STRATEGIES["SHARK-01"]`.
- `atr_period = 14`, `r_multiple` as `DEFAULT_TARGET_R`, `time_stop_bars = 42`
  at 4h (~7 days), `use_time_stop = True`.
- Signal decided on bar `i−1` close, filled at bar `i` **open** — the engine's
  existing no-lookahead convention, preserved.
- `atr_stop = 1.5` (the cell frozen in `PREREG_1P5ATR_2026-09-27.md`).
- **No parameter search. No timeframe change. No new indicator.**

## 3. The regime filter — one, frozen, and it is the literature's one

**From** Kurth, Eisler, Rej & Bouchaud, arXiv:2607.01550 (**⚠ arXiv preprint,
not peer-reviewed**), App. D.1: *"the vast majority of PnL comes from periods of
**low volatility**… the post-2008 PnL collapse can be attributed to
**high-volatility days**."* This is the **only** regime filter in the entire
literature review with an empirical result behind it, and it is the only one
that raises gross edge **and** lowers cost at once — which §1c's `1/sqrt(q)` bar
shows is the only kind that can work. This repo's §1b cost table
(12.0 bps calm → 34.9 bps COVID) is exactly that gradient.

**Definition, frozen:**

```
vol42  = stdev of the last 42 four-hour log returns (7 days), annualised
vol365 = vol42 computed over a trailing 365-bar (1-year) window
TAKE the trade  ⟺  vol42 < median(vol42 over the trailing 365 bars)
```

- **Ex-ante**: uses only completed bars up to the signal bar. No lookahead.
- **Time-series, not cross-sectional**: computable per symbol, so a symbol that
  downloads late cannot change another symbol's filter state.
- Keeps ~50% of trades **by construction** — the hurdle is therefore the
  `f = 0.5` row of §1c: the kept trades need **+33% gross edge just to break
  even**, and **0.174R** to break even in total-return terms.

**Two cells, both reported, no selection between them:**

| cell | rule | filter |
|---|---|---|
| **A** | SHARK-01 @ 1.5 ATR | none |
| **B** | SHARK-01 @ 1.5 ATR | low-vol, as defined above |

Plus **two controls at 1.0 ATR** (A-1.0, B-1.0) so the filter's contribution
is separable from the stop-width contribution. **All four are reported whatever
the outcome. Picking the best one is forbidden and would void this file.**

## 4. Costs — measured per symbol, not a flat constant

`cost_R = round_trip_bps / (atr_stop × atr_pct × 10,000)`, so a flat bps
assumption is **not** neutral across a 104-name panel (§1b: the long tail is
1–3 orders of magnitude thinner than BTC).

1. **Per-symbol effective spread** via Roll on `aggTrades`, the method already
   built and validated in `tools/cross_section/measure_cost.py` and
   `tools/cost/measure_impact.py`, at a **calm date and a stress date**.
2. Round trip = 2 × effective spread + taker fee (0.050%/side, the exchange
   figure already verified in `SHORT_TERM_LEVERAGE_RESULT_2026-09-27.md` §7).
3. **Regime multiplier applied and disclosed**: the §1b calm→COVID spread is
   **2.9×**; the primary is the calm figure and a stress figure is reported
   beside it, never a mid-point.
4. **Funding is charged.** It cannot be omitted: at 0.01%/8h over a 42-bar
   (7-day) hold that is **0.21% of notional**, which for a 3.75% stop is
   **≈0.056R — larger than the entire 0.0428R edge.** Funding history is
   downloaded per symbol from Binance Vision `fundingRate`.
   *If a symbol's funding cannot be fetched, that symbol is DROPPED and the
   drop reported — an unfunded book is a book with a fabricated edge.*

## 5. The bar — fixed now

Statistic: dependence-adjusted t on per-trade R; IAT and effective N reported
next to the t (`AGENTS.md` §3.1). Bootstrapped over **trades**, not bars.

**PASS requires ALL of:**

| # | gate | threshold |
|---|---|---|
| G1 | dependence-adjusted t on net R, **full sample** | **≥ 2.0** |
| G2 | **Deflated Sharpe Ratio**, `trials ≥ 41,472` (the project's own search) | **significant at 95%** |
| G3 | **PBO (Probability of Backtest Overfitting) via CSCV** | **< 20%** |
| G4 | **per-symbol consistency** | **≥ 50% of symbols individually net-positive**, **and** the aggregate's sign not carried by the single best symbol (drop-best-symbol leaves it positive) |
| G5 | **positive in ≥ 3 of 4 chronological splits** (train 2023, validation 2024, oos 2025, final_unseen 2026) | the 2025-only failure of the previous reading |
| G6 | **survives the stress cost regime** (the 2.9× multiplier) | net R still > 0 |
| G7 | **gross-R at 1.5 ATR > gross-R at 1.0 ATR** | the payoff-geometry mechanism must be real, not just lower cost |

> **G4 is new and is the gate §3.3 said was missing** — that line's survivor was
> "three symbols out-earning a fourth" with *no cross-symbol gate at all*. It is
> the single most important addition here, because a wide panel is exactly where
> a 3-symbol effect hides.
>
> **G3 is non-negotiable.** Bailey, Borwein, López de Prado & Zhu 2016 (*JC*):
> on a **random walk** an 8,800-node grid yields IS Sharpe **1.27**, PSR
> **2.83** — yet **PBO = 55%** with **~53% of out-of-sample Sharpes negative.**
> A 104-name × 4-cell panel is a large search space and PBO is the statistic
> that prices it.

**Falsification.** If any of G1–G3 or G6 fails, the line is **closed** and the
answer to the user is reported plainly: the effect did not generalise, or did
not survive costs, or was a search artefact. **A negative result is a valid
result** (`AGENTS.md` §5).

## 6. What is forbidden

- Any filter other than the one in §3, or any variation of its window.
- Choosing among the four cells, or reporting a sub-period as the headline.
- Reporting the aggregate without the per-symbol distribution and the drop-best-symbol test.
- A flat bps cost across the panel.
- Equal-weight as the primary (§3.25 rule 1: the EW/VW bias ratio is **67×**).
- Re-running with different parameters, timeframes or symbols hoping for a
  better number — the exact error this apparatus exists to detect.

## 7. Cross-engine validation — the user's explicit request

The wide sweep runs on `shark_hunter.backtest.engine` (256 tests green). That
engine is the project's own, and §3.4 is the record of what happens when one
engine's numbers are believed without a second opinion.

**Therefore the same frozen rule is also implemented as a freqtrade strategy and
run through `freqtrade backtesting` on a held-out subset of the same symbols.**

Agreement is reported on: trade count, net R per trade, profit factor, and the
t-statistic. **The two engines are not reconciled by picking the friendlier
number.** A disagreement above 15% on net R is itself a reported finding and
halts the run until the cause is found.

## 8. Known limitations, stated before the result is believed

1. **Survivorship** — §1. Every figure is an upper bound.
2. **The era question is unresolved.** Kurth et al. show the speed–Sharpe
   relation **reversed sign after 2008**; HOP 2013's ladder rises with lookback
   (1.26→1.43→1.52) but predates this regime. There is **no contemporaneous
   measurement for crypto perps at 4h.** This design is not justified by
   citation; it is justified by being measured.
3. **Sepp & Lucic (⚠ preprint)** show the **sign** of net expectancy is
   span-invariant for short-memory alpha — but that is about signal **span**,
   not stop width. It is **not** a reason to expect this to fail; it is a reason
   not to expect slowing down to rescue it.
4. **The low-vol filter rests on a preprint.** Stated as such wherever it appears.
5. **McLean & Pontiff 58%** is an equities, cross-sectional, pre-2014 prior and
   says *"We do not study time series predictability."* It applies as a
   discount on expectations here, not as a measurement.
6. **A pass on a 104-name panel is a statement about a survivor universe
   aggregated with inverse-vol weights.** It is not a statement about a book
   you can trade at size. §1b's measured depth caps book notional at
   **$0.8M/day (0.2% band) to $3.9M/day (1% band)** for the thin side.
