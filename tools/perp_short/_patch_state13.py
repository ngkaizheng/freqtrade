"""One-off: record the widened-universe result and RETRACT the deployment verdict.

This entry exists to do two things the state file must be able to do:
  1. record the single most important measurement of the project so far, and
  2. make the retraction of the DELIVERABLE row unmistakable, IN PLACE, with the
     new number attached - because the delivered artefact is still on disk with a
     runbook attached, and a reader who finds only that will deploy it.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **THE WIDENED UNIVERSE — 411 perps the panel never saw — AND THE RESULT "
    "THAT RETRACTS THE DELIVERABLE** | **2026-09-28 — THE DEPLOYMENT VERDICT IS "
    "WITHDRAWN. On the 2026 tradable universe the strategy is -33.1% at measured "
    "COVID costs and 0.0% at calm. The +52.4% was a 2023-vintage SURVIVOR "
    "phenomenon.** | Prereg `PREREG_WIDENED_UNIVERSE_2026-09-28.md` "
    "**frozen before a single kline was downloaded**; result "
    "`WIDENED_UNIVERSE_RESULT_2026-09-28.md`; "
    "`tools/widepanel/{fetch_widened,export_widened,build_widened_configs}.py`; "
    "data `user_data/data/wide526/` (515 symbols, 1,545 files, 224 MB). "
    "**WHY THIS WAS WORTH RUNNING:** the delivered book was measured on 104 perps "
    "that existed before 2023-01 AND are still listed; `exchangeInfo` counted "
    "**526 USD-M perps listed on 2026-09-28**, so 80% of what a user can actually "
    "trade had never produced a single trade in this project. **Grobys, Sandretto "
    "& Aijo (2026), *Finance Research Letters* 109602, PEER REVIEWED, predicted "
    "exactly this: 'significant payoffs documented for momentum strategies are an "
    "artefact of coins that are only temporarily accessible for trading.'** "
    "**COHORTS, by listing year, from exchangeInfo and never from a result: A=104 "
    "(<=2023-01), B=66 (2023), C=94 (2024), D=210 (2025), E=41 (2026, 11 dropped "
    "for <420 warmup bars, each logged).** **U0 REPLICATION GATE PASSES, "
    "bit-for-bit: cohort A reproduces the delivered book exactly (+89.26%, 1,132 "
    "trades), so the new data is provably being read the same way.** "
    "**THE RESULT:** | | A (104, tested) | BCDE (411, untested) | **ALL (515)** | "
    "|-  | -: | -: | -: | | engine output | +89.26% | +57.15% | **+4.14%** | "
    "| gross | +161.1% | +108.9% | **+47.0%** | | measured calm +12bps | +100.6% "
    "| +40.4% | **-0.0%** | | **measured COVID +34.9bps** | **+52.4%** | **+9.5%** "
    "| **-33.1%** | | CAGR / Sharpe / PF (covid) | 13.0% / 0.50 / 1.10 | 2.7% / "
    "0.36 / 1.01 | **-11.0% / 0.14 / 0.95** | | mean R | **+0.1256** | "
    "**-0.4036** | | t by-timestamp | -0.175 | **-2.946** | | worst pair | -2.61R "
    "| **-34.92R** | | market-neutral excess | +0.434% (t +1.56) | +0.060% (t +0.14) "
    "| **GATES U1/U2/U3/U4 ALL FAIL; U0 passes. On the universe a 2026 user can "
    "actually trade, this is 2 of 4 years positive, PF 0.95, and NEGATIVE at "
    "every cost regime that includes slippage.** ⚠ R is not strictly comparable "
    "across cohorts: the `max_stake_frac=0.25` cap binds on the high-ATR long tail, "
    "so a -0.40R there is many small losing positions against a few large wins - "
    "the account curve (+9.5% for BCDE, -33.1% for ALL) is the full picture. "
    "**This is the first time this project CONFIRMED a peer-reviewed external "
    "warning with its own frozen rule on 515 instruments, and the third time the "
    "internal and external evidence finally agree (see Nefedov 2026 on deflation "
    "and friction).** |"
)

RETRACT = (
    "| **A drawdown circuit breaker that fails OPEN, silently, and the backtest "
    "prints a normal curve** (new, cross-cutting, **the 5th instance of this "
    "family, and the first one that was a RISK CONTROL**) | **⚠ RETRACTED AS A "
    "DEPLOYMENT RECOMMENDATION 2026-09-28 — SEE THE WIDENED-UNIVERSE ROW ABOVE. "
    "The code and the gates are still correct; the conclusion that it was worth "
    "deploying on 104 symbols is not.** | **DO NOT DEPLOY ON THE 515-SYMBOL "
    "UNIVERSE.** The book measures +52.4% at measured COVID costs on the 104 "
    "perps that existed before 2023-01 and are still listed, and **-33.1% on the "
    "515 that are actually tradeable today, with 0.0% even at calm costs.** The "
    "survivorship was never corrected for; "
    "`WIDENED_UNIVERSE_RESULT_2026-09-28.md` measures it rather than assuming it, "
    "and Grobys/Sandretto/Aijo (2026, FRL, peer reviewed) had already said this "
    "would happen. The rest of this row is preserved as the evidence chain for the "
    "retracted claim. | **TRAP — shipped in `PerpShort4hDeploy`, never fired once "
    "across a 43.9% drawdown, and looked perfect** | `confirm_trade_entry` in "
    "backtesting is wrapped as "
    "`strategy_safe_wrapper(self.strategy.confirm_trade_entry, "
    "default_retval=True)` (`backtesting.py:1191`) - **any exception inside it is "
    "swallowed and the entry is allowed through**, so a broken risk control does "
    "not even error. Three layers each hid it: (1) **`bot_loop_start` is called "
    "MORE THAN ONCE in a backtest** (it is reached per pair as data is prepared), "
    "so `self._peak_equity = None` ran repeatedly and the peak tracked the "
    "CURRENT equity - the log shows `equity=111250 peak=111250` then "
    "`equity=102072 peak=102072`, so **dd was identically 0.0000 at every entry**; "
    "(2) `if eq is None or eq <= 0: eq = dry_run_wallet` turned 'wallet unreadable' "
    "into 'equity never moves'; (3) the wrapper above swallowed anything raised. "
    "**All three fixes are in the file**: lazy one-shot state init, RAISE instead of "
    "falling back when the wallet is unreadable, and a WARNING on every trip that "
    "says to check `breaker_trips` is non-zero. **The general rule: a control that "
    "silently does nothing is worse than no control, because it buys comfort - and "
    "the only way this was found was that the run produced exactly 1,140 trades, "
    "byte-identical to the un-broken arm, which is not a number a breaker's first "
    "version should ever produce.** |"
)

VSTACK_TRAP = (
    "| **`np.vstack` over per-symbol frames assumes they all have the SAME bar "
    "count** (new, cross-cutting, **the 7th instance**) | **TRAP — invisible on a "
    "104-symbol panel that shares a start date, fatal on a 515-symbol one** | "
    "`r_stats.market_excess` built the equal-weight panel with `np.vstack` over "
    "each symbol's own forward-return array. On the 104-symbol panel every symbol "
    "starts 2023-01 and has 8,034 bars, so the assumption is satisfied by luck and "
    "the bug never fires. **The widened panel has 1,456 bars on a 2026 listing "
    "against 7,938 on a 2023 one, and it raised immediately: 'array at index 0 "
    "has size 2091 and array at index 1 has size 2716'.** Fixed by padding to the "
    "LONGEST symbol with NaN and equal-weighting by nan-mean over the symbols that "
    "exist on that bar - which is also the correct definition, since a coin that "
    "did not exist in 2023 should not carry a 100% weight in the 2023 equal "
    "weight. **Verified by regression: cohort A's numbers are bit-identical after "
    "the fix.** **The general rule: an assumption that happens to hold on the "
    "current dataset is NOT tested, and a universe that is no longer uniform is "
    "what finally tests it.** |"
)

CHANGE = (
    "| 2026-09-28 | **THE MOST IMPORTANT RESULT OF THE PROJECT, AND IT WITHDRAWS "
    "THE DEPLOYMENT VERDICT: ON THE 2026 TRADABLE UNIVERSE THE STRATEGY IS "
    "NEGATIVE.** `WIDENED_UNIVERSE_RESULT_2026-09-28.md`. **WHAT WAS DONE:** the "
    "delivered book was measured on 104 perps that existed before 2023-01 and are "
    "still listed; `exchangeInfo` counts **526 USD-M perps listed today**, so 80% "
    "of what a user can trade had never produced a single trade here. Cohorts were "
    "cut by listing year from `exchangeInfo` and never from a result: A=104, "
    "B=66, C=94, D=210, E=41 (11 dropped for <420 warmup bars, each logged). 411 "
    "new symbols downloaded and exported, one shared exporter for all 515. **U0 "
    "REPLICATION GATE PASSES BIT-FOR-BIT** - cohort A reproduces the delivered "
    "+89.26% / 1,132 trades exactly, so the new data is provably read the same way. "
    "**THE RESULT:** | | A (tested) | BCDE (untested) | **ALL 515** | | engine | "
    "+89.26% | +57.15% | **+4.14%** | | gross | +161.1% | +108.9% | **+47.0%** | "
    "| measured calm | +100.6% | +40.4% | **-0.0%** | | **measured COVID** | "
    "**+52.4%** | **+9.5%** | **-33.1%** | | CAGR/Sharpe/PF (covid) | 13.0/0.50/1.10 "
    "| 2.7/0.36/1.01 | **-11.0/0.14/0.95** | | mean R | **+0.1256** | **-0.4036** | "
    "| t by-timestamp | -0.175 | **-2.946** | | worst pair | -2.61R | **-34.92R** | "
    "| market-neutral excess | +0.434% (t+1.56) | +0.060% (t+0.14) | **U1, U2, U3 "
    "and U4 ALL FAIL.** **So the +52.4% is a 2023-vintage SURVIVOR phenomenon, "
    "and this project has now CONFIRMED - with its own frozen rule on 515 "
    "instruments - exactly what Grobys, Sandretto & Aijo (2026, Finance Research "
    "Letters, PEER REVIEWED) published: 'significant payoffs documented for "
    "momentum strategies are an artefact of coins that are only temporarily "
    "accessible for trading.'** It is also the third time the internal and external "
    "evidence have finally agreed (Nefedov 2026 on deflation and friction was the "
    "first). ⚠ R is not strictly comparable across cohorts because the "
    "`max_stake_frac=0.25` cap binds on the high-ATR long tail; the ACCOUNT curves "
    "are the full picture and they are -33.1% and +9.5%. **THE DEPLOYMENT ROW IS "
    "RETRACTED IN PLACE, WITH THE NEW NUMBERS ON IT, because the artefact is still "
    "on disk with a runbook attached.** *(b) ⚠ 7th silent bug, and the cleanest "
    "example yet: **`np.vstack` over per-symbol frames assumes they all have the "
    "same bar count.** On the 104-symbol panel every symbol starts 2023-01 and has "
    "8,034 bars, so the assumption is satisfied BY LUCK and the bug never fires; on "
    "the 515-symbol panel a 2026 listing has 1,456 bars against 7,938 and it "
    "raised immediately. **An assumption that happens to hold on the current "
    "dataset is not tested - a universe that stops being uniform is what finally "
    "tests it.** Fixed by padding to the longest with NaN and nan-mean weighting, "
    "and verified by regression on cohort A. *(c) Three download failures, all "
    "silent: fetching ONE month per symbol can never clear a 420-bar warmup, so "
    "**all 422 were rejected and the log said 'downloaded 0/422' while looking "
    "healthy**; the Binance Vision `fundingRate` path has no `/{tf}/` segment; and "
    "`to_datetime` was given both `unit=` and `format=`, on files where "
    "`calc_time` is an INT in the fresh downloads and a STRING in the old ones - "
    "that raise fired AFTER the klines were already written, so the log said 0 and "
    "the disk held 411.** |"
)

A = "| **THE WIDENED UNIVERSE"
B = "| **A drawdown circuit breaker that fails OPEN, silently, and the backtest"
C = "| **Two different quantities named `n`**"
D = "| 2026-09-28 | **SECOND LITERATURE PASS:"


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
    lines[hdr + 2:hdr + 2] = [ROW, VSTACK_TRAP]
    hit = next((i for i, l in enumerate(lines) if l.startswith(B)), -1)
    if hit >= 0:
        lines[hit] = RETRACT
    hit2 = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if hit2 >= 0:
        lines[hit2 + 1:hit2 + 1] = [VSTACK_TRAP]
        # avoid a duplicate copy of the vstack row
        lines.remove(VSTACK_TRAP) if lines.count(VSTACK_TRAP) > 1 else None
    ch = next((i for i, l in enumerate(lines) if l.startswith(D)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted widened-universe row, vstack trap, retracted deployment row, "
          "change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
