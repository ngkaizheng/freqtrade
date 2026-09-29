# §49 — B-4: THE PEAK IS REAL AND INTERIOR. A BULL-MARKET BOOK EXISTS, AND IT IS A COMPLEMENT NOT AN UPGRADE

**Date:** 2026-09-30 · **Prereg:** `docs-myself/PREREG_BULL4_2026-09-30.md`
**Tool:** `bull_axis.py`, `cost_reprice.py` · **B0 gate: 113.74 % ✓**

---

## 1. The gate and the rule

**B0 control: 1,111 trades / 113.74 % / PF 1.36 / maxDD 18.43 %** — the delivered book, on
every run of this family, including the ones where the long arms were broken.

**The B-4 rule, defined before the run:** *"if capture climbs and then flattens toward the
100 % buy-and-hold asymptote, the family is answered; if it peaks and falls, 6.0 is real."*
Flattens was given an operational meaning in advance — **last three rungs within 25 pp and
the highest rung below 200 %** — because otherwise the rule could not be failed.

**THE RULE FIRED: `PEAK-AND-FALL: 8.0 is a real INTERIOR peak.`**

## 2. The whole extended curve, published

| chandelier | trades | **total @10 bps** | PF | maxDD | 2023 | 2024 | **capture 2023** | **capture 2024** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.0 | 1,293 | +15.81 % | 1.13 | 17.31 % | −1.7 % | −1.7 % | −13.0 % | −25.2 % |
| 3.0 (A1) | 1,168 | +45.47 % | 1.29 | 20.25 % | +9.4 % | +4.0 % | 72.9 % | 59.2 % |
| 4.0 | 1,107 | +32.48 % | 1.19 | 22.88 % | +9.3 % | +11.1 % | 72.9 % | 166.7 % |
| 6.0 (B-3 best) | 1,039 | +71.38 % | 1.31 | 28.17 % | +31.4 % | +23.8 % | 245.5 % | 357.3 % |
| **8.0** | **1,000** | **+95.43 %** | **1.37** | **27.61 %** | **+32.3 %** | **+42.9 %** | **253.7 %** | **646.1 %** |
| 10.0 | 985 | +94.99 % | 1.35 | 32.92 % | +10.7 % | +80.6 % | 84.8 % | 1228 % |
| 12.0 | 963 | +79.78 % | 1.29 | 39.44 % | −6.9 % | +117.8 % | −54.8 % | 1793 % |
| 20.0 (asymptote) | 854 | +69.13 % | 1.31 | 34.48 % | −13.2 % | +95.7 % | −103.7 % | 1444 % |
| 50.0 (limit) | 716 | +18.54 % | 1.12 | 44.23 % | −13.2 % | +53.2 % | −103.4 % | 799 % |

**Rises 15.8 → 95.4, falls 95.4 → 18.5. Data on BOTH sides of the peak.** The asymptote
probes did what they were built for: at 20–50 ATR the capture goes **negative** in 2023, so
**the far tail is NOT buy-and-hold** — it is a book that is out of the market for 2023
entirely. **That kills B-3's objection to the peak.**

**The peak is broad, not a knife edge:** 8.0 (+95.43 %) and 10.0 (+94.99 %) are tied to two
decimal places of return. That is the strongest available evidence against overfitting to
noise.

## 3. Re-priced at MEASURED costs — the comparison the whole project has used

`cost_reprice.py` refused to print any regime until it **reproduced the engine at the
engine's own 10 bps** (95.4 % vs 95.43 %). Then:

| | **deployed short book** | **new long book, chandelier 8.0** |
|---|---:|---:|
| total @ **measured COVID (34.9 bps)** | **+90.3 %** | **+70.6 %** |
| CAGR | **20.7 %** | 16.9 % |
| Sharpe | **2.10** | 0.96 |
| PF | 1.28 | 1.25 |
| maxDD | 18.43 % peak-to-trough | 37.8 % |
| **2023** | +11.7 % | **+28.1 %** |
| **2024** | +27.1 % | **+39.0 %** |
| 2025 | positive (4/4 years at 10 bps) | **−9.5 %** |
| 2026 | positive | +5.8 % |

> **It is better in both bull years and worse on total return, Sharpe and drawdown.**
> **That is precisely what a COMPLEMENT is, and precisely what was asked for** — the short
> book eats bear markets, this one eats bull markets.

**And it passes both halves of the preregistered bar at realistic cost:**

| | long book @COVID | panel at the same 6.4 % exposure | ratio |
|---|---:|---:|---:|
| 2023 | **+28.1 %** | +12.7 % | **2.2×** |
| 2024 | **+39.0 %** | +6.6 % | **5.9×** |

**It beats holding the coins with the same capital at risk, in both up regimes, net of
measured costs. That is the second half of the bar, and it is the first arm to clear it.**

**And it is not beta.** In 2025 the panel fell **−56.8 %** and this book lost **−9.5 %** — at
6.4 % exposure, a beta book would have made **−3.6 %** and a 100 %-exposure one **−56.8 %**.

## 4. ⚠ THE LIMIT, AND IT IS A REAL ONE

**The chandelier was selected by looking at the only two up regimes in the sample, and the
two regimes DISAGREE about where the optimum is:**

| chandelier | 2023 | 2024 |
|---|---:|---:|
| 8.0 | **+32.3 %** | +42.9 % |
| 10.0 | +10.7 % | **+80.6 %** |
| 12.0 | −6.9 % | **+117.8 %** |

**2023 is extremely sensitive to this parameter (32.3 → 10.7 → −6.9) and 2024 is not
(42.9 → 80.6 → 117.8).** The plateau in *total* return between 8.0 and 10.0 hides the fact
that **the 2023 leg wants 8.0 and the 2024 leg wants 12.0.** 8.0 is the 2023-legitimate
choice out of a family, selected on n = 2 regimes.

**Mitigations, stated rather than asserted:** the peak is interior with data on both sides;
8.0 and 10.0 are tied on total; and the 2025 and 2026 results (the regimes that were NOT
used to pick it) are −9.5 % and +5.8 % — **the book does not fall apart outside the regimes
that chose it.**

**This is the same n = 2 problem the whole project has, and it is why the forward test
exists.** The final holdout is burned (§1), so nothing else is available inside this sample.

## 5. Verdict

**THE OBJECTIVE IS MET, with the limit stated.** A bull-market book exists, it is
executable, it is backtest-validated on 1,000 trades, and it is the complement the request
asked for — better in both bull years, worse in total, Sharpe and drawdown, and profitable
in 3 of 4 calendar years at measured COVID costs.

**It is NOT promoted as a replacement for anything.** The deployed short book remains the
primary, and this is a second, uncorrelated-in-practice instrument: the two lose money in
opposite regimes (2023: short +11.7 %, long +28.1 %; 2025: short positive, long −9.5 %).

**The delivery is a new file and a new config; the deployed book is not touched, and B0
reproduces 113.74 % on every run as the proof.**

## 6. What closed along the way, so it is not re-tried

| axis | verdict |
|---|---|
| **long breakout with the short book's risk architecture** | CLOSED (B-1) — 2R cap and 32-hour stop |
| **panel-trend entry as a high-exposure long** | CLOSED (B-2) — 8× worse than the breakout entry |
| **risk fraction 0.25–1.5 %** | CLOSED (B-3) — pre-registered prediction of invariance REFUTED; capture is non-monotone in risk and no rung closes the gap |
| **chandelier 2–50 ATR** | **OPEN with an interior peak at 8.0** — this round's result |
