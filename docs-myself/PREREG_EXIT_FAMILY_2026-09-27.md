# PREREG — Exit-family study on a frozen `RegimeVolBreakout5m` entry

**Status: FROZEN 2026-09-27, BEFORE any arm of this study was run.**

The only result that existed when this was written is the **baseline**
(`docs-myself/RUNBOOK-regime-vol-breakout-5m.md` §4), which is a
control-group input, not a candidate. No exit variant had been run on any
window when these arms, this window, and these decision rules were fixed.

---

## 1. The question, and why it is a real question

The baseline established one thing and one thing only:

> The **entry + exit combination** has no gross edge. Gross (fee ≈ 0) is
> **−1.51%, PF 0.95** over 9,236 trades.

It did **not** establish that the entry is worthless. The exit decomposition
showed a strong asymmetry:

| exit path | trades | share | net USDT |
|---|---:|---:|---:|
| allowed to run (`tp_1_8pct`, `time_stop`) | 2,117 | 22.9% | **+2,076** |
| cut short (`trailing_stop_loss`, `exit_signal`, `stop_loss`) | 7,119 | 77.1% | **−3,309** |

So: **the subset of trades that were permitted to develop made money; the
majority that were cut early lost it.** Two candidate explanations, and this
study cannot distinguish them:

- **H_a — the entry is dead.** A 5m breakout with no gross edge, period.
- **H_b — the exit is the binding constraint.** The entry carries edge that a
  3×ATR stop firing on 52.6% of trades and an `ema_21`/`ema_50_1h` exit winning
  1.3% of the time destroys before it can be expressed.

`RESEARCH_STATE.md` §1 already closed 5m breakout *as previously specified*
(`PerpTrendBreakout`, gross ≈ 0). H_a is the prior. **H_b has never been
tested**, because every prior 5m line used a different exit model. This study
tests H_b and is designed to return a null if H_a is true.

---

## 2. Frozen vs varied

**FROZEN — the entry, byte-for-byte.** The signal code from
`RegimeVolBreakout5m.populate_indicators` / `populate_entry_trend` is reused
unchanged: the 1h EMA50/200 + ADX regime, the 5m EMA21/55 trend filter, the
24-bar Donchian breakout with `shift(1)`, `volume_expansion` (1.30×),
`vol_expansion` (1.05×), ADX > 18, the RSI bands, `body_atr ≥ 0.30`,
`volume > 0`, and the `data_valid` guard.

**No entry parameter is tuned, in this study or any arm of it.** The
`enter_long` / `enter_short` columns are identical across every arm and on every
window. This is what makes the arms paired.

**VARIED — the exit only.**

---

## 3. Arms

All arms share one definition of **R**, fixed in advance to avoid the repo's
already-paid-for footgun (`RESEARCH_STATE.md` §1, the `stoploss`/leverage row):
**R is the price distance from entry to the arm's own stop, frozen at the entry
bar.** A trailing stop has no frozen R, which is exactly why the baseline's
3×ATR trail is the thing under test and not a candidate.

R = |entry_price − stop_price| / entry_price, evaluated on the **entry bar's**
ATR, with a floor of 0.2% so a dead-vol bar cannot produce an absurd R.

| arm | stop | target | time stop | `exit_signal` |
|---|---|---|---|---|
| **X0** *(control)* | 3×ATR trail, re-anchored each bar + 0.9% static | +1.8% | 90 min | on |
| **X1** | 1.5×ATR, **frozen at entry** | 3R | 90 min | on |
| **X2** | 1.5×ATR, **frozen at entry** | 3R | 180 min | on |
| **X3** | 2.5×ATR, **frozen at entry** | 2R | 180 min | on |
| **X4** | 2.5×ATR, **frozen at entry** | 2R | 180 min | **off** |
| **X5** | none | none | 18 bars fixed | **off** |

**Eight arms, including the control.** Chosen to decompose the baseline's two
loss-making exit paths rather than to search a grid:

- **X1 vs X0** — isolates *stop geometry* (frozen wide vs re-anchored tight).
- **X2 vs X1** — isolates *time* (180 vs 90 min) at fixed stop and target.
- **X4 vs X3** — isolates *the `exit_signal` path*, the one that won 1.3%.
- **X5** — the null-of-last-resort: pure entry, no exit logic at all. If even
  a bare fixed 18-bar hold is not profitable, the entry is dead and no exit can
  rescue it.
- **X3 vs X1** — the direction of the `cost_R` law. `cost_R = round_trip_bps /
  (stop_multiple × atr_pct × 10,000)`, so a wider stop **divides cost per R**
  by the stop multiple. The 4h line measured 1.5 ATR strictly better than 1.0
  ATR (net R +0.1385 → +0.2270); this is the 5m test of the same effect.

**`X1`/`X2` (3R) vs `X3`/`X4` (2R)** deliberately spans the 2R–3R range the 4h
payoff frontier published, where 4.0R collapsed because the target became
unreachable inside the time stop. 3R at a 1.5×ATR stop is inside that failure
mode and is expected to be the weakest of the four.

---

## 4. Windows

| window | dates | role | status |
|---|---|---|---|
| **FRESH** | **2025-11-19 → 2026-09-26** | **the test** | **never seen** — the baseline ended 2025-11-18 |
| OLD | 2023-01-01 → 2025-11-18 | diagnostic only | **contaminated** — this is where the exit failure was found |

**314 days.** The baseline run stopped at 2025-11-18; the data on disk ran out
there and only reached 2026-09-26 on the funding/mark series. The 5m OHLCV has
been extended forward for this study.

> **This is the load-bearing honesty of the design.** Every exit variant is run
> on FRESH and **only FRESH**. The OLD window is reported alongside purely as a
> diagnostic, is labelled contaminated everywhere it appears, and **may not be
> used to select, rank, or justify an arm.** If FRESH and OLD disagree, that
> disagreement is a reported finding, not a reason to prefer either.

---

## 5. Metrics, decided in advance

**Primary statistic: mean net R per trade, per arm, on FRESH.**

R is normalised by each arm's own frozen stop, so arms are comparable even
though their price risk differs. This is the repo's `AGENTS.md` §3 rule
("report in units of risk, not cash") applied to a design where cash would be
actively misleading.

**Secondary, all reported:**

1. Profit factor, net of cost.
2. **Cost decomposition** — gross R (fee ≈ 0) and net R, so the cost-bound vs
   signal-bound question is answered directly rather than inferred. *This is
   the §3.32 rule: never infer a gross number from a net one.*
3. Paired ΔR vs X0 on the **same trades** (McNemar-style: same entries, different
   exits).
4. Break-even cost per arm, in bps: the round-trip fee at which mean net R = 0.

**Cost assumption.** 6 bps per side = **12 bps round trip**, the same figure the
baseline used, **plus real funding**, which is charged automatically from the
1h funding_rate/mark files present for all 8 pairs. Cost is *not* varied in this
study; the cost sensitivity is `SHORT_TERM_LEVERAGE_RESULT`'s existing grid and
is not reopened. **If an arm is cost-bound rather than signal-bound, that is
reported by the gross/net split and is a distinct verdict from "no edge".**

---

## 6. Decision rule, fixed in advance

1. **Holm–Bonferroni across the 8 arms** on the primary statistic, at
   **t = 2.0** on the dependence-adjusted statistic. `n_eff = n / IAT`, with IAT
   estimated from the arm's own return series **sorted by entry time** — the
   ordering bug in `PAYOFF_FUNDING_LONG_2026-09-27` made t look 4.2× too large
   and is asserted, not assumed.
2. **A cell is a candidate only if:**
   - mean **net** R > 0, and
   - the Holm-adjusted statistic clears t = 2.0, and
   - it is **positive in ≥ 2 of 3 chronological sub-splits** of FRESH.
3. **Null across all 8 arms ⇒ the entry is dead** (`H_a`). The study then closes,
   and per `AGENTS.md` §1a no further exit search is run on it. The 8 arms are
   8 trials, not a continuum; "we tried some exits" is not a licence to try more.
4. **A candidate is NOT a pass.** It is a lead that owes a forward test on data
   after 2026-09-26, and the required forward duration is computed and reported
   **with the result**, not later.
5. **The full frontier is published.** All 8 arms, every metric, in the report.
   The best cell is never quoted alone.

---

## 7. Power, checked before committing (AGENTS.md §1a)

At the baseline's 8.78 trades/day, FRESH yields **≈ 2,757 trades**, identical
across arms (paired design).

| σ_R | IAT=4 | IAT=8 | IAT=16 | IAT=32 |
|---:|---:|---:|---:|---:|
| 0.6 | 0.046R | 0.065R | 0.091R | 0.129R |
| 0.8 | 0.061R | 0.086R | 0.122R | 0.172R |
| 1.0 | 0.076R | 0.108R | 0.152R | 0.215R |
| 1.5 | 0.114R | 0.162R | 0.229R | 0.323R |

MDE = minimum detectable |mean net R| at t = 2. **The hurdle to clear is the 5m
`cost_R` of 0.62–0.75R** — the gross mean R must exceed that just to break even.

**The worst cell (0.323R) is below the hurdle (0.75R).** The design can separate
edge from cost-bound across the entire assumption grid, so it can conclude.

> This is the opposite situation to `PREREG_1P5ATR_2026-09-27`, which needed
> 9,060 trades / 19.6 years and was correctly not run. **A 314-day window is
> ample here because the effect being tested is large (0.75R) and the dispersion
> is small — not because the window is long.** If a later arm is proposed on a
> 1d or 4h timeframe, this calculation does not transfer and must be redone.

---

## 8. What would falsify this study's own framing

Stated so it cannot be discovered after the fact:

- If **X5** (no exit logic, fixed 18 bars) is the best arm, the result is not
  "the exit matters" — it is "the exit logic is all cost", and H_b is
  **rejected**.
- If every arm is cost-bound (gross > 0, net < 0), the verdict is
  **"right shape, wrong timescale"** — the 5m cost law, not a dead signal —
  and that is a *different* finding from a gross null.
- If arms disagree in sign between FRESH and OLD, the exit geometry is
  **regime-dependent**, and no single arm is a result.

---

## 9. Deviations

Any departure from this document must be recorded **here, with the number that
was already seen**, before the affected run. Amendments made after seeing
results are disclosure, not pre-registration.

### Amendment A — 2026-09-27, two code bugs; **the entire first run is VOID**

Disclosed with the numbers already seen. The first execution of all six arms on
the FRESH window produced:

| arm | trades | net | PF | what actually happened |
|---|---:|---:|---:|---|
| X0 | 2,662 | −4.07% | 0.58 | correct — this is the control and it reproduced the baseline's shape |
| X1 | 2,440 | −3.34% | 0.66 | **ran on a −10% backstop; no stop, no target** |
| X2 | 2,294 | −3.34% | 0.64 | **same; byte-identical to X3** |
| X3 | 2,294 | −3.34% | 0.64 | **same** |
| X4 | **8** | +0.98% | 4.24 | **custom_exit disabled entirely** |
| X5 | — | — | — | voided with the rest |

**Bug 1 — `use_exit_signal` is not a safe switch for the signal rule.**
`IStrategy._get_exit_trade_type` (`interface.py:1469`) evaluates `custom_exit`
**only inside** `if self.use_exit_signal:`. Setting it False to disable the ema
exit signal therefore also disables the take-profit and the time stop, leaving
the stoploss as the only exit. X4's 8 trades in 312 days is that bug, and
**"8 trades, PF 4.24, +0.98%" is exactly the shape of a false positive** — it
would have read as the best arm in the study. Fixed: `use_exit_signal` stays
True on every arm and the `sig_off` arms emit zeros from
`populate_exit_trend` instead, so `exit_` is None and control falls through to
`custom_exit`.

**Bug 2 — `pd.Timestamp.floor("5m")` raises on pandas 3.** `'m' is no longer
supported` (ambiguous: minutes vs milliseconds); only `"5min"` parses.
`ShortBreakout4h` floors on `"4h"` and never hit this, so the pattern was copied
into a 5m strategy without the hazard being visible. Consequences, in order:

1. `entry_atr` raised, was caught by a local `except (…, ValueError)`, returned
   `None`;
2. `frozen_stop_price` → `None`, so `custom_stoploss` returned `None`;
3. freqtrade's `strategy_safe_wrapper(…, supress_error=True)` covered the rest;
4. **the frozen stop was never set, and the 2R/3R target was silently disabled
   too**, because `r_unit()` calls the same function.

Every frozen-ATR arm therefore ran on the class-level `−10%` backstop. The tell
was `stop_loss_abs / open_rate = 1.100` in the export, and the tell that should
have stopped it sooner was **X2 and X3 being byte-identical** — two arms with
different stops and different targets cannot produce the same 2,294 trades
unless neither stop nor target is reachable.

**Three layers of silence around one bug**, and the backtest still printed a
confident table. Fixed by using `freqtrade.exchange.timeframe_to_prev_date`
(the canonical helper, parses `"5m"`), by re-raising rather than swallowing a
frequency error, and by adding `tools/verify_exit_study.py`, a regression gate
that **asserts the realised stop distance is not the backstop**. An arm whose
realised stop equals the class `stoploss` now fails the build.

**Neither amendment changes a preregistered arm, window, metric or decision
rule.** They are corrections that make the code do what §§2–5 already said it
would. X0 was not re-run to a different result and its agreement with the
baseline is retained as evidence the fix did not disturb the control.

