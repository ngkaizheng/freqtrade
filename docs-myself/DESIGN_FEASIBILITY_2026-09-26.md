# Design Feasibility: can any design in this project reach a verdict?

> ## ⚠ CORRECTION 2026-09-26 — read this before the body
>
> An adversarial review found that **the conclusion in §4 is wrong or half
> wrong.** This report must no longer be cited for "a cross-sectional design is
> rejected."
>
> **1. The required-Sharpe constant used the wrong benchmark.** This report
> applied `E[max of N]` with N = 41,472 — the benchmark that answers *if you
> re-search all 41,472 rules in a fresh window*. That is the right question
> **at the selection step**, which is where the DSR is meant to apply, once. It
> is the wrong question for a **pre-registered forward test of one frozen rule**,
> where N = 1 and the benchmark is the ordinary 1.645. Corrected requirement
> for a 3-year pre-registered test:
>
> | design | rebalances | required net annualised Sharpe |
> |---|---:|---:|
> | weekly | 156 | **0.950** (0.740 at 90% confidence) |
> | daily | 1095 | **0.789** |
>
> §1's "~2.0–2.4" is a **2.1–3.0x overstatement** and is withdrawn. The
> deflation is paid once on the search; the selected rule is then tested as one
> test. Carrying a 41,472-fold deflation into every future test forever is not
> what the DSR does.
>
> **2. The −89.49% drawdown objection is void.** It came from
> `tools/crypto_momentum_study.py:93`, which is documented **long only** and
> whose own equal-weight baseline is −87.02%. The drawdown is beta, not a
> property of a dollar-neutral cross-sectional design. The review rebuilt the
> actual design (long top-K / short bottom-K, same 47 symbols, weekly,
> Newey-West + IAT): **MaxDD −37% to −51%**, beta vs the universe **−0.278**.
> The rebuilt design still does not clear 0.95 net Sharpe, but its prior is
> **zero, not negative**. It was untried, not closed.
>
> **3. The information-coefficient band is withdrawn.** The "0.021–0.035" in §1
> was an unsourced derivation and appears nowhere else in this repository.
> Measured on this repository's own 47-symbol panel, 1-day forward rank IC is
> **−0.0158 to −0.0246** (HAC t −3.27 to −5.40) — inside the claimed band, so
> it was not a high bar. (It is 1-month *reversal* with high turnover, so not
> deployable as measured — but the premise was false.)
>
> **4. Fayez Junior cannot bear the weight §2 put on it.** OpenAlex reports
> 0 citations, not published, 0 indexed references. It is a legitimate warning
> that a significant IC can coexist with a losing book (§3.6) and nothing more.
> It is not evidence about the design.
>
> **What survives — and it is the strongest part of this report:**
>
> - **§3 diversification saturates** (0.662 → 0.548 from 5 to 200 names) — and
>   the funding correlation is 0.627, worse still.
> - **§3.2 the 5-symbol universe and the rebalance cadence** — the strongest
>   surviving leg, unchanged.
> - **§5 McLean & Pontiff 58%** — and *understated* here: their abstract says
>   post-publication decline is greater for predictors with higher in-sample
>   returns, so a t = 3.71 signal should decay **more** than 58%.
>
> **The one claim the review could not verify.** It cites Fieberg, Liedtke,
> Poddig, Walker & Zaremba, *"A Trend Factor for the Cross Section of
> Cryptocurrency Returns,"* JFQA 2025, doi 10.1017/S0022109024000747: 3,000+
> coins, weekly rebalance, H−L **3.87%/wk gross t=5.19 Sharpe 1.94** and
> **2.90%/wk net of 30–40bp costs, t=3.89**, over 55,296 research designs with
> median Sharpe 1.34. **Web-search credits were exhausted before this could be
> verified first-hand, and it is load-bearing.** If it holds, it is a
> peer-reviewed, cost-adjusted crypto cross-sectional result at a Sharpe the
> corrected benchmark can clear, at a 30–40bp cost that is 2–4x this
> repository's own 12–18bp perp round trip. **Verify it before acting on it.**
>
> **Corrected position: see the final section of this file.**

---

**Date:** 2026-09-26 · **Question:** is there a research design this project can
actually run that produces a conclusive answer in acceptable time?

## Answer

**No.** Not on the data on disk, and — for the specific family of designs that
would be the natural next step — the prior is now too poor to justify the cost
even if the data existed.

This reverses the preliminary read I gave earlier in this session. The
correction and the evidence for it are in §5.

---

## 1. The corrected frontier

Parameters measured from this project's own corpus, not assumed:

| input | value | source |
|---|---|---|
| `rho_resid` (BTC-orthogonalised alt correlation) | **0.297** | 52,145 hourly bars, 4 alts |
| cross-sectional sigma, 1d / 7d / 14d / 30d | 2.18% / 6.29% / 9.65% / 15.26% | same |
| round-trip cost per name | 12–18 bps | `shark_hunter/config.py:99-158` |
| perp universe on disk | **5** (`binance_v2`) / 9 (`shark_data`) | verified |

A cross-sectional book produces **one return per rebalance**. T observations,
full stop — *not* one per symbol. Required per-rebalance Sharpe for a verdict:

| universe | rebalance | obs in 3y | req. Sharpe/rebal | annualised, after deflation for 41,472 trials |
|---:|---:|---:|---:|---:|
| 5 | weekly | 156 | 0.13 | ~2.0 |
| 5 | biweekly | 78 | 0.19 | ~2.1 |
| 5 | monthly | 36 | 0.27 | ~2.4 |
| 50 | weekly | 156 | 0.13 | ~1.9 |
| 200 | weekly | 156 | 0.13 | ~1.9 |

Widening the universe barely helps. Diversification saturates because
`rho_resid = 0.297`:

| names | 5 | 20 | 50 | 100 | 200 | 500 |
|---|---:|---:|---:|---:|---:|---:|
| portfolio vol / single-name vol | 0.662 | 0.576 | 0.558 | 0.551 | 0.548 | 0.546 |

Going from 5 names to 200 buys a **1.21x** reduction in portfolio volatility.
There is essentially nothing past ~20 names.

**The requirement is a net annualised Sharpe of roughly 2.0–2.4.**

---

## 2. Why the requirement is unreachable

**2.1 The one direct test of this exact design is negative.**

Fayez Junior, *"Failure of Cross-Sectional Alpha Screening on Cryptocurrency
Perpetual Futures,"* SSRN 6701738 (2026): 10 Binance USDT-margined perps,
price + volume + funding signals, Jul 2022 – Apr 2026, purged walk-forward.

- naive linear model: net Sharpe **−3.22**
- XGBoost ranker: rank IC **+0.0243 (t = 3.55)** but net Sharpe **−2.91**,
  max drawdown **−95.6%**

*"The evidence compels rejection of the hypothesis that the employed OHLCV and
funding rate signals contain exploitable cross-sectional alpha for large-cap
crypto perpetual futures at an eight-hour horizon."*

Caveat: single-author SSRN preprint, 0 citations, not peer reviewed, 10 names,
one window. But it is the only direct test found, and it is negative.

**Note the XGBoost line, because it is a warning about how E#2 would be
evaluated.** A *statistically significant* information coefficient coexisted
with a −95.6% drawdown. Testing IC rather than net P&L in R units would have
produced a false positive. This is the same trap that let
`H13_1H_STRONG_UP_SHORT` be frozen with dev PF 1.02.

**2.2 The supporting literature does not point the other way.**

- **Grobys & Sapkota (2019), *Economics Letters***, 143 cryptos 2014–2018:
  *"do not indicate any evidence of significant momentum payoffs."*
- **Liu, Tsyvinski & Wu (2022), *Journal of Finance***: crypto market, size and
  momentum are real — but *"all of these are accounted for by the three-factor
  model."* Factor exposure, not alpha. Documented horizon is weeks-to-months.
- **He, Manela, Ross & von Wachter (arXiv:2212.06888)**: perpetual-futures
  mispricing *"comove across currencies, and diminish over time."* Funding
  dispersion is a common factor, not cross-sectional alpha — this specifically
  undercuts the funding-carry-in-cross-section variant.
- **McLean & Pontifford (2016), *Journal of Finance***: total post-publication
  decline **58%**, of which 32pp is the data-mining component. (My earlier
  "roughly a third" was the data-mining component only; the total is nearly
  double.) No crypto analogue has been run — so the crypto decay rate is
  unmeasured, and the equities figure is the only anchor.

---

## 3. Why it is unreachable on this data, regardless

**3.1 The universe is 5 symbols.** Verified: `binance_v2/canonical/price/`
contains exactly BTC, ETH, SOL, BNB, XRP. The best perp stack anywhere in the
repo is `shark_data/` at 9 symbols, 3.66 years, perfectly aligned.

A "top quantile / bottom quantile" on 5 names is a 2-vs-2 spread. On 9 names it
is 1-vs-1. The premise of a cross-sectional design — breadth — is absent.

**3.2 The cadence collapses N.** Cross-sectional observations are rebalances,
not symbol-events:

| design | observations |
|---|---:|
| 5 perps, monthly rebalance, 5.96y | **71** |
| 5 perps, quarterly, 5.96y | **24** |
| 9 perps, monthly, 3.66y | ~44 |

Under `AGENTS.md` §1a, a design whose required sample size is undefined after
multiple-testing correction means **stop the line of inquiry**, not collect more
of the same data.

**3.3 The one wide universe is spot, and it has already been tried.**

`tools/crypto_momentum_study.py`, 47 Binance spot pairs, daily, weekly
rebalance — verified in `docs-myself/findings-ma200-and-momentum.md`:

| variant | CAGR | MaxDD | Sharpe | turnover/yr |
|---|---:|---:|---:|---:|
| momentum 30d top5 | 66.69% | **−89.49%** | 1.02 | 39.6x |
| momentum 90d top10 | 30.89% | −87.73% | 0.75 | 18.0x |

It passed its placebo (random top-5 mean CAGR 12.17%, p = 0.000) and had no
look-ahead. It was rejected on drawdown and on unquantified survivorship. The
repo's own verdict: *"Every CAGR above is an upper bound; the true figure is
unknown."*

**3.4 There is no untouched data left.** `FINAL_HOLDOUT_DO_NOT_TOUCH.json`
records the holdout as unblinded on 2026-09-26T01:42:43. Any new design starts
with zero clean out-of-sample data.

---

## 4. The decision

**Do not run Experiment #2 as a directional-alpha search on crypto perpetuals
at 15m–4h horizons.**

This is not a close call, and it rests on three independent legs:

1. **The design fails on arithmetic** — it needs a net annualised Sharpe of
   ~2.0–2.4, and the direct empirical test found −3.2.
2. **The data fails independently** — 5 symbols, and a rebalance-cadence design
   yields tens of observations, not thousands. Widening helps by 1.21x at most.
3. **The project has already run the closest available version** (47 spot pairs)
   and it was rejected on −89% drawdown.

Continuing would mean paying months to obtain a verdict the evidence has
already priced.

---

## 5. What I got wrong, and the correction

Earlier in this session I told the user:

> "横截面 170 币日频调仓 → 一年 62,000 笔"

**That is wrong.** It is 170 × 365, i.e. it counts each symbol as a separate
observation. A long-short book produces **one return per rebalance** — 365 per
year regardless of width. It is the same counting error that inflated the
original hypothesis count: treating correlated duplicates as independent
evidence.

Two further errors, both now corrected in this document:

- I treated "widen the universe" as the main lever. Measured `rho_resid` shows
  diversification saturates by ~20 names; the lever is the construction, not
  the width.
- I computed the frontier's viability from arithmetic alone and never checked
  whether an edge of the required size **exists**. Arithmetic establishes what
  you would need; it does not establish that you can get it. The 62,000
  figure and the required-IC table were both missing that check.

The correct statement of the result: *the cross-sectional design is not the fix
for the observation-count problem, because it trades many correlated names for
one observation per period. The observation-count problem is not solvable
within crypto perps at these horizons.*

---

## 6. What is worth doing instead

Ranked by prior, not by how interesting it is.

**6.1 Funding / basis cash-and-carry — the only structurally better prior, and
it is a different objective.**

A market-neutral carry trade (long spot, short perp, same asset) is not a
prediction problem. The payoff is observable at trade time from the funding
stream, rather than inferred from history. Its risks are different: exchange
risk, funding-regime duration, liquidation, and the tail where the basis
dislocates. It requires its own validation, not the directional framework's.

Data already on disk: `user_data/data/binance_funding/` — **20 symbols, 8h
settlements, 2019-09-10 → 2026-09-19**, 6,493 common settlements from
2020-10-16. That is ~7 years of carry history on 20 names, and it costs
nothing to look at.

Caveat to state up front: He et al. find mispricing *comoves* across
currencies, which means the carry is correlated and the book is not as
diversified as it looks. It does not mean the carry is absent.

**6.2 Fix the framework; do not point it at a new hypothesis.**

The gate calibration audit stands on its own and is not affected by this
decision: R1 (dependence-adjusted significance), R4 (`logic_hash` across
phases), R5 (`NO_MEANINGFUL_SAMPLE` as a hard block) are measurement fixes.
Apply them before any further study runs, whatever the next study is.

**6.3 Do not buy more data before a power calculation.**

Per `AGENTS.md` §1a and the lesson from both prior studies. This document is
that calculation for the designs considered here — and it is why the answer is
no.

---

## 7. What remains genuinely uncertain

- Fayez is one unreviewed preprint. It is the most on-point evidence and it is
  negative, but it is not settled.
- `rho_resid` was measured on 4 alts over 5.96 years. It would differ at 4h
  frequency and on a wider universe.
- **No published estimate of a crypto anomaly half-life exists.** The 58%
  equities figure is the only anchor and it is likely optimistic for
  4-hour signals.
- The carry option in 6.1 is a reprioritisation, not a free win. It has not
  been tested here.

---

## 8. CORRECTED POSITION (2026-09-26, after adversarial review)

**The original answer — "no feasible design" — does not stand. The corrected
answer is narrower and different:**

> **A cross-sectional crypto design is not refuted. It is *untried on the data
> this project holds*, and the only thing standing in its way is the
> universe.**

### What actually blocks it

**One thing, and it is a data problem, not a research problem:** 5 perpetuals
(`binance_v2`) or 9 (`shark_data`). A quantile sort on 5 names is a 2-vs-2
spread, and the cadence then yields tens of observations rather than thousands.

The review's own audit established that Binance currently lists **527 trading
USDT perpetuals plus 130 settling**, and that archive coverage extends back to
each symbol's own listing date. **Widening the universe is therefore
achievable** — which reverses an earlier statement in this report that "adding
symbols does not help." That statement was about *diversification*, and it is
still true: portfolio volatility only falls 1.21x from 5 to 200 names. But
breadth was never the point — the point is that **a cross-section needs enough
names to rank**, and 5 is not enough.

### What changed in the arithmetic

| | original | corrected |
|---|---:|---:|
| required net annualised Sharpe, 3y weekly pre-registered | 2.0–2.4 | **0.95** |
| same, daily | ~2.4 | **0.79** |
| same, 90% confidence | — | **0.74** |
| prior on the design | "poor" | **zero, not negative** |

### The recommended next step, revised

1. **Verify the CTREND paper first** (JFQA 2025, doi 10.1017/S0022109024000747).
   It is load-bearing and this session could not verify it. If it holds, the
   prior on a crypto cross-sectional trend factor is materially positive at
   weekly horizon, net of 30–40bp costs.
2. **Rebuild the universe.** Download 100–200 USD-M perpetuals with 4h/daily
   klines back as far as each listing allows. This is the binding constraint
   and it is an afternoon of downloading, not a research project.
3. **Pre-register ONE frozen cross-sectional rule** — the point of pre-
   registration is that the 41,472-fold search penalty is not carried into the
   forward test. The benchmark is 1.645, not 4.1.
4. **Audit the short leg for rebases separately.** The review found that the
   short side of a crypto momentum sort systematically selects dead or rebased
   tokens, with single days of −1,374%. A universe of today's survivors makes
   this worse, not better, and it must be a named gate rather than a surprise.
5. **Keep the diversification caveat.** It survives and it bounds the upside:
   20 names captures essentially all of the available variance reduction, so
   this is not a reason to go to 500.

### What is still true

- The burned holdout is a real data problem and prospectively collected data is
  the only clean confirmation set that will exist.
- `tools/carry/REPORT.md`'s carry conclusion is separately re-checked below; it
  was **half** right — the gross funding switch is back on, the *excess* over
  Binance's administered component is still negative.
- McLean & Pontiff's 58% applies, and is more likely a floor than a ceiling for
  a signal with in-sample t = 3.71.
