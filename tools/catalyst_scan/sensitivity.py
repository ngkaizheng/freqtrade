"""Sensitivity of the v4 result to the judgment calls that are actually close.

AGENTS.md section 3: "Publish the curve, never the chosen cell." Four of the
v4 dimension scores sit on a boundary, and two candidates land within ~1.5
points of the 55 bar, so the published status is not robust to my own scoring
choices. Rather than assert a single number, this prints how each status moves
when a contested judgment is decided the other way.

The axes below are the ones that are genuinely contestable, not an exhaustive
grid. A sweep over all seven dimensions would produce a meaningless cloud; what
matters is which specific calls I made that a reasonable analyst would make
differently.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from v4_run import CANDIDATES, REGIME_FACTOR  # noqa: E402
from v4_score import Candidate, evaluate  # noqa: E402

DIMS = ["G", "F", "C", "A", "L", "S", "R"]


def variant(base: Candidate, **changes) -> Candidate:
    scores = dict(base.scores)
    ev = changes.pop("evidence", base.evidence)
    for k, v in changes.items():
        assert k in DIMS, k
        scores[k] = v
    return Candidate(
        token=base.token, archetype=base.archetype, scores=scores,
        evidence=ev, data_ok=base.data_ok, data_note=base.data_note,
        veto=base.veto, override=base.override,
        override_reason=base.override_reason,
    )


def line(label: str, c: Candidate, regime: float = REGIME_FACTOR) -> str:
    r = evaluate(c, regime)
    flag = ""
    if r["status"] != evaluate(c, REGIME_FACTOR)["status"]:
        flag = "   <-- status changes"
    return (f"  {label:<52s} raw {r['raw']:6.2f}  final {r['final']:6.2f}  "
            f"{r['status']}{flag}")


def main() -> None:
    by = {c.token: c for c in CANDIDATES}

    print("=" * 100)
    print("AXIS 1 - KNTQ Catalyst: does a verbally-confirmed, never-published date "
          "score 2 or 3?")
    print("  (s57: 2 = official plan, date/execution uncertain | "
          "3 = officially confirmed, reasonable time window)")
    print(line("KNTQ base  C=3 (my call: testnet live, mainnet said 'end of Oct')",
               by["KNTQ"]))
    print(line("KNTQ       C=2 (project has never published a date)",
               variant(by["KNTQ"], C=2)))
    print(line("KNTQ       C=2 + evidence D (date is L4 only)",
               variant(by["KNTQ"], C=2, evidence="D")))

    print()
    print("=" * 100)
    print("AXIS 2 - AVA evidence class: is an official blog post + a reported "
          "first settlement Confidence B or C?")
    print("  (s64: B = official + protocol accounting, not fully on-chain | "
          "C = official claims + secondary confirmation)")
    print(line("AVA base  evidence C (my call: no on-chain tx hash verified)", by["AVA"]))
    print(line("AVA       evidence B", variant(by["AVA"], evidence="B")))
    print(line("AVA       evidence A (buyback proven on-chain)", variant(by["AVA"], evidence="A")))

    print()
    print("=" * 100)
    print("AXIS 3 - the buyback-vs-dilution arithmetic on KNTQ (S dimension)")
    print("  S=2 my call. FDV/MC 3.57; the buyback retires 12.9M/yr against 719M "
          "still unissued = 1.8% of the overhang.")
    print(line("KNTQ base  S=2", by["KNTQ"]))
    print(line("KNTQ       S=1 (obvious dilution)", variant(by["KNTQ"], S=1)))
    print(line("KNTQ       S=0 (severe dilution, no absorption)", variant(by["KNTQ"], S=0)))

    print()
    print("=" * 100)
    print("AXIS 4 - AVA Fundamental: is a ~$89-177K/month buyback 'large' enough "
          "for F=4?")
    print("  (s56: 4 = verified + growth headroom | 3 = real capture)")
    print("  Reality check: $89-177K/month against ~$285M/month of volume is "
          "0.03-0.06% of turnover.")
    print(line("AVA base  F=4 (my call: verified, permanent, scales)", by["AVA"]))
    print(line("AVA       F=3 (real capture, but immaterial as a flow)", variant(by["AVA"], F=3)))

    print()
    print("=" * 100)
    print("AXIS 5 - Regime factor (s65, 0.90-1.10). Full range applied to the two "
          "candidates that clear every hard gate.")
    print(f"  regime label: {REGIME_FACTOR:.2f}")
    for tok in ("AVA", "KNTQ", "AERO", "LDO"):
        print(f"  {tok}:")
        for rf in (0.90, 0.95, 1.00, 1.05, 1.10):
            print(line(f"    regime {rf:.2f}", by[tok], regime=rf))
        print()

    print("=" * 100)
    print("AXIS 6 - the one that decides the headline: how much would the whole "
          "result move if the 55 bar were different?")
    print("  Candidates clearing ALL of s67's hard gates, across the s68 bands:")
    print(f"  {'token':<8s} {'final':>7s}  {'norm':>6s}  band at 55 / 65 / 75 / 85")
    for c in CANDIDATES:
        r = evaluate(c, REGIME_FACTOR)
        if r["qualification"] != "PASS":
            continue
        bands = []
        for bar in (55, 65, 75, 85):
            bands.append("yes" if r["final"] >= bar else "no ")
        print(f"  {c.token:<8s} {r['final']:7.2f}  {r['norm']:6.2f}      "
              f"{'     '.join(bands)}")
    print()
    print("  Nothing in the set reaches the 85 Deep-DD bar under ANY of the "
          "settings above.")


if __name__ == "__main__":
    main()
