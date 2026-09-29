# AMENDMENT 1 — a control arm, added because the 4.0-ATR result is confounded

**Date:** 2026-09-28, **written after the stop frontier ran and before the control
arm ran.** Disclosed here rather than edited into the original prereg silently.

---

## 1. The confound the stop frontier created

`PREREG_STOP_MULTIPLE_2026-09-28.md` varied the stop width with the 42-bar time
stop frozen. The exit mix says what happened:

| atr_stop | stop-out | reached 2R | **time stop** |
|---|---:|---:|---:|
| 1.5 | 64.2% | 27.6% | 7.9% |
| 2.5 | 46.9% | 16.7% | 35.9% |
| 4.0 | **31.4%** | 7.2% | **60.7%** |

**At 4.0 ATR the strategy is no longer a stop-and-target strategy — 61% of its
trades are closed by a 7-day clock.** So "widening the stop improved mean R from
−0.016 to +0.121" is, mechanically, at least partly the same statement as
"holding for 7 days improved mean R". Those are different claims and the design
as frozen cannot separate them.

**Worse, the dependence-adjusted t peaked at 2.5 and then FELL** (by-timestamp,
calm: 0.48 → 0.22; covid: 0.00 → −0.15) while the mean kept rising. Rising mean
with falling t means the dispersion is rising faster than the mean — the classic
signature of a trade that survives more often but loses more when it fails.

## 2. The control, frozen before it runs

**One arm. `atr_stop = 4.0`, everything identical, and the ENTRY SIGNAL
REPLACED BY A TIMING-DESTROYED ONE.**

```
real entry      : rvol(20) >= 2.0 AND close < prev20_low AND low_vol
control entry   : the SAME number of bars per pair, chosen pseudo-randomly
                  from a fixed seed, with no reference to price or volume
```

The frequency per pair is matched to the real signal's, so trade count,
holding time, exposure and clustering are all comparable. What is destroyed is
only the **timing**. If the control earns a comparable mean R, then the entire
stop-width improvement is a property of *being in the market for 7 days on a
panel that fell a median of 80.9%*, and the signal contributes nothing.

Implementation: a deterministic LCG seeded from a hash of the pair, so the
control is **reproducible bit-for-bit** and cannot be re-rolled until it looks
good. The draw is made once per bar index, not per run.

## 3. The gate — fixed now

| # | gate | threshold |
|---|---|---|
| C1 | the control's mean R at measured_covid is **not** >= 80% of the real 4.0-ATR arm's | if a timing-destroyed entry earns nearly as much, the signal is worth nothing |
| C2 | the real 4.0-ATR arm beats the control at **every** cost regime, not just one | a single-regime win is a regime coincidence |
| C3 | the by-timestamp t of the real arm exceeds the control's at every regime | significance measured against the control, not against zero |

**If C1 fails, the stop-width result is void**, whatever its P&L says, and the
honest conclusion becomes: *this 4h short signal has no content, and the entire
frontier was measuring a 7-day hold on a falling market.*

## 4. Forbidden

- Re-rolling the control's seed. One seed, declared in code, fixed.
- Adding a second control arm, or a randomised variant of any other parameter.
- Quoting the real arm without the control beside it.
