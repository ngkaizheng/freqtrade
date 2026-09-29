# Findings: Power Analysis — Correcting My Own Published Number

Run 2026-09-19. Scripts: `tools/power_analysis.py`,
`tools/power_autocorr_check.py`, `tools/power_crosscheck_resolve.py`,
`tools/power_which_is_right.py`.

**This corrects a number I have quoted repeatedly in docs and in conversation.**

---

## The claim I kept making

Throughout rounds 2–9 I wrote, in `FINAL-DECISION.md`, `LESSONS.md`,
`FORWARD-PROTOCOL.md` and in chat:

> "To detect a **+0.17 Sharpe** edge at 80% power needs **~271 years**."

## What was wrong with it

That formula, `n ≈ (2.8/SR)²`, tests an **absolute Sharpe against zero**. The
claim here is entirely different: the **rule beats a matched flat control**. That
is a **paired** comparison of two series driven by the *same* underlying returns,
so the **difference** is far less noisy than either level.

| statistic | value |
|---|---:|
| observed Sharpe(rule) | 1.451 |
| observed Sharpe(flat) | 1.265 |
| edge (the actual claim) | 0.187 |
| **naive absolute formula** | **225 years** |

I had been quoting the wrong statistic's requirement.

## The correct calculation

Work on the **paired excess series** (`rule_net − flat_net`, already net of costs):

| | value |
|---|---:|
| mean excess daily | +0.000419 (**+15.31%** annualised) |
| sd excess daily | 0.009802 |
| SE of the mean | 0.000134 |
| **t-stat on the mean** | **3.12** |

Requirement for 80% power at 95% confidence: **11.7 years** (vs 225).

## Then autocorrelation made it longer again

The excess series is not iid — the rule holds positions for weeks, so returns
overlap.

| lag | ρ | t |
|---:|---:|---:|
| 2 | +0.0281 | +2.05 |
| 4 | +0.0573 | +4.18 |
| 6 | +0.0637 | +4.64 |
| 13 | +0.0326 | +2.38 |
| 20 | +0.0511 | +3.72 |

* sum of ρ over lags 1–20: **+0.2783**, t = **4.54**
* **Ljung-Box Q(20) = 77.3** (critical ~31.4 at 5%) → **autocorrelation is real**
* variance inflation factor: **1.556**
* effective sample: 5,312 nominal days → **3,415 effective (0.64×)**

Corrected requirement: **~18 years**.

## Two methods disagreed, and I resolved it rather than averaging

| method | implied requirement |
|---|---:|
| analytic + autocorrelation inflation | **~18 years** |
| non-overlapping blocks (0.5–2.9y) | ~5 years |

They disagreed **in direction**, so one had to be wrong:

* the **overlapping**-block version was invalid at large block sizes — 800 windows
  over ~5 independent blocks makes sd(mean) far too small (that figure was ~4–9y)
* the **non-overlapping** version is valid but has only 5–29 samples
* the decisive test was on the autocorrelations themselves: **5/20 lags
  individually significant**, and Ljung-Box confirms joint significance

**Conclusion: autocorrelation is real → the ~18-year figure is the
better-supported one.** The ~5-year block estimate understates the need.

## Corrected statement of my claims

| claim | status |
|---|---|
| "~271 years" | ❌ **WRONG** — wrong statistic (absolute vs paired). Overstated by ~15×. |
| "~12 years" | ⚠️ right statistic, ignored autocorrelation |
| **"~10–20 years"** | ✅ **best estimate**, ~18y with inflation applied |

## What this changes — and what it does not

**Does not change any decision.** 5, 12, or 18 years are all far beyond a usable
forward window. The forward test still cannot settle the edge; its value remains
**Question A (implementation fidelity)**, which resolves in weeks and needs no
power argument.

**Does change my credibility on the number.** I quoted an overstated figure in
seven documents and repeatedly in conversation. The direction of my more recent
correction was right; its magnitude was still wrong.

---

## Meta-lesson: diminishing returns

I spent four scripts resolving a quantity that **changes no decision**. Once every
candidate estimate exceeded ~5 years, the practical answer ("cannot settle it
forward") was already fixed.

That is worth recording as its own lesson: **precision on an irrelevant
quantity is not progress.** The right move is to establish the order of magnitude,
confirm it does not change the decision, and stop.

---

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools\power_analysis.py            # paired vs absolute
.\.venv\Scripts\python.exe tools\power_autocorr_check.py      # inflation
.\.venv\Scripts\python.exe tools\power_crosscheck_resolve.py  # block cross-check
.\.venv\Scripts\python.exe tools\power_which_is_right.py      # Ljung-Box verdict
```
