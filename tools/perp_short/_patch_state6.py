"""One-off: record the MARKET-BETA CORRECTION and the 2026-09-28 literature.

AGENTS.md section 2: "If the literature disagrees with what the work so far
implies, the literature wins and the earlier conclusion gets revised. If an
earlier conclusion is found to be wrong, state it plainly and correct the record
rather than burying it."

So this does BOTH, in the append-and-correct style:
  * a CORRECTION row that names the specific claim being overturned and what
    replaced it, above the row that made the claim;
  * the two literature rows that independently bracket the signal family.
The superseded row is LEFT IN PLACE and marked, not deleted. A later agent
reading only that row must be able to see it was overturned and by what.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

CORRECTION = (
    "| ⚠ **CORRECTION 2026-09-28 (later the same day) — THE 'CONTROL-VALIDATED "
    "EDGE' ABOVE IS MARKET BETA, NOT A SIGNAL. The row beneath states the "
    "opposite and is kept deliberately so the reversal is visible.** | "
    "**DO NOT CARRY FORWARD THE 'the signal is real' CLAIM. Full correction: "
    "`CORRECTION_MARKET_BETA_2026-09-28.md`.** | The timing-destroyed control "
    "was a correct test that asked the wrong question. It can only answer 'does "
    "the entry timing carry information' - and it does - but it CANNOT separate "
    "(a) cross-sectional information from (b) market-direction information, "
    "because a random-entry book loses under BOTH. **The decisive test is "
    "market-neutralisation, and it is zero.** For every bar where the panel "
    "signalled, the equal-weight 104-coin forward 42-bar return by coincidence "
    "count is **-1.465% / -1.928% / -1.950% / -2.645% / -1.583% / -4.678%** for "
    "n = 1 / 2 / 3-4 / 5-7 / 8-12 / **13+**, **monotone, corr = -0.700**, and "
    "the 13+ bucket is -4.678% at t = -4.61. **Unconditional baseline: the "
    "panel falls -0.547% per 7 days on its own over the whole sample** - about "
    "-8.7%/yr, so a short-only book needs no signal at all to earn. **And the "
    "decisive number: at n_coincident >= 13 the SIGNALLING symbol's own forward "
    "return is -5.377% against the panel's -5.341% - an EXCESS of -0.036%, "
    "t = -0.37, over 4,200 observations.** At most ~1% of the book's move is "
    "idiosyncratic; the other 99% is the market. **The `R` statistics are "
    "unaffected and remain correct; what they measure is beta plus a timing "
    "overlay, not an edge. And §1d already closed trend timing on the canonical "
    "paper (Hurst/Ooi/Pedersen 2017, JPM, peer-reviewed, null).** |"
)

LIT_ROW = (
    "| **Kim & Hansen (2026), volume/order-flow spike -> next bars, Binance "
    "perps — THE FAMILY IS PRICED 6-7x BELOW COST** | **2026-09-28 — EXTERNAL, "
    "AND IT AGREES WITH OUR OWN MEASUREMENT** | `arXiv:2607.09426`, v2 "
    "2026-07-16, **PREPRINT — NOT PEER REVIEWED** "
    "(https://arxiv.org/abs/2607.09426). ⚠ Hansen acknowledges funding from "
    "**Ripple's UBRI**; know that before quoting. Binance USD-M perps, 6 "
    "contracts, 2021-01-01→2024-10-31, ms aggregate trades, HAC-corrected for "
    "overlapping forward returns, joint moving-block bootstrap preserving serial "
    "AND cross-asset dependence. **Volumetric burst is real and 1%-significant: "
    "the first 10s of quarter-hour minutes show +26% trades, +32% dollar volume, "
    "+26% absolute returns.** The predictive result at OUR horizon (4h) is "
    "significant for 4 of 6 contracts at 95%. **The number that decides: the "
    "lagged-flow component contributes 'a stable five to six basis points across "
    "horizons' (interquartile effect). Against this repo's 35 bps round trip "
    "that is 6-7x too small** - and even their 12h public-signal IQR of 16.9 bps "
    "is under half the cost. **NO COSTS ANYWHERE in the paper** - predictive "
    "slopes, not P&L. **THE CROSS-CHECK IS THE POINT: our own 5m factor scan "
    "measured 2.47 bps gross. Two independent instruments, same family, same "
    "order of magnitude, both far below cost. That closes the volume-spike "
    "family far more convincingly than our own scan did, because it is external, "
    "overlap-corrected, and bootstrapped across assets.** Their own stated "
    "weakness: the 10s forecast reaches only R^2 3.4% / AUC 0.60. Robustness "
    "they did: nested interactions dropped, +/- imbalance split, sign-only, "
    "Hodrick SEs, and **excluding the 00:00/08:00/16:00 funding-settlement "
    "quarter-hours (unchanged, so not a funding artefact)**. |"
)

LIT_ROW2 = (
    "| **Two more published nulls (2026-09-28) + one real gap in the literature** "
    "| **RECORDED — DO NOT RE-SEARCH** | **(1) Grobys, Kolari, Sandretto, Shahzad "
    "& Aijo (2025), 'Cryptocurrency momentum has (not) its moments', *Financial "
    "Markets and Portfolio Management* 39(4), doi:10.1007/s11408-025-00474-9 — "
    "PEER REVIEWED.** SPOT (CoinMarketCap), top-30 large caps, weekly, "
    "2016-2023, 416 obs. **COSTS NOT INCLUDED.** Plain momentum **0.90%/wk, "
    "which the authors themselves call 'an insignificant average raw payoff'**; "
    "vol-managed 1.86-2.40%/wk. **Three reasons it is a caution, all from the "
    "paper's own text: (i) its own Table 11 value-weighted risk-adjusted "
    "regressions have intercepts -0.0106 (t -1.25), -0.0083 (t -1.42), -0.0095 "
    "(t -1.63) - negative and insignificant; (ii) 'the variance of this strategy "
    "is statistically undefined as implied by a power law exponent of alpha < 3' "
    "and 'risk-managing cryptocurrency momentum does not significantly change the "
    "tail risk' - **a Sharpe target is not well-posed on this family**; (iii) "
    "December 2020 crashed **-255.23% in one month from ONE coin in the short "
    "leg**, and trimming that single observation is what produces their t = 2.63.** "
    "**(2) Garcia Seuma (2026-07-29), 'Where does the criticality live?', "
    "arXiv:2607.27070, PREPRINT.** 7 BTC liquidation cascades 2022-2025 incl. the "
    "record $19B event, minute-level. **'No variable is event-invariant.'** Price "
    "carries the critical-slowing-down signature in 5 of 7 events 'but is silent "
    "in exactly the two sudden-news shocks'. The only regularity surviving all "
    "events is a compression of taker order-flow variance (Fisher-combined p ~ "
    "5e-6) and that is **'a population-level precursor, not a per-event alarm'**. "
    "**This is a published null on the premise SHARK-07 currently rests on.** "
    "**(3) Zhu & Cai (2026-09-04), arXiv:2609.04917, PREPRINT**, 32pp review: "
    "'**no general AI architecture is shown to deliver persistent, cross-regime, "
    "capacity-aware net alpha**'. **THE GAP IS THE FINDING: arXiv returns 4 "
    "papers TOTAL for cryptocurrency AND 'transaction costs' AND q-fin.TR.** No "
    "peer-reviewed, cost-adjusted, intraday/daily crypto-PERP signal with a large "
    "effect size exists. **Also: nothing at all was published 2026-09-27 or "
    "2026-09-28 in any index - say that plainly rather than implying a search "
    "was shallow.** **Two in-house follow-ups: (a) pull He et al. 'Fundamentals "
    "of Perpetual Futures' v7 (2026-09-17) Table 8, the FEE-AND-SPREAD table - "
    "this repo's carry review quotes only the zero-cost Table 6; (b) manually "
    "open Frontiers in Blockchain doi 10.3389/fbloc.2026.1811716 (peer-reviewed, "
    "perp-inclusive, JS-rendered, unread).** |"
)

STRUCTURAL_ROW = (
    "| **'A freqtrade strategy with slippage in its methodology' is a CATEGORY "
    "THAT CANNOT BE SATISFIED** (new, structural) | **TRAP — the request is "
    "unanswerable by construction, so don't keep searching for it** | The "
    "backtester has no slippage and no market-impact model "
    "(`docs/backtesting.md:562`, `:571`). **Therefore no strategy running in "
    "this engine can have a slippage-inclusive backtest methodology, at all** - "
    "the claim would be false or would refer to an external wrapper. The most "
    "transparent non-clone found (darkvolg/Trading 'TrendRider', Bybit perps, "
    "13 pairs, 1h, GPL-3.0, with walk-forward holdout, a validation gate that "
    "rejects params failing to beat baseline, rolled-back-and-documented failed "
    "hyperopt runs, and a public paper-trading dashboard) **models no slippage**, "
    "has been paper-trading **$500 since 2026-04-01**, headlines '**13 days of "
    "breakeven trading**', backtests over 3.6 months, and is a lead funnel. "
    "**Interesting as a reproducibility exercise, worthless as an edge "
    "reference.** |"
)

CHANGE = (
    "| 2026-09-28 | **⚠ CORRECTION TO THE 2026-09-28 STOP-MULTIPLE ENTRY: THE "
    "'CONTROL-VALIDATED EDGE' IS MARKET BETA. A DIFFERENT TEST OVERTURNS IT, AND "
    "THE EARLIER ENTRY IS KEPT AND MARKED RATHER THAN DELETED.** "
    "`CORRECTION_MARKET_BETA_2026-09-28.md`. **The timing-destroyed control was a "
    "correct test that asked the wrong question** - it can show the entry timing "
    "carries information, but it cannot separate cross-sectional information "
    "from market-direction information, because a random-entry book loses under "
    "both. **The decisive test is market neutralisation.** Forward 42-bar "
    "equal-weight panel return at every signalling bar, by coincidence count: "
    "**-1.465 / -1.928 / -1.950 / -2.645 / -1.583 / -4.678 %** for n = 1 / 2 / "
    "3-4 / 5-7 / 8-12 / **13+**, **monotone, corr -0.700**, 13+ at t = -4.61. "
    "**Unconditional baseline -0.547% per 7 days: the panel falls ~8.7%/yr on "
    "its own, so a short-only book needs no signal to earn.** And at n >= 13 the "
    "**signalling symbol's own forward return is -5.377% against the panel's "
    "-5.341%: excess -0.036%, t = -0.37, over 4,200 observations** - at most ~1% "
    "of the move is idiosyncratic. **The R statistics stand; what they measure "
    "is beta plus a timing overlay, and §1d already closed trend timing "
    "(Hurst/Ooi/Pedersen 2017, JPM, null). Per AGENTS.md 1a this line is not "
    "'under-powered', it is 'measured'.** *(9) SAME NIGHT, LITERATURE: an "
    "external instrument prices this exact family **6-7x below cost**. Kim & "
    "Hansen, arXiv:2607.09426 (PREPRINT; Binance USD-M perps, 6 contracts, "
    "2021-2024, ms data, HAC + joint moving-block bootstrap) find the "
    "order-flow component contributes **'a stable five to six basis points across "
    "horizons'** at 4h - against this repo's 35 bps round trip. **Our own scan "
    "measured 2.47 bps. Two independent instruments agree.** Plus two further "
    "published nulls (Grobys et al. 2025 vol-managed momentum, peer-reviewed; "
    "Garcia Seuma 2026 no event-invariant liquidation early-warning, which is a "
    "null on SHARK-07's premise) and one structural fact: **arXiv returns 4 "
    "papers TOTAL for crypto AND 'transaction costs' - the absence of "
    "cost-adjusted perp signal literature is a FINDING, not an unfinished "
    "search**, and **nothing at all was published 2026-09-27/28.** Plus a "
    "category that cannot be satisfied: no freqtrade strategy can have slippage "
    "in its methodology, by construction. Full review "
    "`LITERATURE_2026-09-28.md`.* |"
)

ANCHOR = "| 2026-09-28 | **THE FIRST CONTROL-VALIDATED EDGE IN THIS PROJECT"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith("| ⚠ **CORRECTION 2026-09-28") for l in lines):
        print("already present")
        return 0

    # 1. the correction row goes ABOVE the row it corrects
    idx = next((i for i, l in enumerate(lines)
                if l.startswith("| **Stop multiple (4h short) + TIMING-DESTROYED")), -1)
    if idx < 0:
        print("anchor row not found")
        return 1
    lines[idx:idx] = [CORRECTION, LIT_ROW, LIT_ROW2, STRUCTURAL_ROW]

    # 2. mark the superseded row in place
    j = next((i for i, l in enumerate(lines)
              if l.startswith("| **Stop multiple (4h short) + TIMING-DESTROYED")), -1)
    if j >= 0:
        lines[j] = ("| **~~SUPERSEDED 2026-09-28 — SEE THE CORRECTION ROW "
                    "ABOVE~~** " + lines[j][2:])

    # 3. change-log entry
    hit = next((i for i, l in enumerate(lines) if l.startswith(ANCHOR)), -1)
    if hit >= 0:
        lines[hit:hit] = [CHANGE]
    else:
        hdr = next((i for i, l in enumerate(lines) if l == "| date | change |"), -1)
        if hdr >= 0:
            lines[hdr + 2:hdr + 2] = [CHANGE]

    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted correction + 3 literature rows + change-log entry; "
          "marked the superseded row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
