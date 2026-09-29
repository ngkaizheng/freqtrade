"""One-off: record the second literature pass.

The single most valuable entry here is the NAMED EVIDENCE GAP. Three separate
questions in this project now resolve to "no published decomposition of the
long/short legs exists" - and each one costs a future agent a full search to
rediscover. Recording it as a trap is what stops that.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

LIT_ROW = (
    "| **Nefedov (2026) — the closest published match to this panel, and it "
    "independently confirms both of this project's main findings** | "
    "**RECORDED — STRONGEST EXTERNAL ANCHOR ACQUIRED 2026-09-28** | "
    "**Nefedov, S. (2026), 'How Much Sharpe is Illusory? Quantifying Backtest "
    "Overfitting in Crypto Factor Strategies', SSRN 7350238, 22pp, deposited "
    "2026-09-28. PREPRINT — NOT PEER REVIEWED.** Verbatim from the deposited "
    "abstract: *" + "\"Auditing six standard factors—momentum, short-term reversal, "
    "volatility, size/liquidity, funding-carry, and beta—on **137 Binance "
    "USDT-perpetual contracts over 2020-2024**, we compare a naïve protocol … "
    "against a rigorous one (nested walk-forward selection, explicit transaction "
    "costs, and the Deflated Sharpe Ratio over a pre-committed grid of 24 "
    "configurations). **Naïve evaluation inflates the annualized Sharpe ratio by "
    "3.6× on average, and under the baseline protocol none of the six factors "
    "survives deflation; four collapse to a negative out-of-sample Sharpe. A "
    "decomposition attributes most of the gap to trading frictions rather than to "
    "in-sample over-optimization.** Funding-carry, the strongest naïve performer, "
    "survives only under optimistic cost assumptions\"" + "* — **137 Binance USDT "
    "perps 2020-2024 is a near-exact venue/instrument match to this project's 104 "
    "perps 2023-2026, and its two conclusions independently confirm both of ours: "
    "momentum does not survive deflation, and THE GAP IS FRICTION, NOT "
    "OVER-OPTIMISATION - which is the external form of this project's entire "
    "'cost is the binding constraint' line.** ⚠ Caveats: **abstract only**, SSRN "
    "403 so it came from the Istina mirror and **the final sentence is truncated "
    "mid-word**; the author is a self-described crypto-derivatives quant, so treat "
    "as practitioner research, not academia. |"
)

LIT_ROW2 = (
    "| **Three more crypto-momentum/MA nulls, and one claim that must NOT be "
    "re-cited as cost-robust** | **RECORDED — DO NOT RE-SEARCH** | **(1) Grobys, "
    "Sandretto & Aijo (2026), 'On survivor cryptocurrency momentum', *Finance "
    "Research Letters*, doi:10.1016/j.frl.2026.109602 — PEER REVIEWED, and "
    "DISTINCT from the Grobys 2025 FMP null already in this file (same author "
    "group, so it strengthens rather than repeats it).** 9 survivor coins, "
    "2017-01→2024-08, weekly. Verbatim: *" + "\"The survivor cryptocurrency momentum "
    "portfolio (SCMP) **does not generate significant payoffs**… **Significant "
    "payoffs documented for momentum strategies are an artefact of coins that are "
    "only temporarily accessible for trading**\"" + "* — and 'even after trimming, "
    "the profitability of plain cryptocurrency momentum is **highly "
    "sample-dependent**'. ⚠ Cost assumptions not in the retrieved highlights — "
    "UNVERIFIED. **(2) Rozario, Holt, West & Ng (2020), arXiv:2009.12155, "
    "PREPRINT** — the SAME dual-MA-crossover long/short construction on BTC spot. "
    "**Explicitly GROSS: 'We assumed negligible transaction fees, bid-offer spread, "
    "slippage and market impact.'** Its headline 255% annualised is 2011-2016 "
    "(BTC's infancy; the authors forward-filled 5,835 of 72,299 rows) and its own "
    "recent-slice verdict is a NULL: '**sub-par** and **negative Sharpe ratios**', "
    "'**no predictable and attractive Sharpe ratios**', 'the notable **absence of "
    "profitable intra-day trend following strategies for BTCUSD spot markets**'. "
    "⚠ Conflict of interest on record: funded by Globe Research, a crypto "
    "derivatives exchange. **(3) Romo, Soto, Vega, Crawford, Salinas & "
    "Becerra-Rozas (2025), *Mathematics* 13(16):2629, PEER REVIEWED, "
    "doi:10.3390/math13162629** — **this is the ONLY peer-reviewed net-improvement "
    "claim for a dual-SMA long/short switch on Binance futures found, and it is "
    "our exact construction on BTCUSDT 15m. DO NOT RE-CITE IT AS COST-ROBUST: "
    "**the paper never states a fee rate anywhere** (Eq. 11 subtracts fees "
    "symbolically), and on **8 overlapping test windows** a Wilcoxon p of 0.018 "
    "is essentially the attainable floor — 'as significant as 8 observations can "
    "show', not significant. Test ROI 1.079 vs buy&hold 1.012. **(4) Nguyen (2026), "
    "arXiv:2602.11708, PREPRINT** — the one paper arguing the OPPOSITE of us: it "
    "treats crypto as 'a structurally bullish asset class' where **the short side "
    "is the hard one** and tilts 70/30 long (Sharpe 2.41 vs 2.12 dollar-neutral), "
    "net of a disclosed 4bps taker. It never reports a short-only arm, states its "
    "OOS window three different ways, and ~half its Sharpe is in-sample selection "
    "(fixed-parameter ablation 1.34 vs 2.41). |"
)

GAP_ROW = (
    "| ⚠ **EVIDENCE GAP, NAMED SO IT IS NOT RE-SEARCHED: no published work "
    "decomposes a crypto long/short trend signal into separate long-leg and "
    "short-leg returns** | **GAP — three separate questions here all resolve to "
    "this, and each would otherwise cost a full search** | Verified across a "
    "2026-08 arXiv/Crossref/OpenAlex/direct-PDF pass: **zero published papers "
    "split the legs.** Not one of four full-text reads reports it; the single "
    "paper that discusses a crypto long/short asymmetry (Nguyen 2026) argues the "
    "**opposite** direction. **Consequences for how this project writes things "
    "up:** (1) this project's 12-cell net-negative long leg (WIDE_PANEL_RESULT "
    "s3) and the direction-switch refutation (2026-09-28) are **neither confirmed "
    "nor contradicted by the literature — the literature is silent, and the "
    "correct sentence is 'no published work decomposes the leg', NOT 'the "
    "literature confirms the long leg fails';** (2) **MOP 2012's 'continuation is "
    "strongest in the indices that fell hardest' has never been tested in crypto** "
    "— it remains an untested intuition here, not an established prior; (3) the "
    "nearest evidence is **split**: Kumar & Jenefer (2026) finds a vol-scaled "
    "long/short trend book underperforming buy&hold by **-7.67% annualised in the "
    "bull phase** and beating it by **+20.95% in drawdowns** (GROSS of costs, "
    "p=0.5835, a 3-page weak-venue paper with two demonstrably WRONG citations — "
    "one resolving to a paper on bank failures — so do not lean on it), Romo et "
    "al. beat buy&hold by only +6.7pp of ROI per 2-month window, and Nguyen "
    "disagrees outright. **Also: there is no published failed-replication or "
    "critique of a slow-MA regime filter on crypto at all** - nothing tests the "
    "construct. **Search-limit caveat carried from the agent: Bing returned 0, "
    "SSRN/MDPI 403, Semantic Scholar 429; no Google Scholar, EconLit, RePEc or "
    "publisher paywalls. 'Empty' means empty within arXiv + Crossref + OpenAlex + "
    "reachable web, NOT provably empty. Four Elsevier paywalled papers were "
    "identified as the obvious remaining gap and they are the ones most likely to "
    "carry a leg decomposition.** |"
)

CHANGE = (
    "| 2026-09-28 | **SECOND LITERATURE PASS: ONE ANCHOR THAT CONFIRMS BOTH MAIN "
    "FINDINGS, THREE MORE NULLS, AND A NAMED EVIDENCE GAP.** "
    "`LITERATURE_2026-09-28B.md`. **(1) Nefedov (2026), SSRN 7350238, deposited "
    "TODAY — the closest published match to this panel and it independently "
    "confirms both of our conclusions.** 137 Binance USDT perpetuals, 2020-2024, "
    "six standard factors audited: **naive evaluation inflates annualised Sharpe "
    "3.6x; none of the six survives deflation; four go NEGATIVE out-of-sample; and "
    "the gap is attributed mainly to TRADING FRICTIONS rather than in-sample "
    "over-optimisation.** That is the external form of this project's 'cost is "
    "the binding constraint' line, on a near-identical venue and instrument. "
    "Caveats: abstract only, SSRN 403, final sentence truncated mid-word, author "
    "is a self-described practitioner. **(2) Three more nulls: Grobys/Sandretto/"
    "Aijo 2026 (FRL, PEER REVIEWED, survivor-coin momentum 'an artefact of coins "
    "that are only temporarily accessible'); Rozario et al. 2020 (same dual-MA "
    "construction, EXPLICITLY GROSS, and its own recent slices are a null - its "
    "255% headline is 2011-2016 BTC infancy); Romo et al. 2025 (Mathematics, "
    "PEER REVIEWED) is **the only peer-reviewed net-improvement claim for a "
    "dual-SMA long/short switch on Binance futures and it is our exact "
    "construction — but it NEVER DISCLOSES A FEE RATE and its p=0.018 on 8 "
    "overlapping windows is the attainable floor, so DO NOT re-cite it as "
    "cost-robust.** Nguyen 2026 (preprint) argues the OPPOSITE, treating the "
    "SHORT side as the hard one in a 'structurally bullish' asset. **(3) ⚠ A NAMED "
    "EVIDENCE GAP, recorded so it is not re-searched: NO published work "
    "decomposes a crypto long/short trend signal into separate long-leg and "
    "short-leg returns.** Zero papers; the only one discussing the asymmetry "
    "argues the other way. **So this project's 12-cell net-negative long leg and "
    "the direction-switch refutation are neither confirmed nor contradicted by "
    "the literature - the correct sentence is 'no published work decomposes the "
    "leg', not 'the literature confirms the long leg fails'.** Also: MOP 2012's "
    "'continuation strongest where it fell hardest' has NEVER been tested in "
    "crypto, and there is no published failed-replication of a slow-MA regime "
    "filter on crypto at all. Search-limit caveat carried verbatim: Bing returned "
    "0, SSRN/MDPI 403, Semantic Scholar 429, no Google Scholar/EconLit/RePEc/"
    "publisher paywalls - 'empty' means empty within arXiv + Crossref + OpenAlex + "
    "reachable web, and four Elsevier paywalled papers are the obvious remaining "
    "gap.** |"
)

A = "| **Nefedov (2026) — the closest published match"
B = "| **Three more crypto-momentum/MA nulls"
C = "| **Direction switch (long/short by the panel's own 200-bar SMA)**"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith(A) for l in lines):
        print("already present")
        return 0
    idx = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if idx < 0:
        print("switch row not found")
        return 1
    lines[idx:idx] = [LIT_ROW, LIT_ROW2, GAP_ROW]
    hit = next((i for i, l in enumerate(lines)
                if l.startswith("| 2026-09-28 | **DIRECTION SWITCH PRE-REGISTERED")), -1)
    if hit >= 0:
        lines[hit:hit] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted 2 literature rows + 1 evidence-gap trap row + change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
