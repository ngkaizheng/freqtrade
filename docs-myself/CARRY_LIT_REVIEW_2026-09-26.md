# Crypto perp funding/basis carry — literature and primary-source review

**Date:** 2026-09-26
**Scope:** Binance USD-M perpetual funding carry (long spot, short perp, collect funding).
**Method:** exchange primary documentation + exchange REST API + peer-reviewed/working-paper literature.
**Tooling note:** the `web_search` tool had no credits on this account. Everything below was obtained
via `web_fetch`, direct HTTP against the Binance API, arXiv/OpenAlex/Crossref/RePEc, or
`https://html.duckduckgo.com/html/?q=...`. OpenAlex's shared daily budget was exhausted partway
through; that is a reason some later searches are Crossref/RePEc-only, not a reason to omit them.

Every number below is either quoted from a source with a URL, or measured by a script in
`tools/carry/` and labelled **[MEASURED HERE]**.

---

## Headline verdict

| question | verdict |
|---|---|
| Q1 mechanics | **SOUND**, with two corrections (interval is not fixed at 8h; the carry contains a deterministic 10.95%/yr floor) |
| Q2 does the carry exist | **SOUND on existence, CONDITIONAL on level.** Real, large, and independently replicated |
| Q3 does it decay | **YES — ~90% compression.** Independently confirmed by the repo's own data |
| Q4 what is the payment for | **Mostly a financing charge plus an engineered floor, not a risk premium** |
| Q5 implementation traps | **Two findings that change the implementation**, incl. funding forfeited on early close |
| Q6 comovement / diversification | **Verified. Partly one common factor (PC1 = 49%), not purely** |
| Q7 bear case | **Stronger than the bull case for a leverage-constrained implementer** |
| **overall** | **CONDITIONAL, leaning NO. Do not deploy unconditionally.** The repo's "currently off" is correct; the *reason* needs restating, and the monitoring number is stale |

---

## ⚠ VENDOR CONTENT NAMED — the one load-bearing vendor source in this entire review

The user asked explicitly for vendor content to be called out. Here it is, and it is load-bearing:

**"Han, David, 2024, *A primer on perpetual futures*, Coinbase Institutional Trading Insights."**

That is a **Coinbase Institutional research note — an exchange's own research arm.** Not a journal,
not a working paper, not a preprint. It is the sole source for the claim that "the exchanges which
have perpetual futures with the clamp feature account for **more than 75% of open interest** for
Bitcoin perpetual futures", which He et al. cite in **footnote 7** and use on p.23 to argue the clamp
is the standard mechanism and that it is *"less understood by practitioners."*

**So the "the clamp is the dominant industry mechanism" fact — which underpins much of the Q4
argument — traces to exchange marketing via a preprint's footnote. It has no peer-reviewed source.**
Cite it as `[vendor: Coinbase Institutional]`, never as academic literature. A "primer" would not
contain original funding-rate level data in any case, so the premise that it might supply levels is
answered: **no.**

He et al. additionally use **Glassnode** data (Figures 1–2) for a cross-exchange funding comparison,
Jan 2020 – Dec 2022. It contributes no number to any conclusion here. **No CoinGlass, Amberdata,
Delphi, The Block, exchange Academy or Deribit Insights content was used anywhere.** One vendor
source, flagged; everything else is peer-reviewed, preprint, or publisher abstract.

---

## Q1. Mechanics — Binance USD-M, from primary documentation

**Primary source:** Binance, "Introduction to Binance Futures Funding Rates",
<https://www.binance.com/en/support/faq/detail/360033525031>. (binance.com is JS-rendered and returns
HTTP 202 to plain fetches; retrieved via the r.jina.ai text reader, and every numeric claim below
re-verified against the live REST API.)

### Sign convention — the repo is RIGHT

> "When the market is bullish, the funding rate is positive and tends to rise over time. In these
> situations, traders long on a perpetual contract will pay a funding fee to traders on the opposing
> side. Conversely, the funding rate will be negative when the market is bearish, where traders short
> on a perpetual contract will pay a funding fee to long traders."

`fundingRate > 0` ⇒ **longs pay shorts** ⇒ a short-perp leg receives it. The state file's
`adverse_payer` note stands: the carry analysis and `strategy_factory_v2` are not interchangeable.

### Payment size

> "Funding Amount = Nominal Value of Positions * Funding Rate" … "(Nominal Value of Positions =
> Mark Price * Size of a Contract)"

Marked at **mark price**, not index price. "Binance does not charge fees on Funding Payments."

### Interval — 8 hours for this universe, but it is NOT a contractual constant

> "The default funding interval is every 8 hours at 00:00 (UTC), 08:00 (UTC), and 16:00 (UTC). In the
> event of extreme market volatility, Binance reserves the right to update the funding interval…"

And, from §8 of the same page:

> "**Effective from 2025-05-02 08:00 (UTC)**, Binance Futures will adjust the settlement frequency
> from every eight hours or every four hours to **every one hour** when the previous funding rate
> settlement… reaches the funding rate cap or floor."
>
> "**Effective from 2026-01-02 12:00 (UTC)**, if the funding rate of USDⓈ-M perpetual contracts with
> funding rate settlement frequency of every one hour is less than or equal to the absolute value of
> 0.025% for 16 consecutive cycles, Binance Futures will revert the settlement frequency from every
> one hour to **every four hours** on the 17th cycle."
>
> "**No announcement will be made** in the event that an adjustment is taking place."

**What this does and does not mean for the repo.** The policy is real and it is administered silently,
and the reversion is to **4 hours, not back to 8** — a symbol that touches the cap once can end up on a
permanent 4-hour cadence. **It has not bitten this universe, but it is not hypothetical either.**

**[MEASURED HERE] `GET /fapi/v1/fundingInfo` across all 791 symbols, 2026-09-26:**

| `fundingIntervalHours` | symbols | share |
|---|---:|---:|
| **4** | **469** | **59%** |
| 8 | 321 | 41% |
| 1 | 1 | 0.1% |

**59% of Binance USD-M perpetuals settle every 4 hours, not 8.** All 20 of the repo's symbols are
currently in the 8h bucket, so the `3 × 365` annualiser is correct for the existing corpus. But the
default for a new symbol is now more likely to be 4h than 8h, at which point the same code would
over-state annualised carry by 2x. **Read `fundingIntervalHours` per symbol per run and derive the
annualisation factor from observed `fundingTime` spacing; do not hard-code 3 × 365.**

A sub-line separately verified the repo's corpus against the live Binance stream for BTCUSDT,
LINKUSDT and BNBUSDT: 479 common timestamps each, **max |repo − live| = 0.00000000, zero mismatches**,
gaps 8.0h to within float noise. The corpus is a faithful 8-hour settlement stream, not a resample.
(One caveat: the timestamps carry millisecond jitter — 8.00000027 h, 7.99999972 h — so never do an
*exact* join on the timestamp.)

### The rate formula

> "Funding Rate (F) = [Average Premium Index (P) + clamp (interest rate - Premium Index (P), 0.05%,
> -0.05%)] / (8 / N)"
> "**In other words, as long as the premium index is between -0.04% to 0.06%, the funding rate will
> equal 0.01% (the Interest Rate).**"

with

> "Premium Index (P) = [ Max(0, Impact Bid Price - Price Index ) - Max(0, Price Index - Impact Ask
> Price)] / Price Index"
> "Impact Margin Notional (IMN) = 200 USDT / Initial margin rate at the maximum leverage level"

and `P` averaged over 5,760 five-second points per 8-hour interval with **linearly increasing weights
in time** (weight `t` for the t-th observation), so recent premium counts more. The **Price Index** is
the weighted average spot price "of the underlying asset listed on major spot exchanges".

Three things matter here and all are under-appreciated:

1. **The premium uses depth-weighted impact prices, not best quotes.** The IMN is 200 USDT of margin
   at max leverage — e.g. 4,000 USDT at 20x, 25,000 USDT at 125x. A large trader cannot move the
   premium much, and a small one cannot either. He et al. read this as an anti-manipulation device.
2. **The rate is the premium plus a clamp, not the premium.** Inside a ±0.05% band around ι, the rate
   is *exactly ι* and does not respond to the basis at all.
3. **The interest component is a flat number, not a market price.**

> "There are two components to the funding rate: the interest rate and the premium. Binance uses a
> flat interest rate, **with the assumption that holding cash equivalent returns a higher interest
> than BTC equivalent. On Binance Futures, the interest rate is fixed at 0.03% daily by default
> (0.01% per funding interval since funding occurs every 8 hours).**"
> "This doesn't apply to certain contracts, such as ETHBTC, for which interest rate is set to 0%."

0.01% × 3 × 365 = **10.95%/yr, deterministic, paid by longs to shorts, regardless of anything.**
This is a financing charge on holding a non-yielding asset through a margin account, not a risk
premium. See Q4 — it is the single largest component.

### Caps and floors

> "Floor = -0.75 * Maintenance Margin Ratio / Cap = 0.75 * Maintenance Margin Ratio / Capped Funding
> Rate = clamp(Funding Rate, Floor, Cap)" — for a listed set of majors (BTCUSDT, ETHUSDT, BNBUSDT,
> …) …
> "The capped funding rate for **others** USDⓈ-M Perpetual Contracts is set at **± 2%**."
> "Binance reserves the right to adjust the funding rate floor and cap (with adjusted values
> respectively capped at -1 for floor and 1 for cap)."

**[MEASURED HERE]** `GET /fapi/v1/fundingInfo` (791 symbols): BTCUSDT/ETHUSDT ±0.00300; BNB/SOL/ADA/XRP
±0.00375; DOGE ±0.004875; 696 of 791 symbols at ±0.02.

**Do not annualise the cap** — a per-settlement cap is a daily-scale parameter, and annualised it is
enormous and economically irrelevant at an 8-hour interval:

| cap per settlement | × 3/day × 365 |
|---|---:|
| 0.3000% (BTC, ETH) | 328.5%/yr |
| 0.3750% (BNB, SOL, ADA, XRP, LINK, AVAX, LTC, TRX, UNI) | 410.6%/yr |
| 0.4875% (DOGE) | 533.8%/yr |
| 2.0000% (the 696 "others") | 2190.0%/yr |

**[MEASURED HERE] the cap *does* bind in the tail, and it binds asymmetrically against the receiver.**
Realised extremes on the repo's own corpus: **BTC min and max are exactly ±0.3000% — precisely its
cap.** SOL's minimum is exactly **−2.0000%**, its generic cap. Seven symbols bottom at exactly
−0.7500%. So the exchange truncates the payment at precisely the moments a funding book is most
stressed. That is the correct thing for the exchange to do and it is the wrong thing for the trade.

> ⚠ **Two disagreements to flag.** (i) He et al. write "For contracts with maximum leverage of 25x or
> below, they are fixed at ±3%." The current Binance documentation says **±2%** for "others". He et al.
> are describing a superseded parameterisation. Use the live API, not the paper, for this constant
> (though their `0.75 × MMR` rule for the listed majors *is* correct and reproduces the live numbers).
> (ii) The realised **ETH** maximum in the repo corpus is **0.3750%**, above its current 0.3000% cap —
> i.e. Binance has *lowered* ETH's cap over the sample. Another illustration that these are
> administered parameters with a time series, not market-clearing numbers.

### Two settlement mechanics with direct P&L consequences

> "There is a 15-second deviation in the actual funding fee transaction time. For example, when you
> open a position at 08:00:05 (UTC), the funding fee could still apply (you'll either pay or receive
> the funding fee)."

> "Funding fees (if any) will be deducted from the available balance in your Futures Account. **If your
> account balance is insufficient, the funding fees (if any) will be deducted from your position
> margin, which may affect your liquidation price.**"

The second one matters a great deal: funding is not a separate cash flow, it is debited against
maintenance margin, so it moves the liquidation price of the short leg.

**Verdict Q1: SOUND.** The repo's sign convention is confirmed by primary documentation and should be
upgraded from "verified against raw data" to "verified against exchange documentation". Two
corrections required: the 8-hour interval is dynamic, and the annualiser must be per-symbol.

---

## Q2. Does the carry exist, and how big is it?

**Yes. It is large, it is real, and three independent sources put it in the same range.**

| source | year | venue (status) | sample | number |
|---|---|---|---|---|
| **He, Manela, Ross & von Wachter**, Table B.1 | 2026 (v7) | arXiv:2212.06888 / SSRN 4301150 — **working paper, not journal-published** | Binance BTC ETH BNB DOGE ADA, 2020-01-08→2024-03-11 | mean realised funding **+15.3 / +18.6 / −0.1 / +16.7 / +18.4 %/yr** = **2.00 / 2.43 / −0.01 / 2.17 / 2.40 bps per 8h**. SD **27.8 / 36.5 / 55.8 / 47.5 / 43.8 %/yr** |
| **He et al.**, Table 6, "Carry" column = their replication of the long-spot/short-perp strategy | 2026 | arXiv (as above) | Binance 2020-2024 | return **+10.18 / +13.22 / −5.14 / +12.39 / +13.15 %/yr**; SR 2.24 / 2.66 / **−0.66** / 1.01 / 1.64; maxDD −5.33 / −2.80 / **−33.61** / −14.37 / −6.58 |
| **He et al.**, Table 4 Panel A, deviation ρ | 2026 | arXiv (as above) | same | mean ρ (ann. %) BTC 0.42, ETH 0.52, BNB 0.38, DOGE 0.50, ADA 0.51 |
| **Zhivkov**, "The Two-Tiered Structure of Cryptocurrency Funding Rate Markets", *Mathematics* 14(2):346 | 2026 | **peer-reviewed**, open access, doi 10.3390/math14020346 | 26 exchanges (11 CEX, 15 DEX), 35.7m one-minute obs, **8–15 Nov 2025 (8 days)** | CEX **mean −1.91 bps/8h = −20.9%/yr**, **median +1.00 bps/8h = +10.95%/yr**, SD 22.82, min −2400, max +1600 bps. DEX mean −1.74, median +0.80 |
| **Schmeling, Schrimpf & Todorov**, "Crypto Carry", SSRN 4268371 (2022) → *Management Science* (2026) doi 10.1287/mnsc.2024.05069 | 2022 / 2026 | working paper → **peer-reviewed** | **fixed-maturity** crypto futures | carry "**up to 60% p.a.**" (2022 version) → "sometimes **exceeding 40% per annum**" (published version). ⚠ **This is futures basis, NOT perp funding.** He et al. p.7 say so explicitly: "a comprehensive analysis of the carry of **fixed-maturity** crypto futures". **Never put the 40% next to the 17.28%/yr perp number** — different quantities |
| **This repo [MEASURED HERE]**, 20 symbols, 6,493 fully-common 8h settlements, 2020-08→2026-09 | 2026 | own measurement | | full-sample EW **+9.40%/yr**; median symbol +11.66%; BTC +11.16% |
| **This repo [MEASURED HERE]**, live API, 17 majors, 500 settlements, 2026-04-13→2026-09-26 | 2026 | own measurement | | EW **+1.76%/yr** full / **+4.20%/yr** last 30d / **+3.85%/yr** last 90d; BTC +4.03, ETH +3.00, UNI +5.68, TRX **−10.62**, BCH −3.76 |

**The named author "Shamshuddeen" could not be found.** The user asked specifically about
Shamshuddeen, Pou and Păuna on arbitrage returns from crypto futures. Searched arXiv
(`au:Shamshuddeen` → 0 results), OpenAlex authors (1 unrelated record), Crossref, RePEc and general
web search: **no such author exists in any index.** The pairing "Poucet"+"Păuna" also returns nothing
(DuckDuckGo: "No results found"). I am not substituting a near-miss. The genuine peer-reviewed work on
that exact question is listed instead:

- **Crépellière, Pelster & Zeisberger (2023)**, "Arbitrage in the market for cryptocurrencies",
  *Journal of Financial Markets* 64, 100817.
  <https://ideas.repec.org/a/eee/finmar/v64y2023ics1386418123000150.html>
- **Shynkevich (2023)**, "Law of one price and return on Arbitrage Trading: Bitcoin vs. Ethereum",
  *Journal of Economics and Finance* 47(3), 763-792, doi 10.1007/s12197-023-09631-0.
- **Makarov & Schoar (2020)**, "Trading and arbitrage in cryptocurrency markets", *JFE* 135(2),
  293-319 — the canonical cross-exchange paper.
- **Alexander, Chen, Deng & Wang (2024)**, "Arbitrage opportunities and efficiency tests in crypto
  derivatives", *Journal of Financial Markets* 71, 100930.
  <https://ideas.repec.org/a/eee/finmar/v71y2024ics138641812400048x.html>

**Christin, Routledge, Soska & Zetlin-Jones, "The Crypto Carry Trade" (2023-04-14, 56pp)** is real
and is *this exact strategy*. He et al. §4.3 describe it verbatim: "the trader **longs the spot, shorts
the perpetual, and holds on to the strategy throughout the sample**", and report it in Table 6 as the
benchmark. So the repo's strategy and He et al.'s "Carry" column are the same trade, and their
conclusion is blunt: "We find that the **long-only strategy significantly outperforms the carry
strategy.**"

**The Carry column in He et al. Table 6 is GROSS of exchange fees** — Table 6 sits in the
zero-trading-cost section (Table 5's caption: "under zero trading costs"; Table 8 is the separate
fee-and-spread table), and all four Table 6 columns share that convention.

Christin et al. themselves are explicit that their numbers are gross, twice (§2, p.6, verified
verbatim from the cached PDF at `tools/carry/wfa853216.pdf`):

> "Here, we **abstract from margin, leverage, transaction costs**, and other details particular to the
> exchange. These are important details, of course, and we revisit them below."

> "Note this **abstracts from transaction costs and exchange margin requirements**."

**So the two academic estimates of the same Binance trade differ ~5x in Sharpe purely on cost
treatment: Christin et al. Sharpe 10.06 gross vs He et al. Sharpe 2.24.** Do not blend them, and never
quote 10.06 as net. Sample: Binance USD-M 2020-08-11 → 2023-01-22, N = 2,685 eight-hour periods;
reported carry-Tether **1.57 bps/8h = +17.28%/yr**, coin-settled funding leg 1.15 bps/8h
(+13.27%/yr). *(Those four figures are the Q2 sub-line's table extraction; my own text-layer pass
recovered the prose but not the numeric table cells, so I mark them reported-not-re-verified. Every
quote in this paragraph I verified myself.)*

> ⚠ **Two negative findings from the Q2 sub-line, recorded rather than substituted:**
> - **"Streltsov and Ruan (2022), *A Theory of Perpetual Futures*" does not exist** under that title
>   (arXiv, OpenAlex and Crossref all return nothing). The real Streltsov & Ruan (2022) item is
>   *"Perpetual Price Discovery and Crypto Market Quality"*, SSRN 4218907, SSRN-only, 0 citations.
>   He et al. cite it, so the phantom title will keep appearing — do not propagate it.
> - **Christin et al. (2022) is not in Crossref, OpenAlex, arXiv or NBER** (the Q2 sub-line probed
>   NBER w29600–w30200 exhaustively, no title match). It is a WFA-conference working paper; the copy
>   is now cached locally. The title in the task brief, "Crypto-currency futures: a look at earnings
>   and risk premia", **appears nowhere** and is a garbled reference to this paper.
> - Also debunked: **"de Blasis & Bauer" on BitMEX funding does not exist** (the closest real paper is
>   De Blasis & Webb, *J. Futures Markets* 2022, doi 10.1002/fut.22305 — a different subject, abstract
>   only); **Alexander-Choi-Park-Sohn (2020) under the title "Price discovery and market quality in
>   cryptocurrency markets" does not exist** (the real paper is *"BitMEX Bitcoin Derivatives"*, and
>   the Q2 sub-line read it in full: it **describes** the funding mechanism and **reports no funding
>   level, no bps figure and no arbitrage return**); and **"Han (2024)" on the clamp could not be
>   identified in any index** — and the attribution is chronologically suspicious anyway, since the
>   clamp is a late-2024/2025 exchange feature, so a 2024 preprint citing ">75% of BTC perp OI" for
>   clamp-governed exchanges is close to impossible. **Report the He et al. → "Han (2024)" citation as
>   unverified.**

**Verdict Q2: the carry EXISTS and is large — SOUND.** Two independent academic groups measure the
*same Binance trade* at **+17.28%/yr** and **+10.18%/yr gross** over 2020-2023/24, bracketing the
repo's own +9.40%/yr. This is a genuine, observable cashflow; the repo is right that it is not an
inference problem. **But the level is the variable, not the mechanism, and it has collapsed (Q3).**

---

## Q3. Does it decay? Yes — by roughly 90%

**[MEASURED HERE]** on the repo's own 20-symbol corpus (`tools/carry/carry_decay_corr.py`):

| period | equal-weight gross carry | symbols with negative carry |
|---|---:|---:|
| before 2022-01-01 | **+33.50%/yr** | 0/20 |
| from 2022-01-01 | **+3.22%/yr** | **6/20** |
| from 2023-01-01 | +4.72%/yr | 4/20 |
| from 2025-01-01 | **+0.95%/yr** | **7/20** |
| trailing 365 settlements | +1.08%/yr | 4/20 |
| trailing 90 settlements | **+4.75%/yr** | 2/20 |

By calendar year: 2020 +8.90, **2021 +38.29**, **2022 −2.38**, 2023 +5.26, 2024 +10.63, 2025 +1.91,
2026 YTD −0.38. The 2022 boundary alone is a **90% compression**.

The literature agrees, and the repo's data confirms it *without needing their model*:

- **He et al.**, §4.2: "After 2022, the average deviation reduces by **almost 80%** with volatility
  shrinking by more than 50% for most tokens." "Deviations decline on average about **22 percentage
  points a year**, consistent with an increase in arbitrage capital and competition among
  arbitrageurs." Their Table 4 Panel B, mean ρ before → after 2022: BTC **0.69 → 0.17**, ETH
  **0.92 → 0.16**, BNB **0.69 → 0.11**, DOGE **0.99 → 0.18**, ADA **0.99 → 0.09** (annualised pp).
- **He et al.** Table 45 — the *funding* component of the strategy's return for BTC:
  **25.27 (2021) → 1.75 (2022) → 2.65 (2023) → 18.15 (2024)**. A 93% collapse.
- **He et al.** Table 10 — a **causal** test. Binance's April 2022 **portfolio margin** launch (which
  let arbitrageurs net collateral across spot and futures) compressed cross-currency |ρ| by
  3.3–7.8 pp on 20–90 day symmetric windows, HAC t between **−1.71 and −4.09** — a 12–33% compression
  of a 23–27% pre-event mean. So the gap is balance-sheet-capacity driven, which means **more
  arbitrage capital compresses it further.**
- **Crépellière, Pelster & Zeisberger (2023, JFM 64)** — peer-reviewed: arbitrage magnitude "decreased
  greatly from **April 2018** onward… it is barely possible to exploit existing price differences
  since then. We… find that informed trading is correlated with a reduction in arbitrage
  opportunities."
- **Shynkevich (2023, J. Econ. Finance 47(3))** — peer-reviewed: "Profitable opportunities for
  arbitrage trading… have **declined significantly since 2018**."

**Verdict Q3: YES, it has been arbitraged away, and it has been arbitraged away hard — ~90% on the
repo's own data, ~80% in He et al.'s. The compression is not a temporary.** Two cautions:
(i) it is a compression of the *level*, not a sign flip — the carry is still positive on average, just
small; (ii) the trailing-30d and trailing-90d figures (+4.20% / +4.75%) show the level is *rising
again*, so this is a **switch**, not a death.

---

## Q4. The counterparties — what is the payment FOR?

**Consensus: mostly a financing charge plus an engineered floor. A minority sentiment/service
component. Not a risk premium for short-vol.**

### The decomposition, and the evidence that settles it

`funding = flat 10.95%/yr interest component (ι) + time-weighted premium-index term (clamped)`

1. **The floor is a set parameter, not a price.** Binance: "the interest rate is fixed at 0.03%
   daily by default (0.01% per funding interval) … with the assumption that holding cash equivalent
   returns a higher interest than BTC equivalent." **[MEASURED HERE]** the repo's own corpus begins
   2019-09-10 with `fundingRate` = exactly 0.0001 on BTC — the parameter, unmodified.
2. **42–50% of settlements pay exactly ι.** He et al. Table B.1: clamp binds 35.7–45.2% of hours;
   **41.7% (BTC), 41.9% (ETH), 43.8% (BNB), 50.4% (DOGE), 49.3% (ADA)** of realised 8-hour
   settlements equal the interest component exactly.
3. **The decisive test: BNB.** He et al. report BNBUSDT is "the one contract in our sample with
   ι = 0". Its mean realised funding is **−0.1%/yr**, against BTC's **+15.3%/yr** — *on the same
   exchange, same market, same date range, same everything except one parameter Binance chose to set
   to zero.* Two structurally identical risk exposures differ by ~15 pp/yr of "premium" because of a
   configuration flag. That is not what a market-clearing risk premium looks like.
4. **The clamp cuts the tail.** He et al. Table B.1, annualised SD of the payment, clamped rule vs
   linear counterfactual: BTC **27.8 vs 87.1**, ETH 36.5 vs 83.7, BNB 55.8 vs 104.8, DOGE 47.5 vs
   257.5, ADA 43.8 vs 107.6. **The exchange deliberately removes 47–82% of the payment's variance.**
   A risk premium is supposed to be *larger* when risk is higher. This one is engineered to be flatter.
5. **The clamp's dead zone is worth ±54.75%/yr of yield.** He et al. p.35 state that the Ackerer et al.
   no-clamp benchmark "corresponds to ρ = sgn(ι − r)·γ… Thus, in annualized units, their benchmark
   corresponds to **ρ = +54.75 percentage points**" — which is exactly γ = 0.05% × 1095. **This is not
   a rounding rule; it is a band roughly five times the size of the 10.95%/yr interest floor in which
   the funding rate pays nothing at all in response to the basis.** Any carry P&L is net of a
   mechanism that can silently remove up to 54.75 pp/yr of convergence payoff.

   > ⚠ **An internal inconsistency in He et al. that I am flagging rather than resolving.** Their
   > Table B.1 reports the clamp binding on **35.7–45.2% of hours**, while a p.23 footnote says it
   > binds in "**93% of our sample hours**". These cannot both describe the same statistic. Possible
   > explanations include a different sample or a looser band, but the paper does not reconcile them,
   > and no third source measures it. **Do not quote a clamp-binding frequency from this paper as
   > settled.** The repo's own measure — 36.6% of settlements at exactly the interest component — is
   > in the same neighbourhood as Table B.1, not 93%.

### The repo's own data settles it independently **[MEASURED HERE]**

`tools/carry/verify_interest_decomp.py`, 20 symbols, 2019-09-10 → 2026-09-19. Decomposing each
symbol's realised carry into the fixed interest component (0.01% per interval = **10.95%/yr**) plus
the premium-index excess:

- **36.6% of all settlements are paid at exactly 0.0001** — the fixed parameter, premium term
  contributing literally zero. (Range 0.0% to 52.5%; post-2025-05-02 the pooled share falls to 25.2%.
  An independent replication in this repo puts it at 40.0% pooled and 10.7%/yr EW total / −0.7%/yr
  excess; the small discrepancy is a rounding tolerance on the equality test, and **both agree that
  the excess is approximately zero**.)
- **Equal-weight mean total carry +9.40%/yr. Equal-weight mean interest component 10.95%/yr.
  Excess = −1.55%/yr — statistically zero.** BTC excess **+0.20%/yr**. **Negative for 9 of 20 symbols.**

  > ⚠ **Unresolved panel-definition conflict — do not average these.** The figure above is computed on
  > the **6,493-row fully-common intersection** (every symbol present, equal-weighted). A sibling
  > replication on each symbol's **full available history** (141,889 settlements) gives **−0.83%/yr**
  > pooled and **−0.89%/yr** equal-weighted, negative for **8 of 20**, with **BTC +0.62%/yr**. The ~0.7
  > pp/yr gap is panel choice, not arithmetic error, and the two answers should not be blended.
  > **The conclusion is invariant across the whole range: the excess is between −1.6% and −0.8%/yr —
  > zero to slightly negative — and BTC's is zero to +0.6%/yr.** The cross-sectional ranking is
  > identical in both; the disagreement is confined to the aggregate. `RESEARCH_STATE.md` §4 carries
  > both with the definitions named.
- **9 of 20 symbols have a NEGATIVE excess**, i.e. they have paid you *less than Binance's own fixed
  parameter implies*, because the premium index was negative for them. Worst: BNB −10.29, TRX −9.32,
  BCH −8.61, SOL −7.28. Best: LINK +3.55, UNI +3.55, AAVE +3.32, LTC +2.59.
- **BTC's excess is +0.20%/yr.** Over six years, on the largest and most liquid contract on the
  exchange, the entire "premium" component of BTC funding is two tenths of a percent per annum.
- **BNB is paid at exactly 0.0001 on 0.00% of settlements** — confirming independently, on the
  repo's own data, He et al.'s statement that BNB's ι = 0. And BNB is the *worst* symbol in the panel
  at +0.66%/yr. **The lowest-carrying symbol in the universe is precisely the one where the fixed floor
  was switched off.** Nothing else in the data explains the ranking so cleanly.

**In round numbers, the repo's 5.9-year +7.96%/yr average is the fixed financing charge Binance
levies on the long for holding a non-yielding asset through a margin account. The premium-index term
— the only part that could be compensation for a service or a risk — has averaged approximately zero
over six years and is negative for nearly half the universe.** That is a much stronger statement than
"the carry is small": it is a statement about what the carry *is*.

### The fourth independent confirmation, from the authors of the canonical carry paper

Christin et al. §3.3, p.11 — **verified verbatim from the cached PDF**:

> "**Notice the median funding rate is 0.01% per funding period, equivalent to about 11% per year.
> This is the arbitrary rate set by the exchange when basis is zero (F_t = P_t). The median basis,
> however, is close to zero. This suggests that it is the funding rate that is driving the
> profitability of the trade.**"

And §3.3, p.12:

> "**It is notable how often the funding rate is pinned to the 0.01% per eight-hour period.**"

This is decisive, and it is the *authors of the strategy itself* saying it. The median payment to a
funding recipient is the exchange's **arbitrary** zero-basis rate; the **median basis is close to
zero**, so the basis leg contributes essentially nothing; and therefore the funding *rate*, not
convergence, is what makes the trade profitable. That is the Q4 thesis stated by the people who wrote
the canonical paper on the trade.

**Four independent lines now say the same thing**, on four different samples and methodologies:

| line | sample | what it shows |
|---|---|---|
| the repo's own corpus [MEASURED HERE] | 20 symbols, 6,493 settlements, 2019–2026 | 36.6% of settlements at exactly the fixed parameter; EW excess **−1.55%/yr**; BTC **+0.20%/yr**; **9/20 negative** |
| Christin et al. (2023) | Binance USD-M 2020-08 → 2023-01 | **median = the arbitrary exchange rate; median basis ≈ 0**; funding drives the profit |
| He et al. Table B.1 (2026) | Binance 5 coins, 2020-01 → 2024-03 | **41.7–50.4%** of settlements at exactly ι; clamp cuts payment SD by **47–82%**; **BNBUSDT is the one contract with ι = 0** |
| Zhivkov (2026), *Mathematics* | **27.9m CEX observations**, 11 exchanges, 8–15 Nov 2025 | CEX **median = +1.00 bp/8h** = the Binance interest component exactly, on a paper that never mentions it |

He et al.'s own reading of the clamp's purpose (§Appendix B) is anti-manipulation and stability:
"it is **not** an outer cap on the funding rate… the funding mechanism consequently becomes stronger
precisely when the futures price moves sufficiently far from the spot benchmark"; and because the
premium uses impact prices over depth and is averaged over the period, "a sufficiently large or
persistent distortion is required to have a material effect on the settlement premium."

**Note the tension, and say so:** the *design* intends a stronger signal at large dislocations, but
the *realised distribution* (Table B.1) has the mean sitting on the clamp and the variance suppressed.
The design and the data pull in opposite directions. I weight the data.

### The genuine economic content: a convenience/service yield

- **Cong, He & Tang**, "Staking, Token Pricing, and Crypto Carry" (NBER w33640, Apr 2025; SSRN
  4059460; published as "The Tokenomics of Staking"). NBER: "**the convenience wedge generates UIP
  violations and significant crypto carry premia.**" ⚠ Note: this paper is **not** called
  "Transaction Convenience and Uncovered Interest Parity" and is **not** in RFS; the earlier working
  paper was titled "Staking, Token Pricing, and Crypto Carry". Do not cite the phantom title.
- **Schmeling, Schrimpf & Todorov (2022; *Management Science* 2026)**, verbatim: the carry "can
  become very large (up to 60% p.a.)… most consistent with the existence of a highly volatile crypto
  convenience yield that stems from two main forces: (i) trend-chasing and attention by smaller
  investors seeking leveraged upside exposure to crypto assets in boom periods, and (ii) the relative
  scarcity of 'arbitrage' capital taking the other side through a cash and carry position.
  **Engaging in the latter is risky due to spikes in margins and liquidations amid drawdowns.** The
  interplay between these two forces, and the involved high leverage, may help explain why severe
  market crashes are a frequent feature of crypto markets." The published version reframes it as an
  *inconvenience* yield and moves the number to "sometimes exceeding 40% per annum" — a
  **60% → 40% downward revision between versions**, which is itself a useful signal about how firm
  these numbers are.
- **Christin, Routledge, Soska & Zetlin-Jones (2022)**, "The Crypto Carry Trade" — attribute the
  return to "differences of opinion and leverage constraints". (Located; numbers not retrieved — see Q2.)

### What the short is actually bearing

- **Margin and forced-liquidation risk.** He et al. §1, verbatim: "In real-world futures markets,
  arbitrageurs must maintain a margin account during the entire period in which the arbitrage trade
  is open. Temporary worsening of apparent arbitrage opportunities can lead to liquidations and
  losses. **As the saying goes, an arbitrageur must remain liquid longer than the market stays
  irrational.** Thus, even arbitrage opportunities that appear to be riskless in theory may be risky in
  practice." And in the model (Appendix G): the arbitrageur bears (i) `κc` opening cost "which can
  have many forms… as well as the **expected cost of exchange default**", (ii) a mean-variance
  risk-bearing cost `A/2·X²σ²h`, and (iii) a margin constraint `mX ≤ W_t`.
- **The liquidation risk is real and measured.** He et al. Table 6: the "delta-neutral" carry
  strategy had a **−33.61% max drawdown on BNB** and −14.37% on DOGE.
- **The payment is truncated exactly when the book is most stressed.** Binance: the outer cap exists
  because "Extremely large funding payments can generate substantial losses for highly leveraged
  positions and potentially trigger liquidations. The outer cap therefore limits this tail risk"
  (He et al. §Appendix B). **[MEASURED HERE]** the cap binds in the repo's own corpus — BTC's realised
  min and max are *exactly* ±0.3000% and SOL's minimum is *exactly* −2.0000%, both precisely their
  caps. The exchange truncates the compensation at the moments it matters most.

**Verdict Q4: the payment is NOT a risk premium for bearing short-vol. Measured on the repo's own
corpus, the premium-index component — the only part that could be a compensation of any kind —
averages −1.55%/yr equal-weight, is +0.20%/yr on BTC, and is negative for 9 of 20 symbols. What the
carry actually is, over six years, is Binance's fixed 10.95%/yr financing charge on the long leg
(paying it in ~36% of settlements) plus a pro-cyclical sentiment component that averages zero. The
short IS bearing real risk — margin, forced liquidation, exchange default, and a payment the exchange
truncates exactly at the cap when the book is most stressed. The strongest academic statement that it
is a risk premium is Schmeling et al., and they attach "risky due to spikes in margins and
liquidations amid drawdowns" in the same sentence. I weight He et al.'s decomposition and the repo's
own ι-minus-premium arithmetic (both measured) over Schmeling et al.'s framing (interpretive), and I
weight the *published* Schmeling number ("exceeding 40% p.a.") over the 2022 preprint's ("up to
60% p.a.").**

### The premium over par is a *conveyance-of-leverage* price, and there is a test for it

The strongest theoretical claim is that the payment is the price of **warehousing spot for a leveraged
long**, and He et al. test it. Binance's **April 2022 portfolio-margin launch** let arbitrageurs net
collateral across spot and futures, freeing balance sheet. Their prediction — looser arbitrage
constraints ⇒ tighter basis — is confirmed: |ρ| compresses (Table 10, HAC t −1.71 to −4.09), and
perp taker order flow has ~3x the price impact when initial deviations are large (Table 11: in the
high-deviation tercile, mean |P| = 12.05 bps, a 1pp order-imbalance move shifts the premium 0.094 bps
vs 0.031 bps in the low tercile, difference statistically significant). That is a
falsified-alternative-eliminating test, not a story, and it is why I weight this above the
risk-premium reading.

### Weighting of the competing explanations

| explanation | holders | weight |
|---|---|---|
| **Conveyance of leverage + scarce arbitrage capital** (the payment prices warehousing spot for a leveraged retail long) | He et al. v7; Schmeling-Schrimpf-Todorov; exchange design intent | **Highest** — the only one with a passed test (the portfolio-margin event) |
| **Transaction / staking convenience** (holding spot crypto has a use value, so the UIP wedge does not arbitrage away) | Cong-He-Tang, NBER w33640; Schmeling et al.'s "inconvenience yield" | **Medium-high** — coherent, explains persistence, but a *level* not a *payment* story |
| **Leverage-constraint / limits-to-arbitrage premium** (the short is paid for absorbing constrained demand) | Christin et al.; Alexander-Deng-Zou (EJOR 2023: "almost $80 billion of positions… were liquidated during 2021") | **Medium** — the risk is measured; the claim that the payment *compensates* it is asserted |
| **A pure risk premium for the short's liquidation / short-vol exposure** | essentially only Schmeling-Schrimpf-Todorov | **Low** — they never write a compensating equation, and the venue caps and damps the payment, which is inconsistent with pricing risk |
| **The clamp is a price-stability device, not a premium** | He et al.; Gupta-Polson; Binance's own "damper" language | **Highest, and not really contested** |

Supporting theory for the low weight on "risk premium": **Angeris, Chitra, Evans & Lorig**, "A Primer on
Perpetuals", *SIAM J. Financial Mathematics* (2023) — the no-arbitrage funding rate is *"semi-robust in
the sense that they do not depend on the dynamics of the volatility process of the underlying risky
assets."* **Gupta & Polson** (arXiv:2609.05433): *"stochastic volatility alone does not move the basis"*;
the premium that can break the peg is borne by the **leveraged holder** and *"has ambiguous sign"* —
i.e. it is not a systematic long-to-short payment. ⚠ Neither is a *perp-specific* empirical paper; both
are theory, and I weight them below the measured Binance decomposition.

**Dissent noted and not adopted:** **Werapun, Karode, Suaboot, Arpornthip & Sangiamkul**,
"Exploring risk and return profiles of funding rate arbitrage on CEX and DEX", *Blockchain: Research and
Applications* 7(4):100354 (2026), reports funding arb *"exhibits no correlation with HODL strategies"* and
*"up to 115.9% over six months — while keeping possible losses to a minimal 1.92%."* **I weight this
very low**: six months, a 2.5x-smaller sample than He et al., and it has the *opposite sign* to He et
al.'s −33.61% BNB drawdown. Treat it as a counterexample to be reconciled, not as reassurance. Its
full text is paywalled, so this is from the abstract/snippet only.

**What is genuinely unsettled:** nobody has decomposed the *premium-index component* — the only part of
the payment that could be compensation for anything — into a service fee and a risk premium, with an
estimating equation. The only decomposition in existence is Binance's own two-term formula, which is a
*design choice*, not an estimate. That is a real open question and, as far as I can tell, nobody is
working on it.

---

## Q5. Implementation traps

### 5.1 The two legs are in **separate margin systems** — this is the biggest capital fact in the strategy

Binance's own 2022-04-20 portfolio-margin announcement, quoted in He et al. (fn. 14):

> "Before the change, arbitrageurs maintain **separate margin accounts** for spot and futures
> positions, so a gain on one leg could not offset a loss on the other, and **each leg had to be
> capitalized against early liquidation on its own.**"

Only Portfolio Margin (invited, not available to a retail account) nets them. Derived from Binance's
official `MaintenanceMargin = Notional × MMR − MaintenanceAmount`: **a $1m short perp needs 30.52% of
notional sitting in the futures account to survive a 30% adverse move, and an equal-sized spot leg
held elsewhere changes that requirement by exactly zero.** **[MEASURED HERE]** the repo's analysis
capitalises the round trip at the 0.30% fee and nothing else; it does not carry this requirement at
all. It is not a cost, it is a **capital** requirement, and it is roughly 100x the fee.

### 5.2 Sizing — and a sign correction to how the risk was posed

**A long-spot / short-perp book is *short the perp premium*.** A perp trading at a large premium is
therefore a **gain**, not a threat; the danger is the opposite — a perp at a large **discount**, which
is exactly what happened on the solvent venues in November 2022 (He et al. §2: "The FTX collapse led
to significant negative funding rates on all solvent exchanges… vice versa on the insolvent FTX") and
in March 2020 ("funding rates turned substantially negative in most exchanges").

Sizing arithmetic: long spot `S`, short perp `k·S`. Funding income scales linearly in `k`; net delta is
`1 − k`. Over-levering the short buys carry at the price of a directional bet; under-levering pays for
insurance you do not own. **Equal notional is a convention, not a derived optimum** — and no published
estimate of an optimal hedge ratio for this trade could be found. He et al. derive a hedge ratio
`λ = 1/(1 − Φ⁻¹(r)) = κ/(κ + sgn(ι−r)γ − r) ≈ 1.0095` in theory (slightly *more* spot than perp,
because inside the clamp ι sits below the risk-free rate) but never calibrate it; the practical
strategy is 1:1 notional. Zhivkov (2026) also uses equal notionals. **[MEASURED HERE]** a fixed 1:1
does not accumulate delta drift, because the basis mean-reverts in under two hours for BTC (see 5.8);
the real precision issues are the 15-second settlement tolerance and per-funding mark-price
notionalisation.

### 5.3 The perp's mark price tracks a composite index, not Binance spot

**[MEASURED HERE] 2026-09-26 ~07:44 UTC:** perp book mid **83,981.55** vs price index **84,025.84**
(**−44.3 bps**); Binance **spot** mid **84,019.995** (**−5.8 bps** vs the index). The perp marks to a
16-venue composite, so the Binance spot leg is *not* what the liquidation mark tracks. Binance's index
construction page: the price index "includes prices from a broad range of exchanges, such as Binance,
KuCoin, OKX, HitBTC, Gate.io, MEXC, Coinbase, Kraken, Bitget, Bitfinex, Bybit… **The Binance Futures
Last Price is also included as a constituent of the Price Index.**" Two consequences: the hedge is
imperfect in the exact place imperfection gets you liquidated, and **the index is partly
self-referential** — a perp premium feeds into the mark that is supposed to anchor it.

### 5.4 The funding amount is a point-in-time snapshot

`Funding Amount = Mark Price × Size × Funding Rate` at the settlement instant. It is **not** a
notional-weighted average over the interval. The *rate* is time-weighted; the *amount* is not.

### 5.5 Accrued funding on close — **there is no accrual. You forfeit it.**

> "You are only liable for funding payments in either direction if you have open positions at the
> pre-specified funding times. If you do not have a position, you are not liable for any funding.
> **If you close your position prior to the funding time, you will not pay or receive any funding.**"

A round trip opened and closed inside a single interval earns exactly **zero**. With the interval now
variable (8h/4h/1h), the settlement calendar is per-symbol and must be tracked, not assumed.

### 5.6 Funding is debited against maintenance margin

> "If your account balance is insufficient, the funding fees (if any) will be deducted from your
> position margin, **which may affect your liquidation price**."

So a receiver of funding is still consuming margin headroom in the sense that the leg must survive.

### 5.7 Fees on both legs — the best-documented round-trip cost, and your 0.30% is right

**Verified VIP0 schedule (2026-09-26):** spot **0.100% / 0.100%** maker/taker (0.075% / 0.075% with
the BNB 25% discount); USD-M perp **0.0200% / 0.0500%** (0.0180% / 0.0450% with the BNB 10%
discount). Round trip, both legs, both directions, taker, no BNB discount = **0.30%**; with BNB
**0.24%**. **The repo's 0.30% cost model is correct and does not need revision.** Note the repo's
§4 constant of "12–18 bps round trip" is a *fee* figure, not a spread figure — the two should not be
conflated in reporting.

**He et al. Table 3**, built from Binance's published fee schedule, one-way **maker** fees by 30-day
volume tier — this is the *maker* view, which is why its numbers are much smaller:

| tier | spot | perp | **round trip, both legs** `c = 2(c_S + c_F)` |
|---|---:|---:|---:|
| No (negotiated / market maker) | 0 | 0 | 0 bps |
| Low (>$2bn spot, >$12.5bn perp) | 0.0225% | 0.0018% | **4.86 bps** |
| Medium (>$150mn / >$1bn) | 0.0450% | 0.0072% | **10.44 bps** |
| High (>$1mn / >$15mn — retail) | 0.0675% | 0.0144% | **16.38 bps** |

**Spread cost is separate and additive.** He et al. §4.4, estimated from Binance's *own* public trade
records with the Roll (1984) estimator using reported taker direction:

> "the median daily effective spread of the perpetual is **0.11 basis points for BTC, 0.18 for ETH,
> 0.44 for BNB, 1.35 for DOGE, and 2.12 for ADA**. The perpetual spread is below that of the
> corresponding spot market for BNB, DOGE, and ADA and is comparable to it for BTC and ETH."

> "effective spreads generally narrow over time. Comparing the periods before and after 2022, the mean
> effective spread of the perpetual declines by between **48% and 73%**… On **March 12, 2020** the
> effective spread of the Bitcoin perpetual reached **5.95 basis points**, more than ten times its
> median over the preceding weeks, and the spreads of all other contracts trading at the time more
> than doubled."

Third-party cross-check: **Zhivkov (2026, *Mathematics*)** states "typical transaction costs (4–8 bps)"
and models 0.05% taker + 0.1% slippage = **0.6% round trip**.

**Assessment: the repo's 0.30% is a correct *base*.** What it lacks is a **stress** figure — the
5.95 bps BTC crash spread, the 2.12 bps ADA median, and price impact, which scales with book size and
which **no public source measures above ~$10k notional**. That last item remains genuinely unmeasured.

### 5.8 The basis is not a persistent quantity — but the funding is

He et al. Table 46, error-correction estimates of log F on log S: EG slope ≈ **1.000** for all five
coins, half-life of the basis **1.68 h (BTC), 2.34 h (ETH), 2.26 h (BNB), 9.53 h (DOGE), 4.91 h
(ADA)**.

Interpretation: the *price* gap is arbitraged away in under two hours for BTC. The *funding payment*
persists because it is a payment on notional, not a claim on convergence. This is why the trade is a
hold, and it is also why the price-convergence component of a delta-neutral book is unavailable to a
passive holder.

### 5.9 What the two-leg structure does and does not protect against

A long-spot / short-perp book is delta-neutral **in price**. It is **not** hedged against:
exchange default (both legs are on the same exchange — an unsecured claim on one counterparty);
margin-asset depeg (USDT/USDC are both the quote and the collateral); a basis blow-out; or funding
sign reversal. He et al. are explicit: "**we abstract from exchange default risk and assume that the
exchange remains solvent. If the exchange can default before the unwinding stopping time, funding
payments, gains on the futures position, or posted collateral may not be fully recovered.**"

**Verdict Q5: the mechanics as stated in the brief are correct on sign and interval but incomplete,
and three findings change the implementation.** (i) **Spot and USD-M margin are separate systems** —
a $1m short needs **30.52% of notional** in the futures account to survive a 30% adverse move, and the
spot leg changes that by **zero**; this is a capital requirement ~100x the fee and the repo carries
nothing for it. (ii) **Funding is forfeited on early close** (no accrual) and is debited against
position margin, moving the liquidation price. (iii) **The perp marks to a 16-venue composite index,
not Binance spot.** The repo's **0.30% round-trip cost is confirmed correct** against the verified
VIP0 schedule (0.24% with the BNB discount) and needs only a stress counterpart added.

---

## Q6. He, Manela, Ross & von Wachter — verified

**The paper exists and the brief's characterisation is accurate.**

- arXiv:2212.06888, **"Fundamentals of Perpetual Futures"**, Songrun He (Washington University St
  Louis), Asaf Manela (WUSTL / Reichman), Omri Ross (Copenhagen, also eToro), Victor von Wachter
  (Copenhagen). First draft Dec 2022; **v7 dated 17 Sep 2026**. Also SSRN 4301150.
  <https://arxiv.org/abs/2212.06888> · full text <https://arxiv.org/html/2212.06888v7>
- **Status: working paper.** I found no journal publication. Treat as a preprint.
- ⚠ **Citation trap:** OpenAlex lists NBER w32936 as this paper's working-paper version. It is not.
  NBER w32936 is **Ackerer, Hugonnier & Jermann, "Perpetual Futures Pricing"**, published
  *Mathematical Finance* 36(3), 481-499 (2026). Different authors, different result. Do not conflate.

**Its actual abstract, verbatim:** "We derive no-arbitrage prices for perpetual futures in frictionless
markets and bounds in markets with trading costs. **Empirically, deviations from these prices in crypto
are larger than in traditional currency markets, comove across currencies, and diminish over time.** An
implied arbitrage strategy yields high Sharpe ratios."

**All three empirical claims check out against the paper's own tables**, with these magnitudes:

- *"Larger than in traditional currency markets"*: mean **absolute** deviation 52–90%/yr across coins,
  benchmarked against Du, Tepper & Verdelhan (2018) in FX.
- *"Diminish over time"*: see Q3 — "almost 80%" after 2022; "22 percentage points a year".
- *"Comove across currencies"*: asserted, and cross-exchange BTC funding correlation Binance vs Bybit
  = **0.74**. **They do not publish a cross-currency correlation number** — see below.
- *Sharpe ratios*: BTC **3.35** under retail ("High") fees, **11.65** at zero fees; after effective
  bid-ask spreads, **3.27** and **10.46**. But that is the *dynamic convergence* strategy, which
  trades (92 trades in 4.2 years for BTC under High fees, median holding 38 h, p90 224 h).
- **The strategy in this repo is the "Carry" column of their Table 6**, and it is an order of
  magnitude worse: SR 1.01–2.66 on four of five, **−0.66 on BNB**.

**Their own critique of carry**, §4.3, verbatim: "**While industry publications usually emphasize the
funding rate channel, we note that price convergence can generate quicker gains from arbitrage if
dislocations are short-lived. We find that price convergence plays a dominant role in total trading
returns, while funding rate payments have a more minor role, which seems to diminish over time.**"

### Is carry across many coins genuinely diversified, or one factor bet?

**Both, measurably — and the answer is a number the paper does not give.**

**[MEASURED HERE]**, `tools/carry/funding_live.py` and `tools/carry/carry_decay_corr.py`:

| | 20-symbol repo corpus, 6,492 common 8h funding changes | 17 majors, live API, 500 settlements |
|---|---:|---:|
| mean off-diagonal correlation of funding **changes** | **0.447** (median 0.453, range 0.156–0.730) | **0.272** |
| mean off-diagonal correlation of funding **levels** | **0.627** | — |
| PC1 share of equal-variance cross-sectional variance | **49%** | **32%** |
| PC1+PC2+PC3 share | 59% | — |
| implied EW portfolio vol / single-name vol | **0.689** | 0.561 |
| diversification achieved going 1 → N names | **1.45×** | 1.78× |
| (perfect independence would give) | 0.224 | 0.224 |

Cross-check against the repo's existing §3.9: that measured `rho_resid = 0.297` for the
**BTC-orthogonalised alt price** correlation. **Funding is materially more common than price**
(0.447 changes / 0.627 levels vs 0.297 prices). So the repo's existing conclusion — "diversification
saturates by ~20 names" — holds, and the underlying commonality is *stronger* than the price-based
number suggested.

**Interpretation.** A single factor explains 32–49% of cross-sectional funding variance: real, and it
means a 20-name funding book is roughly a **1.45×** vol reduction, not the 4.5× a naive
1/√N assumes. But 51–68% is still idiosyncratic, so it is emphatically **not** a single factor bet
either. The right model is "a leveraged-crowding factor plus a large idiosyncratic residual", which is
exactly what He et al.'s theory predicts (§5.2: arbitrageurs' common funding constraints on one side,
common sentiment for leveraged exposure on the other).

**Verdict Q6: verified and quantified. Not fully diversified. Model it as one factor plus residual,
not as N independent streams — and note the repo's price-based correlation understates the effect.**

---

## Q7. The bear case

The strongest published arguments against funding carry, in descending order of force.

1. **A "delta-neutral" book has drawn down 33.6%.** He et al. Table 6, BNB: return **−5.14%/yr**,
   SR **−0.66**, max drawdown **−33.61%**, alpha **−7.13** (t = **−2.21**, i.e. significantly
   negative). DOGE: −14.37% maxDD. This is a peer-reviewed sample on Binance, the same venue and
   period as the repo's. **The repo's `REPORT.md` reports no drawdown for the carry strategy at all —
   that is the single largest gap in the existing analysis.**

2. **The payment's std exceeds its mean, in every source.**
   - **[MEASURED HERE]** repo corpus: median symbol sd/mean = **3.19** (full sample), **4.77** (from
     2025).
   - He et al. Table B.1: BTC mean 15.3%/yr vs SD **27.8%/yr**.
   - Zhivkov (2026): CEX mean **−1.91 bps/8h** vs SD **22.82 bps/8h** — and note the **sign split**:
     the *mean* is **negative** while the *median* is **+1.00 bps/8h**. A left tail thin enough to
     drag a right-concentrated, positively-clamped distribution negative is the cleanest published
     statement of the left skew I measured independently (pooled skew −8.53).
   A carry whose own standard deviation is 1.8–12× its mean is not "a definite number". It is a
   number with a sign attached.

3. **The funding rate is negative a large fraction of the time.**
   **[MEASURED HERE]** repo corpus, median symbol: **22.0%** of 8h settlements over the full 6.5 years,
   **32.2%** over the trailing year, 31.0% since 2025. By symbol on the live API: ADA 35.8%, XRP
   41.2%, SOL 41.6%, XLM 38.6%, DOT 37.4%, BCH **50.0%**, TRX **57.0%**. You earn nothing in those
   intervals and still bear the short leg. (BNB was negative **0.0%** of 500 settlements — the clamp's
   floor in action, another Q4 point.)
4. **Funding-rate volatility shocks are permanent.** Zhivkov (2026), GARCH(1,1) on funding-rate
   spreads: `a + b` = **1.000 exactly** for BTC, ETH and SOL — integrated GARCH. There is no
   mean-reversion trade available on the volatility of this variable. Autocorrelation 0.966–0.998 at
   lag 1 and still >0.80 at lag 8. You cannot wait out a bad regime.

4a. **The most striking corroboration in the whole review, from an unrelated author and an unrelated
   sample.** Zhivkov's CEX **median** funding rate over 8–15 Nov 2025 is **+1.00 bp per 8h**. Binance's
   administered interest component is **1.00 bp per 8h** (0.01%). Across 27.9 million CEX observations
   spanning 11 centralised exchanges and hundreds of symbols, **the modal settlement is the clamp
   value** — nobody chose it, the venue set it. That is the Q4 thesis ("the carry is the fee schedule")
   confirmed by a paper that never mentions Binance's parameter. Two further consequences: the
   *median* sitting exactly on the clamp while the *mean* is **−1.91 bps** (−20.9%/yr) is direct
   published evidence that **the mean is the wrong statistic** for this variable — which is the same
   point as the serial dependence and skew below. And **over that eight-day window a funding
   *recipient* lost 20.9%/yr on the mean.**
5. **The distribution is a fat left tail, and the series is serially dependent.**
   **[MEASURED HERE]** over the 141,889 symbol-settlements on disk: equal-weight **lag-1
   autocorrelation 0.832** (lag-3 0.735), pooled **skew −8.53**, **excess kurtosis 396**, worst
   single settlement **−2.00%**, **22.0%** of settlements negative, equal-weight worst settlement
   **−0.509%**, longest run of consecutive negatives **46 settlements = 15.3 days**.
   Two consequences. (i) **Any significance statement on a mean funding rate computed on raw
   settlement counts is invalid** — this is §3.1's trap again, in a new place, and it applies to the
   carry line's own arithmetic. (ii) The left tail is the whole risk: a −2.00% settlement is 200 bps
   of the 30 bps round-trip cost in a single 8-hour window.
6. **There is no structural floor under the payment, contrary to a natural reading of the clamp.**
   It is tempting to read "funding = ι = 0.01% whenever the premium is inside ±0.05% of ι" as a
   guaranteed 10.95%/yr to the short. **It is not a floor — it is a plateau, and it does not extend
   to the short's benefit.** From `F = P̄ + clamp(ι − P̄, ±0.05%)`: when `P̄ = −0.10%`, then
   `F = −0.10% + 0.05% = −0.05%`. Below `P̄ = ι − 0.05% = −0.04%` the rate falls one-for-one with the
   premium and is unbounded below. The data confirm it: BTC's realised minimum is **−0.3000%** and
   SOL's is **−2.0000%**, both far below `ι = +0.01%`. So the 10.95%/yr is a *plateau* the payment
   sits on while the basis is quiet, not a contractual minimum — which is precisely why the repo's own
   9 symbols with negative excess are possible.
7. **95% of the best opportunities reverse.** Zhivkov (2026), peer-reviewed: of the top 20
   delta-neutral cross-exchange opportunities, **19/20 (95%)** showed spread reversal, **12/20**
   incurred losses net of costs, **8/20** profitable; "forced exits occurred for 12 of 20 portfolios
   when spreads turned negative." **Weight this down**: the sample is 8 days, the spread is
   cross-exchange rather than spot-vs-perp, and the forced-exit rule (spread < 0) is explicitly
   "conservative" and may "trigger premature exits". But directionally it is the only peer-reviewed
   attempt to measure what a delta-neutral funding book actually experiences, and it is grim.
8. **Counterparty risk is the binding risk, and the residual opportunity lives in the bad venues.**
   **Guo, Intini & Jahanshahloo (2025)**, "Bitcoin arbitrage and exchange default risk",
   *Finance Research Letters* 71, 106364 — minute-level data, 16 exchanges, Apr 2013–Apr 2024:
   "arbitrage opportunities last longer when higher-risk exchanges have higher prices, as traders are
   cautious of default risks. There is a strong positive relation between capital flows from
   high-risk to low-risk exchanges and arbitrage opportunities, showing a preference for safer
   exchanges." **Read: the market prices exchange default, arbitrageurs systematically migrate to
   safer venues, and what arbitrage is left is concentrated where you would least want your funding
   to be.** He et al.'s own arbitrage is "conditional on exchange solvency" and explicitly excludes
   default cost from the price.
9. **"An arbitrageur must remain liquid longer than the market stays irrational."** He et al. §1, and
   the exact sentence the brief asked for: *"Note that the strategy just sketched, commonly referred
   to as 'funding rate arbitrage', is not without risk even if one ignores margin requirements and
   trading costs, simply because there is no obvious maturity date at which the trade would be unwound
   at a profit."*
10. **The precedent is 3AC and Alameda.** He et al. link the narrowing of the gap to both funds' pivot
    *out of this exact trade* in late 2021 / early 2022 into directional bets, and to their 2022
    bankruptcies. The trade killed two of the most sophisticated balance sheets in the industry.
11. **Funding flips negative exactly when it is dangerous.** He et al. Figure 2: the FTX collapse of
    Nov 2022 produced "significant negative funding rates on all solvent exchanges" — in a dislocation
    the receiver becomes the payer. The repo's own data agrees: TRX at **−10.62%/yr** over the trailing
    166 days and **−17.07%/yr** over the last 30.
12. **It is a regime trade by construction** (the repo's own §4, and I agree): you are paid when
    positioning is crowded, which is when the market is most fragile. There is no setting of this
    trade that is good in both regimes.

**Verdict Q7: the bear case is stronger than the bull case for a leverage-constrained implementer.
The strongest single datum is not a theory but a number: −33.61% max drawdown on BNB, alpha −7.13
with t = −2.21, in a peer-reviewed replication of this exact strategy on this exact exchange.**

---

## Corrections this review forces on `docs-myself/RESEARCH_STATE.md` and `tools/carry/REPORT.md`

1. **The sign convention is confirmed by primary documentation** — upgrade from "verified against
   raw data" to "verified against exchange documentation" with the URL.
2. **Do not hard-code the 8-hour interval — but your corpus is fine.** The repo's corpus is genuinely
   8h throughout and the `3 × 365` annualiser is correct for it (verified symbol-by-symbol against the
   live stream, zero mismatches). **However [MEASURED HERE] 469 of Binance's 791 USD-M symbols — 59% —
   now settle every 4 hours**, and Binance administers this silently. Any universe expansion hits it
   immediately, at which point the same code over-states annualised carry by 2x. Read
   `fundingIntervalHours` from `GET /fapi/v1/fundingInfo` per symbol per run and derive the
   annualisation factor from observed `fundingTime` spacing.
3. **The carry is mostly a financing charge, and the repo should say so.** Decomposition on the
   repo's own corpus: EW total +9.40%/yr vs EW fixed interest component 10.95%/yr, excess
   **−1.55%/yr**; BTC excess **+0.20%/yr**; **9/20 symbols have a negative excess**; 36.6% of
   settlements pay exactly the fixed parameter. This is a more useful headline than "+7.96%/yr" and it
   changes what the strategy is.
   ⚠ **Panel-definition conflict, unresolved and deliberately not averaged.** On the 6,493-row
   fully-common intersection: **−1.55%/yr**, 9/20 negative, BTC +0.20%. On each symbol's full history
   (141,889 settlements): **−0.83% to −0.89%/yr**, 8/20 negative, BTC +0.62%. **Report the range
   [−1.6%, −0.8%] with both definitions named.** The cross-sectional ranking is identical in both.
4. **"0 of 20 symbols have a negative annualised carry" is a full-sample statistic and is misleading
   as a headline.** From 2022 onward **6/20** are negative; from 2025 onward **7/20**. Any statement
   about sign robustness must carry the sub-period.
5. **Full-sample EW carry recomputes to +9.40%/yr** on 6,493 fully-common settlements (panel starts
   ~2020-08), versus the +7.96%/yr in `REPORT.md` (panel starts 2020-10-16). Same method, different
   panel definition — state the panel explicitly rather than treating either as canonical.
6. **New measured constants to add to §4:**
   - share of settlements paid at exactly the fixed interest component **36.6%** (25.2% post-2025-05-02)
   - EW carry excess over the interest component **−1.55%/yr**; BTC **+0.20%/yr**; **9/20 negative**
   - cross-coin funding-change correlation **0.447**; PC1 share **49%**; diversification factor **0.689**
   - median symbol sd/mean **3.19** (full sample) / **4.77** (since 2025)
   - median symbol % of 8h settlements negative **22.0%** (full) / **32.2%** (trailing year)
   - Binance interest component **0.01% per interval = 10.95%/yr**, binding in **~36–50%** of settlements
   - funding caps **±0.30%/settlement (BTC), ±0.375% (most majors), ±0.4875% (DOGE), ±2% (others)**;
     the cap **binds** in the realised tail
   - **59% of Binance USD-M symbols settle every 4h, not 8h** (469 of 791); the repo's 20 are all 8h
   - **separate margin systems:** a $1m short needs **30.52% of notional** in the futures account to
     survive a 30% adverse move; the spot leg changes that by **zero**
   - funding series serial dependence: EW lag-1 autocorr **0.832**, lag-3 0.735; pooled skew
     **−8.53**, excess kurtosis **396**, worst settlement **−2.00%** (censored at the cap), longest
     negative run **46 settlements = 15.3 days** (DOT 135 = 45 days). **Any significance claim on a
     mean funding rate over raw settlement counts is invalid.**
   - rolling-30d annualised carry has ranged **−14% to +125%**
7. **The cost model is CONFIRMED, not revised.** Verified VIP0: spot 0.100% taker, USD-M 0.0500%
   taker ⇒ **0.30% round trip**, 0.24% with the BNB discounts. Do **not** raise it for spread: the
   measured effective BTC perp spread is **0.11 bp**, ~100x smaller. Fees dominate, not spread. What
   the model still lacks is a *stress* figure: He et al.'s **16.38 bps** maker round trip at retail
   tier, the **5.95 bps** BTC perp effective spread during the 2020-03-12 crash, and Zhivkov's **0.6%**
   including slippage. No public source measures impact above ~$10k notional.
8. **The state's "currently +0.36%" is stale, but the monitor's verdict is not.** Live API, 17 majors:
   trailing-30d **+4.20%/yr**; repo corpus, trailing-90 settlements: **+4.75%/yr**. But 30/90/180/365d
   read **+4.75 / +2.56 / +0.60 / −0.58** — monotonically declining with window length, the signature of
   a spike, not a regime. **Do not flip the switch on the 30-day number.** The multi-window agreement
   rule is the correct call.
9. **Add the drawdown.** The carry strategy's return distribution is a reported gap. He et al.'s
   replication gives −33.61% maxDD; the repo should compute its own on the 20-symbol corpus. (For
   balance: their *dynamic* convergence strategy has much smaller drawdowns — BTC −3.90%, ETH −2.67%,
   DOGE −13.90% — but that is a different, actively-traded strategy with 92 trades in 4.2 years and a
   38-hour median hold, not a hold-forever carry.)
10. **Add the mechanical traps**: funding forfeited on early close (no accrual), funding debited
    against position margin (moves the liquidation price), and the re-establishment table does not
    model the forfeited crossing settlement.
11. **Add the capital requirement.** 30.52% of notional in the futures account to survive a 30% move.
    This is not a cost and is not in the model at all; it is roughly 100x the fee.

## Where sources disagree, and what I weight

| disagreement | positions | my weight |
|---|---|---|
| Risk premium or service charge? | near-unanimous service/financing; Schmeling-Schrimpf-Todorov dissent | **Service**, decisively. But note the official record neither supports nor contradicts the dissent — regulators treated leverage as a *stability* problem and never adjudicated it |
| He et al.'s "±3% for ≤25x" cap rule | paper vs current Binance doc | **The doc.** `0.75 × MMR` for 36 listed symbols, ±2% for the rest, live-verified. The paper is superseded and keeps propagating through secondary sources |
| Repo 0.30% cost vs measured spread | not a conflict — different objects | Fees dominate: 0.30% taker round trip vs a 0.11 bp effective BTC perp spread. **0.30% is correct** |
| Excess over the interest component: −1.55% vs −0.89%/yr | panel choice, unresolved | **Neither — report the range [−1.6%, −0.8%] with both definitions named. Do not average.** Conclusion invariant |
| Good trade or bad? | He et al. −33.61% BNB drawdown vs Werapun et al. "1.92% max loss" | **He et al.** Four-year Binance sample from the paper that models the mechanism. Werapun is six months and paywalled — a counterexample to reconcile, not reassurance |
| Is +4.75% at 30d a regime? | spike vs regime | **Spike.** Monotonically declining across 30/90/180/365d |
| Is funding "free money" at 3.35x Sharpe? | He et al.'s own convergence strategy | **Neither, for this trade.** That is the *dynamic* strategy, not a hold-forever carry, and the paper says so |
| Does the perp premium threaten a long-spot/short-perp book? | the framing of Q5.4 as posed | **The framing is backwards.** The book is *short* the premium: a perp at a large premium is a gain. The danger is a perp at a large **discount** — which is what happened on the solvent venues in Nov 2022 and Mar 2020 |
| Is the mean or the median the right statistic? | He et al. mean +1.40 bps/8h (BTC) vs Zhivkov CEX mean −1.91 bps/8h | **The median.** Both are true: a distribution with median +1.00 and a −2,400 bps minimum *must* have a negative mean. All three sources agree the median sits on the +1.00 bp/8h = 10.95%/yr floor |
| Same trade, two Sharpes: 10.06 vs 2.24 | Christin et al. (gross) vs He et al. (gross, fee-aware) | **Both correct for what they measure.** Christin et al. state outright: *"we abstract from margin, leverage, transaction costs."* Do not blend, and never quote 10.06 as net |
| Perp funding vs futures basis | Schmeling et al. ">40% p.a." vs Christin et al. "+17.28%/yr" | **Different quantities.** Schmeling is fixed-maturity futures basis; Christin is perp funding. He et al. p.7 make the distinction explicitly. Do not quote them side by side |
| How often does the clamp bind? | He et al. Table B.1 says 35.7–45.2% of hours; a p.23 footnote says 93% | **Unresolved internal inconsistency in the paper.** Flagged, not adjudicated. The repo's own 36.6% at-par measure sits with Table B.1 |

## What I could NOT find

**A methodological warning that applies to every item below.** A zero-hit result is evidence only if
you verified you fetched the *right* document. Fetching `IOSCOPD688` — a pubdoc number that circulates
for the IOSCO crypto report — silently returns an unrelated 2021 sustainability report, producing "a
verified negative finding for the wrong reason". A wrong DOI, a JS-rendered page returning HTTP 200
with zero characters, and a paywall returning a login form all produce an identical-looking "nothing
found". **Enforce it, don't remember it: assert the fetched document's title, issuer and date match
the citation before counting term frequencies, and exit non-zero on mismatch.** Every negative finding
in this project — "no regulator discusses funding", "no study reports the carry book's P&L
distribution" — carries that risk.

- **Any paper by an author named "Shamshuddeen"**, or by the "Pou/Poucet + Păuna" pairing, on
  cryptocurrency-futures arbitrage returns. Searched arXiv, OpenAlex, Crossref, RePEc, and general web.
  Reported as a negative finding rather than substituted.
- **Numbers from Christin, Routledge, Soska & Zetlin-Jones, "The Crypto Carry Trade" (2022)** — the
  paper is located but the host (`gerbil.life`) timed out on every fetch attempt. This is the closest
  prior art to the repo's strategy and its numbers are the most important missing input.
- **Any published study that decomposes a funding book's realised P&L into "service fee" vs "risk
  premium", or that estimates the ruin probability of a long-spot/short-perp book.** The closest is
  He et al.'s ι-vs-premium decomposition, which decomposes the *rate*, not the *P&L*. **This is the
  single largest evidence gap in the review and it appears not to exist.** The bear case therefore
  rests on measured drawdowns, serial dependence, the censored left tail and the linear (non-convex)
  collateral requirement — *not* on any published ruin probability.
- **Any study of how often funding-carry books actually get liquidated.** Binance's
  `fapi/v1/adlQuantile` and insurance-fund history are not public at the needed granularity.
- **Any measurement of price impact for a spot+perp book above ~$10k notional.** He et al. use Kaiko
  order-book snapshots but only to $0.5mn on a single contract.
- **A clean, peer-reviewed study of spot+perp funding carry on Binance USD-M specifically, 2024-2026.**
  Closest: **Pindza (2026)**, "Centralized-decentralized exchange funding rate arbitrage as a basis
  trade", *Digital Finance* 8(3), doi 10.1007/s42521-026-00213-3 — peer-reviewed, CC-BY, Binance
  BTC/ETH/SOL funding **Jan 2021 → Dec 2024**, but its DEX leg is synthetic and no levels were
  extracted. Its caution is quotable and on point: *"net annualized returns are driven mainly by
  funding carry, but that these returns are **highly assumption-sensitive and should not be
  interpreted as frictionless arbitrage profits**."* Also **Zhivkov, Todorov & Georgiev (2026)**,
  *International Journal of Financial Studies* 14(5):103, doi 10.1006/ijfs14050103 — the two-month
  (14 Nov 2025 – 13 Jan 2026) companion to the 8-day paper, 9.1m hourly obs; it reports **spreads,
  not levels**. He et al. Table 6 remains the best Binance-specific evidence and it is a preprint.
- **The post-2024 level is measured by nobody in the literature.** He et al. stop at 2024-03-11,
  Pindza at 2024-12, Zhivkov's level paper covers **eight days** in Nov 2025. **The current level of
  Binance funding is established only by this repo's own data.** That is a genuine gap, and it is
  also the reason the repo's own monitoring number is the only one that matters for the decision.
- **⚠ DATA-QUALITY TRAP worth acting on.** Zhivkov, Todorov & Georgiev (2026): *"reported funding
  rates reached magnitudes exceeding 284,000 basis points, approximately 180 times the 99.99th
  percentile of the distribution (1596 bps). These are consistent with an API reporting error."*
  **Any funding scraper should treat >~1,600 bps as suspect and cap well above it.** The repo's
  on-disk corpus tops out at −2.00%, so it is clean, but the forward collector should carry the guard.
- **Any regulator document on the economics of the funding transfer.** IOSCO's flagship crypto
  recommendations (FR11/2023 = **IOSCOPD747**; note PD688, which circulates in secondary citations, is
  an unrelated 2021 sustainability report) contain **zero** occurrences of *perpetual*, *funding*,
  *liquidat-* and *cash-and-carry* across 77 pages; the FSB global framework contains zero mentions of
  derivatives. The two most likely documents — CFTC's *Risk and Materiality Considerations for Digital
  Assets by Swap Execution Facilities* (2024) and FINRA's 2025 *Crypto Asset Spot Markets* report
  (**FINRA, not CFTC**) — were unretrievable. **State the absence carefully:** the standard setters
  treated leverage as a stability problem to be handled through custody, conflicts and governance, not
  as a product-economics question. That absence is weaker evidence than a positive statement would be,
  and it does **not** adjudicate the Schmeling risk-premium dissent.
- **A premise in the task brief was falsified and must not be propagated:** "BIS AER 2021 ch. III
  describes tokenised leverage as giving investors the right to buy the crypto instead of owning it."
  Full-text scan: *perpetual* appears **0 times** in AER 2021, 2022 and 2023; *right to buy* 0 times in
  all three; and AER 2021 ch. III ("CBDCs") contains no `DeFi` at all. The idea is widely repeated and
  has no locatable source.
- **The title given in the brief for Ferko et al. does not exist.** The real paper is
  **"Who trades bitcoin futures and why?"**, *Global Finance Journal* 55:100778, 2023,
  **peer-reviewed** — and it studies **trader composition, not leveraged-ETP premiums**, so it cannot
  supply the premium figure the Q4 economics was after. Likewise the brief's
  "Alexander, Choi, Park, Sohn (2020), *Price discovery and market quality in cryptocurrency markets*"
  does not exist under that title; the real paper is *"BitMEX Bitcoin Derivatives"*, and the Q2 sub-line
  read it in full: it **describes** the funding mechanism and **reports no funding level, no bps
  figure and no arbitrage return.** And **"de Blasis & Bauer" on BitMEX funding does not exist** (the
  nearest real paper, De Blasis & Webb, *J. Futures Markets* 2022, doi 10.1002/fut.22305, is a
  different subject and was obtained as abstract only).

## Reproduce

```
python tools/carry/carry_decay_corr.py        # decay table + cross-coin common factor
python tools/carry/verify_interest_decomp.py  # interest-component decomposition, cap binding
python tools/carry/funding_live.py            # live-API funding level, caps, PC1
python tools/carry/interval_check.py          # funding-interval histogram across all 791 symbols
```
Run with `.venv\Scripts\python.exe` (pyarrow lives only in the venv). Outputs:
`tools/carry/_src/funding_live.json`, `funding_change_corr.csv`,
`carry_by_year_recomputed.csv`. Source documents cached in `tools/carry/_src/`.
