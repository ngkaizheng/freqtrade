# The signal and the cost live in different places

> ## ⚠ CORRECTION 2026-09-26 (later the same day) — the economic table below is void
>
> The reversal edge was computed as `3.51 × |IC| × σ` = 0.274%/day. **That is a
> Gaussian identity, not a measurement.** The actual equal-weight decile
> long-short earns **+0.0059%/day, t = +0.14**, cumulative **−26.1%**. The
> formula overstated by **90.5×**, and the breakeven is **~0.6 bps**, not
> 26.6 bps.
>
> **So the conclusion inverts: the binding constraint is the signal, not
> execution cost.** Measured cost at $10k/name is 3.6 bps mean (2.7 median)
> before fees; the edge is 0.6 bps.
>
> Also: the "liquidity provision premium" reading is **Zaremba, Bilgin, Long,
> Mercik & Szczygielski, IRFA 81:101908 (2021)**, doi 10.1016/j.irfa.2021.101908,
> verbatim, and already in this project's §3.27(a). It was cited here as a
> contribution. It is not.
>
> The measured-cost table below survives — it was a real measurement. Everything
> that used it to price a 27 bps edge is withdrawn. See `E4_REVERSAL_FINDING.md`
> (rewritten) and `verify_claim1.py`.

---

**Date:** 2026-09-26
**Status: a clean structural negative, and the most useful result in this project.**

---

## The finding

The E#4 reversal signal is real. It is also, apparently, in the one place it
cannot be harvested.

| universe | median daily quote volume | IC | t (dependence-adjusted) | gross/day |
|---|---:|---:|---:|---:|
| 200 oldest-listed perps (long tail) | ~16m USD | **−0.0195** | **−3.79** | 0.274% |
| 50 most liquid perps | ~91m USD | **−0.0060** | **−0.99** | 0.077% |

**The signal is three times weaker on the liquid universe and is not
statistically distinguishable from zero there.** Priced with the *measured*
cost, the liquid universe loses money at every book size:

| per-name size | book cost (measured) | + VIP0 fee | all-in | net/yr |
|---:|---:|---:|---:|---:|
| $10,000 | 3.1 bps | 10.0 bps | 13.1 bps | **−21.2%** |
| $50,000 | 7.7 bps | 10.0 bps | 17.6 bps | −38.3% |
| $250,000 | 18.4 bps | 10.0 bps | 28.4 bps | −78.5% |
| $1,000,000 | 38.0 bps | 10.0 bps | 48.0 bps | −152.6% |

## The measurement that made this decidable

Until now every number in this debate was an assumption:

| source | assumed cost |
|---|---:|
| Fieberg et al. (JFQA 2025) | 30 bp long / 40 bp short |
| Arefev (SSRN 7404139) | ~59 bp implied |
| this repository, before today | 12–18 bp |
| **measured today, 20 liquid perps, live depth** | **3.1 bps at $10k → 38.0 bps at $1M**, before fees |

A single depth snapshot cannot give historical impact, and it is a lower bound
— it excludes adverse selection while an order works. But it is measured, it
came from this venue, and it is three times better documented than any of the
assumptions it replaces. Quoted spread, median 0.8 bps.

## Why this is worth more than a null

Every previous negative in this project said "there is no signal." This one
says something sharper and more useful:

> **The signal is a liquidity-provision premium, and a liquidity-provision
> premium is largest exactly where liquidity is scarcest.**

That is coherent economics rather than an embarrassment. Reversal pays the
patient holder for absorbing order flow. Order flow is thickest where liquidity
is worst, which is the long tail — and the long tail is also where the crossing
cost is highest and where the book thins out in front of a position of any
size. **The size of the premium and its harvestability are inversely related,
and on this venue the trade-off is not worth taking at either end.**

It also explains the pattern in the external literature, which had looked
anomalous:

- **Fieberg et al.** find a large *momentum* effect in the largest and most
  liquid coins, net of 30–40 bps.
- **Arefev** find momentum on 832 Binance perps with a gross of +0.573%/week
  that disappears into noise once ~59 bps is subtracted.
- **This project** finds *reversal* in the long tail, real and significant, and
  absent on the liquid set.

Those are not contradictory. They are the same surface seen from two sides: in
deep, liquid books the effect is momentum and it is large enough to survive
cost; in thin books the effect is reversal and it is not. **The venue's own
liquidity determines which one you see.**

## What follows

1. **Do not pursue the long-tail reversal.** The measurement is the reason, not
   the prior. The cost of trading the long tail is precisely the part this
   project could not previously measure and can now.
2. **The one configuration worth a pre-registered test** is the thing nobody in
   this project has tested on this venue: **momentum in the liquid majors**,
   which is what Fieberg reports and what the measured cost says is affordable
   (13–18 bps all-in against a 1.25% breakeven). That is a genuinely untried
   experiment here, not a repeat of E#3, which ran momentum on the wrong
   universe.
3. **The forward collector is now the right instrument.** The open question is
   no longer whether a backtest can produce a number; it is what execution
   actually costs on these books over time. The collector should start
   archiving periodic depth snapshots, because a single snapshot is the
   weakest thing in this report.

## What this does not say

- It does not say there is no edge in crypto. It says the edge and the
  affordability are in different places, and that on this venue the trade-off
  does not work at either end.
- It does not refute Fieberg. Momentum on liquid majors remains untested here.
- The cost figure is one snapshot on one day at 18:43 UTC. It should be turned
  into a distribution, and that is cheap.

## The lesson

The project spent a day proving it could detect a real effect
(IC −0.0195, t −3.79, p ≈ 6.7e-4 after family correction) and then spent an
hour proving it could not have it. **Both halves were necessary, and only the
second one would have mattered if the first had been reported alone.**
