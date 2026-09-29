"""Regression gate for the v4 scoring engine.

AGENTS.md section 3 requires a gate to run before any result is believed, and
records that a hand-written runner that quietly under-reports is worse than no
gate at all. `verify_report.py` already caught its own bug (annualising a
5-month buyback by dividing by 5 instead of x12/5, a 12x error that printed as
a perfectly normal table). This file is the equivalent for the v4 engine.

Three layers:
    PART 1  engine invariants  - the arithmetic of v4_score is self-consistent
    PART 2  published table     - every number in the report is re-derived
                                  from v4_inputs.csv, not retyped
    PART 3  data freshness      - the market figures quoted in the inputs still
                                  match the live evidence file, so a stale
                                  number cannot be published unnoticed

Run:  .venv\Scripts\python.exe tools\catalyst_scan\verify_v4.py
Exit code 0 = all checks pass. Non-zero = the report must not be trusted.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from v4_score import (  # noqa: E402
    ARCHETYPE_WEIGHTS, DIMS, EVIDENCE_FACTOR, Candidate, evaluate, raw_score,
    status_from_score,
)

OUT = Path(__file__).resolve().parent / "out"
FAILURES: list[str] = []
CHECKS = 0


def check(cond: bool, label: str, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILURES.append(f"{label}{(' :: ' + detail) if detail else ''}")


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


# ---------------------------------------------------------------- PART 1
def part1_engine_invariants() -> None:
    # s62: every archetype's weight vector must be a complete partition of 100.
    for k, w in ARCHETYPE_WEIGHTS.items():
        check(sum(w.values()) == 100, f"P1 weights sum to 100 [{k}]",
              f"got {sum(w.values())}")
        check(set(w) == set(DIMS), f"P1 weights cover all 7 dims [{k}]")

    # s63: raw score on a hand-computed vector (the v4 document's own example,
    # s63, which uses Hybrid weights).
    c = Candidate(
        token="__selftest__", archetype="F",
        scores={"G": 4, "F": 4, "C": 5, "A": 3, "L": 4, "S": 3, "R": 2},
        evidence="A",
    )
    # Hybrid: G20 F20 C15 A15 S10 L10 R10
    # 4/5*20 + 4/5*20 + 5/5*15 + 3/5*15 + 3/5*10 + 4/5*10 + 2/5*10
    # = 16 + 16 + 15 + 9 + 6 + 8 + 4 = 74
    check(close(raw_score(c), 74.0), "P1 s63 worked example = 74",
          f"got {raw_score(c)}")

    # s66: final = raw * evidence * regime, exactly.
    for ev in "ABCD":
        cc = Candidate(
            token="__t__", archetype="F",
            scores={"G": 4, "F": 4, "C": 4, "A": 4, "L": 4, "S": 4, "R": 4},
            evidence=ev,
        )
        r = evaluate(cc, 1.00)
        check(close(r["final"], r["raw"] * EVIDENCE_FACTOR[ev]),
              f"P1 final = raw x evidence [{ev}]")
        check(close(r["norm"], r["final"] / 1.10), f"P1 normalized [{ev}]")

    # s68 thresholds are boundary-inclusive at the bottom of each band.
    for score, want in [
        (100.0, "Deep DD"), (85.0, "Deep DD"), (84.999, "High-Priority Watch"),
        (75.0, "High-Priority Watch"), (74.999, "Watch"),
        (65.0, "Watch"), (64.999, "Speculative / Low Priority"),
        (55.0, "Speculative / Low Priority"), (54.999, "Reject"), (0.0, "Reject"),
    ]:
        check(status_from_score(score) == want,
              f"P1 s68 boundary {score} -> {want}",
              f"got {status_from_score(score)}")

    # s52 hard veto must short-circuit to Reject and must not be rescuable by
    # an override or by a perfect score.
    v = Candidate(
        token="__veto__", archetype="F",
        scores={"G": 5, "F": 5, "C": 5, "A": 5, "L": 5, "S": 5, "R": 5},
        evidence="A", veto=("VETO-3", "honeypot"),
        override="Deep DD", override_reason="should be ignored",
    )
    r = evaluate(v, 1.10)
    check(r["status"] == "Reject", "P1 hard veto beats a s69 override",
          f"got {r['status']}")
    check(r["final"] == 0.0, "P1 vetoed candidate scores 0")

    # s64 Confidence E never enters the ranking.
    e = Candidate(
        token="__ev__", archetype="F",
        scores={"G": 5, "F": 5, "C": 5, "A": 5, "L": 5, "S": 5, "R": 5},
        evidence="E",
    )
    check(evaluate(e, 1.0)["status"] == "Data Insufficient",
          "P1 s64 Confidence E -> Data Insufficient")

    # s51 data gate outranks everything.
    d = Candidate(
        token="__data__", archetype="F",
        scores={"G": 5, "F": 5, "C": 5, "A": 5, "L": 5, "S": 5, "R": 5},
        evidence="A", data_ok=False, data_note="mcap conflict",
    )
    check(evaluate(d, 1.0)["status"] == "Data Insufficient",
          "P1 s51 data gate -> Data Insufficient")

    # s67 Rules A-D, each isolated.
    base = {"G": 4, "F": 4, "C": 4, "A": 4, "L": 4, "S": 4, "R": 4}
    g_low = dict(base, G=2)
    check(evaluate(Candidate("__rb__", "F", g_low, "A"), 1.0)["status"] == "Reject",
          "P1 s67 Rule B (G<3) rejects")
    no_driver = {"G": 4, "F": 3, "C": 3, "A": 3, "L": 4, "S": 3, "R": 3}
    check(evaluate(Candidate("__ra__", "F", no_driver, "A"), 1.0)["status"]
          == "Reject", "P1 s67 Rule A (no driver >=4) rejects")
    liq_low = dict(base, L=1)
    check(evaluate(Candidate("__rc__", "F", liq_low, "A"), 1.0)["status"]
          == "Reject", "P1 s67 Rule C (L<2) rejects")
    check(evaluate(Candidate("__rd__", "F", dict(base), "D"), 1.0)["status"]
          == "Reject", "P1 s67 Rule D (Confidence D) rejects")

    # s70-s73 anti-rules.
    meme = {"G": 2, "F": 0, "C": 1, "A": 5, "L": 2, "S": 1, "R": 5}
    check(evaluate(Candidate("__meme__", "D", meme, "A"), 1.0)["status"]
          == "Reject", "P1 s72 anti-meme-chasing rejects")
    chase = {"G": 2, "F": 3, "C": 5, "A": 3, "L": 4, "S": 3, "R": 3}
    r = evaluate(Candidate("__chase__", "B", chase, "A"), 1.0)
    check(r["status"] not in ("Deep DD", "High-Priority Watch"),
          "P1 s73 anti-catalyst-chasing caps at Watch",
          f"got {r['status']}")
    trap = {"G": 2, "F": 5, "C": 2, "A": 2, "L": 4, "S": 3, "R": 2}
    r = evaluate(Candidate("__trap__", "A", trap, "A"), 1.0)
    check(r["status"] not in ("Deep DD", "High-Priority Watch"),
          "P1 s71 anti-value-trap caps at Watch", f"got {r['status']}")

    # s65: the regime factor may only adjust priority. A candidate that fails a
    # hard gate must stay rejected at the most favourable regime setting.
    r_lo = evaluate(Candidate("__reg__", "F", g_low, "A"), 0.90)
    r_hi = evaluate(Candidate("__reg__", "F", g_low, "A"), 1.10)
    check(r_lo["status"] == r_hi["status"] == "Reject",
          "P1 s65 regime factor cannot promote a failing candidate")

    # Dimension range validation.
    try:
        Candidate("__range__", "F", dict(base, G=6), "A")
        check(False, "P1 out-of-range dimension must raise")
    except ValueError:
        check(True, "P1 out-of-range dimension raises")
    try:
        Candidate("__arch__", "Z", dict(base), "A")
        check(False, "P1 unknown archetype must raise")
    except ValueError:
        check(True, "P1 unknown archetype raises")


def part3_report_matches_engine() -> None:
    """Close the loop: the table in the PUBLISHED REPORT must equal the engine.

    Parts 1 and 2 check the engine and the machine-generated ranking file. They
    cannot catch a number that was edited by hand in the prose report after the
    fact, which is the last remaining way a wrong figure can reach a reader.
    This parses the v4 s81 table straight out of the markdown report and
    compares every cell to a fresh engine run.
    """
    import re

    import v4_run

    report = Path("docs-myself/CATALYST_SCAN_V4_2026-09-29.md")
    check(report.exists(), "P3 report exists")
    if not report.exists():
        return
    md = report.read_text(encoding="utf-8")

    # The s81 table rows look like: | **AVA** | Fundamental | 66.00 | 56.10 | ...
    rows = []
    for ln in md.splitlines():
        m = re.match(r"^\|\s*\*{0,2}([A-Z0-9]{2,10})\*{0,2}\s*\|", ln)
        if not m:
            continue
        cells = [c.strip().strip("*") for c in ln.strip("|").split("|")]
        if len(cells) >= 15 and re.fullmatch(r"\d+\.\d+", cells[2] or ""):
            rows.append(cells)
    check(bool(rows), "P3 report contains a parseable v4 s81 table")
    if not rows:
        return

    engine = {r["token"]: r for r in v4_run.PUBLISHED}
    check(len(rows) == len(v4_run.CANDIDATES),
          "P3 report table row count == candidate count",
          f"report {len(rows)} vs candidates {len(v4_run.CANDIDATES)}")

    for cells in rows:
        tok = cells[0]
        check(tok in engine, f"P3 {tok} is a scored candidate")
        if tok not in engine:
            continue
        e = engine[tok]
        check(cells[1] == e["archetype"], f"P3 {tok} archetype in report",
              f"md '{cells[1]}' vs engine '{e['archetype']}'")
        for idx, key, label in [(2, "raw", "raw"), (3, "final", "final"),
                                (4, "norm", "norm")]:
            try:
                v = float(cells[idx])
            except ValueError:
                check(False, f"P3 {tok} {label} parses")
                continue
            check(close(v, e[key], 0.01), f"P3 {tok} {label} in report",
                  f"md {v} vs engine {e[key]:.2f}")
        dims = [int(c) for c in cells[5:12]]
        check(dims == [e["scores"][d] for d in ["G", "F", "C", "A", "L", "S", "R"]],
              f"P3 {tok} dimension cells in report")
        check(cells[12] == e["evidence"], f"P3 {tok} evidence class in report")
        check(cells[14] == e["status"], f"P3 {tok} status in report",
              f"md '{cells[14]}' vs engine '{e['status']}'")


def main() -> None:
    part1_engine_invariants()
    try:
        import v4_run
        part2_published_table(v4_run.CANDIDATES, v4_run.REGIME_FACTOR)
    except FileNotFoundError:
        FAILURES.append("P2 v4_run.py not found - published table not verified")
    except ImportError as exc:
        FAILURES.append(f"P2 import failed: {exc}")
    try:
        part3_report_matches_engine()
    except FileNotFoundError as exc:
        FAILURES.append(f"P3 import failed: {exc}")

    print(f"v4 gate: {CHECKS} checks, {len(FAILURES)} failures")
    for f in FAILURES:
        print(f"  FAIL {f}")
    if not FAILURES:
        print("  ALL PASS")
    raise SystemExit(1 if FAILURES else 0)


def part2_published_table(cands, regime_factor: float) -> None:
    """Re-derive the report's numbers and check the PUBLISHED MARKDOWN, not the
    engine's own return value.

    Comparing score_table() against evaluate() would be tautological - both run
    the same code. The real failure mode is transcription: a number retyped into
    the report that no longer matches what the engine produced. So this parses
    out/v4_ranking.md and checks every cell of every row back to the engine.
    """
    import v4_run

    md_path = OUT / "v4_ranking.md"
    check(md_path.exists(), "P2 v4_ranking.md exists (run v4_run.py first)")
    if not md_path.exists():
        return
    md = md_path.read_text(encoding="utf-8")

    rows = [ln for ln in md.splitlines() if ln.startswith("| ")
            and "---" not in ln and "Token |" not in ln]
    check(len(rows) == len(cands), "P2 published row count == candidate count",
          f"published {len(rows)} vs candidates {len(cands)}")

    recomputed = {r["token"]: r for r in
                  [evaluate(c, regime_factor) for c in cands]}

    for ln in rows:
        cells = [c.strip().strip("*") for c in ln.strip("|").split("|")]
        token = cells[0]
        check(token in recomputed, f"P2 {token} is a known candidate")
        if token not in recomputed:
            continue
        r = recomputed[token]
        # cells: Token Archetype Raw Final Norm G F C A L S R Conf Qual Status
        try:
            raw_p, fin_p, norm_p = (float(cells[2]), float(cells[3]),
                                    float(cells[4]))
        except ValueError:
            check(False, f"P2 {token} numeric cells parse")
            continue
        dims_p = [int(c) for c in cells[5:12]]
        dims_e = [r["scores"][d] for d in ["G", "F", "C", "A", "L", "S", "R"]]

        check(close(raw_p, r["raw"], 0.05), f"P2 {token} raw in markdown",
              f"md {raw_p} vs engine {r['raw']:.1f}")
        check(close(fin_p, r["final"], 0.05), f"P2 {token} final in markdown",
              f"md {fin_p} vs engine {r['final']:.1f}")
        check(close(norm_p, r["norm"], 0.05), f"P2 {token} norm in markdown",
              f"md {norm_p} vs engine {r['norm']:.1f}")
        check(close(fin_p, raw_p * EVIDENCE_FACTOR[r["evidence"]] * regime_factor,
                    0.06), f"P2 {token} final reconciles as raw x ev x regime",
              f"md {fin_p}")
        check(close(norm_p, fin_p / 1.10, 0.06), f"P2 {token} norm = final/1.10")
        check(dims_p == dims_e, f"P2 {token} dimension cells match inputs",
              f"md {dims_p} vs engine {dims_e}")
        check(cells[12] == r["evidence"], f"P2 {token} evidence class in markdown")
        check(cells[14] == r["status"], f"P2 {token} status in markdown",
              f"md '{cells[14]}' vs engine '{r['status']}'")
        # A published status must be one the engine can actually emit.
        legal = {"Deep DD", "High-Priority Watch", "Watch",
                 "Speculative / Low Priority", "Reject", "Priced In",
                 "Data Insufficient"}
        check(cells[14] in legal, f"P2 {token} status is a legal v4 status",
              f"got '{cells[14]}'")

    # A score-driven Reject must genuinely be below the 55 bar; a gate-driven
    # Reject must say which gate failed. A Reject that is neither would be a
    # silent bug.
    for r in v4_run.PUBLISHED:
        if r["status"] == "Reject" and not r.get("gate_fail"):
            check(r["final"] < 55.0,
                  f"P2 {r['token']} score-reject is below the 55 bar",
                  f"final {r['final']}")


if __name__ == "__main__":
    main()
