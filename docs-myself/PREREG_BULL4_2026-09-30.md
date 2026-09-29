# PREREG — B-4: EXTEND THE CHANDELIER, AND MEASURE ITS ASYMPTOTE

**Written:** 2026-09-30, before any B-4 backtest. Follows `PREREG_BULL3_2026-09-30.md` (B-3).

---

## 1. What B-3 left open, in its own words

C4 (**chandelier 6.0**) is the first arm in this project to pass the **second half** of the
bar — 245.5 % of the matched-exposure benchmark in 2023, 357.3 % in 2024. It was **not
promoted**, for three reasons, all of them about where it sits rather than what it is:

1. **It is the boundary cell.** 6.0 is the widest chandelier tested. §20c: a best value at
   the edge is a direction, not a peak.
2. **The curve is non-monotone** — 15.81 → 45.47 → **32.48** → 71.38 — so noise and signal
   are not yet separable.
3. **The mechanism is suspicious in a specific way.** A 6-ATR chandelier is a very loose
   stop, so a breakout entry with it converges on **buy-and-hold with a crash exit**, which
   is exactly what the matched-exposure benchmark already measures. The tell: in 2025 the
   panel fell **−56.8 %** and C4 made **exactly 0.0 %**, against A1's +17.9 %.

## 2. The decision rule, fixed now, before the run

> **If capture climbs and then flattens toward the 100 % buy-and-hold asymptote, C4's "edge"
> was never an edge and the family is answered. If capture peaks and falls, 6.0 is real.**

**"Flattens toward 100 %" needs a definition, or the rule is unfalsifiable.** It is defined
here as: **the last three rungs of the curve have a capture spread under 25 pp, and the
highest rung's capture is below 200 %.** Under that definition, a peak-and-fall shape
decides promotion and a plateau-to-asymptote shape ends the family.

## 3. The arms — one curve, extended, plus its endpoints

Same entry (frozen breakout mirror), same `risk_per_trade` 0.5 %, same breaker 0.20.
**Only `chandelier_atr` moves.**

| arm | `chandelier_atr` | what it is for |
|---|---:|---|
| C5 | **8.0** | the immediate extension; is 6.0 a peak? |
| C6 | **10.0** | the far side of a peak, if there is one |
| C7 | **12.0** | the flatness test |
| **X1** | **20.0** | **ASYMPTOTE PROBE** — a stop this wide should never bind |
| **X2** | **50.0** | **the pure limit** — essentially buy-and-hold from the first entry |

**B0 control as the gate, as always: it must reproduce 113.74 %.**

> **Why the asymptote probes exist.** B-3's objection to C4 is that it may simply *be*
> buy-and-hold. **The cleanest way to settle that is to measure the limit.** At 20–50 ATR the
> chandelier sits so far below entry that the stop cannot bind, `custom_exit` returns `None`
> in run mode, and the trade becomes "hold from the first entry" — so the capture ratio
> converges to whatever the entry's own timing is worth against holding. **If C4's capture
> is already close to what the asymptote arms produce, C4 was buy-and-hold and the family
> ends here.** It also gives the curve a scale, which is what makes a plateau interpretable.

**KNOWN LIMIT, stated in advance:** at very wide chandeliers the stop stops binding, so
`max_open_trades: 24` and free balance will cap exposure instead. **The asymptote arms are
therefore a CAPPED buy-and-hold, not a pure one**, and their capture is an UPPER BOUND on
what a loose chandelier can be worth. Reported with that stated.

## 4. Pre-registered decisions

* **B0** reproduces 113.74 % → otherwise void.
* **The whole curve is published**, C2 through X2, whatever it says.
* **The §2 rule decides** promotion or closure. No cell is chosen after the fact.
* **If C5–C7 show a peak**, the next round may promote that peak **only if** it also beats
  the asymptote arms' capture — i.e. only if it is doing something buy-and-hold is not.

## 5. What this does NOT do

* **Does not touch the delivered book.** `exit_mode` defaults to `"fixed"`, every short path
  delegates to `super()`, and **B0 is the proof on every run.**
* **Does not promote anything on this round's evidence alone.** This round answers one
  question — is 6.0 a peak or a direction — and the answer decides the next round.
