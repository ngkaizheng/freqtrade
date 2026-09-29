"""One-off: record the stop-multiple + control result in RESEARCH_STATE.md.

This is the FIRST control-validated edge in the project, and it is also the first
one whose power requirement is computed and shown rather than deferred. Both
halves of that belong in the state file, including the half that says the
optimum may lie outside the grid that was swept.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Stop multiple (4h short) + TIMING-DESTROYED CONTROL** | "
    "**2026-09-28 — THE FIRST CONTROL-VALIDATED EDGE IN THIS PROJECT, AND IT IS "
    "STILL NOT SIGNIFICANT. Do not deploy; do not re-sweep.** | Preregs "
    "`PREREG_STOP_MULTIPLE_2026-09-28.md` and `PREREG_STOP_CONTROL_2026-09-28.md` "
    "(the second written AFTER the frontier ran and BEFORE the control ran, "
    "disclosed as an amendment). Result `STOP_MULTIPLE_RESULT_2026-09-28.md`; "
    "`user_data/strategies_frontier/PerpShort4hStop.py`, "
    "`PerpShort4hControl.py`; `tools/perp_short/{stopfront_report,control_compare}.py`. "
    "**WHY THIS PARAMETER:** §1c's `cost_R = bps/(stop_multiple x atr_pct x 1e4)` "
    "puts the stop multiple in the DENOMINATOR, and it is the only term a strategy "
    "chooses. `PREREG_WIDE_PANEL_2026-09-27` compared only **1.0 vs 1.5**; 2.5 and "
    "4.0 had never been run. At 1.5 ATR the stop killed **64.5%** of trades - the "
    "same 'stop is inside the noise band' shape `PerpTrendSlow` named. **FRONTIER, "
    "104 symbols, whole curve published:** mean net R at engine-default "
    "**-0.0295 / +0.0831 / +0.1747 / +0.2208** and at **measured_covid "
    "**-0.1296 / -0.0158 / +0.0758 / +0.1213** for atr_stop 1.0 / 1.5 / 2.5 / 4.0 "
    "- an **8x** improvement, and the **mechanistic gate S7 PASSES**: stop-out "
    "rate falls **71.8% -> 64.2% -> 46.9% -> 31.4%**, monotonically, exactly as "
    "the hypothesis said. Sizing is matched (`custom_stake_amount` divides by "
    "`stop_mult x atr_pct`), so the wide arm is NOT a bigger-position arm. "
    "**BUT AT 4.0 ATR, 60.7% OF TRADES EXIT ON THE 42-BAR TIME STOP AND ONLY 7.2% "
    "REACH 2R** - the strategy has become 'hold 7 days', and buy-and-hold on the "
    "same 103 pairs has a MEDIAN of **-80.9%**, so 'wider stop helped' and 'a 7-day "
    "hold helped' were the same sentence. **THAT IS WHY THE CONTROL EXISTS.** "
    "**CONTROL: identical 4.0-ATR arm with the entry timing destroyed, frequency "
    "matched bar-for-bar (75/65/65/67/63 on BTC/ETH/SOL/DOGE/AAVE), seed fixed in "
    "code so it cannot be re-rolled.** Exit mix nearly identical (control 32.4% "
    "stop / 5.1% target / 62.1% time; real 31.4% / 7.2% / 60.7%), so the two are "
    "structurally comparable. **RESULT - mean R, real vs control:** "
    "**+0.2208/+0.0359, +0.1866/+0.0047, +0.1558/-0.0234, +0.1213/-0.0548** across "
    "engine/calm/volatile/covid. **C1, C2, C3 ALL PASS.** "
    "**⚠ THE NUMBER THAT MATTERS: THE MARGIN IS +0.1849 / +0.1819 / +0.1792 / "
    "+0.1762 R/trade - essentially CONSTANT across a 2.9x cost range.** An edge "
    "manufactured by a cost assumption would drift with the assumption; this one "
    "does not, so it is a property of the SIGNAL. **In 2024, the only year the "
    "signal actually contributes, the control is -0.095 and the real arm is "
    "+0.348.** **VERDICT: the edge is REAL and it is NOT SIGNIFICANT** - "
    "by-timestamp t at covid is **-0.15**, by-week **+0.64**, naive **+0.60**, and "
    "reaching t=2.0 needs **~10x the sample, i.e. ~14 years**, at this "
    "parameterisation. **S1 PARTIALLY FAILS: mean R is MONOTONE TO THE GRID EDGE, "
    "so the optimum may lie beyond 4.0 ATR and the prereg forbids looking - this "
    "direction is KNOWN-UNEXPLORED, not falsified. Also: 2023 degrades sharply as "
    "the stop widens (-0.194 -> -0.522), so the line is regime-dependent, which is "
    "the very thing Hurst/Ooi/Pedersen 2017 (§1d) found null.** |"
)

CHANGE = (
    "| 2026-09-28 | **THE FIRST CONTROL-VALIDATED EDGE IN THIS PROJECT — AND THE "
    "FIRST POWER REQUIREMENT COMPUTED RATHER THAN DEFERRRED. Both are negative "
    "news about deployability and positive news about the method.** Preregs "
    "`PREREG_STOP_MULTIPLE_2026-09-28.md` + `PREREG_STOP_CONTROL_2026-09-28.md` "
    "(the second disclosed as an amendment, written after the frontier and before "
    "the control). Result `STOP_MULTIPLE_RESULT_2026-09-28.md`. **THE STOP "
    "MULTIPLE IS THE ONE LEVER §1c'S COST LAW NAMES AND THE PANEL NEVER PULLED** "
    "(`cost_R = bps/(stop_mult x atr_pct x 1e4)`; the prereg compared only 1.0 vs "
    "1.5). Frontier, 104 symbols, whole curve: mean net R at measured_covid "
    "**-0.130 / -0.016 / +0.076 / +0.121** for atr_stop 1.0 / 1.5 / 2.5 / 4.0, with "
    "the stop-out rate falling **71.8% -> 31.4%** monotonically (gate S7 PASS). "
    "**But at 4.0 ATR, 60.7% of trades exit on the 42-bar TIME STOP** and buy&hold "
    "on the same panel has a median of **-80.9%**, so the result was confounded "
    "with 'a 7-day hold helps'. **Hence a control: same arm, entry timing "
    "destroyed, frequency matched bar-for-bar, seed fixed in code.** **Real vs "
    "control mean R: +0.2208/+0.0359, +0.1866/+0.0047, +0.1558/-0.0234, "
    "+0.1213/-0.0548** (engine/calm/volatile/covid) - C1, C2, C3 all pass, and the "
    "**margin is +0.1849/+0.1819/+0.1792/+0.1762, i.e. CONSTANT across a 2.9x "
    "cost range.** That constancy is the finding: a cost-manufactured edge would "
    "drift with the assumption. **In 2024 the control is -0.095 and the real arm is "
    "+0.348 - that is the signal's one real year.** **AND STILL: t(by-timestamp) at "
    "covid is -0.15, t(by-week) +0.64, t(naive) +0.60; reaching 2.0 needs ~10x the "
    "sample = ~14 years. S1 partially fails - mean R is monotone to the grid edge, "
    "so the optimum may be beyond 4.0 ATR and the prereg forbids looking, which "
    "makes that KNOWN-UNEXPLORED rather than falsified. 2023 degrades from -0.194 "
    "to -0.522 as the stop widens: the line is regime-dependent, the same object "
    "Hurst/Ooi/Pedersen 2017 found null.** **Do not deploy. Do not re-sweep.** "
    "*(7) A methodological note worth keeping: the control and the real arm do NOT "
    "execute the same number of trades (2,876 vs 1,140) even though their SIGNALS "
    "match bar-for-bar, because the real signal clusters and gets rejected by the "
    "slot limit while the randomised one does not. **Comparing the two in USDT "
    "would have compared a 2,876-trade book with a 1,140-trade book and charged "
    "the control 2.5x the fees. R per trade is the only fair comparison here, and "
    "the pre-registered control says so explicitly.* |"
)


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any("Stop multiple (4h short) + TIMING-DESTROYED" in l for l in lines):
        print("already present")
        return 0
    idx = next((i for i, l in enumerate(lines)
                if l.startswith("| **Cost-admissible universe")), -1)
    if idx < 0:
        print("anchor not found")
        return 1
    lines[idx:idx] = [ROW]
    hdr = next((i for i, l in enumerate(lines) if l == "| date | change |"), -1)
    if hdr >= 0:
        lines[hdr + 2:hdr + 2] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted stop-multiple row and change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
