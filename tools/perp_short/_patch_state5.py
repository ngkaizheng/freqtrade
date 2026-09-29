"""One-off: record the stop-vs-class-backstop collision as a cross-cutting trap.

Found by the stop-multiple gate, and it is the third instance in this session of
the same shape: a constant measured on a 24-symbol liquid subset being used as a
bound on a 104-symbol long-tail panel.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Widening the stop multiple collides with the class `stoploss`** (new, "
    "cross-cutting) | **TRAP — a 4xATR stop on a thin name can EXCEED the −30% "
    "backstop, and freqtrade would silently make the backstop the operative stop** "
    "| `PerpShort4h` sets `stoploss = -0.30` purely as a backstop, and "
    "`custom_stoploss` tightens it to the ATR anchor. **That works only while the "
    "anchor is WIDER than the class value**, because `adjust_stop_loss` accepts a "
    "tightening move only (`trade_model.py:886-893`). Measured on the 4.0-ATR arm "
    "over 104 symbols: realised stop distance is **median 9.87% of price, p95 "
    "16.11%, max 28.35% (PEOPLE/USDT 2024-08-05)** — i.e. **1.65 points from the "
    "backstop**. On this run nothing clamped (28.35% < 30%), so the numbers stand, "
    "but **the next rung up would break silently**: any name whose 4xATR exceeds "
    "30% gets the −30% backstop as its real stop, the R denominator no longer "
    "matches the anchor, and the backtest reports it as a normal loss. "
    "**RULE: before running any stop multiple above ~1.5, widen the class "
    "`stoploss` first, and let `verify_stop.py` prove it.** The gate now measures "
    "the realised stop distribution and raises an explicit `unreachable` list when "
    "an ATR anchor is wider than the class backstop. **This is the third time in "
    "one session that a constant measured on the 24-symbol liquid majors was used "
    "as a bound on the 104-symbol long tail** — first the 5.04% stop ceiling, then "
    "the 20% version of it, now the 30% backstop. |"
)

CHANGE_ANCHOR = (
    "the pre-registered control says so explicitly.* |"
)
CHANGE = (
    " *(8) ⚠ THIRD INSTANCE OF THE SAME SHAPE, AND IT IS ABOUT THE STOP ITSELF: "
    "**widening the stop multiple collides with the class `stoploss`.** "
    "`PerpShort4h` uses `stoploss = -0.30` as a backstop that `custom_stoploss` "
    "tightens, which works **only while the ATR anchor is wider than −30%**, "
    "because `adjust_stop_loss` accepts tightening moves only. On the 4.0-ATR arm "
    "the realised stop distance is **median 9.87%, p95 16.11%, max 28.35% of "
    "price** — 1.65 points from the backstop. Nothing clamped on this run so the "
    "numbers stand, but **the next rung up breaks silently**: a thin name whose "
    "4xATR exceeds 30% gets −30% as its real stop, the R denominator stops matching "
    "the anchor, and the trade is reported as a normal loss. Widen the class "
    "`stoploss` before any wider stop, and let the gate prove it. (Earlier today "
    "the same 24-symbol-subset constant caused two false gate failures at 5.04% "
    "and at 20%.)* |"
)


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any("collides with the class `stoploss`" in l for l in lines):
        print("already present")
        return 0
    idx = next((i for i, l in enumerate(lines)
                if l.startswith("| **Two different quantities named `n`**")), -1)
    if idx < 0:
        print("anchor not found")
        return 1
    lines[idx:idx] = [ROW]

    hit = next((i for i, l in enumerate(lines) if CHANGE_ANCHOR in l), -1)
    if hit >= 0:
        lines[hit] = lines[hit].replace(CHANGE_ANCHOR,
                                        CHANGE_ANCHOR[:-1].rstrip() + CHANGE + " |")
    else:
        print("WARN: change-log anchor not found; row inserted only")

    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted stop/backstop-collision trap row"
          + (" and change-log note" if hit >= 0 else " (change-log anchor missing)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
