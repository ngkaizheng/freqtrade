"""One-off: append the target-R frontier verdict to the 2026-09-28 state rows.

The frontier ran AFTER the first state-file edit, so the row and the change-log
entry written earlier describe a hypothesis that has since been tested and
refuted. This corrects them in place rather than quietly overwriting - the rule
is append-and-correct, and the correction is the finding.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

PERP_CORRECTION = (
    " **UPDATE 2026-09-28 (same day, later): THE TARGET-R HYPOTHESIS WAS "
    "PRE-REGISTERED AND THEN REFUTED — THE LINE IS NOW CLOSED.** Prereg "
    "`PREREG_TARGET_R_2026-09-28.md` (frozen before running), sweep "
    "`target_r in {1.5, 2.0, 3.0, 5.0, 10.0, none}`, whole curve published, no "
    "cell selected, everything else frozen. **At measured_covid, 104 symbols: "
    "mean R -0.0383 / -0.0158 / +0.0114 / -0.0024 / +0.0093 / -0.0065.** The "
    "best cell (3.0R) reaches **t = 0.10** against a bar of 2.0, and the "
    "**by-timestamp treatment is NEGATIVE IN ALL SIX CELLS (-0.26 to -1.08)**. "
    "**The decisive row is the last one: with the profit target removed entirely "
    "(stop + 42-bar time stop only), mean R is still -0.0065.** So **2R is NOT "
    "the binding constraint and the hypothesis is dead** — same shape as "
    "`EXIT_FAMILY_RESULT_2026-09-27.md` on 5m: *the exit diagnosis was right, the "
    "exit fix is not a rescue*. The mechanism IS visible where predicted (2026: "
    "mean R -0.138 at 2.0 -> +0.076 at 10.0) but the same change makes 2023 worse "
    "(-0.194 -> -0.280) and nets to zero. **VERDICT: CLOSED — do not mine this "
    "line further (AGENTS.md 1a).** The earlier text in this row is left as "
    "written; this is the correction."
)

LOG_ANCHOR = "**VERDICT: the WIDE_PANEL short leg does not survive measured costs in the engine that was supposed to confirm it. A negative result, reported as one.** |"
LOG_CORRECTION = (
    " **LATER THE SAME DAY: THE TARGET-R FRONTIER RAN AND REFUTED THE "
    "DIAGNOSIS.** Prereg `PREREG_TARGET_R_2026-09-28.md` was frozen first; the "
    "curve is `target_r in {1.5, 2, 3, 5, 10, none}` at measured_covid, mean R "
    "**-0.0383 / -0.0158 / +0.0114 / -0.0024 / +0.0093 / -0.0065**. Best cell "
    "t = **0.10**; by-timestamp t is **negative in all six cells**. Removing the "
    "profit target entirely still gives mean R **-0.0065**, so **2R was never the "
    "binding constraint**. Identical shape to the 5m exit-family study. **LINE "
    "CLOSED.** *(6b) One more trap found doing it: `--export-directory` MANGLES a "
    "directory whose name contains a dot* - `frontier_out/1.5` was rewritten to "
    "`frontier_out/1-<timestamp>.meta.json` because the dotted name is read as a "
    "file stem, the directory did not exist, and **six completed backtests lost "
    "every export with only a traceback in the log**. Use `tr_1p5`."
)

EXPORT_TRAP_ROW = (
    "| **`--export-directory` mangles a dotted directory name** (new, "
    "cross-cutting) | **TRAP — six completed backtests lost every export, and the "
    "log only shows a traceback** | Passing `--export-directory "
    "user_data\\frontier_out\\1.5` produced a write to "
    "`user_data/frontier_out/1-<timestamp>.meta.json`: the dotted directory name "
    "is read as a file stem and what looks like an extension is stripped. The "
    "directory never existed, so every `--export trades` in **all six frontier "
    "cells** was discarded **after the backtest had already run to completion** "
    "— the only evidence was a `FileNotFoundError` at the very end of the log "
    "file, which a `Select-String` for the strategy summary never matched. "
    "**Cost: ~25 minutes of backtest, twice.** Use a dot-free name (`tr_1p5`) and "
    "**assert the export exists before starting anything that depends on it** — "
    "`frontier_report.py` now prints `NO EXPORT - skipped` per missing cell "
    "rather than producing an empty curve that reads like a result. |"
)


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")

    # 1. correct the PerpShort4h status row
    done = set()
    for i, l in enumerate(lines):
        if l.startswith("| **`PerpShort4h`**") and PERP_CORRECTION[:40] not in l:
            lines[i] = l.rstrip()[:-1].rstrip() + PERP_CORRECTION + " |"
            done.add("perp")
        if LOG_ANCHOR in l and "TARGET-R FRONTIER RAN" not in l:
            lines[i] = l.replace(LOG_ANCHOR, LOG_ANCHOR[:-1].rstrip() + LOG_CORRECTION + " |")
            done.add("log")

    # 2. add the export-directory trap row next to the other new traps
    if not any("mangles a dotted directory name" in l for l in lines):
        idx = next((i for i, l in enumerate(lines)
                    if l.startswith("| **A `custom_stoploss` stop exports")), -1)
        if idx >= 0:
            lines[idx + 1:idx + 1] = [EXPORT_TRAP_ROW]
            done.add("export_row")

    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("patched:", sorted(done) or "nothing (already applied)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
