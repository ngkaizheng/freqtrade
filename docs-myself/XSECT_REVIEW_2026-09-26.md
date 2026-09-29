# Cross-Sectional Crypto-Perp: Design and Evidence Review

**Date:** 2026-09-26 · **Question:** is a cross-sectional crypto-perp design worth
building on the data available, and what is the cheapest test that decides it?

**Scope note.** The `web_search` tool was out of credits for this session
(HTTP 400, "insufficient credits"). All work was done via OpenAlex, Crossref and
ARXIV APIs plus direct publisher / repository PDF retrieval, which are not
credit-metered. **Every number below was read in a primary source**, and each is
labelled with its source-quality class and with whether the full text or only the
abstract was read. Where evidence is absent, that is stated as a finding.

Cached primary sources in this repo:

| file | what it is |
|---|---|
| `docs-myself/_xref_pdfs/ctrend_cambridge.pdf` | Fieberg et al. (JFQA 2025), published version, CC-BY |
| `docs-myself/_xref_pdfs/ctrend.txt` | extracted text, 38 pp |
| `docs-myself/_xref_pdfs/Survivorship_and_Delisting_Bias_in_Cryptocurrency_Markets.pdf.txt` | Ammann et al., extracted text, 3,151 lines |
| `tools/xsect/falsification_power.py` | power analysis, runs in <1 s |

---

## 0. The headline

**The load-bearing citation in the prior review is real, peer-reviewed, and
survives verification — but it says something narrower than the prior review
claimed, and a second paper in the same literature says something close to the
opposite.**

1. **VERIFIED.** Fieberg, Liedtke, Poddig, Walker & Zaremba, *"A Trend Factor for
   the Cross Section of Cryptocurrency Returns,"* JFQA 60(7), 2025, 3116–3153.
   Every number the prior session quoted is exact, to the decimal.
2. **BUT** the headline 3.87%/wk Sharpe 1.94 is a **machine-learned ElasticNet
   composite of 28 technical indicators** on 3,244 CoinMarketCap coins,
   **value-weighted**, weekly, **Apr 2015 – May 2022**. In the *same paper*,
   **plain cross-sectional momentum has a median Sharpe of 0.83 and is
   statistically significant in only 49% of 55,296 design specifications.**
3. **And** Ammann et al. (2022), on a 3,904-coin delisting-corrected sample,
   find **one-week cross-sectional momentum has a value-weighted H−L of
   0.13%/week (t = 0.13)** over 417 weeks. That is a hard null on the exact
   construction a pilot would naturally reach for.

So the design is **not refuted** — but the evidence in its favour is attached to a
specific, non-trivial, machine-learned, large-cap, value-weighted, 2015–2022 spot
factor, and **not** to a simple momentum sort.

---

## 1. CONSTRUCTION — what published crypto cross-sectional research actually uses

### 1.1 The canonical construction (Fieberg et al. 2025, **peer-reviewed**)

Full text read. Table 2, Table 3, Table 6, Table 8, Table 9.

| element | what they do |
|---|---|
| universe | CoinMarketCap, **min market cap USD 1m**, 3,244 unique coins |
| period | **Apr 2015 – May 2022, 423 weekly observations** |
| formation | **quintiles**, sorted at the start of each week on the signal |
| **weighting** | **value-weighted within quintile** (explicitly; Table 6 varies this) |
| rebalance | **weekly** |
| signal | ElasticNet cross-sectional regression on **28 technical indicators** (momentum oscillators, moving averages, volume, volatility), ranks mapped to [-0.5, 0.5] per Kelly-Pruitt-Su |
| estimation | rolling 52-week window, **value-weighted WLS** ("to mitigate the influence of micro-cap coins") |
| outliers | returns truncated at the 0.5 / 99.5 percentiles |
| factor returns | zero-investment: long top quintile, short bottom quintile |
| inference | **Newey–West** t-statistics |
| risk adjustment | CCAPM 1-factor, and the **Liu-Tsyvinski-Wu 3-factor** (market, size, momentum) |

**There is no risk parity, no inverse-vol scaling, and no sector neutralisation in
this design.** The beta and size exposures of the spread portfolio are ~0
(β_MKT = 0.03, β_SIZE = −0.03) but the **momentum beta is 0.79 (t = 14.88)** —
it is a big momentum bet that survives a 3-factor regression with a weekly alpha
of 2.62% (t = 4.22).

### 1.2 Time-series vs cross-sectional

The paper's own design-choice axis is literally labelled `CS` (cross-sectional)
vs `TS` (time-series) forecasting. **The cross-sectional specification is the
baseline and the better one**; the paper's conclusion is that the cross-section
carries the information. The "time-series" variants (a single coin's own history
predicting its own return) are a design choice, not the headline.

### 1.3 What survives costs, out of sample

Table 9, Panel B — **the most relevant table in the paper for a perp book**, top
100 cryptocurrencies only:

| | value |
|---|---|
| H−L gross | 3.40%/wk, t = 4.48 |
| H−L **net** of 30bp long / 40bp short | **2.45%/wk, t = 3.22** |
| net of 50/60bp | 1.90%/wk, t = 2.50 |
| turnover | 68.21%/wk |
| **breakeven cost (net = 0)** | **1.25%** |
| **cost at which net stops being 5% significant** | **0.70%** |

Costs are 30/40bp **per trade** following Bianchi et al. (2022), applied as
`Σw|Δw| × rate` on each leg. **The cushion is 4–10× this repository's own 12–18bp
perp round trip.** Cost is not what kills this factor at a weekly cadence.

### 1.4 Holding period

Verbatim: *"Most cryptocurrency momentum strategies no longer produce significant
profits at a 3- or even 2-week horizon."* CTREND itself stays significant *"as long
as the holding periods do not exceed 4 weeks"*; 2-week rebalancing already costs
1.5pp of average weekly return (3.87 → 2.34%). The paper also reports that a
**1-day implementation lag** cuts the median Sharpe from 1.46 to **1.24**.

### 1.5 THE CONSTRUCTION DETAIL THAT MATTERS MOST: sign and horizon, not size

Table 2 sorts every indicator separately, same sample, same quintiles, same
weekly rebalance. H−L gross, t in parentheses:

| momentum oscillators (overbought/oversold distance) | H−L | t |
|---|---:|---:|
| **rsi** | **+3.17** | **3.87** |
| **stochK** | **+2.56** | **4.13** |
| **cci** | **+2.35** | **3.40** |
| stochD | +1.92 | 2.99 |
| stochRSI | +0.95 | 1.25 |

| moving averages (trend distance) | H−L | t |
|---|---:|---:|
| sma_3d | −0.89 | −1.11 |
| **sma_5d** | **−2.90** | **−3.35** |
| **sma_10d** | **−2.37** | **−2.90** |
| **sma_20d** | **−3.13** | **−3.80** |
| **sma_50d** | **−2.49** | **−2.88** |
| sma_100d | −0.96 | −1.12 |
| sma_200d | +0.04 | 0.05 |
| macd | +0.85 | 1.17 |

**At the 3–50 day horizon, price-minus-SMA is a cross-sectional REVERSAL signal
with t = −2.9 to −3.8.** Short-horizon oscillator signals are cross-sectional
MOMENTUM with t = +3.4 to +4.1. **The sign of a "momentum" factor in crypto is
determined by the formula, not by the horizon alone, and the two families are
opposite.**

### 1.6 VERDICT Q1

Use **quintiles, weekly rebalance, value-weighted, ≥3 years, ≥100 names, Newey–West**.
**Do not use equal weighting** (see §4 — it carries a 62%/yr bias). Do not expect
risk parity or sector neutralisation to be part of the published recipe; they are
not. The one construction choice that is not optional is the **sign convention**:
a plain SMA-distance sort at 5–50 days is a reversal, not momentum, and a daily
rebalance makes that worse rather than better.

---

## 2. POWER — sample size, holding period, and delivered net Sharpe

### 2.1 What published studies needed

| study | coins | period | observations | holding | net Sharpe |
|---|---:|---|---:|---|---:|
| Fieberg et al. (JFQA 2025), full | 3,244 | Apr 2015 – May 2022 | **423 weekly** | 1 week | ~**1.45** |
| Fieberg et al., top-100 | 100 | same | 423 | 1 week | ~**1.4** |
| Fieberg et al., median of 55,296 designs | — | same | 423 | 1 week | **1.34** |
| …with a validation sample | — | same | 423 | 1 week | **1.19** |
| Ammann et al. (2022) | 3,904 | Jan 2014 – Dec 2021 | **417 weekly** | 1 week | **0.06** (1-wk momentum, VW) |

**423 weeks of weekly data on 100–3,244 coins is the sample the best published
result used.** That is the number to hold in mind: the field did not need more
than this, because the effect it measured was **large**.

### 2.2 Delivered Sharpe, net of costs — the numbers

**Gross annualised Sharpe 1.94** (3.87%/wk, t = 5.19, H−L weekly sd 14.34%).
Net of 30/40bp: **2.90%/wk, t = 3.89** → implied net annualised Sharpe ≈ **1.45**.
Top-100 subset net: **2.45%/wk, t = 3.22** → ≈ **1.4**.

### 2.3 The power calculation for THIS project

`tools/xsect/falsification_power.py` (run it; output reproduced in §6):

| panel | weeks | KILL bar @95% | KILL bar @90% | SR @80% power |
|---|---:|---:|---:|---:|
| 3y weekly (repo's stated test) | 156 | 1.14 | **0.95** | 1.63 |
| 4y weekly | 208 | 0.99 | 0.82 | 1.41 |
| **5y weekly** | **260** | **0.88** | **0.74** | **1.26** |
| 6.5y weekly | 338 | 0.77 | 0.64 | 1.10 |

The script **reproduces the repo's internal 0.95 and 0.74 constants exactly**
(`1.645/√156 × √52 = 0.950`), which validates the method.

**Two conclusions:**

- **The bar is lower on a longer panel.** 3y → 5y moves the 90% bar from **0.95
  to 0.74**. The falsification test should use *all* available perp history, not
  a 3-year window. This is a free 22% reduction in the bar.
- **A 5-year weekly panel has 80% power to detect a true Sharpe of 1.26**, and
  the published net result is **~1.45**. So the test is *correctly calibrated*:
  ~80% powered to detect exactly the effect the literature claims.

### 2.4 VERDICT Q2

**The internal 0.95 is defensible but it is not the best available benchmark, and
it is the wrong one for plain momentum.** The published distribution is:

- machine-learned multi-indicator composite, net of costs: **1.2 – 1.9**
- plain cross-sectional momentum, median across designs: **0.83**
- 1-week momentum, value-weighted, bias-corrected, large universe: **0.06**

**Use 1.19 (the median of the best published factor across 55,296 design
specifications, with a validation sample) as the external reference point.** It is
25% above 0.95 and it is a published number. If the pre-registered rule is a
*single simple sort*, however, 0.95 is a bar the literature says that family fails
about half the time — the median for plain CS momentum is 0.83.

---

## 3. THE BEAR CASE

*(Full sweep of the replication-failure literature was delegated and is reported
in §3.5; the load-bearing items below were verified directly.)*

### 3.1 The strongest single result: Ammann et al. (2022)

> **Ammann, M., Burdorf, T., Liebi, L., & Stöckl, S., "Survivorship and Delisting
> Bias in Cryptocurrency Markets."** St. Gallen / Swiss Institute of Banking and
> Finance, 2022-11-28. SSRN 4287573. **WORKING PAPER — NOT refereed** (the
> repository record explicitly states "Refereed: No"). 6 citations.
> [alexandria.unisg.ch](https://alexandria.unisg.ch/entities/publication/ed11eb12-4cd1-4e08-b3a4-f577ad6e4a66) ·
> [doi:10.2139/ssrn.4287573](https://doi.org/10.2139/ssrn.4287573)
> **Full text read.**

Table VIII — **one-week cross-sectional momentum**, 417 weeks, 07-Jan-2014 to
28-Dec-2021, sorted each Tuesday on the trailing 7-day return, held to the next
Tuesday, quintiles:

| | all coins | surviving only |
|---|---:|---:|
| **value-weighted H−L** | **0.13% (t = 0.13)** | **0.78% (t = 0.77)** |
| VW alpha vs market | −0.06 (t = −0.06) | 0.61 (t = 0.60) |
| **equal-weighted H−L** | **−11.46% (t = −32.91)** | **−8.40% (t = −19.19)** |
| EW alpha | −11.32 (t = −32.56) | −8.24 (t = −18.81) |

Verbatim: *"we cannot confirm that past winners outperform past losers in the
consecutive week… These results suggest **no momentum effect** in cryptocurrency
markets and stand in contrast to previous findings. Surprisingly, **no momentum
effect is documented even when a survivorship-biased sample is used.**"*

A t of **0.13 over 417 observations** is about as clean a null as one gets.

**But the same paper's Figure 7 is the reason this is not fatal to the design:**
within surviving coins, the momentum premium is **0.78% for the whole sample but
2.51% for the largest 100 surviving coins**, value-weighted. So the effect, such
as it is, is concentrated in **large caps** — which is where a perp cross-section
should live, and where a top-100 perp universe sits.

### 3.2 Factor exposure, not alpha (Liu, Tsyvinski & Wu 2022, **peer-reviewed**)

*Journal of Finance* 77(2), doi [10.1111/jofi.13119](https://doi.org/10.1111/jofi.13119),
**627 citations.** Abstract verified via OpenAlex: *"We find that three
factors—cryptocurrency market, size, and momentum—capture the cross-sectional
expected cryptocurrency returns… Ten characteristics form successful
long-short strategies and generate sizable, statistically significant excess
returns, **we show that all of these are accounted for by the three-factor
model.**"*

This is the canonical reference for the view that crypto cross-sectional returns
are **factor exposure, not alpha**. Fieberg et al. answer it (their momentum
beta is 0.79 but their alpha survives at 2.62%/wk, t = 4.22), so this is a live
dispute, not a settled null.

### 3.3 Within the best paper, the simple signal fails

Fieberg et al. on **CMOM (plain cross-sectional momentum)**, across the same
55,296 designs: **median Sharpe 0.83, max 2.30, min −4.47**, and by the Lo (2002)
test significantly positive in only **49%** of specifications. A pure-FM
factor-model variant reaches a median of only **0.94**, and the price filter ≥$1
(which "drastically reduces the size of the cross section") knocks CSMB down to
**0.41**.

**This is the cleanest available statement that "crypto cross-sectional momentum
works" is false as a general claim.**

### 3.4 The crypto momentum literature contains a direct, unresolved contradiction

Both sides verified via OpenAlex abstracts (full texts not retrieved — stated
plainly):

> **Grobys, K. & Sapkota, S., "Cryptocurrencies and momentum,"** *Economics
> Letters*, 2019, doi [10.1016/j.econlet.2019.03.028](https://doi.org/10.1016/j.econlet.2019.03.028).
> **PEER-REVIEWED. 144 citations.** Verbatim: *"Retrieving a set of **143
> cryptocurrencies** for a sample spanning **2014–2018**, we investigate the
> popular momentum strategy implemented in the cryptocurrency market. **Contrary to
> earlier studies, our findings do not indicate any evidence of significant
> momentum payoffs, supporting the view that the cryptocurrency market is far more
> efficient than suggested studies.**"*

> **Grobys, K., "Technical trading rules in the cryptocurrency market,"** *Finance
> Research Letters* 32, 2019, doi [10.1016/j.frl.2019.101396](https://doi.org/10.1016/j.frl.2019.101396).
> **PEER-REVIEWED. 102 citations.** Verbatim: *"…on the **eleven most-traded
> cryptocurrencies in 2016–2018**… a variable strategy is successful when using
> **20 days** average moving strategy. Specifically, **excluding Bitcoin, technical
> rule generates an excess return of 8.76% p.a.** after controlling for market
> return. Suggest that cryptocurrency markets are inefficient."*

**Two peer-reviewed papers by the same lead author, differing by a factor of 2 in
citations, reach opposite conclusions on crypto momentum.** The reconciliation
visible in the abstracts is **universe width** (143 coins vs 11 majors) and
**cost treatment** — the +8.76% is *excess over market*, not a dollar-neutral
long-short spread, so it carries the market beta this project is trying to remove.

**Neither study is a cross-sectional sort.** Both are time-series/technical rules
applied per asset. So this contradiction bounds the *prior* on the construction
this project would use, but it does not directly refute it. It does mean that
"crypto momentum" as a phrase carries no reliable prior at all — the field's two
most-cited direct answers to the same question disagree.

### 3.5 Cost-adjusted nulls

**None found.** No peer-reviewed study located in this session reports a crypto
cross-sectional factor that dies after realistic costs. Fieberg et al.'s own
breakeven cost (0.70–1.25% for the signal to remain 5% significant, vs this
repo's 12–18bp round trip) is evidence to the *contrary*: crypto cross-sectional
sorts are not cost-fragile at a weekly cadence, and the binding constraint is
signal decay, not fees. **This is a genuine evidence gap and it is the one place
where the bull case is strongest.**

### 3.6 THE MOST ON-POINT PAPER IN THE ENTIRE REVIEW — a net-of-costs null, on perps, 2020–2026

> **Arefev, O., "Cross-Sectional Momentum in Cryptocurrency: A Net-of-Costs
> Replication on Tradable Binance Perpetuals (2020–2026),"** SSRN 7404139, posted
> 2026. doi [10.2139/ssrn.7404139](https://doi.org/10.2139/ssrn.7404139).
> **WORKING PAPER — NOT REFEREED**, single author, **0 citations**, self-described
> as a "note". **Abstract verified independently against the Crossref-deposited
> JATS record** (not from a blog or an aggregator); full text not retrieved
> (SSRN returns 403).

Verbatim from the deposited abstract: *"on a universe of instruments directly
tradable by eligible retail participants on Binance USDⓈ-M perpetual futures, does
a cross-sectional momentum spread remain statistically distinguishable from zero
after realistic costs over the more recent 2020-2026 period? Using an independent
replication (**832 archived perpetual symbols**, a daily-close panel,
**pre-committed J/K parameters, explicit survivorship handling**, and **three
significance tests with different dependence assumptions**), we find that **neither
of the two literature-backed specifications permitted under a pre-committed
protocol (J=1/K=1 and J=2/K=2) yields a net-of-costs spread distinguishable from
zero under any of the three tests. The gross J=1/K=1 spread (+0.573%/week) is of
the same order of magnitude as realistic costs (0.40 pp/week) and disappears into
noise once they are subtracted; the J=2/K=2 net spread additionally flips sign
with an arbitrary choice of rebalancing phase.** … **We do not claim momentum is a
myth: we show that a deliberately constrained, cost-realistic implementation on a
tradable universe does not translate directly from the academic literature into a
tradable retail strategy.**"*

**Why this is the most important single item in the review:** it is the *exact*
design, the *exact* venue, the *exact* modern period, with survivorship handled
and pre-registered parameters. **It is, in effect, the Tier 1 falsification test of
§6 — already run, and it came back null.** It is 0-citation and unreviewed, so it
does not settle the matter, but it moves the prior from "positive" to
"materially negative" for **plain cross-sectional momentum on perps**.

**It also exposes the cost-model gap between the literature and reality.** Arefev
uses **0.40 pp/week** of cost against a gross spread of **+0.573%/week**. At
~68% weekly turnover (Fieberg's Table 9 figure) that implies a per-trade cost near
**59bp**, roughly **2× the 30/40bp** Fieberg et al. adopt from Bianchi et al. (2022).
Their wide "breakeven 1.41%" cushion therefore assumes a cost roughly half what a
retail taker actually pays on a perp. **The published cost cushion is built on an
optimistic cost model.**

### 3.7 Two peer-reviewed mechanisms saying the cross-section is a liquidity artifact

**Both found by the delegated sweep, not in the original brief. Together they are
the strongest bear-case material in this review.**

**(a) Zaremba, Bilgin, Long, Mercik & Szczygielski, "Up or down? Short-term
reversal, momentum, and liquidity effects in cryptocurrency markets,"** *IRFA*
81:101908 (2021), doi [10.1016/j.irfa.2021.101908](https://doi.org/10.1016/j.irfa.2021.101908).
**PEER-REVIEWED, 45 citations. ABSTRACT ONLY** (ScienceDirect 403). >3,600 coins,
daily. Verbatim: *"**We argue that the daily reversals result from the illiquidity
of the vast majority of traded cryptocurrencies. In consequence, the pattern is
cross-sectionally dependent on liquidity, and the handful of largest and most
tradeable coins exhibit daily momentum rather than a reversal.**"*

**This is the IRFA paper the task brief referred to, now correctly attributed.**
It supplies the mechanism *and* the boundary: crypto cross-sectional
return-persistence is **produced by the illiquid tail**, and **changes sign once
you restrict to tradeable coins**. It is a direct argument that a 9-perp or
top-100-perp universe should show *momentum* where the broad literature shows
*reversal* — which is exactly what your pilot found, and it means the pilot's
result is the *predicted* sign, not a surprise.

**(b) Liu, Tsyvinski & Wu, "Common Risk Factors in Cryptocurrency,"** NBER WP
25882 (2019), 48pp — **WORKING PAPER version, FULL TEXT READ** (the *J. Finance*
2022 published version was **not** read; the two differ — JF says "Ten"
characteristics, NBER says "Nine", so **do not mix numbers between versions**).
Two results that cost the momentum headline:

- **"Bitcoin for Short" (Table 12).** Restrict the short leg to Bitcoin — the only
  universally shortable instrument in 2014–2018 — and the **1-week (t = 0.694),
  2-week (t = 1.498) and 4-week (t = 1.204)** momentum spreads **all lose
  significance**; only 3-week survives (t = 2.248). Verbatim: *"the mean returns of
  the one-, two-, and four-week momentum strategies are no longer statistically
  significant."* **The momentum result is contingent on being able to short small,
  illiquid coins.**
- **Size split.** Below-median-size momentum **+0.6%/wk, insignificant**; above-
  median **+4.2%/wk, significant**. Verbatim: *"This is in sharp contrast to the
  equity market."*
- **Size split in Ammann et al. agrees:** the momentum premium is 0.78% for all
  survivors but **2.51% for the largest 100**.

**Taken together: the short leg is where the money is, the short leg is the
illiquid tail, and the illiquid tail is exactly what a perp universe cannot
replicate.** That is the single biggest structural risk to a long-short perp book
and it is invisible in a long-only backtest.

**Dobrynskaya, "Cryptocurrency Momentum and Reversal,"** *J. Alternative
Investments* 2023, doi [10.3905/jai.2023.1.189](https://doi.org/10.3905/jai.2023.1.189).
**PEER-REVIEWED, 10 citations. ABSTRACT ONLY.** 2,000 largest coins, 2014–2020,
horizons 1 week–2 years. Verbatim: *"The switching of momentum into reversal occurs
after approximately **one month** — much quicker than the equity market, and
evidence of the 'faster metabolism of cryptocurrencies.'"* This dates the
sign-flip at **~1 month**, which brackets where §1.5's oscillator/moving-average
split sits.

### 3.8 The bull case, restated fairly — and a post-2020 momentum flip

> **Fieberg, Liedtke, Metko & Zaremba, "Cryptocurrency factor momentum,"**
> *Quantitative Finance* 2023, doi
> [10.1080/14697688.2023.2269999](https://doi.org/10.1080/14697688.2023.2269999).
> **PEER-REVIEWED, 10 citations. ABSTRACT ONLY.** *This is a different paper from
> the JFQA 2025 CTREND item — different venue, different author list.* Over
> **3,900 coins spanning 2014–2022**, it **replicates 34 anomalies** and finds
> *"past winners consistently outperform losers"* with a magnitude that
> *"parallels that of its stock market counterpart."*

**This directly refutes the crypto-vs-equity premia-gap claim** — the published
statement is that the magnitudes are the **same**, not weaker. It also says factor
return autocorrelation *"is not widespread"* (a partial rebuttal to the §3.1
IAT concern). **ABOVE ALL ELSE: the largest documented crypto anomaly census is 34
anomalies, against Hou-Xue-Zhang's 447/452 for equities — a 13× difference in
search space, and the DSR penalty scales with it.**

> **Ali, Peng & Shams, "Unravelling cross-sectional patterns in cryptocurrencies:
> a four-factor asset pricing model,"** *China Accounting and Finance Review* 2025,
> doi [10.1108/cafr-06-2024-0077](https://doi.org/10.1108/cafr-06-2024-0077).
> **PEER-REVIEWED (Emerald), 0 citations. ABSTRACT ONLY.** 1,160 coins,
> Jan 2014 – Dec 2022, 468 weeks. Verbatim: *"**Contrary to the prevailing views,
> the observed reversal effect challenges the established momentum effect**"*, plus
> a significant illiquidity premium not explained by size. Runs 4 years past
> Liu-Tsyvinski-Wu's end. **A different model, not a replication — do not call it
> one.**

### 3.9 VERDICT Q3

**Costs do matter — but not for the reason the bull papers assume, and the
perps-specific evidence is a null.**

| evidence | direction | source quality |
|---|---|---|
| **Arefev (2026): net-of-costs cross-sectional momentum on Binance perps, 2020–2026, 832 symbols, 3 tests — NULL** | **bear** | working paper, 0 cites |
| **Zaremba et al. (IRFA 2021): the pattern IS the illiquid tail; sign flips on tradeable coins** | **bear** | peer-reviewed, 45 cites |
| **LTW (NBER 25882): 3 of 4 momentum spreads die if the short leg is BTC; +0.6%/wk insignificant below median size** | **bear** | working paper (JF version peer-reviewed) |
| **Ammann et al. (2022): 1-wk momentum VW 0.13%/wk, t = 0.13 over 417 weeks** | **bear** | working paper, 6 cites |
| **Grobys & Sapkota (2019): no significant momentum payoffs, 143 coins** — contradicted by Grobys (2019) at +8.76%/yr on 11 majors | **contested** | peer-reviewed both sides |
| **Fieberg et al. (QF 2023): 34 anomalies replicated, magnitude parallels equities** | **bull** | peer-reviewed, 10 cites |
| **Fieberg et al. (JFQA 2025): CTREND ~1.45 net, 28-indicator ML composite, 2015–2022 spot** | **bull** | peer-reviewed, 20 cites |

**The honest reading: the bull evidence is for a machine-learned composite on
broad, illiquid, 2014–2022 spot universes, at a cost model roughly 2× more
optimistic than a retail perp taker pays. The bear evidence is specifically about
*tradeable, cost-realistic, post-2020 perp* universes — which is the thing being
built.**

---

## 4. LISTING BIAS

### 4.1 What the literature has measured

Ammann et al. is the only study found that quantifies this directly. Full text
read. Sample: **3,904 cryptocurrencies, 07-Jan-2014 → 28-Dec-2021.**

| quantity | value |
|---|---|
| coins in sample | 3,904 |
| **delisted** | **1,222 = 39.5%** |
| surviving to 2021 | 2,682 |
| of delisted, delisting return = −100% | **932 = 76.3%** |
| **mean delisting return** | **−77.8%** |
| *comparison: Nasdaq-listed stocks* | *−55%* |
| delisting reason: abandoned by developers | **>64%**, mean return **−97%** |
| **annualised bias, value-weighted portfolio** | **0.93%** |
| **annualised bias, equal-weighted portfolio** | **62.19%** |
| weekly bias, value-weighted | 0.018% |
| weekly bias, equal-weighted | 0.934% |
| size premium overestimation in survivor-only sample | **50.3%** |
| **mortality rate, average 2014–2020** | **37.06%/yr** |
| mortality rate of the 2014 cohort | **75.15%** ("only every fourth crypto that existed in 2014 is still listed") |
| **share of dissolved coins that die within 60 weeks of listing** | **51%** |

### 4.2 The correct defence, and it is NOT a listing-age filter

**The measured bias is 67× larger under equal weighting than under cap
weighting (62.19% vs 0.93% per year).** The defence the literature supports is
therefore **weighting**, not filtering:

1. **Weight the cross-section by market cap (or inverse vol).** This removes
   ~98.5% of the measured bias. A minimum-history filter does essentially nothing,
   because it never re-admits a dead coin — the omitted return is the terminal
   −100%, and the damage is proportional to *weight*.
2. **If a listing-age filter is used, the literature's own number is 60 weeks,
   not 26.** 51% of dissolved coins die inside 60 weeks; a 26-week floor leaves
   the majority of the hazard window open. **But state the reason correctly:**
   this filter buys *attrition-hazard and data integrity* — avoiding a coin about
   to die, or one that has just migrated its contract — **not return information.**
   Liu-Tsyvinski-Wu test coin age explicitly as a cross-sectional characteristic
   and find a **null**: long-short (5−1) = **−0.005%/week, t = −0.358** (NBER WP
   25882 Table 7; *working paper* version, full text read — the JF 2022 version
   differs: JF says "Ten" characteristics, NBER says "Nine", so do not mix numbers
   between versions). **Age carries no return information; it buys a cleaner
   panel, not an edge.**
3. **Backfill, if you want the correction rather than the mitigation.** Ammann et
   al. used the full CoinMarketCap historical universe (3,904 coins), not the
   current listing. That is the standard route and it is the same source Fieberg
   et al. used. `exchangeInfo` genuinely cannot do this. **Arefev (2026) is the
   only study in this review that reports handling survivorship explicitly**, on
   **832 archived perp symbols** — which is part of why its universe is a fairer
   test of a *tradeable* cross-section than any of the spot papers.

Corroborated from the other side by Fieberg et al.: their headline portfolios are
explicitly **value-weighted**, the regression is fit by **value-weighted WLS**
"to mitigate the influence of micro-cap coins with minor economic significance,"
and their robustness figure is *"value-weighted portfolios only… to minimize the
influence of the tiniest cryptocurrencies."*

### 4.3 A nuance that cuts in the other direction, and it favours the design

Ammann et al.'s own annual attrition rate collapses over time: **2018 = 32.44%,
2020 = 0.46%, 2021 = 0.23%**, average 14.65%. The 62%/yr equal-weighted bias is
driven by the 2014–2019 vintage, when a large share of coins died. **A
Binance-perp cross-section is by construction a listing-survivorship-filtered
universe** — an exchange lists a contract only while it trades. The perps
universe is already closer to value-weighted-by-existence than the CoinMarketCap
micro-cap swamp. So the measured 62% figure is an **upper bound** for a perp
panel, and probably a severe one.

### 4.4 VERDICT Q4

**Yes, there is published work, it is one paper, it is not refereed, and it is
decisive on the weighting question.** Keep a minimum-history filter (it prevents a
new listing entering the sort — a separate defect) but **raise it to ≥60 weeks on
the literature's own hazard curve, and pre-register cap-weighted or inverse-vol
rather than equal-weighted.** Report the equal-weighted version as the diagnostic;
if the edge exists only there, that is the finding. The residual, irreducible
survivorship bias in a perps panel is **disclosable but not correctable** — the
repo's §3.8 rule stands.

---

## 5. LIQUIDITY

### 5.1 What is published

No dedicated paper giving a minimum 24h volume or orderbook-depth threshold for a
tradeable crypto cross-section was found in this session. **That is an evidence
gap, stated plainly, and an independent sweep confirmed it from a second
direction.** Three useful negatives from that sweep:

- **There is no published crypto Amihud cutoff.** Liu-Tsyvinski-Wu compute the
  measure as a *characteristic* and find it a **null**: long-short (5−1) =
  **+0.026%/week, t = 1.478** (NBER WP 25882 Table 7, working-paper version,
  full text read). The measure exists; nobody has proposed a level above which a
  coin is tradeable.
- **A second median-volume figure, for the canonical study:** Liu-Tsyvinski-Wu
  §2, verbatim — *"The mean (median) daily dollar volume in our sample is
  18,305.83 (103.89) thousand dollars"* → **median daily dollar volume
  US$103,890/day** in the mkt-cap- >$1M, 2014–2018 cross-section from which the
  three-factor model was estimated. (Fieberg's 2015–2022 median is $245,420/day;
  the two are reconcilable once the 2014–2018 vintage and the subsequent volume
  boom are accounted for.) **Neither figure is a current floor.**
- **Two citations in circulation appear not to exist.** "Bianchi & Babiak, *A
  dynamic model of liquidity in cryptocurrency markets*, JFE 2023" returns **no
  match on Crossref**; nor does "Bianchi & Babiak (2022), *On the performance of
  cryptocurrency factor portfolios*." The real papers are Bianchi, Babiak &
  Dickerson, *JBF* 2022, doi 10.1016/j.jbankfin.2022.106547, and Bianchi &
  Babiak, *JBF* 2022, doi 10.1016/j.jbankfin.2022.106467. **Do not repeat the
  fabricated titles.** Fieberg et al. cite the *real* 106547 paper as their cost
  source, so their cost assumption is traceable even where the hand-me-down
  version is not.
- **The task brief's Binance listing sub-numbers** (≥6 months listed, ≥100,000
  users, ≥50,000 DAU, ≥$5m ADV, ≥$1.5m spot notional ADV, top-100 CoinGecko,
  $5,000 min order) **were never in a source.** They read like exchange
  documentation but were not verified against it. **Treat every one as an
  unverified assertion.** Independent retrieval also failed: Wayback availability
  API on three URL variants → all `"archived_snapshots": {}`; CDX → `[]`; the
  Binance CMS JSON API → 403.

**Fieberg et al. Table 1** (full text read) — the sample they obtained a
published, cost-adjusted Sharpe of 1.94 from:

| year | coins | mean mcap ($m) | median mcap ($m) | mean volume ($k) | **median volume ($k)** |
|---|---:|---:|---:|---:|---:|
| 2015 | 74 | 135.1 | **2.53** | 1,197.9 | **9.75** |
| 2016 | 147 | 161.8 | 3.09 | 1,834.5 | 21.68 |
| 2017 | 773 | 436.6 | 9.08 | 18,744.1 | 126.34 |
| 2018 | 1,479 | 371.4 | 9.00 | 21,725.0 | 120.43 |
| 2019 | 1,237 | 269.2 | 5.32 | 69,245.4 | 143.35 |
| 2020 | 1,384 | 397.7 | 6.24 | 143,747.3 | 233.49 |
| 2021 | 2,213 | 1,382.0 | 13.71 | 187,546.8 | 571.95 |
| 2022 | 1,684 | 1,214.9 | 12.93 | 113,512.9 | 540.95 |
| **full** | **3,245** | 746.5 | **8.48** | 107,365.5 | **245.42** |

**The median coin in the headline result traded $245,420/day.** The 2015 median
was **$9,750/day**. The result is therefore *far more* illiquid than anything a
top-100 perp universe would be.

### 5.2 The published answer to "how many names and how liquid"

**Fieberg et al. Table 8** — the identical signal on progressively larger / more
liquid subsets, so the tradeability boundary is directly readable. H−L gross per
week, value-weighted:

| subset | by market cap | by Amihud illiquidity |
|---|---|---|
| keep 50% | 3.84% (t 5.00) | **4.36% (t 5.62)** |
| keep 30% | 3.46% (t 4.17) | 3.65% (t 4.21) |
| keep 20% | 2.74% (t 2.94) | 2.83% (t 2.87) |
| keep 10% | 2.51% (t 3.01) | 2.20% (t 2.76) |
| **top 100** | **3.39% (t 4.49)** | **3.30% (t 4.36)** |

**The effect is if anything stronger on the liquid half, and fully survives in a
100-name universe.** Ammann et al. independently find the same: the momentum
premium within survivors is 0.78% for the whole sample but **2.51% for the largest
100**.

### 5.3 VERDICT Q5

**A top-100-by-volume perp universe is far more conservative than the universe the
published result came from, and the effect survives it intact.** The demonstrated
tradability bar is **the top 100 by size or by Amihud liquidity** — not 500, and
not 5. Binance lists 527 trading USDⓈ-M perps, so 100 names is comfortably
available and the binding constraint (breadth for ranking) is solved.

**No published numeric volume floor exists.** If one is needed, derive it from the
repo's own measured cost curve rather than from the literature: pick the volume
floor at which `shark_hunter.config.round_trip_for(symbol)` stops exceeding the
conservative 30bp used by Fieberg et al. That is a defensible, repo-grounded
substitute for a threshold nobody has published. **Exchange listing criteria were
not retrieved** — `binance.com` FAQ pages are JavaScript-rendered and return an
empty HTTP 202 to `web_fetch`; the Wayback Machine was not reachable in-session.

---

## 6. WHAT WOULD KILL THIS — the falsification test

**The design principle: you are not searching for a marginal edge. You are testing
for the EXISTENCE of a large, already-published edge.** That is what makes the test
cheap, well-powered, and decisive — and it is why the `AGENTS.md` §1a
"can this test conclude?" objection, which correctly killed the Shark Hunter
forward test, does **not** apply here.

### Tier 0 — integrity, coverage, and COST audit (≈30 min, no strategy code, BLOCKING)

Before anything is computed, answer and assert:

0. **Measure this repository's realised round-trip cost on a top-100-perp basis.
   Do this first.** The entire bull/bear disagreement in this literature is a
   ~3–5× difference in the cost assumption (§8.1), and neither paper measures it.
   Re-derive `round_trip_for(symbol)` from order-book or trade data across the 100
   names, publish the distribution, and report the **breakeven cost at which the
   net spread goes to zero**. A test whose verdict flips between two published
   cost assumptions has not been run yet. This is the cheapest, highest-value
   action in the whole review.
1. **Panel depth.** For each of the top 100 USDⓈ-M perps by volume, how far back
   does `fapi/v1/klines` (1d) actually return non-empty data? Print the depth
   distribution. **The test needs ≥260 weekly rebalances** (5y). If the median
   depth is <156 weeks, stop and report that.
2. **Dead-signal guard** (`AGENTS.md` §3). Assert that each rebalance produces a
   non-zero number of long and short positions. A mask built with `&=` from all-
   `False` produces exactly zero and reads as "no edge" — that has already
   happened in this repo.
3. **Contract-migration scan.** Perps get replaced; the repo has already found a
   single day of **−1,374%** on the short leg of a spot momentum sort. Scan for
   daily returns beyond ±90% and adjudicate each one by hand before it enters a
   panel. Do not truncate silently.
4. **Funding is already excluded.** Measured funding cross-correlation is **0.627**
   with **PC1 = 66.9%** (`RESEARCH_STATE.md` §4). A funding-ranked cross-section
   is a one-factor bet on the exchange's administered median settlement. **Do not
   test funding as a cross-sectional signal** — this is already decided.

### Tier 1 — the replication spread (one afternoon, THE test)

**This is the cheapest test that can decide the question.**

- **Universe:** top 100 Binance USDⓈ-M perps by trailing 30d dollar volume, with
  **≥60 weeks** of continuous daily history (Ammann et al.'s hazard curve, §4.2).
- **Cadence:** weekly. Form at each Friday close, hold 7 days. **One return per
  rebalance.**
- **Signal:** plain trailing momentum at k ∈ {7, 14, 30, 60, 90, 120} days. Plus
  one oscillator (RSI) and one SMA-distance, because §1.5 shows they have
  **opposite signs** and running only one of them guarantees a wrong answer.
  **Publish the whole k-curve as a frontier. Do not select the best cell** — that
  is the multiple-testing error the whole exercise exists to avoid.
- **Formation:** long top quintile, short bottom quintile.
- **Weighting:** **report both inverse-vol and market-cap-weighted.** The
  equal-weighted version is a diagnostic only, per §4.
- **Statistic:** mean weekly H−L return; Newey–West HAC t with lag = k/7.
  Cost the net series with the Tier-0 cost curve times realised turnover
  (`TO` per Gu et al. 2020, the definition Fieberg et al. use).
- **Beta check:** regress the spread on the equal-weighted universe return. A
  book with |β| > 0.3 is a market bet, not a cross-sectional result. This is the
  failure mode the repo's own long-only −89% drawdown objection was really about.

**Pre-registered decision rule** (from `tools/xsect/falsification_power.py`,
5y weekly panel, n = 260, IAT = 1 because the statistic is already HAC):

| bar | rule | action |
|---|---|---|
| **KILL** | lower 95% bound on net annualised Sharpe **≤ 0.88** | cannot rule out zero after costs → **STOP** |
| **DECAY** | point estimate **< 0.50** | below the published median 1.19 after McLean–Pontiff's 58% post-publication haircut → **STOP** |
| **PROCEED** | point estimate **≥ 1.19 net** *and* lower 95% bound > 0.88 | survives at published-median strength → continue to Tier 2 |

**The reference point 1.19 is external**: the median annualised Sharpe of the best
published crypto cross-sectional factor across 55,296 design specifications with
a validation sample. It replaces the internal 0.95.

**Calibration:** on 260 weekly rebalances the test resolves a true Sharpe of
**1.26 at 80% power**, and the published net result is **~1.45**. So the test is
~80% powered to detect precisely the effect the literature claims. It will fire
reliably if the effect is absent, and correctly decline to fire if it is present.

### Tier 2 — only if Tier 1 passes (not part of the one-day decision)

Leg decomposition (long leg and short leg separately — a one-sided book is a beta
bet); betas against BTC and against the universe; per-decile monotonicity; and a
pre-registered forward holdout, which must be prospectively collected since
`FINAL_HOLDOUT_DO_NOT_TOUCH.json` records the holdout as burned.

### 6.1 VERDICT Q6

**The one-day test is Tier 0 + Tier 1: a weekly, quintile-sorted, value-weighted
long-short trend spread on the top 100 USDⓈ-M perps, over the full 5 years of
available history, reported as a frontier over lookbacks, with a pre-registered
one-sided decision against 0.88 / 0.50 / 1.19.** It costs one afternoon of
downloading and produces a verdict that is statistically capable of concluding —
which the prior 3-year, 5-symbol design could not.

---

## 7. Where the evidence is ABSENT

Stated plainly, because a documented absence is a finding:

1. **No published minimum 24h volume or orderbook-depth threshold** for a tradeable
   crypto cross-section. The only anchor is Fieberg et al.'s *demonstrated*
   tradability level (top 100 by size or Amihud), not a stated floor.
2. **No peer-reviewed study of a cross-sectional crypto factor that dies after
   realistic transaction costs.** Fieberg et al.'s 0.70–1.25% breakeven suggests
   the opposite at weekly cadence, but nobody has run the null.
3. **No post-publication decay study for crypto anomalies.** McLean & Pontiff's
   58% is an equities figure applied by analogy. The crypto decay rate is
   unmeasured, and it is a load-bearing number in the Tier 1 DECAY bar.
4. **No study of a perp cross-section specifically.** Every load-bearing source
   here is **spot** (CoinMarketCap). Whether spot cross-sectional premia transfer
   to perps is exactly what Tier 1 tests — it is not answered by the literature.
5. **Binance's own listing criteria were not retrieved.** `binance.com` FAQ pages
   are JavaScript-rendered and return an empty HTTP 202 to `web_fetch`, and the
   Wayback Machine holds **no snapshot** of `binance.com/en/support/faq/360047994851`
   (queried directly, with and without a 2024 timestamp — both empty). An
   exchange-imposed volume floor would be the cleanest available answer to Q5.
6. **The IRFA reversal paper cited in the task brief was not verified** in this
   session. The *size/liquidity* boundary it is said to describe is independently
   reproduced by Fieberg et al. Table 8 and Ammann et al. Figure 7 (§5.2), but the
   paper itself is unverified.
7. **The "crypto momentum" prior is unusable as a prior.** Two peer-reviewed
   papers by the same lead author, differing ~2× in citations, reach opposite
   conclusions on the same question (§3.4). Any argument of the form "momentum
   works in crypto, therefore this should work" rests on a literature that
   contradicts itself in print.
8. **No paper computes a required sample size or minimum detectable effect for any
   crypto cross-sectional factor.** Confirmed independently: OpenAlex
   `"power analysis cryptocurrency"` and `"minimum detectable effect"` return only
   mining/power-grid papers; arXiv `cryptocurrency AND statistical power` returns 8
   hits, all mining. **This is the central methodological gap** — the sample size
   in §2.3 had to be computed, not cited, and `tools/xsect/falsification_power.py`
   is that computation.
9. **No crypto paper applies an explicit multiple-testing correction to a
   cross-sectional factor.** The largest documented crypto anomaly census is
   **34** (Fieberg et al., *Quantitative Finance* 2023) against Hou-Xue-Zhang's
   **447/452** for equities — a **13× smaller search space**, and the DSR penalty
   scales with it. **Any crypto Sharpe quoted in the literature has not been
   deflated for a crypto-sized search.** This repo's own `E[max of 41,472]`
   deflation is, if anything, conservative for crypto.
10. **No peer-reviewed paper tabulates crypto factor returns against the
    corresponding equity factor returns in comparable $/month or %/month units.**
    The closest published statement (Fieberg et al. QF 2023) says the magnitudes
    **parallel** each other, not that crypto is weaker. **Kogan, Makarov,
    Niessner & Schoar, "Are cryptos different?"** (*JFE* 159, 2024) is a
    **retail-behaviour paper** — full text grepped: `"transaction cost"` 2×,
    `"bps"` **0×**, `"turnover"` **0×** — and reports **no factor long-short
    return in any unit**. **Do not cite it for a premia gap.**
11. **No paper decomposes a crypto factor return by listing cohort** (first week /
    first month / first 3 months of listing). The Liu-Tsyvinski-Wu *age* null is a
    cross-sectional characteristic test, not a decomposition. **How much of a crypto
    factor return comes from new listings is unmeasured.**

### 7.1 Corrections to citations encountered in this review

Strike or re-label these. Several read like primary sources and are not.

| citation as it circulates | status |
|---|---|
| "Bianchi & Babiak, *A dynamic model of liquidity in cryptocurrency markets*, JFE 2023" | **No Crossref match. Appears not to exist.** Real: Bianchi, Babiak & Dickerson, *JBF* 2022, doi 10.1016/j.jbankfin.2022.106547 |
| "Bianchi & Babiak (2022), *On the performance of cryptocurrency factor portfolios*" | **No Crossref match. Appears not to exist.** Real: Bianchi & Babiak, *JBF* 2022, doi 10.1016/j.jbankfin.2022.106467 |
| Kogan et al. (JFE 2024) as a crypto-vs-equity **premia gap** | **Misattributed.** Behaviour paper, no factor returns reported |
| Hou-Xue-Zhang multiple-test hurdle **\|t\| > 3.0** | **t = 3.0 is Harvey-Liu-Zhu's (2017 WP). The published HXZ hurdle is t = 2.78** (RFS 2020 abstract) |
| "58% post-publication decline" attributed to **Hou-Xue-Zhang** | **Not in HXZ** — full-text search: "post-publication" 0 hits. It is **McLean & Pontiff's** (and this repo's §3.15 already records that correctly) |
| HXZ anomaly count | **447 (WP) / 452 (published)** — cite whichever you use |
| Binance listing sub-numbers in the task brief | **Never in a source.** Unverified assertions that read like exchange documentation |
| **Fieberg et al. (JFQA 2025) CTREND** | **Genuine, peer-reviewed — but distinct from Fieberg, Liedtke, Metko & Zaremba, "Cryptocurrency factor momentum," *Quantitative Finance* 2023.** Different venue, different author list. Do not merge their results |

---

## 8. RECOMMENDATION

### 8.1 The prior has changed: run the test, but expect a null, and the test has already been run once

**The earlier framing in this document — "build the falsification test" — is right
but understates what is now known: the test has already been run, by someone
else, and it came back negative.**

Arefev (2026) executed precisely the Tier 1 design in §6 — top tradable Binance
USDⓈ-M perps, survivorship handled, pre-committed parameters, 2020–2026,
dependence-robust tests — and found **neither pre-committed specification yields a
net-of-costs spread distinguishable from zero under any of the three tests**
(§3.6). It is a 0-citation unreviewed preprint and cannot close the question. But
it is on-point in a way nothing else in the literature is, and it means the
question is no longer "is there an edge?" but **"does Arefev's null replicate on
this repository's cost model?"**

**That reframing is the single most useful output of this review**, because the
answer turns almost entirely on one number neither paper can supply:

| | cost assumption | implied per-trade cost at 68% weekly turnover |
|---|---|---|
| Fieberg et al. (JFQA 2025), bull case | 30bp long / 40bp short, from Bianchi et al. (2022) | **~30–40bp** |
| **Arefev (2026), null** | **0.40 pp/week aggregate** | **~59bp** |
| **This repository (`shark_hunter/config.py`)** | **12–18bp round trip** | **12–18bp** |

**The entire bull/bear disagreement is a factor of ~3–5 in the cost assumption,
and no paper measures it.** Arefev's implied per-trade cost is ~3–4× this
repository's measured perp round trip, and ~1.5–2× Fieberg's. So:

- **If this repository's 12–18bp is right, Arefev's null is a cost-model artefact
  and the gross spread survives.** Arefev's own gross J=1/K=1 spread is
  +0.573%/week ≈ **+30%/yr gross** — that is a real gross number.
- **If Arefev's ~59bp is right, the edge is gone and no design fixes it.**

**Therefore the cheapest, highest-value action is not the strategy backtest at all
— it is measuring this repository's actual realised round-trip cost on a
top-100-perp basis, from order-book or trade data, before anything else is
written.** That measurement converts the central disagreement from a literature
argument into a local fact, and it is the one input every downstream conclusion
depends on. Put it at the top of Tier 0.

### 8.2 What still stands from the earlier framing

The prior rejection was withdrawn for good reasons (the 0.95 bar was misapplied,
the drawdown objection was a long-only artifact, the IC band was unsourced). This
review does **not** reinstate it. The design remains untried *here*, and the
untried thing is cheap to try.

But the evidence in its favour is narrower than "cross-sectional momentum in
crypto works":

- the positive result is a **28-indicator machine-learned composite**, not a
  momentum sort, and it is **~1.45 net** on **value-weighted, 2015–2022, spot** data
  at a cost ~3× below Arefev's;
- **plain cross-sectional momentum is a null in that same paper's design sweep**
  (median Sharpe 0.83, significant in 49% of 55,296 specifications);
- **one-week cross-sectional momentum is a hard null on a bias-corrected
  3,904-coin sample** (value-weighted H−L 0.13%/wk, t = 0.13, over 417 weeks);
- **two peer-reviewed mechanisms say the crypto cross-section's return-persistence
  pattern is produced by the illiquid tail** (Zaremba et al. IRFA 2021) and that
  **3 of 4 momentum spreads die if the short leg is restricted to Bitcoin**
  (Liu-Tsyvinski-Wu) — and the illiquid short leg is exactly what a perp universe
  cannot replicate;
- and the **sign of a short-horizon "momentum" signal is a formula choice, not a
  horizon** — SMA-distance is reversal at t = −3.4, oscillators are momentum at
  t = +3.9.

**One piece of good news for the pilot:** Zaremba et al. find the largest, most
tradeable coins show **momentum where the broad cross-section shows reversal**.
The pilot's momentum result on 9 large perps is therefore the *predicted* sign for
a tradeable universe, not an anomaly — which is also exactly what Arefev failed to
replicate net of costs. Both can be true: the sign is right and the magnitude does
not cover the bill.

**None of this is a refutation. All of it is a specification — except Arefev,
which is a specification that has already failed once.**

### 8.3 The first falsification test, in one line

> **Download 1d klines for the top 100 Binance USDⓈ-M perps with ≥60 weeks of
> history; each Friday form a long-top-quintile / short-bottom-quintile book on
> trailing momentum for k ∈ {7, 14, 30, 60, 90, 120} days; weight inverse-vol and
> cap-weighted; report the whole frontier of weekly H−L Sharpe net of the measured
> per-symbol cost curve, with Newey–West t and the beta against the universe; and
> apply the pre-registered one-sided rule — STOP if the lower 95% bound is below
> **0.88**, STOP again if the point estimate is below **0.50**, continue only if
> it reaches **1.19 net** with the bound above 0.88.**

### 8.4 Three things that would make the test wrong, and to state in the report

1. **Do not report the equal-weighted result as the headline.** Ammann et al.
   measure the survivorship bias at **62.19%/yr** equal-weighted versus **0.93%/yr**
   value-weighted. Equal-weighting a crypto cross-section imports a bias larger
   than any plausible edge.
2. **Do not report a single lookback.** Publish the frontier. Selecting the best
   cell from six lookbacks is six tests, and `AGENTS.md` §3 exists for that reason.
3. **Do not charge a single 12–18bp cost constant across 100 names — and do not
   let the cost assumption decide the verdict by default.** Cost scales with size,
   and **the cost assumption is the single largest source of disagreement between
   the bull and bear papers** (§8.1). Measure this repository's own realised
   round-trip cost on a top-100-perp basis first, publish it, and show the
   breakeven cost at which the net spread goes to zero. A test whose answer flips
   between two published cost assumptions has not been run yet.

### 8.5 The one thing that would most change this recommendation

**The realised per-trade cost measurement in §8.1.** Everything else is
second-order relative to it. If this repository's true cost is near its assumed
12–18bp, Arefev's null is an artefact and the design proceeds. If it is near
Arefev's ~59bp, the line is closed regardless of what the gross spread is, and
the correct action is to stop.

If that cost question is settled and the answer is favourable, then the
discriminating result is Tier 1's: a large positive spread that is
**value-weighted and beta-neutral** moves the prior decisively positive and the
next step is a prospective holdout. A reproduction of Arefev's null or Ammann's
~0 **closes the cross-sectional line** — and the finding would be that spot
micro-cap premia do not transfer to perp majors at realistic retail costs, which
is itself a publishable negative and a genuine contribution, because Arefev is
0 citations and unreviewed.
