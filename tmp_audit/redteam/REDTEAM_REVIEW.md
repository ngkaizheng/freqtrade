# Red-team review of the three headline claims

**Date:** 2026-09-26 · **Role:** adversarial reviewer · **Mandate:** refute, not agree.

Scripts that produced the local measurements: `tmp_audit/redteam/ls_test.py`,
`tmp_audit/redteam/ic_test.py`, `tmp_audit/redteam/fund2.py`, `tmp_audit/redteam/getpdf.py`.
I did **not** edit `RESEARCH_STATE.md` — a concurrent agent owns that file and a
clobber is worse than a late entry. The corrections it needs are listed in §7.

---

## Verdict summary

| claim | verdict |
|---|---|
| **1(a)** one return per rebalance | **SURVIVES** as a counting rule, but is **MISAPPLIED** — see #1 |
| **1(b)** diversification saturates at `rho_resid=0.297` | **SURVIVES** |
| **1(c)** required net Sharpe ~2.0–2.4 | **WRONG as a forward-test benchmark. Refuted empirically.** |
| **1(d)** Fayez Junior is a load-bearing negative | **OVERSTATED — cannot bear that weight** |
| **1(e)-i/ii** 5 symbols, rebalance cadence | **SURVIVES — strongest surviving leg** |
| **1(e)-iii** "47-symbol universe rejected on −89.49% DD" | **WRONG — category error; that is a long-only book** |
| **2** carry not worth deploying | **HALF WRONG** — cost claim false; decomposition claim correct |
| **3(a)** required Sharpe ~2.0–2.4 unreachable | **WRONG** |
| **3(b)** corpus has 5 symbols | **SURVIVES** |
| **3(c)** momentum is priced, not alpha | **CONTESTED** by a later top-tier paper |
| **7** McLean & Pontiff 58% | **SURVIVES — and is understated** |

---

## #1 — WRONG: the 2.0–2.4 required Sharpe is the wrong benchmark, and the briefing's own number is wrong

### The briefing's arithmetic is broken
`sqrt(2 ln 41472)` = **4.6115**, not 4.196. (4.196 implies `N = 6,656`.)

The repo's own `DESIGN_FEASIBILITY_2026-09-26.md` table is, however, internally
consistent: it uses the refined asymptotic `E[max_N] ≈ 4.081`, and
`4.081 / sqrt(3 years) = 2.36` — which is its "~2.0–2.4". So the *document* is fine;
the *briefing* misquotes it. Minor, but it signals the number is being passed
around without re-derivation.

### The benchmark is the actual error
`E[max of N]` answers: **"if I re-measure all 41,472 of my rules in a fresh 3-year
window, what's the best zero-signal Sharpe I expect to see?"** That is the right
question for a *search*, and it is exactly what Bailey & López de Prado's DSR is
meant to deflate — **at the selection step, once.**

It is the wrong question for a **pre-registered forward test of one frozen rule**,
where `N = 1` and the benchmark is the ordinary 1.645:

| design (3 years) | T | required annualised Sharpe, 1 test | project says |
|---|---:|---:|---:|
| weekly rebalance | 156 | **0.950** | ~2.0–2.4 |
| daily rebalance | 1095 | **0.789** | ~2.0–2.4 |

At 90% confidence the weekly bar is **0.740**. The project carries a 41,472-fold
deflation into every future test *forever*, which is not what the DSR does. The
deflation is paid once on the search; the selected rule is then tested as one test.

The burned holdout (`FINAL_HOLDOUT_DO_NOT_TOUCH.json`, unblinded 2026-09-26) is a
**data-availability** problem. It is not a licence to keep re-deflating, and it is
not repaired by deflation — a genuinely new forward collection (`collect_forward.py`
is already running) is a clean single test.

### The empirical record refutes "unreachable"

**Fieberg, Liedtke, Poddig, Walker & Zaremba, "A Trend Factor for the Cross Section of
Cryptocurrency Returns," *Journal of Financial and Quantitative Analysis* (2025),
doi 10.1017/S0022109024000747, CC-BY OA, 19 citations.** 3,000+ coins, Apr 2015–May 2022,
weekly rebalance, value-weighted quintiles (extracted from the OA PDF):

| | gross | net @30bp long / 40bp short | net @50/60bp |
|---|---:|---:|---:|
| H−L quintile spread, all coins | 3.87%/wk, t=5.19, **Sharpe 1.94** | 2.90%/wk, **t=3.89** | 2.35%/wk, t=3.16 |
| H−L, **largest 100 coins only** | 3.40%/wk, t=4.48 | 2.45%/wk, t=3.22 | 1.90%/wk, t=2.50 |

- Alpha vs the **Liu–Tsyvinski–Wu 3-factor model**: **2.62%/week, t = 4.22**.
- Turnover 68%/week. **Breakeven cost 1.41%**; still 5%-significant at a 0.88% cost.
- **55,296 research designs** tested; the **median** annualised Sharpe across designs
  is **1.34** (range 0.91–10.92). The project searched 41,472.

The 30–40bp cost assumption is **Bianchi et al. (2022)**, i.e. *CryptoCompare data*,
and is **2–4x the project's own measured 12–18 bps perp round trip.** This is
cost-adjusted, peer-reviewed, top-tier, and it clears both 0.95 and 2.0–2.4 after
an exhaustive design sweep of the same order as the project's own.

**Correct position:** a cross-sectional crypto design needs a net Sharpe of ~0.95
(3y, single pre-registered test), not 2.0–2.4. That is a real bar — well above a
good buy-and-hold — but it is not "unreachable," and the project's own prior is
calibrated off a benchmark that does not apply to the test it contemplates.

---

## #2 — WRONG: the −89.49% drawdown is a long-only artifact and cannot reject the cross-sectional design

`tools/crypto_momentum_study.py:93` — the function docstring says it outright:

```
"""Daily target weights (long only, equal weight within selection).
```

Weights are `w[chosen] = 1.0/len(chosen)` — long only, fully invested, no short leg.
Its own equal-weight baseline has **−87.02%** MaxDD over the same window. The drawdown
is crypto beta.

I built the design the project actually rejected — dollar-neutral, long top-K /
short bottom-K, same 47 symbols, same window, weekly rebalance, Newey–West HAC t
and IAT-adjusted effective N per repo traps 3.1/3.2
(`tmp_audit/redteam/ls_test.py`):

| variant | net Sharpe | HAC t | CAGR | **MaxDD** |
|---|---:|---:|---:|---:|
| mom30d, K=20/leg, 10bps | 0.307 | 1.84 | 24.6% | **−36.8%** |
| mom30d, K=20/leg, 20bps | 0.287 | 1.72 | 22.4% | **−39.6%** |
| mom30d, K=20/leg, 50bps | 0.227 | 1.36 | 15.9% | **−50.7%** |

- **Beta vs the equal-weight universe: −0.278.** The book is dollar-neutral, as intended.
- Equal-weight all-47 over the same window: CAGR 32.1%, MaxDD −86.9%.

**The drawdown objection is void: −89% → −37% is entirely the long-only construction.**

### But the honest counterweight
The rebuilt design **still does not clear the bar**: net Sharpe 0.23–0.31, HAC
t = 1.4–1.8, against a 0.95 requirement. And the K=10-per-leg variants are wrecked
by **data artifacts, not signal** — the short leg of a crypto momentum sort
systematically selects dead/rebased tokens, producing single days of −1,374%.

**Correct position:** "don't run the cross-sectional design on this 47-symbol
survivor-only spot panel" **survives**. The *reason* given does not: the study it
cites never implemented the design, so there is no prior evidence against the design
at all. It is a prior of *zero*, not a prior of *negative*. That is a material
difference for a research line, and it is the difference between "closed" and "untried."

---

## #3 — WRONG: required IC of 0.021–0.035 is not a high bar in crypto

Measured on the project's **own** 47-symbol daily panel (`tmp_audit/redteam/ic_test.py`):

| lookback | 1-day fwd rank IC | HAC t | 7-day | 14-day | 30-day |
|---|---:|---:|---:|---:|---:|
| 14d | **−0.0246** | **−5.40** | +0.0030 | +0.0145 | +0.0128 |
| 30d | **−0.0224** | **−4.90** | −0.0019 | +0.0008 | −0.0108 |
| 60d | **−0.0222** | **−4.57** | −0.0162 | −0.0185 | −0.0237 |
| 90d | **−0.0182** | **−3.72** | −0.0098 | −0.0042 | −0.0072 |
| 180d | **−0.0158** | **−3.27** | −0.0056 | −0.0025 | −0.0058 |

`|IC|` of **0.016–0.025 with t up to 5.4** sits inside the claimed 0.021–0.035
band. The signal is **1-month reversal**, not momentum, and it is high-turnover, so
it is not a deployable result. But the *premise* — that 0.021–0.035 is out of reach
for crypto cross-sectional prediction — is false on this project's own data.

(Also worth noting: the 0.021–0.035 band appears **nowhere** in `docs-myself/`; the
only IC in the repo is Fayez's +0.0243. The band is an unsourced external derivation.)

---

## #4 — HALF WRONG: Claim 2

### Wrong part 1: "they did NOT measure the basis leg" is false
It was measured. `RESEARCH_STATE.md` §4:
`basis leg of a long-spot/short-perp hedge, quarterly ≈ −0.1 bps/quarter (mean);
sd ~5.4 bps` — from `funding_full_hedge.py`, 4 symbols with both legs, 2023+.

And the premise "the basis leg is typically a large part of cash-and-carry returns"
is wrong *for perps*. Christin et al., *The Crypto Carry Trade*, Table 8:
funding × = 17.2%/yr, change-in-basis y = **0.1%/yr**. The authors themselves (§3.3,
p.11): *"the median basis, however, is close to zero. This suggests that it is the
funding rate that is driving the profitability of the trade."*

(It *is* large for **fixed-maturity** futures — Schmeling/Schrimpf/Todorov,
*Management Science* 2026, "sometimes exceeding 40% per annum". That is a different
instrument and a genuinely open adjacent line.)

### Wrong part 2: "net −3.24%/yr" is stale and window-selected
I pulled live Binance USD-M funding for 23 majors, 500 settlements,
2026-04-13 → 2026-09-26 (`tmp_audit/redteam/fund2.py`):

| window | EW gross carry |
|---|---:|
| trailing 30d | **+3.84%/yr** |
| trailing 90d | **+3.23%/yr** |
| trailing 365d | **+1.52%/yr** |

Against the project's own thresholds: trailing-30d **+3.84% clears the +3.60%**
monthly trigger; trailing-365d **+1.52% clears the +1.20%** quarterly trigger.
Monthly re-establishment is a *choice*, not a requirement — the project's own table
gives +6.76% at quarterly. The briefing's +0.36% is the repo's own **superseded**
figure (§3.15 corrected it to +1.08%).

`RESEARCH_STATE.md` §2a already says: *"The §2 switch is now ON on the short horizon."*
**The briefing restates a position the project has already partially retracted.**

### What survives: the decomposition, and I confirmed it independently
Live 2026 data: pooled **median** funding **+0.0033%/8h**, mean +0.0014% → +1.52%/yr,
and only **21.6%** of settlements sit at Binance's administered ι = 0.0100%
(down from the 39.7% the repo measured historically). Therefore:

```
realised 2026 EW carry        +1.52 %/yr
administered component  0.216 x 10.95 = +2.37 %/yr
EXCESS (market-driven)         −0.85 %/yr
```

The project's full-panel figure is **−0.88%/yr**. My independent live computation
matches to two decimals, on data the project never saw. **§3.17 is the single
strongest result in the file and it is correct.**

**Correct position:** "cash-and-carry currently loses money after costs" is **not
supported** — it is roughly breakeven at quarterly re-establishment and positive at
30 days. "The carry is an exchange-administered financing charge, not a risk premium"
is **strongly supported**. The claim is right for the wrong reason.

---

## #5 — OVERSTATED: Fayez Junior cannot carry Claim 1(d)

Verified via OpenAlex (doi `10.2139/ssrn.6701738`):

```
cited_by_count      : 0
is_published        : false
referenced_works_count : 0
publication_year    : 2026, type: preprint, SSRN Electronic Journal
```

Single-author preprint. **Zero citations, zero indexed references, no peer review,
10 symbols, one window.** Nobody has cited it either way. Building a load-bearing leg
of a three-legged argument on it is not defensible.

Note also an internal inconsistency: the briefing says "net Sharpe −3.22" for
"the only direct empirical test," while `RESEARCH_STATE.md` §3.6 and
`DESIGN_FEASIBILITY` §2.1 both report **−3.22 for the naive linear model** and
**−2.91 for the XGBoost ranker**. The briefing has collapsed two numbers into one.

**Correct position:** Fayez is a *valid warning* about IC-vs-P&L (§3.6 is a good
lesson, well-taken) and **zero** evidence about whether the design works. The
"single empirical test" framing inflates a null-unknown into a null-found.

---

## #6 — Claim 3's closure is too strong

`Claim 3` asserts directional alpha at 15m–4h is "not a viable research target" on
three grounds. (a) is wrong (#1). (b) survives. (c) is contested:

- **CTREND (JFQA 2025)** reports alpha against the *same* Liu–Tsyvinski–Wu 3-factor
  model of **2.62%/week, t = 4.22**, across 55,296 research designs, robust to
  subperiods and market states, and net of 30–40 bps costs. A later, higher-tier
  paper than LTW directly contradicts the negative reading of that model.
- **Grobys & Sapkota (2019)** is 143 coins, **2014–2018**, weekly/monthly momentum.
  It predates essentially the entire sample in which the effect is now claimed to
  exist. It is evidence about 2014–2018, not about 2026.

**On the microstructure angle the project says it never examined** (fair, and it
should stay open — but with no positive evidence attached):

- **arXiv:2602.00776**, *Explainable Patterns in Cryptocurrency Microstructure*
  (Jan 2026): **Binance Futures perpetual** books + trades at **1-second** frequency,
  2022-01→2025-10, BTC/LTC/ETC/ENJ/ROSE, CatBoost with direction-aware GMADL, plus
  taker **and** maker backtests. Taker IR: ROSE 5.28, ENJ 6.58, BTC 0.25, LTC 0.07.
  **But:** t-test vs buy-and-hold is **n.s. for BTC (p=0.75) and LTC (p=0.57)**;
  **every maker p-value exceeds 0.05**; and *"Latency is not explicitly modeled;
  results should be interpreted as an upper bound in the fastest regime."*
- **arXiv:2608.09576** (Aug 2026), European crypto ETPs, 1-min bars: four anomaly
  types predictable one bar ahead, **AUC-ROC up to 0.82**.

So: the category is **open but unproven**, and the honest correction to Claim 3 is
that *"not a viable research target" is a stronger statement than the evidence in
either direction supports.* It is open, thin, latency-dominated, and should not be
closed by analogy to momentum.

---

## #7 — What survives my attack, stated once

- **Claim 1(a) — one return per rebalance.** Correct as a counting rule, and the
  project is right to forbid `170 × 365`. But it is a statement about *portfolio-level*
  inference, not a statement that breadth is worthless. Fama–MacBeth and the
  Grinold fundamental law (`IR ≈ IC × √(breadth × relative efficiency)`) treat
  breadth as buying *information ratio*, not observation count. The project's
  conclusion — width is not the lever — is right; the reasoning conflates the two.
- **Claim 1(b) — diversification saturates.** Survives. 0.662 → 0.548 from 5 to 200
  names. Reinforced by §4: funding-rate `rho` across 20 perps is **0.627** (PC1 66.9%),
  a far more concentrated factor than the price correlation suggests.
- **Claim 1(e-i/ii — 5 symbols, cadence.** Survives. Verified: 5 (`binance_v2`) /
  9 (`shark_data`). A top-quintile/bottom-quintile sort on 5 names is 2-vs-2. **This
  is the strongest surviving leg of the entire argument.**
- **McLean & Pontiff.** Survives verbatim — the JF abstract confirms **58% total**,
  **26pp** out-of-sample, **32pp** data-mining. And it is **understated**: the same
  abstract reports that *"post-publication declines [are] greater for predictors with
  higher in-sample returns."* A signal with gross t = 3.71 should be expected to decay
  **more** than 58%, not less. No crypto- or HF-specific decay estimate exists; the
  project is right that this is a prior, not a fact.
- **The short-leg data-quality finding (#2).** My rebuilt test shows the short leg of
  a crypto momentum sort systematically selects dead/rebased tokens (−1,374% single
  days). This is a *new* trap in the same family as §3.13/§3.22 and is worth recording.

---

## 8 — Corrections `RESEARCH_STATE.md` needs (not applied — concurrent-agent risk)

1. **§4 and §7: remove "A cross-sectional crypto-perp design is rejected on three
   independent grounds."** Legs (c) and (e-iii) are void. The status is **untried on
   the available data**, not rejected. Legs (b), (d) and (e-i/ii) stand.
2. **§4: required net annualised Sharpe.** "~2.0–2.4" is the *simultaneous-inference*
   benchmark for a 41,472-rule re-screen. For a single pre-registered 3-year forward
   test the figure is **0.950** (weekly) / **0.789** (daily). Add the CTREND reference.
3. **§7 bullet "Funding carry is not a live opportunity today"** quotes the superseded
   +0.36%. Live: +1.52%/yr trailing-365d, +3.84%/yr trailing-30d — both above the
   project's own triggers. §2a already contradicts §7; **§7 is the stale one.**
4. **§2 "Not measured: the basis leg"** — it *is* measured (§4, `funding_full_hedge.py`).
5. **New trap:** the short leg of a cross-sectional crypto sort selects the worst
   data quality. Any cross-sectional study must cap per-name notional and audit the
   short leg for rebases/renames separately from the long leg.
6. **§3.6:** add that Fayez is 0-citation / unpublished / 0 indexed references, and
   that the briefing's "−3.22" conflates the naive model with the XGBoost ranker.
