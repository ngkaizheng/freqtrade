"""One-off: insert the 2026-09-28 rows into RESEARCH_STATE.md's section 1 table.

Kept as a script rather than an inline `python -c` because PowerShell eats
backticks inside a double-quoted -c argument, and this file is full of them.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW_PERP = (
    "| **`PerpShort4h`** (the WIDE_PANEL short leg, made deployable) | "
    "**2026-09-28 — BUILT, GATED, AND IT FAILS ITS OWN PREREGISTERED GATE** | "
    "Full: `docs-myself/PERP_SHORT_4H_RESULT_2026-09-28.md`. Preregs "
    "`PREREG_104_FT_COSTS_2026-09-28.md` + `PREREG_TARGET_R_2026-09-28.md`, both "
    "frozen before their numbers. **The first 104-perp panel ever run inside "
    "freqtrade, and the panel claim does not survive it.** Cost frontier (104 "
    "symbols, gross -> measured COVID 34.9bps): **+134.4% -> −22.4%**, PF 1.13 "
    "-> 0.96, maxDD 42.2% -> 48.6%. Same on 24 liquid majors: +144.3% -> "
    "**+23.7%**, PF 1.05, maxDD 29.7%. **In R units, G1 t>=2.0 / G1b / G2 / G3 all "
    "FAIL at every cost regime** (104 @COVID: mean R −0.016, 42% of symbols "
    "positive, **1 of 4 calendar years positive**). `max_open_trades` 24 vs 104 "
    "gives byte-identical trades, so concurrency is not the explanation, and the "
    "flat bps is **optimistic for the long tail**. **The diagnosis: buy-and-hold "
    "on the same 103 pairs has a MEDIAN of −80.9%, and the short book still lost "
    "22.4% — because the frozen rule banks 2R (~7.2%).** Registered as a post-hoc "
    "hypothesis in a pre-registered frontier (target_r in {1.5, 2, 3, 5, 10, "
    "none}, whole curve published, no cell selected). Gates green: **421/421 stops "
    "verified at 1.5xATR(entry), median error 0.00000%**; truncation-causality "
    "PASS on 6 symbols. **Deliverables that survive the negative verdict:** a "
    "runnable strategy, three self-rejecting gates, two new cross-cutting traps, "
    "and the full 104-perp dataset. |"
)

ROW_ATR = (
    "| **`entry_atr` fallback picks the OLDEST bar** (new, cross-cutting) | "
    "**TRAP — it silently capped the ATR at 3 months stale, and a stop can never "
    "be loosened** | On the **entry candle** `self.dp.get_analyzed_dataframe` has "
    "**not yet been extended to the entry bar**, so a timestamp lookup of the "
    "entry bar always misses (measured: `frame=[2023-09-22 .. 2023-12-24 20:00]`, "
    "`n_match=0`, for a trade opening 2023-12-25). `ShortBreakout4h.entry_atr` "
    "then fell back to `df[\"atr\"].iloc[0]` — the **OLDEST** bar. BTC 2023-12-25: "
    "**304.28 returned, 484.94 true**; stop at +456.43 instead of +727.41. "
    "`LocalTrade.adjust_stop_loss` only ever **tightens** "
    "(`trade_model.py:886-893`: *\"stop losses only walk up, never down\"*), so the "
    "error is **permanent for the life of the trade**. **179 of 502 stop-outs were "
    "wrong and the equity curve looked normal throughout; fixing it moved +26.06% "
    "-> +97.44% on identical inputs.** **The fallback must be `iloc[-1]`** — on "
    "the entry candle that IS the signal bar, the only ATR knowable at decision "
    "time. This is the AGENTS.md §3 silent-fallback family reached through a "
    "data-provider lag, and it bit a **baseline** strategy, so every comparison "
    "drawn against `ShortBreakout4h` before 2026-09-28 was measured on a "
    "mis-stopped book. Pinned by `tools/perp_short/verify_stop.py`. |"
)

ROW_TRAIL = (
    "| **A `custom_stoploss` stop exports as `trailing_stop_loss`** (new, "
    "cross-cutting) | **TRAP — it makes a frozen stop look like a trailing stop, "
    "and hides it from `== \"stop_loss\"` filters** | `LocalTrade.adjust_stop_loss` "
    "sets `is_stop_loss_trailing = True` on **any** modification of an already-set "
    "stop (`trade_model.py:895-896`), so the flag means *\"adjusted at least "
    "once\"*, **not** *\"a trailing stop moved\"*. Measured on `PerpShort4h`: **421 "
    "trades exported as `trailing_stop_loss`, every one of them a frozen 1.5xATR "
    "stop; the strategy defines no trailing stop at all.** Two consequences, both "
    "wrong: (a) counting `exit_reason == \"stop_loss\"` returns **zero** and reads "
    "as *\"the stop never fired\"*; (b) seeing 421 \"trailing stops\" and concluding "
    "trailing is the problem invites **deleting a stop that is doing exactly what "
    "it was frozen to do** — which is what `RegimeBreakoutExitStudy` was one step "
    "away from doing when it found `exit_signal` winning 28 of 2,182. Both "
    "exit-reason decompositions in this repo must count **both** reasons. |"
)

OLD = ("THE FEE FRONTIER IS REGISTERED BUT **NOT RUN** (machine memory")
NEW = ("THE FEE FRONTIER IS REGISTERED AND IS **BEING RUN BY A SECOND AGENT** "
       "— deliberately not duplicated here")


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    idx = next((i for i, l in enumerate(lines)
                if l.startswith("| **Freqtrade official / community strategies**")), -1)
    if idx < 0:
        print("anchor row not found")
        return 1
    if "PerpShort4h" in "\n".join(lines[idx:idx + 4]):
        print("already inserted; nothing to do")
        return 0
    before = lines[idx]
    demoted = before
    for old, new in ((OLD, NEW),
                     (OLD + " — see the change log).**",
                      NEW + " — deliberately not duplicated here.**")):
        if old in demoted:
            demoted = demoted.replace(old, new)
    lines[idx] = demoted
    lines[idx:idx] = [ROW_PERP, ROW_ATR, ROW_TRAIL]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    changed = demoted != before
    print(f"inserted 3 rows at line {idx + 1}; community row rewritten: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
