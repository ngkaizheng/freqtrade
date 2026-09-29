"""One-off: the final consolidation - power, dispersion, and the forward collector.

Three things are recorded together because they only mean anything as a set:
  * the forward test needs 6.8 years (strict) / 2.7 (naive),
  * the dispersion driving that number is CROSS-SECTIONAL, and cutting it would
    be minimum-of-N selection which was NOT done,
  * a forward collector is configured and smoke-tested so the research produces
    its own evidence from here on instead of being re-derived from the same bars.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **FINAL CONSOLIDATION: power, dispersion, and a forward collector** | "
    "**2026-09-29 — THE LINE IS CLOSED AS A RESEARCH QUESTION AND OPENED AS A "
    "FORWARD COLLECTION. 6.8 years under the strict test.** | "
    "`docs-myself/FINAL_DELIVERABLE_2026-09-29.md`; "
    "`tools/perp_short/{forward_power,dispersion,build_forward_collector}.py`; "
    "config `user_data/config_perp_forward_dry.json` "
    "(**SMOKE-TESTED AND RUNNING, dry_run true, no credentials, no orders**). "
    "**THE PRODUCT, stated exactly:** on the most liquid 50 of 515 Binance USD-M "
    "perps, the frozen 4h short book returns **+89.9% at measured COVID costs, "
    "CAGR 20.5%, Sharpe 0.67, maxDD 31.5%, 3 of 4 calendar years positive**, "
    "against a bare 'always short the equal-weight panel' benchmark of **-65.6% "
    "with 88.6% drawdown**. **IT IS NOT ALPHA.** Market-neutralised excess is "
    "NEGATIVE at every rung that clears t>=2.0 (N=25 -1.300%, t=-2.54), the "
    "signal-bar panel forward return is -2.123% against an unconditional -0.547%, "
    "and the direction switch that tried to add a long leg made it worse. **IT IS "
    "TIMING.** **IT DOES NOT GENERALISE TO THE UNCONSTRAINED UNIVERSE**: the same "
    "rule on all 515 is -33.1% at COVID costs. **THE RUNG IS NOT STABLE**: "
    "development picks 25, OOS picks 40, the full sample picked 50; the "
    "reproducible statement is a RANGE (N=25..300 positive OOS, only 515 not), "
    "so N=100, the mid, is the honest operating point. **OOS under the strictest "
    "treatment is t=0.03.** **FORWARD POWER: 250 trades/year at N=50, mean R "
    "+0.2128, sd 2.7728, IAT 2.51 -> t=2.0 needs 1,704 independent trades = "
    "**6.8 years**; the naive treatment says 2.7 years.** "
    "**⚠ AND THE DISPERSION THAT CAUSES IT IS CROSS-SECTIONAL, NOT TAIL:** the 10 "
    "worst symbols own **-70.4% of the total R** (-129.3 against +183.5); "
    "excluding them lifts mean R from +0.2128 to **+0.4559** and would cut the "
    "forward test from **6.8 years to 1.3**. **THIS SCREEN WAS NOT BUILT** - "
    "ranking symbols on the same 3.4 years the result is measured on is the "
    "minimum-of-N construction this project exists to refuse, and it is how a "
    "-0.55R book becomes +0.60R with nothing about the market changing. The "
    "number is recorded as a DIAGNOSTIC. The tail itself is bounded (p0.1% -3.62, "
    "min -3.84, only 9 trades below -3R, so the 4xATR stop works) - the problem "
    "is that **21 of 49 symbols have a negative mean R.** |"
)

CHANGE = (
    "| 2026-09-29 | **THE LINE IS CLOSED AS RESEARCH AND OPENED AS A FORWARD "
    "COLLECTION; AND THE ONE FIX THAT WOULD MAKE IT SETTLEABLE IS EXACTLY THE ONE "
    "THAT WAS REFUSED.** `FINAL_DELIVERABLE_2026-09-29.md`. **Power, computed "
    "rather than asserted** (`RESEARCH_GOAL.md` 2.F.3: a dry-run's duration comes "
    "from a preregistered power calculation, not from 'run it a few weeks'): at "
    "N=50 the book generates **250 trades/year**, mean R +0.2128, **sd 2.7728**, "
    "**IAT 2.51** - so a forward test reaching t=2.0 needs **1,704 independent "
    "trades = 6.8 years** under the IAT treatment, 2.7 naive. "
    "**⚠ AND THE DISPERSION IS CROSS-SECTIONAL, NOT A TAIL.** The tail is "
    "bounded - p0.1% is -3.62, worst trade -3.84, only 9 trades below -3R, so "
    "the 4xATR stop is working. But **the 10 worst symbols own -70.4% of the "
    "TOTAL R** (-129.3 against +183.5), and excluding them lifts mean R from "
    "+0.2128 to **+0.4559** and cuts the forward test from **6.8 years to 1.3**. "
    "**A per-symbol screen was NOT built.** Ranking symbols on the same 3.4 years "
    "the result is measured on is the minimum-of-N construction this project "
    "exists to refuse - it is how a -0.55R book becomes +0.60R with nothing about "
    "the market changing. The number is recorded as a diagnostic and explicitly "
    "NOT acted on. **The other candidate repair - scaling exposure down in "
    "uptrends without going long - cannot be validated at all**, because it would "
    "be designed after seeing 2023 and the only out-of-sample window (2025-2026) "
    "is a falling market where the repair is a no-op, so the test has no power "
    "to detect the benefit it was built for. `AGENTS.md` 1a: a design that "
    "cannot conclude is worse than none. **A forward collector is configured, "
    "smoke-tested and left RUNNING** (`user_data/config_perp_forward_dry.json`, "
    "N=100 the mid of the range, 0.5% per trade, liquidity-ORDERED whitelist, "
    "separate database, dry_run true, **no credentials and no orders**). It "
    "resolves nothing; it starts producing the series the 6.8 years needs. |"
)

A = "| **FINAL CONSOLIDATION: power, dispersion, and a forward collector"
C = "| 2026-09-28 | **THE LAST UNEXAMINED DECISION TESTED"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith(A) for l in lines):
        print("already present")
        return 0
    hdr = next((i for i, l in enumerate(lines) if l.startswith("| line | state |")), -1)
    if hdr < 0:
        print("section 1 header not found")
        return 1
    lines[hdr + 2:hdr + 2] = [ROW]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted final consolidation row and change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
