# PRE-REGISTRATION — the stop multiple: the one lever the cost law names and the panel never pulled

**Date frozen:** 2026-09-28, **before any rung of this frontier was run.**

---

## 0. Why this parameter, and why now

`RESEARCH_STATE.md` §1c states the identity this repository keeps re-deriving:

```
cost_R = round_trip_bps / (stop_multiple × atr_pct × 1e4)
```

**The stop multiple is in the denominator of the cost.** Everything else in that
formula is a property of the market; the multiple is the only term a strategy
chooses. Halving it halves the cost paid per unit of risk — *with the signal
completely unchanged*.

**And it was never swept.** `PREREG_WIDE_PANEL_2026-09-27.md` §2 froze
`atr_stop = 1.5` and gate G7 compared only **1.0 against 1.5** (gross at 1.5 was
higher — PASS). 2.5 and 4.0 have never been run on this signal, in either engine.

The exit decomposition says what the 1.5 ATR stop has been doing:

| exit | trades | share |
|---|---:|---:|
| `target_2r` | 307 | 27.6% |
| `time_stop` | 88 | 7.9% |
| **stop** | **713** | **64.5%** |

**Roughly two trades in three die on the stop.** That is the signature the
project has already named once — `PerpTrendSlow` found *"111 of 170 trades were
stop-losses, 0 of them profitable"* and called the 3-ATR-on-1h stop *"inside the
noise band"*. A stop that is hit 65% of the time is, mechanically, a stop that
is too close: it is being hit by the same bar-to-bar wiggle that generated the
entry signal in the first place.

## 1. Hypothesis

**H_a.** The 64.5% stop-out rate is caused by a stop placed **inside the noise
band**, not by a bad signal. A stop at 2.5–4.0 × ATR should cut the stop-out
rate materially while preserving the entry's gross edge.

**H_b.** Because `cost_R ∝ 1 / stop_multiple`, widening the stop from 1.5 to 4.0
ATR cuts the cost per unit of risk by **2.7×** — at measured_calm that is
roughly 0.061R → 0.023R. If the cost is the binding constraint, mean net R rises.

**H_c (the falsifier, stated so it cannot be quietly dropped).** The target-R
frontier (`PERP_SHORT_4H_RESULT_2026-09-28.md` §5.1) already showed that **exit
geometry does not rescue this signal**: removing the profit target entirely still
left mean R at −0.0065. If stop width behaves the same way — mean R flat while
the shape changes — then **H_c wins and the line is closed for a third and final
time.**

## 2. What is frozen, and what varies

**Frozen, byte-identical to `PerpShort4h`:** the entry (rvol(20) ≥ 2.0, 20-bar
Donchian breakdown), the low-volatility regime filter and both its windows, the
universe (all 104 panel symbols), the time stop (42 bars), the costs, the
1x sizing, and the **risk per trade (1% of equity)**.

**One parameter varies — a published frontier, never a chosen cell:**

```
atr_stop ∈ {1.0, 1.5 (frozen baseline), 2.5, 4.0}
```

The target stays at **2R of the entry-bar stop distance**, i.e. it scales with
the stop. That is the frozen rule's own definition, generalised; it is not a
second parameter moving at the same time.

> **Sizing needs no change and that is deliberate.** `custom_stake_amount`
> already sizes `risk_per_trade × equity / (atr_stop × atr_pct)`, so a wider
> stop automatically produces a **smaller position for the same dollar risk**.
> The comparison is therefore genuinely risk-matched, and the wider-stop arm is
> not accidentally a bigger-position arm.

**The whole curve is published. Choosing a rung is forbidden** — that is the
maximum-of-4 construction this apparatus exists to catch, and the target-R
frontier is the standing example of doing it correctly (best cell t = 0.10).

## 3. The gate — fixed now

| # | gate | threshold |
|---|---|---|
| S1 | the curve has **interior structure** — not monotone to the edge of the grid, and not flat | flat = the stop is not the constraint (H_c wins) |
| S2 | at the best rung, dependence-adjusted t on net R at **measured_covid** | **≥ 2.0**, **no deflation for the 4-rung search** |
| S3 | mean R > 0 at measured_covid at that rung | |
| S4 | ≥ 50% of symbols individually net-positive | |
| S5 | positive in ≥ 3 of 4 calendar years | |
| S6 | the best rung is also positive at **measured_calm** and at engine-default | a rung that only works when slippage is assumed away is not a result |
| S7 | **the stop-out rate actually falls**, and by roughly what H_a predicts | otherwise H_a is false regardless of what the P&L says |

> S7 is the mechanistic gate, and it is the reason this design is not just
> another parameter sweep: **it can fail while the P&L looks good.** A rung that
> makes money without changing the stop-out rate has not done what the hypothesis
> said it would, and that has to be visible.

## 4. What a pass would and would not mean

- **A pass is still in-sample**, and the favourable direction of this parameter
  was already visible in G7 (1.5 beat 1.0) before this file existed. The whole
  curve is reported precisely for that reason.
- **It would not reopen the 104-symbol G1 failure on its own.** It would say the
  stop was the constraint, which is a different claim from "there is an edge".
- **A pass here and a pass on the liquidity ladder would be two independent
  levers both pointing at COST.** If both land, the honest summary is
  *"this signal is real but too expensive at 1.5 ATR on 103 contracts"*, and the
  deployable object is a **cost-engineered** version, not a validated alpha.

## 5. Forbidden

- Quoting a single rung.
- Varying the target, the time stop, the regime filter, or the universe in this
  design. The target is pinned at 2R of the entry stop by construction.
- Any hyperopt.
- Re-opening this with a second stop sweep if it fails.
