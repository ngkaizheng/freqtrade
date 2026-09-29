# Handoff prompt — paste this into a fresh session

> Self-contained. A new agent with working `web_search` credits can execute it
> cold. Save as `docs-myself/SESSION_HANDOFF_2026-09-26.md` and paste the
> block marked "BEGIN PROMPT".

---

BEGIN PROMPT

You are taking over a quantitative crypto research project at
`E:\FreqTrader\freqtrade`. Read `AGENTS.md` first — it is a working agreement,
and section 0 requires you to read and maintain `docs-myself/RESEARCH_STATE.md`,
the single source of truth.

**You have web-search credits; the previous session did not.** Verifying claims
it could not check is a large part of your value.

## 1. The single most important thing in this file

### 1a. The mechanism behind this project's Sharpe result is documented as ABSENT in Bitcoin

**Bouri, Azzi & Dyhrberg (2017), "On the return-volatility relationship in the
Bitcoin market around the price crash of 2013," *Economics* 11(1), article 2,
doi 10.5018/economics-ejournal.ja.2017-2, peer-reviewed, 168 Crossref citations,
CC-BY.** Verbatim from the deposited abstract:

> "The results for the entire period provide **no evidence of an asymmetric
> return-volatility relation** in the Bitcoin market... prior to the price crash
> of December 2013, **positive shocks increased the conditional volatility more
> than negative shocks. This inverted asymmetric reaction of Bitcoin to
> positive and negative shocks is contrary to what one observes in equities.**
> **As leverage effect and volatility feedback do not adequately explain this
> reaction**, the authors propose the safe-haven effect."

Note the last clause: they did not merely fail to find the leverage effect —
they **explicitly tested and rejected it** as the explanation for Bitcoin.

**The three-link chain, all independently verified:**

1. **Harvey et al. (JPM 2018)** — vol-targeting's Sharpe gain holds **only for
   risk assets**, and is linked to the leverage effect.
2. **Hood & Raughtigan (JPM 52(1), 2025)** — they attribute vol-targeting alpha
   **precisely** to the trend loading the leverage effect creates, and show it
   fails for commodities, fixed income and FX — the classes without the effect.
3. **Bouri et al. (2017)** — Bitcoin does not have the effect, and before 2014
   had its sign **reversed**.

> **Bitcoin sits in the failing group. E#8's Sharpe gain of 0.30 → 0.58 rests
> on a mechanism that a 168-citation peer-reviewed paper documents as absent in
> this asset.**

The return side is thin on its own terms too. **Ahmed, W.M.A. (2020), "Is
there a risk-return trade-off in cryptocurrency markets? The case of
Bitcoin," *Journal of Economics and Business* 108, doi
10.1016/j.jeconbus.2019.105886, peer-reviewed:** all realised volatility proxies
have a significant **negative contemporaneous** relation with Bitcoin returns,
but **weak** evidence of a negative **intertemporal** relation — and the
intertemporal one is the only thing that could make volatility a tradable
signal. **Do not upgrade it into a forward-looking edge.**

### 1b. The mechanism behind the DRAWDOWN result IS verified in crypto

**Gradojević & Tsiakas (2021), "Volatility cascades in cryptocurrency
trading," *Journal of Empirical Finance* 62, doi
10.1016/j.jempfin.2021.04.005, peer-reviewed:** "when moving from short to
long horizons, volatility cascades are **strongly asymmetric: high volatility at
short horizons is now likely to be followed by low volatility at long
horizons. These results are robust across time periods and cryptocurrencies.**"

**This is the mechanism a vol-scaled overlay actually exploits in this asset,
and it holds.** The three independent routes that reached this same split —
Harvey et al.'s asset-class condition, Yuyama et al.'s empirical "risk-adjusted
performance is mixed", and the absent leverage effect — all say the same thing.

### 1c. So the defensible framing is the opposite of the one the numbers invite

> **A strategy whose drawdown improves and whose Sharpe does not is a
> coherent, well-supported claim with a citable mechanism. A strategy whose
> Sharpe improves is a claim whose mechanism is documented as absent in your
> asset.**

Write it this way:

> "Volatility is mean-reverting across horizons in crypto (Gradojević &
> Tsiakas 2021), so a vol-scaled overlay reduces risk into spikes. But the
> return-side leverage effect that generates volatility-targeting alpha in
> equities is absent — and before 2014 inverted — in Bitcoin (Bouri, Azzi &
> Dyhrberg 2017), so an improved Sharpe should not be expected from the
> mechanism. In equities that Sharpe gain largely does not survive costs
> (Barroso & Detzel 2021) or real-time implementation (Cederburg et al. 2020)
> anyway, and where volatility-managed portfolios were found to work
> out-of-sample and net of costs, they were conditional *multifactor*
> constructions rather than scalar vol targets (DeMiguel, Martín-Utrera &
> Uppal 2024)."

**That is publishable, it is honest, and it is the opposite of "vol targeting
improved my Sharpe."**

### 1d. Modelling note before you interpret the lagged re-run

**Chaim & Laurini (2018), "Volatility and return jumps in bitcoin,"
*Economics Letters*, doi 10.1016/j.econlet.2018.10.011, peer-reviewed, ~190
citations:** jumps to **volatility are permanent** while jumps to mean returns
are contemporaneous only. A vol-target rule that reacts to a spike and then
holds a low weight into the aftermath is therefore **carrying a persistent low
weight** — it is not a temporary de-risking. Worth stating before interpreting
the lagged version's numbers.

### 1e. Two phantom citations — do not propagate them

- **Alexander & Heck, "The risk of price cascades in Bitcoin," doi
  10.1016/j.jfs.2020.101287 — the DOI does not resolve** (Crossref HTTP 404).
  The real paper is "Price discovery in Bitcoin," *J. Financial Stability*
  50:100776, doi 10.1016/j.jfs.2020.100776 — different paper, different topic.
- **"Volatility-Targeted Investment Strategies" (Baillie, Cochrane, Sullivan,
  Tivnan)** is not findable under that title. The verified parent is *Volatility
  as an Asset Class* (Palgrave), doi 10.3726/978-3-653-04787-5/14. **Use
  Moreira & Muir (JF 72(4), 2017) instead.**

## 2. The statistical problem this project cannot escape

The project has been asking "can I find a crypto strategy with net Sharpe
> 0.75?". **The answer to whether that question is even answerable with this
data is no**, and it comes from the project's own power machinery
(`tools/xsect/falsification_power.py`):

> At 5 years of weekly data, the detectable Sharpe at 80% power is **1.26** and
> the 95%-confidence KILL bar is **0.88**. **A true net Sharpe of 0.75 sits
> below both.** This sample cannot resolve the thing being asked about.

| | P |
|---|---:|
| you will produce a backtest **showing** net Sharpe > 0.75 | **50–60%** |
| that result is real, cost-adjusted, and survives | **2%** (1–5%) |
| for volatility targeting specifically: true OOS net Sharpe > 0.75 | **3–6%** |
| for volatility targeting specifically: the **drawdown reduction is real** | **~40%** |

> **Bet on the drawdown claim. Stop asking in Sharpe units and start asking in
> drawdown units, which is measurable.** The one mechanism that improved the
> objective is a *risk-sizing* result; every *signal* result was a null.

## 2. Where the project stands

North star: a repeatable, cost-adjusted, out-of-sample crypto edge, executed as
a risk-managed system.

Fifteen experiments. Full detail in `docs-myself/RESEARCH_STATE.md`; do not
re-derive these numbers.

| line | outcome |
|---|---|
| Strategy Factory V2 (92 preregistered hypotheses, 5 perps) | CLOSED, 0 survivors; framework not calibrated |
| Shark Hunter (volume/order-flow, 9 perps) | CLOSED. Gross real, net too thin |
| Cross-sectional momentum (E#6) | Wrong payoff shape: capture 0.39 up / 1.13 down |
| Time-series momentum, long/cash (E#7) | No 2022 protection (0.96x vs hold) |
| Price trailing stop (E#9) | **No information** — post-stop 20d return indistinguishable from a random day |
| Signal exit, 21–126d (E#10) | Best Sharpe seen (0.73 at 42d) but still −71% drawdown |
| Volatility targeting only (E#8) | **−83.6% → −33.4% drawdown** |
| **MOP proper (E#11)** | **+15.6% CAGR, −25.1% max DD, Sharpe 0.82, positive in 9/9 cells in 2022 when the basket lost 63.9%** |

**E#11 is the result that matters** (`docs-myself/E11_RESULT.md`). It is the
actual Moskowitz-Ooi-Pedersen construction — long-short, per-name inverse
volatility scaling, diversified across 1–12 month lookbacks, two-stage
portfolio volatility target — on the 50 most liquid Binance USD-M perps,
2020-01 → 2026-08, after a measured 13.6 bps round trip.

**Six look-ahead bugs have been found in this project.** E#8 and E#11 both had
a one-bar look-ahead in the volatility weight; both were fixed and **both
results survived**, with E#11 slightly improving. Assume a seventh.

## 3. Your tasks, in priority order

### TASK 1 — Measure underwater duration, and publish it

**Nobody has ever published the drawdown duration of a crypto strategy, for
any asset class.** The literature reports depth; nobody reports how long
recovery took. This is a clean, cheap, genuinely novel measurement that the
project can own.

**Lempérière et al. (arXiv:1404.3274) §4.3:** typical drawdown duration =
**1/Sharpe² years**. At Sharpe 0.82 that is 1.5 years; at 0.585, 2.9 years.
Context: Bitcoin's 2017 peak was regained **1,068 days (2.9 years)** later,
5 March 2024.

**Vedernikov, Liesiö & Seppälä (2024), "Portfolio Models for Optimizing
Drawdown Duration," *IJTAF* 27(2):2450014, doi 10.1142/S0219024924500146**
names this gap explicitly — developing models for drawdown duration "has
received **minimal attention** in the literature" — and shows a "clear
trade-off between minimizing drawdown duration and maximizing expected
returns." **That is the frontier paper. Nobody has drawn it for crypto, and
if you plot E#8/E#11's underwater time against return you are filling a gap it
explicitly names as empty.**

Write `tools/forward_measurements/underwater_duration.py`:
- for the frozen E#11 construction and for the E#8 vol-target construction,
  compute the equity curve and report: max depth, **longest underwater stretch
  in days**, number of distinct drawdown episodes, time-to-recovery
  distribution, and the ratio of observed duration to the 1/Sharpe² benchmark;
- compare max depth to the Brownian-motion theoretical anchor
  **E[MDD] = 2γσ√T, γ = √(π/8) ≈ 0.6267** (Magdon-Ismail, Atiya, Pratap &
  Abu-Mostafa, *J. Applied Probability* 41(1), 2004) — a check on the
  measured −33.4%;
- report the **worst** year for the frozen rule, not the average.

**Read this before interpreting any drawdown number in this project.** E#12
established that volatility targeting is a pure risk-scaling overlay: its Sharpe
is **invariant at 0.58 across every target and every scaling** (10%, 20%, 35%,
50%; normalised ×1, ×1.5, ×2). The grid in E#8 was one strategy at 24 risk
levels, not 24 strategies. Two consequences:

- The **Sharpe gain** (buy-and-hold 0.30 → 0.58, IAT-adjusted 0.55) is real
  and scale-invariant — that is the Moreira-Muir effect and it survives.
- The **drawdown gain is mostly de-risking.** At the canonical normalised
  setting (mean exposure 1.0) the max drawdown is **−69.0%**, barely better
  than holding. E#8's −33.4% came from running at **mean exposure 0.39** — a
  risk-budget choice, not a validated parameter. **A fixed 20% absolute target
  is not the canonical rule**: Moreira-Muir normalises so average leverage is
  about 1 and the target is endogenous. No canonical paper uses an absolute
  target and none validates 20%. Guo & Liu (SSRN 3385377, preprint) object to
  precisely that constant.

Also note **Moreira & Muir's Figure 3 says the failure mode is the opposite of
the intuition a fixed low target embodies**: "Our strategy takes relatively
more risk when volatility is low (e.g., the 1960's) hence its losses are not
surprisingly concentrated in these times." The danger is too much exposure in a
*quiet slide*, not too little during a noisy crash.

**And the scale is Gaussian-calibrated on a fat-tailed asset.** Cheng, Deng,
Wang & Yu (*Applied Economics* 53(47), 2021, doi 10.1080/00036846.2021.1922597,
peer-reviewed; free preprint arXiv:2102.04591) report force-liquidated BitMEX
investors at **average leverage ~60x**, and that "the normal distribution
assumption on return significantly underestimates margin levels by at least
50%" (measured daily excess kurtosis **65.36**). The normalised rule here runs
at **p99 exposure 2.00, max 2.30** — worth reporting against the 3x–5x margin
anchor their paper implies.

**The one positive worth building on:** **DeMiguel, Martín-Utrera & Uppal
(2024), "A Multifactor Perspective on Volatility-Managed Portfolios," *The
Journal of Finance*, doi 10.1111/jofi.13395, peer-reviewed, open access.**
Verbatim: "Cederburg et al. show that these strategies fail out-of-sample, and
Barroso and Detzel show they do not survive transaction costs. **We propose a
conditional multifactor portfolio that outperforms its unconditional
counterpart even out-of-sample and net of costs**... factor risk prices
generally decrease with market volatility." **The qualification is the point:
it is a conditional *multifactor* construction, not a scalar vol target.**
E#8 conditions on nothing but the asset's own realised vol. This paper is the
citable route to making the result stronger.

### TASK 2 — Retrieve five papers, in this order

1. **Hudson & Urquhart (2021), "Technical trading and cryptocurrencies,"
   *Annals of Operations Research* 297(1), 191–220, doi
   10.1007/s10479-019-03357-1.** Peer-reviewed, CC-BY, ~88 citations. ~15,000
   rules, multiple-hypothesis procedures, breakeven costs "substantially higher
   than those typically found in cryptocurrency markets", "protection against
   lengthy and severe drawdowns" — **and "no predictability for Bitcoin in the
   out-of-sample period."** The bps breakeven figure is paywalled and is the
   **only one in existence**. **The OOS clause is a direct hit on E#11 and is
   exactly what the forward test must settle.**
2. **Kaya & Mostowfi (2022), "Low-volatility strategies for highly liquid
   cryptocurrencies," *Finance Research Letters* 39, doi
   10.1016/j.frl.2021.102422.** Peer-reviewed, CC-BY. Abstract fragment:
   *"selects cryptocurrencies based on their historical volatility and is
   complemented by a simple stop-loss rule."* **The only published crypto
   strategy combining volatility control AND a stop-loss.** Verdict unknown.
   This is the closest analogue to the failed E#6/E#9 line.
3. **Detzel et al. (2021), *Financial Management* 50(1), doi
   10.1111/fima.12310.** Crypto **and** matched equity universes in one
   framework, price-to-MA ratios, "economically significant alpha and Sharpe
   ratio gains relative to buy-and-hold" in both. This is the direct
   crypto-vs-equities benchmark answer.
4. **Deprez & Frömmel (2024), *International Review of Economics & Finance*
   93, 858–874, doi 10.1016/j.iref.2024.05.003.** 75,360 rules, net of cost,
   FDR (Storey 2002 / Romano-Wolf in the reference list), out-of-sample,
   **positive on Bitcoin spot**. Get the numbers: surviving-rule count, net
   Sharpe, t-stat, breakeven cost.
5. **Anghel (2022), "No pain, no gain: You should always incorporate trading
   costs for a bias-free evaluation of trading rule overperformance,"
   *Economics Letters* 216, 110584.** The cost-quantification companion to the
   2021 anchor negative.

### TASK 3 — Build the forward test

This is the only thing that settles E#11.

- Freeze the construction as written in `PREREGISTRATION_E11.md` and
  `e11_mop.py`. **Pre-commit the cell now, before seeing forward data**:
  **15%/15%** (Sharpe 0.78, −19.7% DD) and **20%/20%** (Sharpe 0.82, −25.1%
  DD) are both registered as alternatives; do not pick between them later.
- Write `user_data/forward/run_frozen_strategy.py`: read
  `klines_1d.csv.gz`, apply the frozen construction, append one row per day to
  `frozen_equity.csv` with date, signal, position, daily return, running
  equity, realised vol, exposure used.
- **Re-assert causality by truncation** (`AGENTS.md` §3): recompute on a
  truncated panel, assert shared bars are bit-identical.
- Schedule it with the existing `freqtrade-forward-collect` task.
- **Pre-register the decision rule before data arrives.** Suggested, to be
  confirmed or replaced in writing: a Sharpe measured on the forward period
  that is materially below the backtest number, or a drawdown that breaches
  −25.1%, is a FAIL regardless of the t-statistic.

### TASK 4 — Analyse the accumulating cost data

`user_data/forward/depth_snapshots.csv.gz` is appended daily by
`freqtrade-depth-collect`. Once there are enough snapshots, report the
**distribution** (median, p10, p90) of the measured round-trip cost at
$10k/$50k/$250k, and say whether the single 2026-09-26 snapshot E#8/E#11 used
(3.6 bps mean at $10k) was typical. Every result in this project is priced off
that one number.

## 4. The published record, in brief

Full detail in `RESEARCH_STATE.md` §3.29 and §5a. The load-bearing items:

- **Anghel (2021), *FRL* 39:101655** — the anchor negative. Applies **White's
  Reality Check (2000) and the Politis-Romano stationary bootstrap** to crypto
  technical rules. After snooping control and frictions, "statistically
  significant positive excess returns are **rarely achieved**" and "trading
  rules **mostly capture market risk premiums**". **This is the equities-standard
  correction, run on crypto exactly once, returning a null.**
- **Hudson & Urquhart (2021)** and **Deprez & Frömmel (2024)** are positive —
  **and they do not use Anghel's procedure.** That is the most likely
  explanation for the field's disagreement.
- **Alexander & Dakos (2019), *Quantitative Finance* 19(9):** *"Less than half
  the cryptocurrency papers published since January 2017 employ correct data."*
- **The >1,000-citation crypto survey is RETRACTED.** Corbet, Lucey,
  Urquhart & Yarovaya, *IRFA* 62 (2019) — Crossref title is literally
  `"RETRACTED: ..."`, retraction registered 2019-03-01 and **again by
  Retraction Watch 2026-02-01**. 1,009 citations remain attached. **Do not
  build anything on it.** (Its sibling *FRL* papers are separate works and are
  not retracted.)
- **No peer-reviewed crypto strategy study on perpetuals exists.** Verified:
  `abs:"perpetual" AND abs:"trading strategy" AND abs:"Sharpe" AND
  abs:"cryptocurrency"` → **0, ever.** Nor a weekly-horizon result, nor a crypto
  volatility-targeting study, nor a crypto Kelly study, nor a crypto
  drawdown-duration statistic. **The full absence map with exact query strings
  is in `RESEARCH_STATE.md` §3.29 — re-run those, do not re-search.**
- **Lempérière et al. (arXiv:1404.3274)**: trend-following Sharpe 0.80 futures
  since 1960 — **reported with NO costs modelled, P&L explicitly "fictitious"**.
  Lookback plateau 2–10 months (0.80 → 0.76), decaying after. 126 days ≈ 4
  months is inside the plateau, so E#7's null was genuine. A 3-day futures
  trend "completely disappeared since 2003".
- **Hsieh (2023), IFAC-PapersOnline:** a hard drawdown limit "becomes a
  stop-loss order, which may miss the profitable follow-up opportunities" — the
  published mechanism for why the stop family fails.
- **Harvey et al. (JPM 2018) split the vol-targeting claim**: the Sharpe benefit
  is asset-class specific; **the left-tail benefit is general** — "left-tail
  events tend to be less severe because they typically occur at times of
  elevated volatility, when a target-volatility portfolio has a relatively small
  notional exposure." **Keep the drawdown result, discount the Sharpe result.**
- **The three-paper rebuttal chain on the Sharpe claim**: Cederburg et al.
  (JFE 2020, 103 equity strategies) — vol-managed portfolios "do not
  systematically outperform" and reasonable out-of-sample versions earn **lower**
  Sharpe; Liu, Tang & Zhou (**JPM 46(1), 2019, 38–51** — *not* 45(4)) —
  correcting the look-ahead makes the drawdown **68–93%**; Barroso & Detzel
  (JFE 2021).
- **DeMiguel, Martín-Utrera & Uppal (2024), *Journal of Finance*, doi
  10.1111/jofi.13395** answers them: a **conditional multifactor** vol-managed
  portfolio "outperforms its unconditional counterpart even out-of-sample and
  net of costs." Conditional on being a *multifactor*, not a scalar target.
- **The levelling is Gaussian on a fat-tailed asset.** Cheng et al. (2021) force-
  liquidated BitMEX investors averaged **~60x** leverage; normal assumptions
  "underestimate margin levels by at least 50%" (daily excess kurtosis 65.36).
- **Petukhina, Trimborn, Härdle & Elendner (2021), *Quantitative Finance*
  21(11), doi 10.1080/14697688.2021.1880023**: adding liquidity constraints
  makes "out-of-sample performance drop considerably, while the
  **diversification benefits persist**" — the same asymmetry this repo measured
  (the carry/funding drag kills the return, not the diversification).
- **Burggraf (2021), *Finance Research Letters* 38:101523** — hierarchical risk
  parity beats risk-minimisation on **tail-risk-adjusted return** out-of-sample
  on crypto. It is the one peer-reviewed crypto precedent for a correlation-
  aware overlay; report a tail metric, not a max drawdown.
- **Hoyle & Shephard (SSRN 3279787) is a PREPRINT, not peer-reviewed.** Its
  statement is the cleanest theory of why vol targeting sometimes fails: the
  Sharpe improvement "is not automatic and depends on the **convexity of the
  precision** and the **covariance of the precision and conditional mean**."
- **MacLean, Thorp & Ziemba is *Quantitative Finance* 10(7) (a page-verified
  lookup gives 10(7):681–687), doi 10.1080/14697688.2010.506108.** The widely
  circulated "*Risk* 23(2):51–57" version **does not exist** — *Risk* is a
  practitioner magazine, minted no DOIs for 2010, and Crossref returns zero.

**A provenance pattern worth recording.** Two arXiv preprints —
**arXiv:2602.11708** ("Talyxion Research, Hanoi"; Sharpe 2.41 / maxDD −12.7% on a
trailing stop) and **arXiv:2511.13239** (same affiliation, same contact
address; Sharpe 5.72 / drawdown 4.56% on a **30-day** sample) — both report
figures their sample lengths cannot support. **If either is cited as evidence
that a trailing stop or a vol overlay works in crypto, that is the reason not
to.**

**Dead fruits** — full list with citations in `RESEARCH_STATE.md` §5b. Short
version: price-based trailing stops; very-short-horizon trends; crypto momentum
as a whole; funding/basis carry; >10-month lookbacks; full Kelly; leverage
≥5x; the Ulcer Index as a contribution; exchange-reported OI and liquidation
feeds (Giagkiozis & Said, *Ledger* 9, 2024: OI "systematically misquoted" by
large exchanges, forced-trade messages delayed); cost-blind perp backtests.

## 5. Rules you must not break

- **Read `AGENTS.md` and `docs-myself/RESEARCH_STATE.md` first.** They contain
  a dozen traps already paid for in time.
- **Do not run another backtest variant on the same 200-symbol download.** It
  has been looked at fifteen times. Each extra look launders a failure into a
  success — that pattern was caught twice in the previous session.
- **An information coefficient is not an edge.** E#4 measured a Spearman IC of
  −0.038, t = −8.03; the actual decile long-short portfolio earned +0.0059%/day
  with t = +0.14 and a cumulative loss of 26%. Always report the portfolio.
- **A claim you cannot verify must be labelled unverified.** The previous
  session invented a cost figure and a "liquidity provision premium" that
  turned out to be Zaremba et al., *IRFA* 81:101908 (2021), five years earlier
  and already in this repo's own §3.27.
- **Do not cite arXiv:2602.11708** ("Talyxion Research, Hanoi": Sharpe 2.41 /
  maxDD −12.7% on a trailing stop). Serial self-publisher selecting assets on
  the data it fits; own no-optimisation ablation Sharpe 1.34; **bear-regime
  Sharpe −0.31**.
- **Update `docs-myself/RESEARCH_STATE.md` before finishing** — status table,
  measured constants, traps, next actions, change-log row.

## 6. Tooling

- `.venv\Scripts\python.exe`, Python 3.11, pandas 3.0, numpy 2.4, scipy,
  pyarrow, pypdf, **pytest 9.1.1 + xdist + mock**.
- Suite: `.venv\Scripts\python.exe -m pytest tests/tools/ -q --no-header -p no:cacheprovider`
  (243 passing).
- `web_fetch` **refuses PDFs** — download with `requests`, read with `pypdf`.
- If `web_search` dies: `lite.duckduckgo.com/lite/?q=` (CAPTCHAs after ~10),
  `api.crossref.org/works/<DOI>` and `?query.title=`,
  `export.arxiv.org/api/query?search_query=abs:"phrase"` (best for establishing
  absence), `api.semanticscholar.org/graph/v1/paper/DOI:...`,
  `ideas.repec.org` (clean finance abstracts, no paywall),
  `web.archive.org` (recovered a 2019 press release no live site carries).
- Binance: `data.binance.vision/data/futures/um/monthly/klines/{SYM}/1d/` and
  `fapi.binance.com/fapi/v1/depth?symbol=X&limit=1000`.

## 7. The one thing that matters

**~2% that a real edge is there; ~50–60% that a backtest will appear to show
one.** That gap is the entire project.

Nothing on this list closes it except TASK 3, the forward test. More backtests
on the same panel do not, and the literature cannot be used to justify stopping
— it only tells you what has already failed.

END PROMPT
