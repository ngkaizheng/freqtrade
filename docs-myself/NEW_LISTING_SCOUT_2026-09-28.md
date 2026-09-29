# NEW-LISTING / LISTING-EVENT MICROSTRUCTURE — literature + feasibility scout

**Date:** 2026-09-28. **Author:** research scout (delegated). **Status:** scouting only — no
strategy written, no data downloaded, no backtest run, no line opened.

**Scope:** the brief asked about opening-price overshoot, first-day/first-hour return
distribution, direction, magnitude in bps, event rate, costs, data availability,
practitioner implementations, and delisting.

**Headline:** the brief's central worry — that this line is underpowered on arrival — is
**wrong by an order of magnitude**. But the effect the brief asked about (intraday opening
overshoot) is **not the effect the literature documents**, and the effect it does document
is a slower, days-horizon reversion with a different, non-obvious entry timing.

---

## 1. EVENT RATE — the brief's premise is wrong, and this is the most important finding

The brief assumed "a major exchange lists only ~10-20 new perps per year … n=50-100 over 5
years … a lead that is underpowered on arrival is not worth pursuing."

**Measured rate on Binance USDT-margined PERPETUALS, four independent sources:**

| source | figure | implied/yr |
|---|---|---|
| CoinGecko, *2026 State of Crypto Perpetuals Report* (May 2026) — "Binance added **305 new perpetuals markets** against 125 new spot listings in the past 16 months" (Jan 2025–Apr 2026) | 305 / 16 mo | **~229** |
| This repo, counted 2026-09-28 from Binance `exchangeInfo` by rule (`docs-myself/PREREG_WIDENED_UNIVERSE_2026-09-28.md`): 66 onboarded 2023, 94 in 2024, **210 in 2025**, 52 in 2026 YTD; 527 total | 210 (2025) | **~210** |
| bykaranteli.com live listing tracker — **five** Binance USDT perps first seen on 2026-09-28 alone (OKLO, CVNA, RUM, TWST, XOM) | 5/day observed | — |
| FMZ Quant (2023-11-20) — "As of November 16, 2023, Binance has listed a total of 86 currencies, averaging more than one every three days" | 86 (11 mo) | ~94–112 |
| moltbook agent "Wink", self-reported — 527 Binance perp listings over 2024–2025 | 527 / 2 yr | ~264 |

CoinGecko also: "6 out of the top 11 exchanges listed an average of **<20 perpetuals
contracts a month**." MEXC 879 and BingX 565 over 16 months; Binance is far more
conservative than the long-tail venues.

**Verdict:** ~200-265 new Binance USDT perps/yr in 2024-2026, ~66-112/yr in 2023.
**≈422 new Binance USDT perps in 2023-2026 (the repo's own cohorts B-E).** That is ample to
detect a 35 bps effect. Per AGENTS.md §1a this line **is** capable of concluding — unlike the
Shark Hunter lead. Say so early, because it reverses the brief's default.

---

## 2. MAGNITUDE — documented, large, and in the OPPOSITE direction to the brief's framing

All figures are **GROSS**. **Not one source in this report includes transaction costs.**

| source | type / status | object | n | period | number |
|---|---|---|---|---|---|
| **Ante (2019)**, *Market Reaction to Exchange Listings of Cryptocurrencies*, BRL WP No. 3 | working paper, **not peer reviewed** | cross-listings, 22 exchanges, daily OHLC from CoinMarketCap | **327** events / 180 coins | 2018-19 | day-0 CAAR **+5.7%** (t=2.99); **(+1,+3) = −1.5% (t=−1.82)**; **Binance n=45: day-0 +14.7%, (+1,+3) −6.3%** |
| **Momtaz (2019)**, *European Journal of Finance* | **PEER REVIEWED** | first exchange listing | — | — | first-day abnormal return **+14.8%** |
| **Benedetti (2019)**, SSRN 3267392 | preprint | token cross-listings, 108 marketplaces | 3,625 tokens | — | raw cum return **+49%** over 2 weeks |
| **Benedetti & Kostovetsky (2019)**, SSRN 3182169 | preprint | ICO first listings | — | — | abnormal buy-and-hold **+48%** first 30 trading days |
| **Ren & Heinrich**, via CoinDesk 2023-01-06 | **Medium blog post** | Binance **spot** listing | **26 coins / 18 mo** | ~2021-22 | **+41% day+1**, +24% day+3, 30d max +73% |
| **GSR (Riezman & Santer, 2026-09-21)** | market-maker research desk, via ChainCatcher/BTCC | token issuance incl. **DELISTED** | **2,300+** | 2013-2026 | median falls **below issue price within 3 days**; **−20 to −25% at 1 month**; −50% at 90d; FDV >$1B **−81% at 1yr** |
| **FMZ Quant (2023-11-20)** | practitioner blog | **Binance USD-M perps**, 4h klines | 86 | 2023 | "after new contracts are listed, they **almost all fall**, and the longer they are listed, the more they fall"; index-relative decline **worse** than market |
| moltbook "Wink" | **AI agent, self-reported backtest** | perp listing short | 527 Binance | 2024-25 | +1887%, Sharpe 0.98 — **DO NOT CITE, see §7** |

**Against the project's 12–35 bps round-trip hurdle:** Ante's −1.5% over three days is
**150 bps**; his Binance-specific (+1,+3) is **≈−630 bps**. Even a 5% capture of the former
clears the 34.9 bps COVID stress by 2x. **On magnitude, this is not a close call** — it is
the first listing framing where the documented effect is not a rounding error against cost.

---

## 3. DIRECTION — consistent across all sources, and it is a REVERSION

**Answer to the brief's Q3: the premium reverts, and it reverts hard. Every independent
source agrees on the sign, across three different eras, three different venues and both spot
and perps.**

- Ante 2019: day-0 **+5.7%** → (+1,+3) **−1.5%, t=−1.82, significant**. "For the three days
  after the listing, the returns are significant and negative (−1.5%) … more traders use the
  increased liquidity to liquidate than new traders are attracted." Binance alone: +14.7% then
  **−6.3%**. His own trader advice: **"buy the rumor, sell the news."**
- The Tie (2026), 1,844 events, 5 exchanges, Jan-2023–Jun-2026: "the adjusted return going
  flat or **turning negative shortly after listing**"; "first-listing tokens show the
  **steepest post-listing price decline**"; small-cap quintiles show "a more pronounced
  post-listing decline consistent with **speculative buying followed by distribution**";
  separation **widens at 2–3 months**.
- RockawayX (2024, Binance/Bybit/MEXC): Binance listings show "a small increase before
  listing, a pump up to several days post listing, and then this gradually **sells off** back
  down to no ROI over 30 days."
- GSR 2026: median **below issue price within 3 days**.
- FMZ 2023 (Binance perps specifically): "almost all fall"; and the index-relative check
  "still looks the same — a continuous decline. In fact, it has **declined even more**
  compared to the index."

### The contradiction, and its resolution — this changes the entry timing

**RockawayX's own TL;DR says the opposite**: "**7 days post-listing, Bybit and Binance
listings were bullish**" and it recommends "buy … on the day of listing and sell before the
7th day."

Both are right on different windows. There **is** a day-0→day-7 continuation (the pop), and
there **is** a week-2→day-90 reversion. **Therefore the brief's implied entry — fade the
opening overshoot, i.e. be short from t=0 — is the wrong entry timing.** The moltbook agent
found the same thing independently and without access to the others: "**Delay matters:
entering immediately = worse results.** Waiting 24h lets the hype fade — then the dump is
more predictable." Entry 24h after listing.

**Three independent sources now agree the tradeable entry is AFTER the pop, not at it.**

---

## 4. COSTS — the brief's worry is correct, but there is a large, verifiable mitigant

The brief is right that listing-day books are thin and wide; the repo has already measured
the long tail (thin-side depth within 0.2% from $10,420 NEO to $43.3M BTC — three orders of
magnitude). A brand-new perp sits at the thin end, and a gross edge must be measured against
a listing-day spread, not the 12.0 bps calm-day constant.

**Mitigant found, primary source, and almost certainly unknown to this project:**

> **Binance runs a ZERO-MAKER-FEE promotion for the first 10 days of every newly-listed
> USDT-margined perpetual.**
> Source: [Binance official announcement, 2025-07-24, amended 2025-10-27](https://www.binance.info/en/support/announcement/detail/06f67008a3ea4caebecc0cb266c26401).
> Verbatim: *"During the first 10 days of each new contract's launch (Incentive Period), all
> users can enjoy **0 maker fees**, while all qualified liquidity providers will benefit from
> higher maker rebates."* Incentive Period runs from Day-0 launch time to **Day 9 23:59
> UTC**. Taker fee unchanged (standard per VIP level).

**Implication:** for a passive/maker implementation the fee leg of the 12-35 bps round trip is
**0 bps, not 10 bps**; the residual is spread crossing plus queue adverse selection. That is a
cost regime unlike any other line in this repo.

> ⚠ **The promotion's stated validity was 2025-07-25 → 2026-01-16 (amended 2025-10-27) and
> has therefore EXPIRED as of today (2026-09-28).** Whether it was extended, renewed or
> allowed to lapse **must be re-verified from Binance's announcement page before any
> preregistration is written.** Do not build a cost model on it without checking.

**Three counter-caveats that partly cancel the mitigant:**

1. The promotion exists to **attract market makers**, so the book may be artificially deep
   for exactly the 10 days you want to trade, and the depth **evaporates on Day 10**. Any
   backtest straddling the boundary is contaminated. Note this aligns almost exactly with the
   24h-entry/2-week-hold object in §3 — the tradeable window sits **inside** the incentive
   period, which is convenient but also means the 2023-2024 events have **no** such promotion
   and must be costed differently.
2. **Freqtrade has no slippage and no queue model** — already logged in this repo as a trap
   ("*a TWAP / market-impact / execution strategy CANNOT be evaluated in this engine at all*").
   A listing-pop fade is substantially an **execution** strategy: its core variable is fill
   probability at the touch, which is not expressible. **This is a structural blocker, not a
   detail.**
3. The brief's arithmetic warning stands: a gross 40 bps can be entirely consumed by crossing
   a 50 bps listing-day spread. **Re-measure realised spread at listing from `bookDepth` /
   aggTrades before sizing anything.** Usefully, `bookDepth` covers **2023-01 onward**, which
   happens to cover the whole 2023-2026 event window — one of the few lines where the repo's
   existing historical depth data aligns with the sample.

---

## 5. DATA AVAILABILITY

- **A ready-made listing registry exists and removes the hardest data problem.**
  [bykaranteli.com/listings](https://bykaranteli.com/listings): "Tracks new USDT-perpetual
  listings across Binance, OKX, Bybit, Gate.io, HTX and BingX, **refreshed hourly**. Every
  dated entry below was first seen by the scanner after the tracking baseline." It also
  exposes a free-datasets page and per-symbol live derivatives data. **Use this as the event
  date source, not a hand-built one.**
- **The manual-dating trap is documented by someone who hit it.** RockawayX: listing data "was
  pulled via Binance's publicly available API … However, **tokens defaulted to the start of
  the month, and therefore each one had to be manually updated by checking timelines per token
  on TradingView**," and "not all of the listed tokens were joined to CoinGecko correctly."
  A listing event dated to the 1st of the month is a silent, catastrophic data error.
- ⚠ **OPEN QUESTION, must be resolved locally:** this repo's `COMMUNITY_STRATEGY_REVIEW`
  records that "**Binance's public `exchangeInfo` no longer returns `onboardDate`** (queried
  2026-09-27)". I could **not** re-verify this. If true, `onboardDate` is not a usable event
  date and the bykaranteli registry must replace it everywhere.
- **Delisted contracts remain permanently unobservable** — no public registry. This biases
  the event pool *within* the sample, on top of the universe-level bias the repo already
  carries.

---

## 6. THE INTRADAY OBJECT IS GENUINELY UNMEASURED — double-edged

The brief asked specifically about the first-hour distribution and opening overshoot. **No
source found measures it.** Every listing study above uses **daily** bars; the closest is FMZ
at **4h**, and FMZ itself concedes "the listing time does not necessarily coincide with the
4-hour mark, which is a bit imprecise."

The best-designed modern study states the gap in its own limitations. The Tie (1,844 events,
2023-2026), verbatim: *"**OHLCV only for price.** The price return calculation uses daily
VWAP rather than intraday data. **The first hours of trading on a new exchange, which may
produce the largest moves, are averaged into the Day 0 bar along with the rest of that
trading day.**"*

**So: a real literature gap — and also no prior to lean on.** Two further signals that this
area is mined-out rather than virgin:

- It is served almost entirely by **vendor research desks selling data or listing consulting
  to issuers** (The Tie/CCData, RockawayX, GSR) and Medium posts. Per AGENTS.md §1.2 that
  should *lower* the prior, not raise it.
- **The headline magnitudes decay monotonically as method quality improves**: 41% (n=26,
  Medium post) → 14.7% (n=327, working paper with a market model) → "largely dissipates … or
  turns negative" (n=1,844, vendor study with BTC adjustment and winsorisation).

---

## 7. PRACTITIONER IMPLEMENTATIONS — and a cautionary tale

- **GitHub: nothing.** Two platform searches for listing-arbitrage / listing-sniping bots
  returned **zero results**. There is no open-source reference implementation to audit.
- The only concrete implementation claim located is from **another AI agent**, on an
  AI-agent social network: [moltbook.com, "Wink", ~232 days old](https://moltbook.com/post/400fb340-94dc-4d3e-8326-fd0fd2352e6a).
  Short new perp listings; entry **24h after listing**; exit TP 30% / SL 20% / 14-day hold;
  claims **527 Binance trades over 2024-2025, +1887%, Sharpe ~0.98**.

**Do not carry that number forward.** Three reasons:

1. Self-reported backtest by an AI agent, no code, no data, unauditable.
2. It reports **one cell out of an explicit 500-combination parameter sweep** ("500 combos
   across delay, hold period, SL, TP"). This is precisely the multiple-testing error the
   charter exists to prevent — the best of 500 unadjusted trials will show a Sharpe near 1
   essentially regardless of signal. It is a *textbook* artifact.
3. Its parameters (30% TP / 20% SL) describe a **low-turnover directional bet on new
   listings**, not a microstructure edge. It is not competing for the same object as a
   12-35 bps intraday hypothesis.

Its one **qualitative** finding is worth keeping, because it matches FMZ independently:
entry delay matters, and immediate entry is worse.

Also noted: [finder-arbitrage.com "New-listing arbitrage: 5-30% windows on CEX"](https://finder-arbitrage.com/blog/new-listing-arbitrage)
advertises 5-30% windows. This is a **paid service pitch**; the "5-30%" is a marketing claim
about cross-exchange price gaps with no auditable method. Treat as a lead to the existence of
practitioners, not as evidence.

---

## 8. DELISTING — underpowered and data-blocked; do not pursue

- Exchange-level delisting events are real and dated: Binance delisted **KDA, FLM and PERP on
  12 Nov 2025** ([TradingView](https://www.tradingview.com/news/coindar:0faa92765094b:0-perpetual-protocol-to-be-delisted-from-binance-on-november-12th/);
  [Blockinsider](https://blockinsider.com/crypto/flm-kda-perp-experience-market-shocks-following-binances-delisting-announcement/)
  — "The announcement of the delisting led to significant volatility"). **No numbers published.**
- **No rigorous event study of exchange delisting was found.** The repo already holds Ammann
  et al. (2022) on CoinMarketCap delistings (39.5% delisted, mean −77.8%) — but CMC delisting
  typically **follows** exchange delisting rather than causing it, so it does not establish a
  tradeable exchange-level signal.
- **Structural blocker, already documented here:** "there is **no public registry of delisted
  USD-M perpetuals**." The event rate is tiny (Binance delists in batches of 2-5, a few times
  a year at most), and the repo has no survivorship-corrected price data to measure it.
  **Verdict: close.**

---

## 9. RECOMMENDATION TO THE PARENT

**Do NOT open this as an intraday opening-overshoot fade.** That framing is (a) unmeasured by
anyone, (b) contradicted on *entry timing* by the only two sources that have actually looked,
and (c) blocked by the repo's own recorded fact that Freqtrade cannot express queue position
or fill probability — which is the entire content of "fade the overshoot."

**Do consider the reframed object: short the newly listed Binance USDT perp starting ~1 day
after listing, holding ~2 weeks.** It is a discrete, datable, well-powered event study whose
documented gross magnitude (150-630 bps over 3 days) is 4-18x the 35 bps stress round trip.
This is the first listing framing in this project where the effect is not a rounding error
against cost.

**Three things would kill it. All three are testable before any strategy code is written:**

1. **⚠ MOST LIKELY FAILURE MODE — it is probably beta, not alpha.** A "short everything newly
   listed" book targets *by construction* the weakest segment of a falling alt market. The
   repo has already been burned by exactly this: `PerpShort4hDeploy` was shown to be a
   market-timing overlay whose control book also lost money. **The mandatory control is a
   short book on an age-matched set of OLD perps over identical calendar windows**
   (`tools/perp_short/beta_check.py`, `r_stats.market_excess()` already exist). FMZ's
   index-normalisation is a weak version of this and it still showed decline, which is the one
   piece of good news — but FMZ normalises to the *equal-weight of all perps*, not to matched
   old perps. **If new-listing shorts do not beat age-matched old-perp shorts, the line is
   beta and it closes.**
2. **Survivorship inside the event pool.** A perp must survive to yield 2 weeks of forward
   data, and new Binance perps get delisted. GSR's 2,300-token dataset is the only listing
   study in this report that controls for this — and it is not public.
3. **Executability.** The whole edge is a short-side entry into a thin book, and the engine
   fills at the candle price with no slippage. **Measure realised listing-day spread from
   `bookDepth`/aggTrades first**, exactly as the 12.0/15.6/22.8/34.9 bps constants were
   measured. `bookDepth` starts 2023-01, which covers the event window.

**Multiple testing:** the effect has been hunted by ≥2 research vendors and 1 AI agent, and
magnitudes decay as method quality improves. Deflate any target accordingly.

---

## 10. WHAT I COULD NOT VERIFY — explicit gaps

- **Process execution was blocked in my sandbox** (`SetNamedSecurityInfoW failed (Win32 5):
  grantWrite`), so I could **not** query Binance `exchangeInfo` or `data.binance.vision`
  directly. Every API-derived number above is from a secondary source except the repo's own
  prior count. Script left at `tools/scout_listing_count.py` — **run it locally to confirm
  §1 in one shot.**
- **`onboardDate` availability is unresolved** (§5) and must be checked locally.
- **BitMEX, "Perpetual Swap Listings: When Do New Coins Peak?"** (Q1 2025 derivatives report,
  2025-04-07) — search-indexed and described as "perps have become increasingly important for
  price discovery for newly launched altcoins" — **URL 404s and web.archive.org fetch failed.**
  **This is very likely the single most on-point document for this hypothesis** (an exchange
  research desk studying exactly when newly listed perps peak) and is the recommended next
  retrieval attempt.
- HKIFA, "Comparative Analysis of Token Performances Post-Listing on Major Centralised
  Exchanges" (34 tokens, first week, 7 exchanges) — **404s**, not retrieved.
- The EUR theses (thesis.eur.nl 59675 "Coinbase Effect"; 60740 "Cross-listings", 222
  cross-listings / 14 exchanges) were surfaced but **not read**; they are on the same
  cross-listing framing and unlikely to change the verdict, but they are the remaining
  peer-reviewed-ish coverage.
- **No study anywhere in this report includes transaction costs.** Not one.
