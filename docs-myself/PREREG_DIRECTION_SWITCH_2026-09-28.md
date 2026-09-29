# PRE-REGISTRATION — a direction switch, because the deliverable is short-only and 2023 cost 40%

**Date frozen:** 2026-09-28, **before any run of this design.**
**Nature of this design: POST-HOC.** The weakness being addressed
(2023 returned **−40.5%** because crypto rose and the book was short) was
**known before this file was written.** That is stated here, not hidden, and
§5 says what it costs the conclusion.

---

## 1. The problem being addressed

`PerpShort4hDeploy` is the delivered artefact. Its single largest risk is not
its drawdown — it is that it is **structurally short-only in a market that
sometimes goes up for a year**:

| year | panel | the book |
|---|---:|---:|
| 2023 | **+62.3% annualised** | **−40.5%** |
| 2024 | +12.7% | +54.4% |
| 2025 | −125.6% | +70.2% |
| 2026 | −73.8% | −9.5% |

A user who runs this through a crypto bull market watches it bleed for quarters.
**That is a defect in the product, not a market risk to be accepted**, because the
same signal machinery exists on the long side and the project's 4-year sample
contains a year in which the long side would have been the right side.

## 2. What is frozen, and what is not

**Frozen (unchanged from the delivered strategy):**
- the entry signal — relative volume ≥ 2.0, 20-bar Donchian, low-volatility
  regime filter, on the **4h** timeframe;
- **stop 4.0 × ATR at the entry bar** (the delivered value, NOT re-tuned — the
  stop frontier was preregistered as one-shot and §5 of that prereg forbids a
  second sweep, and that applies here too);
- **target 2R**, **time stop 42 bars**;
- 1x, 1% risk per trade, 24 slots, the drawdown circuit breaker;
- costs: the measured 12.0 / 22.8 / 34.9 bps round trip.

**One thing varies: the direction, chosen by a regime rule.**

```
regime_t  =  1  if  equal-weight panel close  >  its own 200-bar SMA   (4h, ~33 days)
          =  0  otherwise

entry = LONG  the 20-bar breakout UP   and regime_t == 1
entry = SHORT the 20-bar breakdown     and regime_t == 0
```

**Why 200 bars and not something tuned:** 200 × 4h = 33 days. It is the
shortest window that is unambiguously a "trend" rather than a swing, it is the
value the panel's own `P = (1−Φ⁻¹(r))⁻¹` construction in He et al. implicitly
treats as slow relative to the 4h trade, and **it is fixed before the run and
will not be varied.** A window search here would be exactly the search this
apparatus exists to refuse.

**This is NOT the closed `btc_regime_filter`.** That line
(`RESEARCH_STATE.md` §1, 2,873 of 5,330 community strategies use it) *filtered*
a fixed-direction strategy by market regime, and Hurst/Ooi/Pedersen (2017, JPM)
tested prospective regime *timing* and found it null. **This does the opposite:
it reads the regime rather than predicting it, and it uses the regime to choose
the direction rather than to suppress trades.** Those are different objects and
the earlier null does not decide this one — which is exactly why the two results
must be reported next to each other and not merged.

## 3. The gate — fixed now

| # | gate | threshold |
|---|---|---|
| T1 | **2023 must improve.** That is the whole point of the design | 2023 return > −40.5%, and the panel rose 62.3% annualised that year |
| T2 | **2024 and 2025 must NOT collapse.** A switch that wins 2023 by giving up the bull-catch years is not a fix | each stays positive |
| T3 | mean net R at measured_covid > 0 | |
| T4 | dependence-adjusted t at measured_covid | **≥ 1.0**, NOT the 2.0 used elsewhere. The bar is deliberately lower here and the reason is stated: this design is post-hoc, so it is a **lead**, and a 2.0 bar on a post-hoc design would be decoration |
| T5 | ≥ 3 of 4 calendar years positive (the un-broken short-only book manages 2) | |
| T6 | still beats the unconditional same-direction book, per `beta_check.py` | both directions, so the long-leg benchmark is "always long the panel" |

**T4's bar is a concession and is labelled as one.** The delivered book has
t = −0.15 on the strictest measure. A post-hoc variant reaching t ≥ 1.0 is
**not** confirmation of anything; it is a reason to spend a forward period on it.

## 4. Falsification

If T1 or T2 or T3 fails, the switch is **not** adopted and the short-only
deliverable stands unchanged. A design that only helps in 2023 has replaced a
timing tool with a different timing tool and has made the product worse, because
it has added a component that only works in one regime.

## 5. What a pass would NOT mean — read this before believing a number

- **The design was written after seeing 2023.** The regime rule's window was
  chosen to be defensible, not because it was swept — but the *decision to
  build a switch at all* came from the result. **Any winning cell here is
  in-sample by construction.**
- **It cannot confirm the underlying signal.** The market-neutralised excess of
  the short leg is indistinguishable from zero; adding a long leg does not fix
  that, it only stops the book from being wrong in one direction.
- **It adds a component.** A two-sided book has two sets of failure modes, and
  the long leg's cost/impact profile is not measured by the panel's per-symbol
  work, which was all short.
- **T4's bar is 1.0, not 2.0**, and that difference must survive into any
  summary of this work. A result quoted without it is a misquote.

## 6. Forbidden

- Varying the regime window, the SMA length, or the panel composition.
- Re-tuning the stop, the target, or the time stop.
- Quoting T4 without the "1.0 not 2.0, and this is post-hoc" caveat.
- Reporting only the years that improved.
