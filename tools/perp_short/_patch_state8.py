"""One-off: record the basis-arbitrage re-test and the Pindza 2026 null.

Both are on the CARRY / microstructure lines. The basis one is a correction of
HOW this repo closed the carry line (it closed a proxy - the funding excess -
rather than the mechanism - basis convergence), and it is a stronger closure
than the one it replaces. The Pindza one is external, peer-reviewed, and the
only paper found that actually models slippage.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

BASIS_ROW = (
    "| **Funding / basis carry — RE-TESTED against the right object (2026-09-28)** "
    "| **STILL CLOSED, but on a much better reason. The old reason measured a "
    "proxy.** | `docs-myself/BASIS_ARBITRAGE_2026-09-28.md`, "
    "`tools/perp_short/basis_check.py`, "
    "`user_data/perp_short_out/basis_check.csv`. **WHAT WAS WRONG WITH THE OLD "
    "CLOSURE:** the carry line was closed because the funding **excess** is "
    "negative (-0.88 %/yr full panel, -1.56 %/yr common intersection). But the "
    "funding payment is a **TRANSFER** - longs pay shorts, no value is created - "
    "**so an 'excess over the administered parameter' is not the thing that can "
    "be harvested. The harvestable thing is the BASIS converging.** He, Manela, "
    "Ross & von Wachter (arXiv:2212.06888 **v7, 2026-09-17**, preprint) price the "
    "perp against F = (1 - Phi^-1(r))^-1 S and trade the deviation, reporting "
    "for BTC on Binance **'a Sharpe ratio of 3.35 under high trading costs' and "
    "'3.27 after additionally accounting for effective bid-ask spreads'**. "
    "**This repo's carry review recorded that paper but quoted only its "
    "zero-cost section. Re-tested here, properly:** the no-arbitrage premium is "
    "DERIVED, not assumed - Binance funding = clamp(8h premium, +-0.05%) + 0.01%, "
    "so p* = clamp(r - 0.0001, +-0.0005), which is **-0.86 bps at a 5%/yr rate** "
    "and moves only 0.14 bps across a 3-8% rate range. **Measured on 46 pairs, "
    "1d, 2023-01 to 2026-08, 1,332 days each: mean ABSOLUTE deviation 8.5 bps, "
    "and 0 of 46 pairs exceed 35 bps - one COVID round trip - let alone the ~2x "
    "a spot+perp pair pays. BTC is pinned at -3.3 +- 3.7 bps.** "
    "**⚠ AND THE KILLER IS NOT MAGNITUDE, IT IS REVERSION: the 7-day forward "
    "change in the premium is ~0.0 bps for essentially every one of the 46 "
    "pairs.** 'Random-maturity arbitrage' earns convergence; **a spread that does "
    "not converge is not an arbitrage at any size.** For scale, their sample had "
    "52-90 %/yr absolute deviation; this one has **3.7 %/yr for BTC** - an order "
    "of magnitude smaller, which is the direction their own paper predicts "
    "('deviations decline on average about 22 percentage points a year'), only "
    "more complete than they expected. **The 2026 absolute deviation (12.3 bps) "
    "is LARGER than 2023's (7.4 bps), i.e. what is left is two-sided noise from "
    "thin liquidity, not a harvestable gap. He et al.'s Sharpe 3.27 does not "
    "reproduce here, and this is why.** |"
)

PINZDA_ROW = (
    "| **Pindza 2026 — the only paper found that MODELS SLIPPAGE, and it is a "
    "peer-reviewed NULL on crypto microstructure** | **RECORDED — this is the "
    "cleanest external anchor that microstructure alpha is not tradeable at "
    "retail fees** | Pindza, Edson (2026), 'Microstructure alpha: hierarchical "
    "learning and cross-asset transfer in cryptocurrency markets', *Frontiers in "
    "Blockchain* 9:1811716, doi:10.3389/fbloc.2026.1811716, **PEER REVIEWED "
    "(Original Research, 2 named reviewers, accepted 2026-05-18)**. "
    "https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/pdf "
    "**(the JS page is unreadable and web_fetch will not parse "
    "`application/pdf`; Python `requests` + `pypdf` works, 15pp/64k chars)**. "
    "**Abstract, verbatim: 'gradient-boosted models overfit severely under proper "
    "leakage controls, and no strategy survives realistic exchange fees... "
    "microstructure signals carry genuine but weak information content that is "
    "useful for understanding market quality but not exploitable at standard "
    "retail fee levels.'** **Costs, verbatim: 'Binance's published VIP-0 "
    "schedule: 10 bps per side for spot (20 bps round-trip) and 2 bps maker/5 bps "
    "taker for USDT-M perpetual futures (4-10 bps round-trip)... additionally a "
    "conservative half-spread slippage equal to the contemporaneous "
    "Corwin-Schultz spread proxy'** - and it names its own omissions (funding, "
    "borrow, queue position, latency) and calls its net Sharpes **'an upper "
    "bound'**. **Result: Aug 2025-Feb 2026, 3,417,972 minute bars, 6 assets x "
    "spot and perps, purged walk-forward (k=5, 5-min purge, 60-min embargo): net "
    "Sharpe spot -31.29 / -52.05 / -50.30 and net Sharpe PERPS -10.68 / -18.42 "
    "/ -16.98** for AR(1) / OLS / LightGBM. The only non-overfit model (OLS) has "
    "a **NEGATIVE gross Sharpe of -0.31** and dR2_OOS +1.23% at **p ~ 0.20**; "
    "LightGBM is **significantly worse than a random walk** (DM -6.83, "
    "p < 1e-11). **Their mechanism sentence is this repo's problem verbatim: 'at "
    "20 bps per round trip on spot, 288 round trips per day generates cumulative "
    "costs that overwhelm any statistical edge by orders of magnitude.'** "
    "**THREE CAVEATS IF CITED:** (A) section 5.3 ADMITS a pilot at HOURLY "
    "frequency where Amihud (0.43) and Kyle's lambda (0.14) failed the 0.5 "
    "threshold, after which the study was rerun at MINUTE frequency with 20x the "
    "data until all 12 passed - **the same 'changed the timeframe after the "
    "earlier one failed' trap this repo's own PREREG_1P5ATR records**, and the "
    "author says so himself; (B) Table 4 gives LightGBM the best GROSS Sharpe "
    "(+0.96) while the same paper shows its forecasts are significantly worse "
    "than a random walk out of sample, and **the paper never states which split "
    "Table 4 uses**; (C) no untouched holdout, 12 features, 12 tests, no "
    "multiple-testing correction. **Not a disqualifier, because a null cannot be "
    "inflated by selection - but do not quote its gross Sharpes without (B).** "
    "**Steal its purge + embargo scheme for this repo's own gates.** |"
)

CHANGE = (
    "| 2026-09-28 | **THE CARRY LINE RE-TESTED AGAINST THE RIGHT OBJECT, AND A "
    "PEER-REVIEWED SLIPPAGE-MODELLING NULL OBTAINED. Both are closes, not "
    "leads.** `BASIS_ARBITRAGE_2026-09-28.md`, `LITERATURE_2026-09-28.md` §5b-5c. "
    "**(1) THE OLD CARRY CLOSURE MEASURED A PROXY.** It was closed because the "
    "funding EXCESS is negative - but the funding payment is a TRANSFER, so "
    "'excess over the administered parameter' is not the harvestable object; "
    "**the harvestable object is the BASIS converging.** He et al. (arXiv:2212.06888 "
    "**v7 2026-09-17**) trade exactly that and report **BTC Sharpe 3.35 at retail "
    "costs, 3.27 after charging the effective bid-ask spread**; this repo had "
    "recorded the paper and quoted only its zero-cost section. **Re-tested here "
    "with the no-arbitrage premium DERIVED from Binance's own funding formula "
    "(p* = clamp(r - 0.0001, +-0.0005) = -0.86 bps at 5%/yr): mean absolute "
    "deviation 8.5 bps over 46 pairs, 0 of 46 above 35 bps, BTC pinned at "
    "-3.3 +- 3.7 bps - and, decisively, the 7-day forward change in the premium "
    "is ~0.0 bps for essentially every pair.** Random-maturity arbitrage earns "
    "CONVERGENCE; **a spread that does not converge is not an arbitrage at any "
    "size.** Their sample had 52-90%/yr deviation, this one has 3.7%/yr for BTC - "
    "an order of magnitude smaller, the direction their own paper predicts. "
    "**Sharpe 3.27 does not reproduce here, and now there is a measured reason "
    "why. LINE CLOSED - on a reason that can survive a reader's objection, which "
    "the old proxy-based one could not.** *(2)* **Pindza (2026), *Frontiers in "
    "Blockchain* 9:1811716, PEER REVIEWED - the only paper found that actually "
    "models slippage (Binance VIP-0 + Corwin-Schultz half-spread), and it is a "
    "NULL: 'no strategy survives realistic exchange fees', net Sharpe perps "
    "**-10.68 / -18.42 / -16.98**, and the only non-overfit model has a negative "
    "GROSS Sharpe. It also self-reports rerunning at minute frequency after a "
    "pilot at hourly frequency failed - **the same timeframe-switch trap this "
    "repo has already recorded twice.** **Its purge+embargo scheme is worth "
    "stealing for our gates.** *(3) METHOD, worth more than either result: a "
    "control group proves THERE IS INFORMATION, not WHAT information; a timing "
    "control cannot separate cross-sectional from directional, so **every "
    "long/short book here must now be reported against the unconditional "
    "same-direction book AND its own market-neutralised excess** - see "
    "`beta_check.py` and `r_stats.market_excess()`.* |"
)

A = "| **Funding / basis carry** | ANALYSED - **off**; the *switch* is re-armed but the trade is not |"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith("| **Funding / basis carry — RE-TESTED") for l in lines):
        print("already present")
        return 0

    idx = next((i for i, l in enumerate(lines) if l.startswith(A)), -1)
    if idx < 0:
        print("carry anchor not found")
        return 1
    lines[idx:idx] = [BASIS_ROW, PINZDA_ROW]

    hit = next((i for i, l in enumerate(lines)
                if l.startswith("| 2026-09-28 | **FOURTH REVISION")), -1)
    if hit >= 0:
        lines[hit:hit] = [CHANGE]
    else:
        hdr = next((i for i, l in enumerate(lines) if l == "| date | change |"), -1)
        if hdr >= 0:
            lines[hdr + 2:hdr + 2] = [CHANGE]

    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted basis re-test + Pindza rows + change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
