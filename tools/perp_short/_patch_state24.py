"""One-off: record the rolling loss distribution, which CORRECTS the drawdown
figure this project had been quoting since round 5.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Rolling-window loss distribution — and it CORRECTS a number this project "
    "has been quoting since round 5** | **2026-09-29 — THE DEPLOYED 0.5% RISK "
    "GIVES A 17.3% MAX DRAWDOWN, NOT 47%. The 47% was the 1%-risk figure.** | "
    "`ROLLING_RISK_2026-09-29.md`; `tools/perp_short/rolling_risk.py`; "
    "corrected in `HOW_TO_RUN_2026-09-29.md` s5a. **A maximum drawdown is ONE "
    "number and it is the wrong one to plan around** - what a person deciding to "
    "trade this needs is the distribution, and every figure reported until now "
    "was a full-sample aggregate, so the 3.4-year path was being described by its "
    "best single observation. **N=50, 3.4y, 862 trades, measured COVID costs, "
    "0.5% per trade:** total +38.7%, **maxDD 17.3%**; rolling windows - median / "
    "p5 / worst / %negative - 1m **-0.6 / -5.7 / -9.1% / 57%**, 3m +3.7 / -9.7 / "
    "**-12.3%** / 36%, 6m +3.8 / -12.6 / **-15.5%** / 34%, **12m +13.8 / -7.1 / "
    "**-10.0%** / 11%** - and **0% of windows fall below -20% at any horizon**. "
    "**BUT THE SHAPE MATTERS AS MUCH AS THE DEPTH: 89% OF ALL DAYS ARE UNDERWATER "
    "(>0.5% below a prior peak), with 1,109 drawdown episodes, longest 267 days, "
    "median 67 days.** So it is not 'profitable most of the time, occasionally "
    "deep' - it is 'almost always somewhere below a prior high, but usually not "
    "far below'. **A person who sizes their expectations off the +38.7% total "
    "will start doubting the thing around month 8.** N=40 over the out-of-sample "
    "window (410 trades, 20 months): total +24.6%, maxDD 11.7%, worst 12m +6.5% - "
    "**but 20 months yields only ~8 rolling 12-month windows, so that +6.5% is "
    "'no bad year was seen', not an estimate.** **⚠ THE TAIL IS ESTIMATED FROM 27 "
    "ROLLING 12-MONTH OBSERVATIONS.** The same argument this project's own power "
    "analysis makes for the effect size (6.8 years) applies to a tail with more "
    "mass than a mean, so **'no 12-month window in 2023-2026 was worse than "
    "-10%' is a statement about 27 observations, not about the future.** |"
)

CHANGE = (
    "| 2026-09-29 | **A NUMBER THIS PROJECT HAD BEEN QUOTING SINCE ROUND 5 WAS "
    "WRONG FOR THE DEPLOYED CONFIGURATION: THE 47% DRAWDOWN IS THE 1%-RISK "
    "FIGURE. At the 0.5% risk HOW_TO_RUN actually recommends, max drawdown is "
    "17.3%.** `ROLLING_RISK_2026-09-29.md`. Every drawdown figure in this file "
    "from `PERP_DEPLOY` onward was computed at 1% risk, while the runbook's own "
    "recommendation had been 0.5% for rounds - so **the number a user would have "
    "sized their account against was 2.8x the number they would have "
    "experienced.** `rolling_risk.py` rebuilds the equity curve at MEASURED costs "
    "and the deployed 0.5% risk and reports rolling windows instead of a single "
    "aggregate: **N=50 over 3.4y - total +38.7%, maxDD 17.3%, worst rolling 12 "
    "months -10.0%, worst 6 months -15.5%, worst 3 months -12.3%, and 0% of "
    "windows below -20% at any horizon.** **⚠ BUT THE SHAPE IS THE POINT: 89% "
    "OF ALL DAYS ARE UNDERWATER, with 1,109 drawdown episodes, longest 267 days, "
    "median 67. It is not 'profitable most of the time and occasionally deep' - "
    "it is 'almost always below a prior high, usually not far below', and a "
    "person sizing expectations off the +38.7% total will start doubting it "
    "around month 8.** **And the tail is estimated from 27 rolling 12-month "
    "observations** - the same argument this project's power analysis makes for "
    "the effect size applies more strongly to a tail, so 'no year was worse than "
    "-10% in 2023-2026' is a statement about 27 observations, not about the "
    "future. `HOW_TO_RUN_2026-09-29.md` s5a is corrected. |"
)

A = "| **Rolling-window loss distribution"
B = "| **`HOW_TO_RUN_2026-09-29.md`"
C = "| 2026-09-29 | **AFTER 17 ROUNDS THE REPO HAD 20+"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith(A) for l in lines):
        print("already present")
        return 0
    idx = next((i for i, l in enumerate(lines) if l.startswith(B)), -1)
    if idx < 0:
        print("anchor not found")
        return 1
    lines[idx:idx] = [ROW]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted the rolling-risk row and change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
