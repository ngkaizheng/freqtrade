# Crypto Catalyst Repricing Scanner — v4 Formal Scoring Round

**Run date:** 2026-09-29 04:37 (UTC+8) = 2026-09-28 20:37 UTC
**Market data:** CoinGecko `last_updated` 2026-09-28T20:02:20Z (candidates) / 19:30:20Z (universe breadth)
**Position size assumed:** ~$500 per idea (v4 §52 VETO-4)
**Window:** 2026-10-01 → 2026-12-28
**Framework:** v3 = research methodology · v4 = formal scoring & elimination
**Gate:** `tools/catalyst_scan/verify_v4.py` — **538 checks, 0 failures**

---

## A. Executive Summary

### The headline

**Applying v4's formal system to the v3 candidate set produces ZERO candidates at Deep DD, ZERO at High-Priority Watch, and ZERO at Watch. One candidate reaches Speculative / Low Priority. That is the result.**

The v3 round promoted one name (KNTQ) to Deep DD on qualitative reasoning. Under v4's own arithmetic, **the same name scores 53.55 and is Rejected.** The framework did not confirm the previous round — it reversed its headline.

| | v3 round (qualitative) | v4 round (formal) |
|---|---|---|
| Deep DD | 1 (KNTQ) | **0** |
| High-Priority Watch | 0 | **0** |
| Watch | 6 | **0** |
| Speculative / Low Priority | 0 | **1 (AVA)** |
| Priced In | 4 | 4 |
| Data Insufficient | 2 | 2 |
| Weak | 2 (ZRO, SUSHI) | 0 (folded into Reject) |
| Reject | 2 (ORE, CC) | 19 |

The v3 round classified 17 names; this round scored 28, because the attention/velocity cohort (§F.3) and the supply-shock names were added.

### Why the field is empty — the three structural reasons

1. **The window is a supply window, not a catalyst window** (carried forward from v3 and reconfirmed). Inside 2026-10-01 → 2026-12-28 there are a handful of dated events, and against them sit confirmed unlocks of 47.7% of float (2Z, 10-02), 14.3% (ENA, 10-05), ~90% (MON, 11-24) and two dated SEI insider unlocks of $5.53M each (10-15, 11-15). The net calendar direction is dilution.

2. **v4 §67 Rule B (Information Gap ≥ 3) eliminates 22 of 28 candidates.** This is the binding constraint, and it is doing exactly what it was designed to do. Almost nothing in this market has an unpriced, dated, material variable.

3. **A catalyst that is already public is not a catalyst.** The single genuine in-window, project-published, hard-dated event found in the entire scan — The Graph's Subgraph Studio migration on 2026-10-08 — had already been reported by four aggregators on 2026-09-25/27, *before* the screen ran. Scored G=1. That is v4 §73 anti-catalyst-chasing in its purest form.

### What I did beyond the v3 round

- **Re-verified every v3 number on fresh data** (2026-09-28T20:02Z vs v3's 19:05Z). All 16 re-verify within normal drift. No v3 data errors found.
- **Built a new attention/velocity screen** (60 names) because **the v3 screen structurally could not produce archetypes C or D**. v3 ranked protocols by `holders revenue ÷ market cap` off DefiLlama, which can only ever surface protocols that already publish a token-capture line. Scoring a universe pre-filtered against two of v4's six archetypes would be scoring a biased sample. This was the most important structural gap in the v3 round.
- **Adversarially DD'd the top 11 of that cohort.** Result: **1 of 11 had a dated in-window event, and it was not a gap.** The cohort is eliminated on Rule B, not on liquidity.
- **Implemented v4 as code** (`v4_score.py`, 538-check gate) so every published number is machine-derived and re-checkable, rather than hand-typed.

### Corrections I made against myself and against the screen

- **My own attention screen mislabelled MARSCOIN** as "Mars Protocol". It is `marscoin-4`, a BNB Chain **meme token**, Binance Seed-Tag listed 2026-09-04 with a 20× perp launched 2026-09-01 — derivatives before spot. It is unrelated to Mars Protocol (Cosmos, ~$130K TVL) and to marscoin.org (a 2014 Bitcoin merge-mining coin). Three entities, one label; my screen merged them.
- **My own screen's numbers were stale on the fast names** by the time they were read: RHEA was −4.7% on 24h in the screen and −30.4% when checked 40 minutes later. Momentum screens decay faster than the research cycle that consumes them.
- **KNTQ's catalyst date is L4, confirmed by primary-source absence.** I re-traced it independently this round: the "20 Oct 2026" figure traces to a **CoinMarketCal calendar entry** → TradingView relay → CoinMarketCap AI summary. Kinetiq's own blog has never published a mainnet date. v4 §57 therefore caps Catalyst at 3, not 4.

---

## B. Market Regime

**Verdict: MIXED, downside tilt.** A broad alt bounce inside a deep bear market that is currently rolling over.

| Measure | Value | Source |
|---|---|---|
| Total crypto market cap | **$2.875T** (−3.31% 24h) | CoinGecko /global |
| 24h volume | $155.5B | CoinGecko /global |
| **BTC dominance** | **58.27%** | CoinGecko /global |
| ETH dominance | 11.37% | CoinGecko /global |
| BTC | $83,869 — 7D **−2.17%**, 30D +7.59%, **−33.5% from ATH** | universe snapshot |
| ETH | $2,692.99 — 7D −1.61%, 30D +10.13%, −45.6% from ATH | universe snapshot |
| SOL | $119.53 — 7D **+2.42%**, 30D +14.44% | universe snapshot |
| HYPE | $88.22 — 7D −3.74% | universe snapshot |
| ETH/BTC | 0.032111 (**+2.36%** over 30d) | computed |
| **Top 200 breadth** | median 30D **+16.8%**, **78% up**, median **−73.9% from ATH**, 25.5% within 25% of ATH | universe snapshot |
| Top 1000 breadth | median 30D +9.0%, 69.7% up, median −84.6% from ATH | universe snapshot |

**Reading.** Four of five majors are negative on 7D and total market cap fell 3.31% in the last 24 hours, so the bounce is stalling rather than broadening. BTC dominance at 58.3% is a risk-off reading. But the median top-200 asset is up 16.8% in a month and the 25.5% sitting within 25% of their ATHs are overwhelmingly cash equivalents — stablecoins, tokenised treasuries, money funds, gold. **This is a bear market in which the only things near their highs are dollars.** That is a market paying for cash flow and refusing to pay for narrative, which is precisely the demand curve every surviving candidate here depends on.

**Regime Factor = 1.00 (neutral).** Risk-off compresses alt multiples; the cash-flow preference supports the theses. They roughly cancel.

> ### ⚠ Load-bearing caveat
> **At Regime Factor 0.95 the entire surviving result disappears.** AVA falls 56.10 → 53.30 and the field is empty. The headline of this report depends on a judgement call the data does not settle. This is stated because a report that hid it would be claiming precision it does not have. See §H.

---

## C. Narrative Heatmap

Limited to what is measurable from primary sources. Phases are judgements; the evidence column is not.

| Narrative | Evidence of current activity | Phase | Note |
|---|---|---|---|
| **Token-capture / buyback** (idiosyncratic) | The single most-funded mechanism in the market this round: AVA permanent reserve (09-23), AERO emissions-to-revenue engine (10-21), SYRUP MIP-021 tiers, LDO NEST (approved, unexecuted), KNTQ KIP-5 | **Mature — and crowded** | Every one of these is already public. This is the *discovered* narrative; that is exactly why §67 Rule B rejects most of them. |
| **ETF / institutional wrappers** | Canary filed Pre-Effective Amendment No. 2 for a staked SEI ETF on 2026-09-21 (BitGo custodian, Cboe BZX expected); SEI +33% in a day on it | **Emerging** | **No scheduled SEC decision date exists.** An undated catalyst cannot be scored as an in-window event, so SEI scores G=1. |
| **Hyperliquid ecosystem** | Kinetiq controls ~82.5% of Hyperliquid's liquid-staking market; Elysium L2 testnet live since 09-22 | Emerging | Concentration risk noted: one ecosystem's L2 carrying the whole KNTQ thesis. |
| **BNB Chain memes** | MARSCOIN: Binance spot 09-04 (Seed Tag) **after** a 20× perp on 09-01; +236% 30D on >80% turnover with "liquidity a small fraction" | **Exhausted / breaking** | Pure reflexivity with no cash-flow capture. 24h already rolling. |
| **Meme / reflexive (broad)** | The 60-name attention screen is dominated by names **down 20–25% in 24h** after +50–200% 7-day runs | **Exhausted** | The acceleration phase ended; the distribution phase is running. |
| **RWA** | ONDO +44.6% 30D at a $2.49B cap, no dated in-window event; its 35.2% unlock lands 2027-01-17, just *outside* the window | Mature | Rerated without a catalyst. |
| **Perp DEX** | LIT $1.12B cap, FDV/MC 4.00, 7D −6.3% against 30D +28% — momentum fading | Cooling | No dated value-capture event found. |
| **THORChain / RUNE** | +68% 30D — while Aug swap volume **−23%** and System income **−23%**, after a third network halt (08-26/27) and a confirmed $10.7M exploit (2026-05-15) | **Deteriorating** | THORChain **cut** the RUNE burn from 5% to 1% of System Income on 2026-09-23 (primary source). |

---

## D. The v4 §81 Ranking Table

Full machine-generated table in `tools/catalyst_scan/out/v4_ranking.md`. Sorted by v4 §84 ranking logic: **veto > information gap > primary driver > liquidity > supply > reflexivity**, with final score as the last tiebreak. This is why AERO (56.05) appears below SYRUP (53.20): §84 ranks information gap and driver strength *above* score, and LDO's G=3 outranks AERO's tie on G=3 only via its S=4.

| Token | Archetype | Raw | Final | Norm | G | F | C | A | L | S | R | Conf | §67 Qualification | **Status** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| **AVA** | Fundamental Repricing | 66.00 | **56.10** | 51.00 | 4 | 4 | 3 | 2 | 3 | 3 | 2 | C | **PASS** | **Speculative / Low Priority** |
| **KNTQ** | Hybrid | 63.00 | 53.55 | 48.68 | 4 | 4 | 3 | 2 | 3 | 2 | 3 | C | **PASS** | **Reject** |
| SYRUP | Fundamental Repricing | 56.00 | 53.20 | 48.36 | 4 | 3 | 2 | 1 | 3 | 3 | 2 | B | FAIL — Rule A (best F=3) | Reject |
| LDO | Fundamental Repricing | 59.00 | 50.15 | 45.59 | 3 | 3 | 2 | 2 | 4 | 4 | 2 | C | **PASS** | Reject |
| AERO | Fundamental Repricing | 59.00 | 56.05 | 50.95 | 3 | 3 | 3 | 3 | 4 | 2 | 3 | B | FAIL — Rule A (best F=3) | Reject |
| SUSHI | Fundamental Repricing | 56.00 | 47.60 | 43.27 | 2 | 2 | 3 | 2 | 4 | 5 | 2 | C | FAIL — Rule B (G=2) | Reject |
| ENA | Catalyst Repricing | 48.00 | 40.80 | 37.09 | 2 | 3 | 2 | 3 | 4 | 1 | 4 | C | FAIL — Rule B (G=2) | Reject |
| ONDO | Fundamental Repricing | 52.00 | 44.20 | 40.18 | 2 | 3 | 2 | 3 | 4 | 2 | 3 | C | FAIL — Rule B (G=2) | Reject |
| ZRO | Catalyst Repricing | 46.00 | 39.10 | 35.55 | 2 | 2 | 2 | 3 | 4 | 2 | 3 | C | FAIL — Rule B (G=2) | Reject |
| IMX | Fundamental Repricing | 46.00 | 39.10 | 35.55 | 2 | 3 | 1 | 3 | 3 | 2 | 2 | C | FAIL — Rule B (G=2) | Reject |
| RHEA | Fundamental Repricing | 40.00 | 34.00 | 30.91 | 2 | 3 | 0 | 3 | 3 | 1 | 2 | C | FAIL — Rule B (G=2) | Reject |
| VSN | Fundamental Repricing | 45.00 | 38.25 | 34.77 | 2 | 3 | 2 | 1 | 2 | 3 | 1 | C | FAIL — Rule B (G=2) | Reject |
| HYPE | Fundamental Repricing | 54.00 | 51.30 | 46.64 | 1 | 4 | 3 | 2 | 5 | 1 | 4 | B | FAIL — Rule B (G=1) | **Priced In** |
| PONS | Supply Repricing | 49.00 | 41.65 | 37.86 | 1 | 3 | 0 | 4 | 4 | 4 | 4 | C | FAIL — Rule B (G=1) | **Priced In** |
| STONK | Supply Repricing | 45.00 | 38.25 | 34.77 | 1 | 3 | 0 | 2 | 4 | 4 | 4 | C | FAIL — Rule B (G=1) | **Priced In** |
| SEI | Catalyst Repricing | 32.00 | 30.40 | 27.64 | 1 | 1 | 1 | 3 | 4 | 1 | 4 | B | FAIL — Rule B (G=1) | Reject |
| MON | Meme / Reflexive | 0.00 | 0.00 | 0.00 | 1 | 1 | 1 | 3 | 4 | 0 | 4 | C | **n/a — §52 VETO-5** | Reject |
| MARSCOIN | Meme / Reflexive | 51.00 | 48.45 | 44.05 | 1 | 0 | 0 | 3 | 2 | 3 | 4 | B | FAIL — Rule B (G=1) | Reject |
| UNI | Supply Repricing | 49.00 | 46.55 | 42.32 | 1 | 3 | 3 | 2 | 5 | 2 | 3 | B | FAIL — Rule B (G=1) | **Priced In** |
| GRT | Catalyst Repricing | 41.00 | 38.95 | 35.41 | 1 | 1 | 3 | 3 | 4 | 1 | 3 | B | FAIL — Rule B (G=1) | Reject |
| RUNE | Fundamental Repricing | 34.00 | 32.30 | 29.36 | 1 | 1 | 0 | 3 | 4 | 3 | 2 | B | FAIL — Rule B (G=1) | Reject |
| LIT | Fundamental Repricing | 33.00 | 28.05 | 25.50 | 1 | 2 | 1 | 2 | 3 | 1 | 3 | C | FAIL — Rule B (G=1) | Reject |
| 2Z | Catalyst Repricing | 28.00 | 23.80 | 21.64 | 1 | 1 | 1 | 3 | 2 | 1 | 2 | C | FAIL — Rule B (G=1) | Reject |
| ORE | Fundamental Repricing | 26.00 | 22.10 | 20.09 | 1 | 3 | 0 | 1 | 2 | 0 | 1 | C | FAIL — Rule B (G=1) | Reject |
| BTT | Fundamental Repricing | 0.00 | 0.00 | 0.00 | 0 | 0 | 2 | 2 | 3 | 3 | 2 | D | **n/a — §51 data gate** | **Data Insufficient** |
| WIN | Fundamental Repricing | 0.00 | 0.00 | 0.00 | 0 | 0 | 2 | 2 | 3 | 3 | 1 | D | **n/a — §51 data gate** | **Data Insufficient** |
| NEON | Meme / Reflexive | 32.00 | 22.40 | 20.36 | 0 | 0 | 0 | 2 | 1 | 2 | 3 | D | FAIL — Rule B (G=0) | Reject |

**Swept and eliminated on the same rule, shown so coverage is visible rather than implied:** XDC (FDV/MC 1.91, turnover 0.06 — thinnest of the 11; Cancun upgrade was Feb 2026), GRASS (dilution via pre-minted vault releases, −8.9% 24h against +57% 30D), VIRTUAL (weakest momentum, +14.8% 30D — a screen artifact), PLUME (6.606B of 10B circulating; the SEC-vault item is aggregator-only and pre-window), SUPER (CoinGecko names it **SuperVerse**; DefiLlama TVL **$35,445** against a $122.5M cap).

**§82 — why the top scores are what they are** (full text in `v4_run.py`):

- **AVA G4** — at −96.3% from ATH with 7D flat and 30D +19.9%, the market is not pricing a permanent buyback at all. The unknown is quantifiable (monthly settlement) and material as a yield.
- **AVA F4** — **primary source**: Travala's own blog, 2026-09-23, announces a *Permanent* Strategic Reserve — the Foundation buys back AVA equal to the prior month's member givebacks and Travala **independently matches it**, with a commitment never to sell or transfer. Direct + recurring + scalable. Not 5: ~$89–177K/month is not "large".
- **KNTQ G4 / F4** — Elysium sequencer revenue $/day is the unpriced variable: quantifiable, testable at T+0, material (50% is bought on-market). Capture is verified on-chain (KIP-5: 5,391,458 KNTQ at $0.15 avg = $808,719 over 5 months ⇒ 12.9M/yr = $3.97M/yr = 4.6% of cap).
- **KNTQ C3 not C4** — §57 score 4 requires a hard date *and* a clear economic impact. The date does not exist in any primary source.
- **KNTQ S2** — FDV/MC 3.57 and the buyback retires only **1.8% of the 719M still unissued per year**.
- **AERO F3 not F4** — sAERO exchange-revenue share is real and verified, but the revenue line is down ~78% from its 2024Q4 peak, so there is no growth headroom.
- **AERO C3 not C4** — the date is the strongest in the set (2026-10-21, primary source), but the AER Engine emissions-cap parameters that would make the economic impact clear are unpublished.
- **GRT F1** — there is no buyback and no burn. The token is *inflationary* at ~2.9%/yr (120.73 GRT/block, no max supply), and GIP-0089 — live 2026-09-01 — redirected 20% of issuance to a Foundation-managed multisig. **Token capture here is directionally negative: it is new sell-side supply.**

### The Attention score cap — stated, not assumed

v4 §58 score 4 requires several attention metrics rising in sync (mentions / engagement / search / volume / holders). With free data sources **only the volume leg is verifiable** — X mentions, Google Trends and holder counts are all behind paid or blocked APIs. So **Score A is capped at 3** unless a coin is independently corroborated as a CoinGecko-trending or dated-media name. The cap is asserted in code (`assert_attention_cap`), and it fired on PONS when PONS was first omitted, because PONS genuinely *is* on CoinGecko trending. No candidate in this scan was scored above 3 on attention.

---

## E. The v4 §85 Decision Tree — where each token stops

```
TOKEN FOUND
   │
   ├─ Data valid? ── NO ──► DATA INSUFFICIENT ....... BTT, WIN
   │        YES
   ▼
Hard veto? ── YES ──► REJECT ..................... MON (VETO-5, unlock ≈750% of float)
   │  NO
   ▼
Identify archetype
   ▼
Score 7 dimensions
   ▼
Evidence adjustment → Regime adjustment
   ▼
Information Gap ≥ 3? ── NO ──► REJECT ............ 22 candidates
   │       YES
   ▼
Primary driver ≥ 4? ── NO ──► REJECT ............. SYRUP, AERO (Rule A)
   │       YES
   ▼
Liquidity ≥ 2? ── all pass
   ▼
Confidence ≥ C? ── all pass
   ▼
Score threshold
   ├─ ≥85  DEEP DD .............. (none)
   ├─ 75-84 HIGH-PRIORITY WATCH . (none)
   ├─ 65-74 WATCH ............... (none)
   ├─ 55-64 SPECULATIVE ......... AVA (56.10)
   └─ <55  REJECT ............... KNTQ (53.55), LDO (50.15)
```

**Overrides applied after scoring (§69):** STONK, PONS, HYPE, UNI → **Priced In**.

---

## F. What Changed From The v3 Round, And Why

This is the part that matters, because the v4 framework did not confirm the previous round — it reversed it.

### 1. KNTQ was downgraded from Deep DD to Reject

v3 called it the single Deep DD. v4 scores it **53.55 → Reject**. The cause is not a disagreement about the thesis; it is that the v3 round's *own* two corrections turn out to be exactly the two dimensions v4 weights.

| | v3's finding | v4 consequence |
|---|---|---|
| "The project has **never published** an Elysium mainnet date" | recorded as a caveat | → **C = 3** (§57: official event, no hard date) |
| "FDV/MC **3.57**" | recorded as "the biggest negative" | → **S = 2** (§60) |
| Buyback **retires 1.8% of the 719M still unissued** | *not computed in v3* | → the mechanism is far weaker against dilution than the 4.6% headline implies |

**AVA outranks KNTQ**, and the entire difference is supply structure: AVA is fully circulating at FDV/MC 1.00 with a *permanent* reserve commitment; KNTQ has 72% of its supply still to issue and a buyback that retires less than 2% of the overhang annually.

### 2. A framework gap v4 does not close — and it is the most important finding in this report

**AVA tops the formal ranking, and the flow arithmetic says its mechanism cannot move its price.**

| | AVA | KNTQ |
|---|---|---|
| Annualised buyback as % of cap | 5.97% | 4.61% |
| **Buyback per day** | **$2,912** | $10,877 |
| **24h volume** | $9.50M | $2.37M |
| **Buyback as bps of daily turnover** | **3.1 bps** | 45.9 bps |

A 5.97% buyback *yield* is an accounting identity. As a *flow*, AVA's buyback is three basis points of daily turnover and cannot support a price. Even at 20× the current buyback, with volume scaling pro-rata, it is 2.6 bps.

**This is a structural hole in v4.** The framework ranks *information gaps* (G) heavily and separately handles *reality checks* (§74–77), but it has **no mechanism for discounting an information gap that the available mechanism is too small to close.** AVA can have a real, unpriced, well-evidenced information gap (G=4) and a mechanism that cannot monetise it, and the score will still rank it first. I have kept the two questions separate rather than resolving it by quietly lowering a score to match my conclusion — that would be letting the conclusion drive the input, which is the error this entire framework exists to prevent.

### 3. The v3 screen could not see two of v4's six archetypes

v3 ranked candidates by `holders revenue ÷ market cap` off DefiLlama. That can only surface protocols that already publish a token-capture line, so **Attention Repricing (C) and Meme/Reflexive (D) were structurally excluded before scoring began.** A new 60-name attention/velocity screen was built to correct this, and it was adversarial-DD'd.

**Result: 1 of 11 had a dated, project-published, in-window event — and it was already public.** The cohort is pure momentum.

- **RUNE** — +68% 30D while Aug swap volume **−23%** and System income **−23%**; THORChain **cut** the RUNE burn from 5% to 1% of System Income on 2026-09-23 (primary source). The tightest supply structure in the cohort (FDV/MC 1.08, realised supply −6.8%/yr) is attached to a *reduced* cash-flow mechanism.
- **SEI** — the +67% was an ETF **filing** (2026-09-21) with **no scheduled SEC decision date**. The only firmly dated in-window events are **bearish**: 113.0M SEI (~$5.53M) unlocking 10-15 and 11-15, ~87% to private investors and insiders.
- **GRT** — the one real catalyst (10-08), already public since 09-25. Token is inflationary with a fresh 20%-of-issuance Foundation redirect.
- **MARSCOIN** — misidentified in my own screen (§A). Its entire move is a Binance Seed-Tag listing from **2026-09-04, three and a half weeks before the window opens**. >80% turnover with reported liquidity "only a small fraction" during a 20×-perp week: that is leverage, not depth (§59's Volume ≠ Liquidity).

### 4. Newly measured net supply — independent confirmation of v3

Realised circulating supply = historical market cap ÷ historical price, 180-day window (`supply_delta_v4.py`). **The 30-day rate is the forward-looking one; annualising a 180-day change gives a historical rate, not a forecast.**

| Token | 30D realised | 180D realised (ann.) | Volume velocity (3d vs prior) |
|---|---:|---:|---:|
| AERO | **+1.330%** (+16.2%/yr) | +14.7%/yr | 2.64× |
| ENA | **+2.719%** (+33.1%/yr) | +38.3%/yr | 2.59× |
| RHEA | **+4.999%** (+60.8%/yr) | **+215.1%/yr** | **19.38×** |
| KNTQ | +0.003% (+0.04%/yr) | +7.9%/yr | **0.92×** |
| AVA | −0.010% | +6.2%/yr | 1.07× |
| LDO | **−0.524%** (−6.4%/yr) | −4.7%/yr | 1.59× |
| RUNE | **−0.559%** (−6.8%/yr) | −13.0%/yr | **10.61×** |
| UNI | −0.429% (−5.2%/yr) | +1.6%/yr | 2.46× |
| HYPE | −0.036% | −13.6%/yr | 1.14× |

This **independently confirms v3's AERO figure** (+17.4%/yr measured, +16.2%/yr here) and adds two findings the v3 round did not have: **LDO's and RUNE's circulating supply are genuinely contracting**, while **KNTQ's volume is decelerating (0.92×)** — which is what a Score A of 2 should mean, measured rather than asserted.

---

## G. Top Candidates — Detail

### G.1 AVA (Travala) — the only survivor, and the reason it is only a survivor

**Formal status: Speculative / Low Priority (56.10).** This is the second-lowest band in v4. It is not a recommendation.

| | |
|---|---|
| MC / FDV | **$17.80M / $17.80M** (FDV/MC **1.00**, 74.37M/74.37M fully circulating) |
| Price / 30D / 7D | $0.2395 / +19.9% / **−0.1%** |
| From ATH | **−96.3%** |
| Turnover | $9.50M/24h = 53% of cap |
| Realised supply | −0.01% over 30d (issuance has stopped) |

**Mechanism (primary source, [Travala blog 2026-09-23](https://www.travala.com/blog/travala-launches-ava-strategic-reserve)):** the Foundation buys back AVA equal to the prior month's member givebacks, and **Travala independently matches it**. The reserve is **permanent** — a commitment never to sell or transfer. This is structurally better than SYRUP's (treasury, re-deployable) and VSN's (treasury, not burned).

**The one key number:** monthly settlement size, observable on the 15th-ish of each month.
- **Confirm:** ≥$90K/month sustained, and Travala's matching leg confirmed at 1:1.
- **Invalidate:** a month below $50K, or any disclosure that the "permanent" reserve is in fact re-deployable.

**Bull / Base / Bear / Extreme**

| Scenario | Condition | Reading |
|---|---|---|
| Bear | Matched leg is smaller than claimed, or the reserve is re-deployable | The "permanent" framing collapses; G drops to 2 |
| Base | ~$89K/month continues | 5.97% annualised yield accrues; price does not respond |
| Bull | Travala matching confirmed at 1:1 **and** Travala's own contribution grows | ~11.9%/yr; the yield becomes arguable at scale |
| Extreme | AVA is re-framed from a treasury token to a cash-flow asset and someone capitalises the yield | This is the only route to a real re-rate, and it is a *narrative* event, not a flow event |

**2×/5×/10×/20× reality check** (base $1.063M/yr):

| Target | Target MC | Required @5% | × current | Required @10% | × current |
|---|---:|---:|---:|---:|---:|
| 2× | $35.6M | $1.78M | **1.67×** | $3.56M | 3.35× |
| 5× | $89.0M | $4.45M | **4.19×** | $8.90M | 8.37× |
| 10× | $178.0M | $8.90M | **8.37×** | $17.80M | 16.74× |
| 20× | $356.0M | $17.80M | **16.74×** | $35.60M | 33.49× |

**v4 §76 verdict:** 10× is *arithmetically* reachable (8.4× buyback growth is not absurd) but **not via the buyback's flow effect** — it requires the market to change how it values a $1M/yr stream. **10× = supported by a narrative re-rating, unsupported by a fundamental one.** That distinction is the whole answer for this name.

### G.2 KNTQ (Kinetiq) — passes every hard gate, fails the score

**Formal status: Reject (53.55), yet it is the only candidate besides AVA to clear all four of v4 §67's gates.** That combination is the most interesting result in this report, and §H explains why it is not a contradiction.

| | |
|---|---|
| MC / FDV | **$86.10M / $306.96M** (FDV/MC **3.57**; 280.48M of 1.0B circulating) |
| Price / 30D / 7D | $0.3070 / +62.1% / **−3.7%** |
| From ATH | −18.6% |
| Turnover | $2.37M/24h = 2.75%; DEX depth only ~$1.2M |
| Realised supply | +0.003% over 30d; **volume velocity 0.92× — decelerating** |

**Mechanism:** Elysium (Hyperliquid's first L2) mainnet → 50% of sequencer revenue bought on the open market → KIP-5 routes all buybacks to the Hyperliquid Assistance Fund → **permanent removal**. KIP-2 adds 70% of protocol revenue + 100% of validator commission.

**Verified cash flow (primary source, [KIP-5, 2026-09-16](https://kinetiq.xyz/blog/kip-5-kntq-buybacks-assistance-fund)):** 5,391,458 KNTQ purchased at $0.15 avg = $808,719 over 5 months ⇒ **12.9M KNTQ/yr = $3.97M/yr = 4.61% of cap.** Independently cross-checked by KIP-5's own "~13% APY on >33% of float staked", which back-solves to 12.0M/yr.

**The catalyst date is L4, and I re-traced it this round:** the "20 Oct 2026" figure originates from a **CoinMarketCal** calendar entry, relayed by TradingView and a CoinMarketCap AI summary. Kinetiq's own blog has never published a mainnet date. Testnet has been live since 2026-09-22 with a stated four-week public test.

**The one key number:** **Elysium sequencer revenue, $/day**, first disclosed at T+0.

| Scenario | Sequencer revenue | Required buyback | Interpretation |
|---|---|---|---|
| Bear | < $5K/day | <$0.9M/yr | "Another unused L2"; +62% gives back |
| Base | $5–50K/day | $0.9–9M/yr | On top of $3.97M existing ⇒ $4.9–13M/yr (5.7–15% of cap) |
| **Bull** | **$50–100K/day** | $9–18M/yr | **$13–22M/yr = 15–26% of cap** ⇒ real re-rate |
| Extreme | >$100K/day + kHYPE recovery | >$18M/yr | Net-deflation narrative established |

**Capture-rate translation (v4 §75).** Only 50% of sequencer revenue is captured, so the multiples become:

| Target | Required incremental buyback | ⇒ required Elysium sequencer revenue | per day |
|---|---:|---:|---:|
| 2× @5% | $4.64M/yr | $9.28M/yr | $25.4K/day |
| 5× @5% | $17.55M/yr | $35.11M/yr | **$96.2K/day** |
| 10× @5% | $39.08M/yr | $78.16M/yr | $214.1K/day |

**v4 §76 verdict: 10× is unsupported by the fundamental route.** 5× requires ~$96K/day — **roughly twice the $50K/day that would merely confirm the thesis** — on an L2 that would be about six weeks old, whose parent ecosystem already settles spot trades on its own mainnet.

**Flow reality check:** the buyback is $10,877/day against $2.37M/24h volume = **45.9 bps of turnover**. That is ~15× more meaningful than AVA's, which is why KNTQ's mechanism is not dismissed here even though its score is lower.

**The dilution arithmetic that v3 did not compute:** the buyback retires 12.9M/yr against **719.5M still unissued = 1.8% of the overhang per year.** The 4.6% headline yield and the 3.57× FDV/MC are not in conflict — they are the same fact seen from two sides, and the second side is the larger one.

**Invalidation:** mainnet slips past 2026-11-30 with no new date ⇒ catalyst cancelled. Mainnet live + 30 days of ramp with sequencer revenue < $5K/day ⇒ thesis void.

---

## H. Two Findings About The v4 Framework Itself

v3 §46 instructs: if the logic is wrong, say so. Two things about the formal system are worth flagging, because both change how the table should be read.

### H.1 §67 and §68 disagree, and the disagreement is currently binding

A candidate can clear **every hard gate** in §67 — real information gap (G≥3), a primary driver ≥4, exitable liquidity, acceptable evidence — and still be labelled **Reject**, purely because its weighted score lands below 55. **KNTQ is exactly this case:** qualification PASS, score 53.55, status Reject.

§67 says a qualified candidate is "not a Reject". §68's threshold table says <55 is Reject. Both are in the document. In this run **§68 was applied as written**, because it is the explicit threshold rule and the user asked for the formal system to be applied. But the practical consequence is that the 55 bar, not the gate, is doing the eliminating for the two best candidates — which is a different research conclusion from "these fail the framework's entry test."

The engine reports `Qualification` as a separate column from `Status` precisely so this is visible rather than buried.

### H.2 There is no mechanism for discounting a gap the mechanism cannot close

Detailed in §F.2. AVA scores G=4 with verified capture and a clean supply structure, and its buyback is 3.1 bps of daily turnover. v4 weights the information gap and handles reality checks separately, but nothing joins them. A score-based ranking will keep surfacing names where the identified information gap is real and the identified mechanism is too small to monetise it.

**This is not a reason to reject the framework.** It is a reason to read `Status` and the reality-check table as two different questions, and never let the first substitute for the second.

---

## I. Sensitivity — The Result Is Not Robust

Because AVA sits 1.10 points above the 55 bar and KNTQ 1.45 below it, the headline is sensitive to judgement calls that are genuinely contestable. Full output: `tools/catalyst_scan/sensitivity.py`.

| Axis | Contestable call | Effect on the result |
|---|---|---|
| **KNTQ Catalyst** | Does a verbally-confirmed, never-published date score C=2 or C=3? | C=2 → 51.00; C=3 → 53.55; C=2 + evidence D → 42.00. **Reject under all three.** Robust. |
| **AVA evidence** | B (official + accounting) or C (official + secondary)? | C → 56.10; B → 62.70; A → 66.00. **Status changes at A.** |
| **AVA Fundamental** | Is a $89–177K/month buyback "large" enough for F=4? | F=4 → 56.10; F=3 → 51.85. **Status changes.** This is the most contestable single number in the report. |
| **KNTQ Supply** | S=2 / S=1 / S=0 | 53.55 / 51.85 / 50.15. Reject throughout. |
| **Regime factor** | 0.90 → 1.10 | At **0.95 the field is empty**: AVA 53.30, KNTQ 50.87. |
| **The 85 bar** | Any setting, any axis | **Nothing reaches Deep DD under any combination tested.** |

**The defensible summary:** *the ordering AVA > KNTQ > everything else is stable, and the conclusion that nothing here is a Deep DD is stable. The exact status of AVA — the only survivor — is not.*

---

## J. Limitations — Stated, Not Buried

1. **No backtest. No statistical claim. No win rate.** This is event research under a scoring framework. It is not evidence that any of these tokens will trade profitably, and nothing here is a buy recommendation.
2. **The attention dimension is structurally capped.** Only the volume leg of §58 is verifiable with free data. Every Score A in this report is ≤3 for that reason, not because attention is uniformly low. **No candidate in this scan could have been scored Attention Repricing at a score that would justify the archetype's 30% weight.**
3. **DEX order-book depth was unobtainable for the entire momentum cohort** — DexScreener returned HTTP 404 for all 11 symbols. Those are CEX-volume names with negligible on-chain footprint, so the Volume-vs-Liquidity distinction could not be tested on them. This is the single largest evidence gap in the report.
4. **Token unlock calendars are assembled from free sources.** Tokenomist per-coin charts and the DefiLlama emissions API are paywalled (HTTP 402). The 2Z / ENA / MON / SEI unlock figures are the least-verified load-bearing numbers here.
5. **Two source conflicts remain unresolved.** CARDS circulating supply disagrees between CoinGecko (543.89M) and the project (429.6M). ORE max supply is stated as both 3,000,000 and 5,000,000. Neither is a candidate this round, but neither was resolved.
6. **A CoinGecko data trap remains live:** `total_volume` can be off by orders of magnitude (SAND showed vol/MC = 292× in the v3 round). The attention screen applies a vol/MC ≤ 25 filter and re-checks outliers, but the trap is in an upstream field and cannot be eliminated from the client side.
7. **Momentum screens decay faster than the research cycle.** RHEA was −4.7% on 24h when screened and −30.4% when checked 40 minutes later. **This candidate table will be stale within days; the elimination *reasons* will not.**
8. **Subagent research was adversarial but serial**, and one of the two research passes was shallower on its lower-priority half by design. The 5–11 cohort sweep in particular deserves a second pass if any of those names matters later.

---

## K. Reproduction

```
tools/catalyst_scan/v4_evidence.py      fresh CoinGecko + DefiLlama pull, attention screen
tools/catalyst_scan/v4_quick.py         fast path: writes the market + screen files immediately
tools/catalyst_scan/supply_delta_v4.py  realised net supply + volume velocity, 180d window
tools/catalyst_scan/regime.py           regime primitives + breadth + category performance
tools/catalyst_scan/reality_check.py    2x/5x/10x/20x + the flow reality check
tools/catalyst_scan/v4_score.py         THE ENGINE: vetoes, weights, gates, thresholds, anti-rules
tools/catalyst_scan/v4_run.py           the candidate set with per-dimension s82 justifications
tools/catalyst_scan/sensitivity.py      the six axes above
tools/catalyst_scan/verify_v4.py        THE GATE: 538 checks
```

Artifacts in `tools/catalyst_scan/out/`: `v4_evidence.csv`, `attention_screen.csv`, `supply_delta_v4.csv`, `regime.md`, `regime_categories.csv`, `reality_check.md`, `v4_ranking.md`, `trending.txt`.

```
.venv\Scripts\python.exe tools\catalyst_scan\v4_run.py
.venv\Scripts\python.exe tools\catalyst_scan\verify_v4.py     # must print ALL PASS
```

**The gate checks (three layers):**
- **Part 1 — engine invariants.** Every archetype's weights sum to 100 and cover all 7 dimensions; the document's own worked example (§63) reproduces at 74; `final = raw × evidence × regime` exactly; all ten §68 threshold boundaries inclusive; a hard veto beats a §69 override; Confidence E and the §51 data gate both exclude; each of §67 Rules A–D in isolation; each of §70–73 anti-rules; the regime factor cannot promote a gate-failing candidate; out-of-range dimensions and unknown archetypes raise.
- **Part 2 — the machine-generated table.** Every cell of every row of `out/v4_ranking.md` re-parsed and re-derived. (Comparing the engine against its own return value would be tautological; the real failure mode is transcription, so the gate reads the published file.)
- **Part 3 — the report itself.** The §81 table in this document is parsed straight out of the markdown and every cell compared to a fresh engine run. This is the layer that catches a figure edited by hand in the prose after the fact.

**The gate has already caught four real defects**, which is the point of running it:
1. The attention cap fired on PONS when it was first omitted (PONS genuinely is CoinGecko-trending, so the fix was to record the corroboration, not lower the score).
2. Double-rounding through 1-decimal display produced **six false failures**. A gate that cries wolf gets ignored, which is worse than no gate — the fix was to publish 2 decimals, not to widen the tolerance until it stopped complaining.
3. Part 3 caught **26 abbreviated archetype names** in this report's table ("Fundamental" for "Fundamental Repricing"). Harmless as prose, wrong as a published table cell.
4. A hand-written sensitivity row passed the unvaried candidate instead of the variant, printing an identical "C=2" line beside the "C=3" line. Found by reading, not by the gate — a reminder that a gate covers what it was written to cover and no more.
