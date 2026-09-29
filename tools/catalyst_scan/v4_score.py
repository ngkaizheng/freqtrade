"""v4 Formal Scoring & Elimination engine.

Implements, in code, the pipeline defined in
`Formal Scoring & Elimination Rules - Crypto Repricing Scanner v4.md`:

    Data Integrity Gate (s51)
      -> Hard Veto       (s52, VETO-1..7)
      -> Archetype       (s53, A..F)
      -> 7-Dim Score     (s54-s61, G F C A L S R, each 0-5)
      -> Raw Score       (s63)  = sum(dim/5 * weight), 0-100
      -> Evidence Factor (s64)  A=1.00 B=0.95 C=0.85 D=0.70 E=excluded
      -> Regime Factor   (s65)  0.90 - 1.10
      -> Final Score     (s66)  = raw * evidence * regime
      -> Minimum Qual.   (s67)  Rules A-D, hard gates
      -> Status          (s68)  85+ / 75-84 / 65-74 / 55-64 / <55
      -> Overrides       (s69)  Priced In / Data Insufficient / Reject
      -> Anti-rules      (s70-s73)

Design decision
---------------
The seven dimension scores and the evidence class are JUDGMENTS and live in
`v4_inputs.csv`, where each one carries a written justification (v4 s82). Every
piece of arithmetic, every gate and every status is computed here, so the
published table can be re-derived from the inputs by `verify_v4.py`. A hand-
typed score table is exactly the kind of thing that rots silently; this split
keeps the judgment auditable and the math checkable.

Status is a function of the FINAL score plus the gates -- never of the score
alone. v4 s69 overrides score, and v4 s70-s73 can veto a high score outright.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ----------------------------------------------------------------- s62 weights
ARCHETYPE_WEIGHTS: dict[str, dict[str, int]] = {
    # A. Fundamental Repricing
    "A": {"F": 25, "G": 20, "C": 15, "S": 15, "A": 10, "L": 10, "R": 5},
    # B. Catalyst Repricing
    "B": {"C": 25, "G": 25, "F": 15, "A": 15, "S": 10, "L": 5, "R": 5},
    # C. Attention Repricing
    "C": {"A": 30, "G": 20, "R": 20, "L": 15, "C": 10, "S": 5, "F": 0},
    # D. Meme / Reflexive
    "D": {"A": 30, "R": 25, "G": 20, "L": 15, "C": 5, "S": 5, "F": 0},
    # E. Supply Repricing
    "E": {"S": 25, "G": 20, "C": 20, "F": 15, "A": 10, "L": 10, "R": 0},
    # F. Hybrid
    "F": {"G": 20, "F": 20, "C": 15, "A": 15, "S": 10, "L": 10, "R": 10},
}

ARCHETYPE_NAME = {
    "A": "Fundamental Repricing",
    "B": "Catalyst Repricing",
    "C": "Attention Repricing",
    "D": "Meme / Reflexive",
    "E": "Supply Repricing",
    "F": "Hybrid",
}

# ----------------------------------------------------------------- s64 evidence
EVIDENCE_FACTOR = {"A": 1.00, "B": 0.95, "C": 0.85, "D": 0.70}
EVIDENCE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}

DIMS = ["G", "F", "C", "A", "L", "S", "R"]


@dataclass
class Candidate:
    token: str
    archetype: str
    scores: dict[str, int]
    evidence: str
    # s51 data integrity gate
    data_ok: bool = True
    data_note: str = ""
    # s52 hard veto: None or a (code, reason)
    veto: tuple[str, str] | None = None
    # s69 override: None or a status string
    override: str | None = None
    override_reason: str = ""
    notes: str = ""
    trace: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        bad = [d for d in DIMS if not 0 <= self.scores.get(d, -1) <= 5]
        if bad:
            raise ValueError(f"{self.token}: dimension out of 0-5 range: {bad}")
        if self.archetype not in ARCHETYPE_WEIGHTS:
            raise ValueError(f"{self.token}: unknown archetype {self.archetype!r}")


def raw_score(c: Candidate) -> float:
    """s63: sum(score/5 * weight) over the archetype's weight vector."""
    w = ARCHETYPE_WEIGHTS[c.archetype]
    return sum(c.scores[d] / 5.0 * w[d] for d in DIMS)


def status_from_score(final: float) -> str:
    """s68 thresholds. Boundary-inclusive, evaluated high to low."""
    if final >= 85:
        return "Deep DD"
    if final >= 75:
        return "High-Priority Watch"
    if final >= 65:
        return "Watch"
    if final >= 55:
        return "Speculative / Low Priority"
    return "Reject"


def evaluate(c: Candidate, regime_factor: float) -> dict:
    """Run one candidate through the whole v4 pipeline and return an audit row."""
    g, f, a, l = (c.scores["G"], c.scores["F"], c.scores["A"], c.scores["L"])
    trace: list[str] = []

    # ---- s51 Data Integrity Gate -------------------------------------------
    if not c.data_ok:
        return {
            "token": c.token, "status": "Data Insufficient",
            "reason": c.data_note or "fails s51 data integrity gate",
            "raw": 0.0, "final": 0.0, "norm": 0.0,
            "archetype": ARCHETYPE_NAME.get(c.archetype, "?"),
            "scores": c.scores, "evidence": c.evidence,
            "qualification": "n/a - stopped at s51",
            "gate_fail": "s51 data integrity",
            "trace": ["s51 GATE FAIL"],
        }

    # ---- s64 Evidence: class E never enters the ranking --------------------
    if c.evidence == "E":
        return {
            "token": c.token, "status": "Data Insufficient",
            "reason": "s64 Confidence E (rumour only) - excluded from ranking",
            "raw": 0.0, "final": 0.0, "norm": 0.0,
            "archetype": ARCHETYPE_NAME.get(c.archetype, "?"),
            "scores": c.scores, "evidence": c.evidence,
            "qualification": "n/a - stopped at s64",
            "gate_fail": "s64 Confidence E",
            "trace": ["s64 EVIDENCE E -> EXCLUDED"],
        }

    # ---- s52 Hard Veto -----------------------------------------------------
    if c.veto:
        code, reason = c.veto
        trace.append(f"VETO {code}: {reason}")
        return {
            "token": c.token, "status": "Reject",
            "reason": f"{code} - {reason}",
            "raw": 0.0, "final": 0.0, "norm": 0.0,
            "archetype": ARCHETYPE_NAME.get(c.archetype, "?"),
            "scores": c.scores, "evidence": c.evidence,
            "qualification": "n/a - hard veto overrides all gates (s52)",
            "gate_fail": f"{code}: {reason}",
            "trace": trace,
        }

    raw = raw_score(c)
    ev = EVIDENCE_FACTOR[c.evidence]
    final = raw * ev * regime_factor
    trace.append(
        f"raw {raw:.1f} x evidence {ev:.2f} ({c.evidence}) x regime "
        f"{regime_factor:.2f} = {final:.1f}"
    )

    # ---- s67 Minimum Qualification (hard gates, evaluated on raw dims) ------
    driver = max(f, c.scores["C"], a, c.scores["S"], c.scores["R"])
    gate_fail = None
    if g < 3:
        gate_fail = f"Rule B: Information Gap {g} < 3 (s67)"
    elif driver < 4:
        best = max(
            (("F", f), ("C", c.scores["C"]), ("A", a),
             ("S", c.scores["S"]), ("R", c.scores["R"])),
            key=lambda kv: kv[1],
        )
        gate_fail = (
            f"Rule A: no primary driver >= 4 (best {best[0]}={best[1]}) (s67)"
        )
    elif l < 2:
        gate_fail = f"Rule C: Liquidity {l} < 2 (s67)"
    elif EVIDENCE_ORDER[c.evidence] > EVIDENCE_ORDER["C"]:
        gate_fail = f"Rule D: Confidence {c.evidence} < C (s67)"
    if gate_fail:
        trace.append(f"QUALIFICATION FAIL: {gate_fail}")
    qualification = "PASS" if not gate_fail else f"FAIL - {gate_fail}"

    # ---- s70-s73 anti-rules -------------------------------------------------
    anti = []
    if a >= 5 and g < 3:
        anti.append("s70 anti-hype: Attention 5 with no information gap")
    if f == 5 and a <= 2 and c.scores["C"] <= 2 and g <= 2:
        anti.append("s71 anti-value-trap: F=5 but A,C,G all <= 2")
    if a >= 5 and c.scores["R"] >= 5 and g <= 2 and l <= 2 and c.scores["S"] <= 1:
        anti.append("s72 anti-meme-chasing: A=5,R=5 with G<=2,L<=2,S<=1")
    if c.scores["C"] == 5 and g <= 2:
        anti.append("s73 anti-catalyst-chasing: C=5 with G<=2")
    trace.extend(anti)

    status = status_from_score(final)

    # s72 is a hard reject; s73 caps at Watch; s70/s71 cap at Watch.
    if any(x.startswith("s72") for x in anti):
        status = "Reject"
    elif any(x.startswith(("s70", "s71", "s73")) for x in anti):
        if status in ("Deep DD", "High-Priority Watch"):
            status = "Watch"

    if gate_fail:
        # v4 s67: failing a qualification gate means the candidate is not
        # investable at ANY score. This is deliberately kept separate from the
        # score test below, because the two disagree in a way worth reporting:
        # a candidate can clear every hard gate (real information gap, real
        # driver, exitable, acceptable evidence) and still land under the 55
        # bar of s68. `qualification` preserves that distinction.
        status = "Reject"

    # ---- s69 overrides beat the score --------------------------------------
    if c.override:
        status = c.override
        trace.append(f"s69 OVERRIDE -> {c.override}: {c.override_reason}")

    return {
        "token": c.token,
        "status": status,
        "reason": "; ".join(anti) if anti else "",
        "raw": raw, "final": final, "norm": final / 1.10,
        "archetype": ARCHETYPE_NAME.get(c.archetype, "?"),
        "scores": c.scores, "evidence": c.evidence,
        "qualification": qualification,
        "gate_fail": gate_fail or "",
        "trace": trace, "notes": c.notes,
    }


def score_table(cands: list[Candidate], regime_factor: float) -> list[dict]:
    rows = [evaluate(c, regime_factor) for c in cands]
    # s84 ranking logic: veto > information gap > driver > liquidity > supply
    # > reflexivity. Sort by status band first, then by the s84 priority keys.
    band = {
        "Deep DD": 0, "High-Priority Watch": 1, "Watch": 2,
        "Speculative / Low Priority": 3,
    }
    def sort_key(r: dict):
        s = r["scores"]
        return (
            band.get(r["status"], 9),
            -s.get("G", 0),
            -max(s.get("F", 0), s.get("C", 0), s.get("A", 0),
                 s.get("S", 0), s.get("R", 0)),
            -s.get("L", 0),
            -r["final"],
        )
    return sorted(rows, key=sort_key)
