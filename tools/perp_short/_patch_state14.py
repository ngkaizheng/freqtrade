"""One-off: record the 515-universe liquidity ladder, which is the first result
in this project to cross t >= 2.0 - and record, in the same row, every reason it
is still a LEAD rather than a strategy.

The temptation with a result like this is to quote the +89.9% / t=2.25 line. The
prereg forbade picking a rung, the whole curve is published here, and the
selection problem is stated inside the same row so it cannot be read off.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Liquidity ladder on the FULL 515-symbol universe — the FIRST result in "
    "this project to cross t >= 2.0, and it is the best of four rungs** | "
    "**2026-09-28 — A LEAD, NOT A STRATEGY. Publish the whole curve and the "
    "selection problem together, or do not publish it at all.** | Diagnostic "
    "`PREREG_LIQUIDITY_ON_515_2026-09-28.md` (frozen before any widened-universe "
    "backtest, with `tools/perp_short/liq_overlap.py` as part of its evidence "
    "base); result `LIQ515_RESULT_2026-09-28.md`; "
    "`tools/perp_short/{liq_overlap,liq515_report}.py`, "
    "`tools/widepanel/build_liq515_configs.py`; "
    "`user_data/perp_short_out/liq515_decomp.csv`. **THE DIAGNOSTIC THAT CAME "
    "FIRST, AND WHY THE PREREGISTERS A DECOMPOSITION GATE:** on this panel a "
    "liquidity filter is roughly HALF a survivorship filter - the top 50 by "
    "median quote volume is **26/50 = 52% cohort A**, top 100 is 43%, and cohort "
    "A's median liquidity rank is 114 against 206-346 for the newer cohorts. So "
    "**'the top rung made money' would have been indistinguishable from picking "
    "up the retracted +52.4% again, and the prereg instead asks WHICH COINS made "
    "it (gate L2).** **THE RESULT, decomposed (measured COVID costs):** | N | A "
    "share | mean R | cohort A | **non-A** | non-A t | |50|52.0%|+0.2128|+0.2247|"
    "**+0.1903**|1.16| |100|43.0%|+0.1558|+0.1479|**+0.1682**|1.30| |200|37.5%|"
    "+0.0833|+0.1237|+0.0372|0.36| |515|20.2%|**-0.4855**|+0.0131|**-0.8019**|"
    "**-3.81**| **At N=100 the NON-SURVIVOR portion beats the survivor portion, "
    "so it is not a survivor filter; at N=515 the non-A portion is -0.8019 at "
    "t=-3.81, which is what separates the COST explanation from the SURVIVORSHIP "
    "explanation on one row.** Gates: L1/L3/L5 PASS (L5 monotone as N narrows, "
    "so COST is the mechanism, consistent with §1c's cost_R law and with the "
    "cohort comparison), L2 PASS for N<=200 and FAIL at 515, L4 PASS only at "
    "N=50 (3 of 4 years). **THE HEADLINE, WITH EVERY CAVEAT ATTACHED: N=50 "
    "gives +89.9% at measured COVID costs, CAGR 20.5%, Sharpe 0.67, maxDD 31.5%, "
    "PF 1.17, 1,081... no, 862 trades, mean R +0.2128, NAIVE t = 2.25 - the "
    "first crossing of the project's t>=2.0 bar.** **WHY IT IS STILL A LEAD, "
    "SIX REASONS, NONE OF WHICH MAY BE DROPPED WHEN QUOTING THE NUMBER:** "
    "**(1) it is the best of four rungs, the prereg forbids picking a rung, and "
    "this project's t>=2.0 bar has never been search-deflated, so the honest bar "
    "after a 4-cell search is higher; (2) the same family one rung away (N=100, "
    "1,081 trades) gives t=1.89, i.e. BELOW 2.0, so the crossing is not stable "
    "within the ladder; (3) ⚠ GATE L0 FAILED and its failure is the eighth "
    "silent problem and the most damaging one in the project - see below; "
    "(4) 52% cohort A share, and the most liquid rung is by construction the one "
    "where survivors weigh most; (5) there is no untouched holdout in this "
    "project, so nothing is out-of-sample; (6) the market-neutralised excess is "
    "unchanged and still indistinguishable from zero - this round did not redo "
    "it and has no reason to think it moved.** |"
)

ORDER_TRAP = (
    "| **⚠ WITH A SLOT LIMIT, THE WHITELIST ORDER DECIDES WHO GETS FILLED — a "
    "21-point swing on the same 515 symbols** (new, cross-cutting, **the 8th "
    "instance, and the most damaging robustness finding in the project**) | "
    "**TRAP — identical universe, identical code, identical parameters, and "
    "+4.14% vs -17.52%** | The same 515 pairs, whitelisted **alphabetically**, "
    "backtest **+4.14% on 1,980 trades**; whitelisted **ranked by liquidity**, "
    "**-17.52% on 1,955 trades**. With `max_open_trades=24` and 515 pairs, more "
    "than 24 pairs frequently signal on the same bar, and freqtrade fills in "
    "pairlist order - so **which trades exist is decided by a detail nobody would "
    "think to vary, namely string sorting.** ⚠ **THIS IS NOT A BUG. It is how "
    "any portfolio with a slot limit behaves**, and it is invisible on a 24-104 "
    "symbol universe where slots rarely bind. The honest responses are: make the "
    "ordering an explicit RULE ('when slots are scarce, take the most liquid'), "
    "record that it is a rule, and report every number under it. All the "
    "liquidity-ladder numbers in `LIQ515_RESULT_2026-09-28.md` are liquidity-"
    "ordered. **But the 21-point swing is also the strongest single piece of "
    "evidence that none of this is a strategy: a result that moves that far on an "
    "arbitrary tie-break has not survived anything.** It is also why gate L0 "
    "(replication) FAILED for the 515 cell. |"
)

CHANGE = (
    "| 2026-09-28 | **THE FIRST t >= 2.0 RESULT IN THE PROJECT — AND THE EIGHTH "
    "SILENT PROBLEM, WHICH IS WHY IT IS A LEAD AND NOT A STRATEGY.** "
    "`LIQ515_RESULT_2026-09-28.md`, `PREREG_LIQUIDITY_ON_515_2026-09-28.md`. "
    "**The widened-universe round left the question 'is this only a survivor "
    "effect?' and this round answers it with a DECOMPOSITION rather than a "
    "headline.** The diagnostic came first: a liquidity filter on this panel is "
    "**half a survivorship filter** (top-50 by median quote volume is 26/50 = "
    "**52% cohort A**; top-100 is 43%; cohort A's median liquidity rank is 114 vs "
    "206-346 for newer cohorts), so 'the top rung made money' would have been "
    "indistinguishable from picking up the retracted +52.4% again. So gate L2 asks "
    "**which coins made it**. **THE DECOMPOSITION AT MEASURED COVID COSTS:** "
    "N=50 mean R +0.2128 (A +0.2247, **non-A +0.1903**); N=100 +0.1558 (A +0.1479, "
    "**non-A +0.1682** - the newer coins carry it); N=200 +0.0833; **N=515 -0.4855 "
    "with non-A at -0.8019, t=-3.81**. **One row separates the COST explanation "
    "from the SURVIVORSHIP explanation.** Gates L1/L3/L5 PASS, L2 passes for "
    "N<=200, L4 passes only at N=50. **N=50: +89.9% at measured COVID, CAGR "
    "20.5%, Sharpe 0.67, maxDD 31.5%, PF 1.17, 3 of 4 calendar years positive, "
    "mean R +0.2128, naive t = 2.25 - the first crossing of the project's bar.** "
    "**It is a LEAD and six things travel with it: it is the best of four rungs "
    "against a bar this project has never search-deflated; the same family one "
    "rung away (N=100, 1,081 trades) gives **t=1.89, BELOW 2.0**, so the crossing "
    "is not stable; gate L0 FAILED; 52% cohort A share; no untouched holdout; and "
    "the market-neutralised excess is unchanged and still indistinguishable from "
    "zero.** *(b) ⚠ **AND GATE L0's FAILURE IS THE MOST IMPORTANT FINDING OF THE "
    "DAY: THE WHITELIST ORDER DECIDES THE RESULT.** The same 515 pairs, same "
    "code, same parameters: **alphabetical order +4.14% (1,980 trades); "
    "liquidity order -17.52% (1,955 trades).** With `max_open_trades=24` and 515 "
    "pairs, more than 24 signal on the same bar constantly, and freqtrade fills in "
    "pairlist order, so **which trades exist is decided by string sorting.** "
    "**This is not a bug - it is how any portfolio with a slot limit behaves - and "
    "it is invisible on a 24-104 symbol universe where slots rarely bind.** The "
    "honest response is to make the ordering an explicit rule and report every "
    "number under it (all ladder numbers are liquidity-ordered). **But a "
    "21-point swing on an arbitrary tie-break is the strongest single evidence "
    "that none of this is yet a strategy.** That is the 8th silent problem in this "
    "session, and the first two were a stale-ATR fallback and a hard-coded short "
    "sign - both of which changed results by factors of 1.4 and 7. |"
)

A = "| **Liquidity ladder on the FULL 515-symbol universe"
B = "| **`np.vstack` over per-symbol frames assumes they all have the same bar"
C = "| 2026-09-28 | **THE MOST IMPORTANT RESULT OF THE PROJECT,"


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
    lines[hdr + 2:hdr + 2] = [ROW, ORDER_TRAP]
    hit = next((i for i, l in enumerate(lines) if l.startswith(B)), -1)
    if hit >= 0:
        lines[hit + 1:hit + 1] = [ORDER_TRAP]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted ladder row, order trap row, change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
