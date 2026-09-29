"""One-off: record the venue line as BLOCKED, with the two bugs found on the way.

BLOCKED and CLOSED are recorded as different states on purpose: CLOSED means it
was tested and the result was empty; BLOCKED means it could not be tested because
a REQUIRED feed is unavailable, which is a different fact with a different
unblocking condition.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Venue cost lever — a second exchange (Bybit, then OKX)** | "
    "**2026-09-29 — BLOCKED, NOT CLOSED. The PRICE data is available and was "
    "downloaded; the REQUIRED funding feed is not.** | Prereg "
    "`PREREG_VENUE_COST_2026-09-29.md`; result `VENUE_BLOCKED_2026-09-29.md`; "
    "`tools/perp_short/{venue_probe,venue_paging}.py`, "
    "`tools/widepanel/{fetch_bybit,fetch_bybit_funding}.py`. **WHY IT WAS WORTH "
    "TRYING:** every recent result is a COST story — +89.9% on the most liquid 50 "
    "of 515, **-33.1% on all 515**, mean R monotone in the width of the universe "
    "(0.2954 -> -0.4855), and §1c's `cost_R` law predicts that ordering exactly. "
    "**All of that is a measurement of Binance.** A venue is the last untested "
    "major axis and a pure cost lever: same signal, same rule, different order "
    "book, different fees, different listing universe. **GATE 0 (charter 2.C) WAS "
    "RUN FIRST AND IT PAID FOR ITSELF:** OKX serves 100 bars/page and reaches "
    "18 days; Bybit serves 1000 bars/page and reaches 5.5 months in one request. "
    "**Paging is the decisive test, not one-request depth** — OKX needs ~76 more "
    "pages to 2023 (~28 s/symbol), **Bybit needs 2** (~6 s/symbol), so Bybit was "
    "chosen on measured feasibility. **The price download then SUCCEEDED: "
    "190/190 symbols, 4h, back to 2023-01, in 107 seconds** (10 of the Binance "
    "top-200 do not exist on Bybit; recorded in "
    "`shark_data/bybit/absent_on_bybit.json`, never silently dropped). "
    "**⚠ AND THEN IT BLOCKED.** freqtrade's futures backtest loads funding with "
    "`fail_without_data=True` (`backtesting.py:428`), so funding is a REQUIRED "
    "feed, not an enhancement. Bybit's `/v5/market/funding/history` returns 200 "
    "rows and `retCode=0` on a plain call, but **the `end` cursor does not "
    "advance** (every symbol sticks at 2026-07/08) and **`startTime` is rejected "
    "outright** (`retCode=10001, 'Time Is Invalid'`); the bulk archive routes "
    "404. **Effective depth is about 1-2 months against a design that needs "
    "2023-01 onward.** The two obvious workarounds are both forbidden and neither "
    "was used: **Binance funding on Bybit prices is a proxy substitution** "
    "(charter 2.C; and funding genuinely differs by venue — this repo's own §2 "
    "records Binance's being ADMINISTERED by its clamp, and He et al. 2026 v7 "
    "measure cross-venue funding correlation at 0.74, i.e. related but not equal), "
    "and **omitting funding makes the Bybit rung systematically optimistic** in "
    "the exact direction the hypothesis is about. **A BLOCKED verdict, not an "
    "approximation.** It unblocks the moment Bybit publishes a bulk funding "
    "archive (the 190 symbols of price data are already on disk and the exporter "
    "and ladder are written), or by switching to OKX at ~5x the download time. |"
)

LOOP_TRAP = (
    "| **A paging loop that cannot prove it is advancing will run forever** (new, "
    "cross-cutting, **the 11th instance, and the second MISSING-SIGNAL variant "
    "of the 10th**) | **TRAP — five minutes and zero files, with no error** | "
    "`fetch_bybit_funding` looped on `end = oldest - 1` with no progress check. "
    "Bybit's funding endpoint accepts the cursor and ignores it, so every request "
    "returned **the same 200 rows**, `oldest` never moved, and the loop spun "
    "until it was killed. **The signature is a run that produces nothing and "
    "reports nothing** — identical in kind to the `t_by_ts = nan` bug, which also "
    "produced nothing and said nothing. **A paging loop that cannot demonstrate "
    "forward progress must break on its own** (`if oldest >= prev_oldest: stop`), "
    "and a downloader must assert a non-zero file count before it is believed. "
    "**Same family as the tenth: a wrong number gets argued about, a missing one "
    "just disappears.** |"
)

STEM_TRAP = (
    "| **`Path(\"X.csv.gz\").stem` is `\"X.csv\"` — AGAIN, and the log looked like "
    "a venue problem** (new, cross-cutting) | **TRAP — already recorded in "
    "§1c/WIDE_PANEL_RESULT and hit a SECOND time in the same session** | "
    "`Path` strips only the LAST suffix, so a funding request went out as "
    "`XRPUSDT.csv`, the API correctly returned nothing for all 190 symbols, and "
    "the log filled with `no funding rows` — which reads as 'Bybit has no funding "
    "data' rather than 'the symbol name has a `.csv` on it'. The original "
    "occurrence is recorded in `WIDE_PANEL_RESULT_2026-09-27.md` §9 and turned "
    "'104 klines + 104 funding' into '0 available, 0 dropped'. **Use "
    "`p.name.removesuffix('.csv.gz')`, and never `.stem` on a double-suffixed "
    "file.** A trap recorded once and re-hit a full session later is a trap whose "
    "recording is not in the place the code is read. |"
)

CHANGE = (
    "| 2026-09-29 | **THE LAST UNTESTED MAJOR AXIS TRIED, AND IT IS BLOCKED ON A "
    "REQUIRED FEED - WHICH IS NOT THE SAME AS CLOSED.** "
    "`VENUE_BLOCKED_2026-09-29.md`, `PREREG_VENUE_COST_2026-09-29.md`. **The "
    "whole recent result is a cost story** - +89.9% on the most liquid 50 of 515, "
    "**-33.1% on all 515**, mean R monotone in universe width, and §1c's `cost_R` "
    "law predicts that ordering exactly - **and all of it is a measurement of "
    "Binance.** A venue is a pure cost lever and the last untested axis. "
    "**Gate 0 first, and it earned its place:** OKX serves 100 bars/page reaching "
    "18 days; Bybit 1000 bars/page reaching 5.5 months in ONE request, and "
    "**paging is the decisive test** - OKX needs ~76 more pages to 2023, **Bybit "
    "needs 2**. **The price download then succeeded: 190/190 symbols, 4h, back to "
    "2023-01, in 107 seconds.** **And then it blocked.** freqtrade loads funding "
    "with `fail_without_data=True` (`backtesting.py:428`), so it is REQUIRED, not "
    "an enhancement; Bybit's funding endpoint answers a plain call with "
    "`retCode=0` and 200 rows but **the `end` cursor does not advance** and "
    "**`startTime` is rejected outright** (`10001, 'Time Is Invalid'`); the bulk "
    "archive 404s. **Effective depth ~1-2 months against a 2023-01 design.** "
    "**Neither workaround was used, and both were refused on the record:** "
    "Binance funding on Bybit prices is a proxy (charter 2.C; funding genuinely "
    "differs by venue - this repo's §2 records Binance's being administered, and "
    "He et al. 2026 v7 measure cross-venue correlation at 0.74, related but not "
    "equal), and **omitting funding makes the Bybit rung systematically optimistic "
    "in exactly the direction the hypothesis is about.** **BLOCKED, not CLOSED:** "
    "it unblocks the moment a bulk funding archive exists, since the 190 symbols of "
    "price data are already on disk. *(b) ⚠ Two more bugs, and the second one is "
    "the 11th instance and the second MISSING-SIGNAL variant of the 10th: **a "
    "paging loop that cannot prove it is advancing runs forever.** Bybit accepts "
    "the funding cursor and ignores it, so every page returned the SAME 200 rows, "
    "`oldest` never moved, and the run produced nothing and said nothing for five "
    "minutes. Same family as `t_by_ts = nan`: **a wrong number gets argued about, "
    "a missing one just disappears.** A paging loop must break when it cannot "
    "demonstrate forward progress. **And `Path(\"X.csv.gz\").stem` returned "
    "`\"X.csv\"` for the second time in this session** - already recorded in "
    "`WIDE_PANEL_RESULT_2026-09-27.md` §9 - so all 190 funding requests went out "
    "as `XRPUSDT.csv` and the log filled with 'no funding rows', which reads as a "
    "venue problem rather than a string bug. **A trap recorded once and re-hit a "
    "session later is a trap whose recording is not where the code is read.** |"
)

A = "| **Venue cost lever — a second exchange (Bybit, then OKX)**"
C = "| 2026-09-29 | **THE LINE IS CLOSED AS RESEARCH AND OPENED AS A FORWARD"


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
    lines[hdr + 2:hdr + 2] = [ROW, LOOP_TRAP, STEM_TRAP]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted venue BLOCKED row, loop trap, stem trap, change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
