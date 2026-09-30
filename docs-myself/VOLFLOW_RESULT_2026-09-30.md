# §43 — F-1: A REAL INCREMENTAL VOLUME EFFECT, AND A REGIME TEST THAT REFUSES IT

**Date:** 2026-09-30 · **Prereg:** `docs-myself/PREREG_VOLFLOW_2026-09-30.md` (before any feature was computed)
**Tools:** `volflow_test.py` (features + Gate A/B), `volflow_by_regime.py` (the guard)
**Data:** 40/40 symbols, 4h, 2023-01-01 → 2026-08-31, 272,557 pooled observations
**Status: NO STRATEGY BUILT.** Gate B passed; the regime guard did not.

---

## 1. Why this line existed

§42's control table promoted it from a guess. `dVol_4` — the change in kline volume —
scored **t = +7.65**, the second strongest predictor measured anywhere in this project, and
it is **not in the closed registry**: entry #11 closed *taker* flow for the absence of L1/L2
data, which is a different data type. §42 also showed the OI line is a weaker echo of
information the books already hold, so the question became: **is volume *level* a third
source, or the same one again?**

## 2. The measurement instrument was wrong three times, and each wrong version looked like a finding

`incremental()` regressed the forward return on `[mom_4, dVol_4, candidate]`.

| v | what it did | what it printed |
|---|---|---|
| 1 | `t = beta/se`, iid SE | on `amihud` the design is near-singular, SE collapses, **t = 1.04e17**. **The gate took the largest \|t\|, so the gate PASSED ON THE ARTEFACT and named the worst feature in the table as the winner.** |
| 2 | "fix": test `mean(residual × regressor)` | **the normal equations force that to be exactly zero** — every t printed 0.00, and a real signal (`vol_z`, partial r 0.048) was reported as failing |
| 3 | Andrews–HAC covariance of the coefficients | condition numbers healthy (1–3) yet t in the hundreds, unexplained and therefore untrusted |

> **Three checks giving three different answers means the answer is to stop building bespoke
> statistics, not to try a fourth variant.** v4 therefore introduces **no new statistic**:
> it residualises both sides on the controls — the textbook partial correlation — and takes
> its significance from `ic_and_t`, the function `check_ic_t.py` had already validated on a
> null (4.3 % at |t| > 1.96), on autocorrelation (NW/naive 0.411) and for power.

**Guards added, because v1's failure was not the formula but the absence of any check that
the number was real:** standardise, report the condition number and refuse above 1e8, and
**refuse any |t| above 50**.

**A gate that accepts the largest number without asking whether it means anything is not a
gate** — that is the generalisable lesson, and it is worse here than the project's usual
instances because v1's artefact did not merely pass, it **won**.

## 3. Gate A — yes, there is something

| feature | h=4 | h=12 | h=24 |
|---|---|---|---|
| `dVol_12` | 0.0079 / 1.94 | **0.0319 / 8.21** | 0.0236 / 6.16 |
| `vol_z` | 0.0194 / 6.25 | 0.0320 / 6.81 | 0.0218 / 3.56 |
| `vol_trend` | 0.0200 / 7.64 | 0.0281 / 8.15 | 0.0245 / 6.82 |
| `rv42` | −0.0218 / −5.96 | −0.0290 / −5.05 | −0.0451 / −5.80 |
| `gk_vol` | −0.0208 / −6.22 | −0.0230 / −4.17 | −0.0351 / −4.80 |

**GATE A PASS** — best univariate `dVol_12` @ 12h, IC = +0.0319, NW-t = +8.21.

## 4. Gate B — the decisive one, and it also passed

Incremental over `[mom_4, dVol_4]`, partial correlation, Newey-West t:

| feature | h=4 | h=12 | h=24 |
|---|---|---|---|
| `dVol_12` | 1.11 / 0.0263 | **8.87 / 0.0354** | 7.61 / 0.0319 |
| `vol_z` | 4.49 / 0.0327 | 5.54 / **0.0475** | 2.71 / 0.0358 |
| `vol_trend` | 4.26 / 0.0292 | 6.91 / 0.0427 | 6.11 / 0.0394 |

**GATE B PASS.** *This is the first candidate in this project to pass an INCREMENTAL test
against controls that are themselves strong.* The mechanism is coherent: the controls are
4-bar price momentum and 4-bar volume **change**; what is left over is the volume **level**
relative to the symbol's own recent norm, and it is orthogonal to both.

**And the strength must be stated honestly: a partial r of 0.035–0.048 is the same order as
what the existing books already have** (`mom_4` IC 0.026). *This is a third source of
information, not a stronger one.*

## 5. ⚠ THE REGIME GUARD, WHICH IS WHY NO STRATEGY WAS BUILT

Section 41's rule: a result that wins only in the regime that selected it is one data point.
The same test, recomputed inside each calendar year:

| feature | 2023 (+198.6 %) | 2024 (+103.6 %) | 2025 (−56.8 %) | 2026 (−17.6 %) | |
|---|---:|---:|---:|---:|---|
| `dVol_12` | 2.78 ✓ | **−0.52 ✗** | 10.51 ✓ | 6.97 ✓ | 3/4 |
| `vol_z` | 5.73 ✓ | 6.63 ✓ | 3.09 ✓ | −2.95 ✓ | 4/4, **sign flips** |
| `vol_trend` | 3.47 ✓ | **−1.02 ✗** | 7.95 ✓ | 6.70 ✓ | 3/4 |

**10 of 12 cells hold. Two candidates fail outright in 2024 — the up year with the largest
sample (73,360 observations).** And the one candidate that holds in all four,
`vol_z`, has partial correlations **+0.074 / +0.100 / +0.045 / −0.020**: **significant in
magnitude everywhere, but the sign is regime-dependent.**

> "Sustained high volume → go long" would have worked in 2023, 2024 and 2025 and been
> **wrong in 2026**. **That is not a rule that diversifies. It is a bet on which regime
> arrives** — and it is precisely the kind of thing this project must not ship, because it
> is the delivered short book's own failure mode wearing a new feature.

## 6. Verdict

* **Gate A PASS, Gate B PASS, regime guard FAIL → NO STRATEGY BUILT.**
* **Tier 2 items D (volatility as a signal) and F (kline-volume flow) close on REGIME
  INSTABILITY, not on absence of signal.** That distinction is the point: the effect is
  real and measurable; **it is not stable enough in direction to trade.**
* **Nothing here invalidates the Gate B result.** A conditional association of 0.035–0.048
  genuinely exists. What fails is the step from "predicts" to "can be traded", and that step
  is exactly what §41 exists to police.

## 7. What the next round must NOT do

* **Not** build a strategy on `vol_z`. The sign flip is disqualifying, and a backtest over
  2023-2026 would hide it by construction because those are the years it was selected on.
* **Not** re-cut the regimes to make the test pass. The preregistration's power appendix
  already says a Gate B FAIL is INCONCLUSIVE; here Gate B **passed** and the guard failed,
  which is the other case and the more serious one.
* **Not** sweep features until one happens to be uniform in all four years. Twelve features
  were fixed in advance; that is the whole protection.

## 8. Where this leaves the objective

Tested and closed on measurements since the gap analysis: **OI (Gate 3, comparative) ·
kline volume flow (regime instability) · volatility as a signal (regime instability).**

**The 4h price/volume/volatility feature space is now exhausted for this universe** — the
three strongest things in it are `mom_4` (already the short book), `dVol_4` and the
volume-level family, and none of the volume-level family is tradeable.

**The next round must therefore go to a mechanism with a DIFFERENT information source, not
another transform of the same bars.** The registry's remaining untestable-by-construction
entries — true order flow (needs L1/L2), options VRP (no options data) — are not reachable
with what is on disk, and re-opening them requires either the data or a new venue.
