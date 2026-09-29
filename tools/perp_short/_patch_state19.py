"""One-off: correct the venue verdict from BLOCKED to CLOSED, and record the
process lesson (Gate 0 must test the feed that BLOCKS, not the one that is easy).
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Venue cost lever (Bybit, then OKX)** | **2026-09-29 — CORRECTED FROM "
    "BLOCKED TO CLOSED. Neither venue publishes historical funding, and no bulk "
    "archive exists.** | `VENUE_BLOCKED_2026-09-29.md` -> "
    "`VENUE_CLOSED_2026-09-29.md`; prereg `PREREG_VENUE_COST_2026-09-29.md`; "
    "`tools/perp_short/{venue_probe,venue_paging,okx_funding_probe,okx_bulk_check}.py`. "
    "**The line remains worth having tried:** every recent result is a COST story "
    "- +89.9% on the most liquid 50 of 515, **-33.1% on all 515**, mean R "
    "monotone in universe width, and §1c's `cost_R` law predicts that ordering - "
    "**and all of it is a measurement of Binance.** A different venue is a pure "
    "cost lever. **THE CORRECTION: last round this was recorded as BLOCKED with "
    "the note 'OKX is feasible but ~5x slower'. That was wrong, and the way it "
    "was wrong is the useful part.** I had tested OKX's CANDLE paging (76 pages, "
    "slow but works) and generalised it to the venue. **I never tested OKX's "
    "FUNDING**, which is the feed that blocks. Measured now: **OKX's "
    "`/api/v5/public/funding-rate-history` returns 296 rows spanning "
    "2026-06-22 to 2026-09-28 and its `after` cursor returns EMPTY on page 4** "
    "(`code=0`, not an error); Bybit is capped at 1-2 months with a non-advancing "
    "`end` and a rejected `startTime`; and **six plausible "
    "`static.okx.com` bulk-archive paths all 404**, including the official "
    "data-download page. **So: CLOSED, not BLOCKED - nothing more can be "
    "downloaded that would change it, which is the whole difference between the "
    "two verdicts.** **⚠ AND THE PROCESS LESSON IS WORTH MORE THAN THE RESULT: "
    "last round the Gate 0 sequence was probe venue -> download 190 symbols of "
    "PRICE data (107s) -> write the exporter -> discover funding unreachable. "
    "**This round it was: test the feed that BLOCKS first, on one symbol, in 30 "
    "seconds - and the answer ended the line.** Rule: **Gate 0 must test the feed "
    "whose absence causes a BLOCK, not the feed that is easiest to get. The "
    "easiest one always succeeds, so testing it first is not a test at all.** "
    "**Notably, both venues DO have complete 4h candles back to 2023 (Bybit: 190 "
    "symbols in 107s), and NEITHER has funding for the same period - so any "
    "cross-venue perpetual research done anywhere today has to answer 'where did "
    "your funding come from'.** |"
)

CHANGE = (
    "| 2026-09-29 | **THE VENUE VERDICT IS CORRECTED FROM BLOCKED TO CLOSED, AND "
    "THE WAY IT WAS WRONG IS THE ACTUAL FINDING.** `VENUE_CLOSED_2026-09-29.md`. "
    "Last round this line was BLOCKED with the note '*OKX is feasible but ~5x "
    "slower*'. **That sentence was wrong.** I had tested OKX's CANDLE paging (76 "
    "pages, slow but works) and generalised it to the venue without ever testing "
    "OKX's FUNDING - which is the feed that blocks. Measured now: **OKX funding "
    "returns 296 rows spanning 2026-06-22 to 2026-09-28, and its `after` cursor "
    "returns EMPTY on page 4**; Bybit is capped at 1-2 months; **six bulk-archive "
    "URLs all 404**, including OKX's own data-download page. **CLOSED: nothing "
    "more can be downloaded that would change it.** That is the entire difference "
    "from BLOCKED. **⚠ AND THE PROCESS LESSON, which is worth more than the "
    "result: last round the Gate 0 sequence was probe -> download 190 symbols of "
    "PRICE data (107 s) -> write the exporter -> discover funding unreachable. "
    "This round it was test-the-BLOCKING-feed-first, on one symbol, in 30 seconds, "
    "and that ended the line.** **Rule: Gate 0 must test the feed whose absence "
    "causes a BLOCK, not the feed that is easiest to fetch. The easiest one always "
    "succeeds, so testing it first is not a test.** The standing lesson from Kim & "
    "Hansen and Pindza applies here too: **both venues have complete candles back "
    "to 2023 and neither has funding for the same period, so any cross-venue "
    "perpetual research done anywhere today must answer 'where did your funding "
    "come from' - and the answer is that it did not come from anywhere.** Neither "
    "workaround was used: Binance funding on another venue's prices is a proxy "
    "(charter 2.C, and funding genuinely differs by venue - this repo's §2 records "
    "Binance's being administered, He et al. 2026 v7 measure cross-venue "
    "correlation at 0.74), and **omitting funding is about 10-18% of this book's "
    "edge - the exact magnitude that could reorder the rungs, in the exact "
    "direction the hypothesis is about.** |"
)

A = "| **Venue cost lever (Bybit, then OKX)**"
B = "| **Venue cost lever — a second exchange (Bybit, then OKX)**"
C = "| 2026-09-29 | **THE LAST UNTESTED MAJOR AXIS TRIED"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith(A) for l in lines):
        print("already present")
        return 0
    idx = next((i for i, l in enumerate(lines) if l.startswith(B)), -1)
    if idx < 0:
        print("superseded row not found")
        return 1
    lines[idx] = ROW
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("corrected the venue row in place and appended the change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
