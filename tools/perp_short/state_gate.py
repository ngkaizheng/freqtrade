"""GATE: is the state file in sync with the header, and does its index still resolve?

WHY THIS FILE EXISTS
--------------------
`RESEARCH_STATE.md` was truncated to zero on 2026-09-30 by line-index surgery in
a shell, and it was untracked, so ~3,400 lines of project history were lost. The
fix was to make the file GENERATED: `tools/state_index.py --build` concatenates
the hand-written `_STATE_HEADER.md` with a mechanically generated index of every
round document.

A generated file can still rot, in two specific ways this gate catches:

  1. **Someone edits `RESEARCH_STATE.md` directly.** The edit is destroyed by the
     next build, and until then the file disagrees with its own source. Rebuild
     and diff.
  2. **A document is renamed or deleted.** The index is 111 markdown links; a
     dead link reads exactly like a live one to a reader, and the whole point of
     the index is that every claim is traceable to a file.

Also checked: the header contains the index anchor, the output is plausible in
size, and there are no U+FFFD replacement characters anywhere in it.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\state_gate.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
DOCS = ROOT / "docs-myself"
HEADER = DOCS / "_STATE_HEADER.md"
STATE = DOCS / "RESEARCH_STATE.md"
BUILDER = ROOT / "tools" / "state_index.py"
ANCHOR = "<!--GENERATED-INDEX-->"
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")

MIN_LINES = 300
LINK_RE = re.compile(r"\]\(([^)\s]+\.md)\)")
# ⚠ THE EXCLUSION POLICY IS IMPORTED FROM THE BUILDER, NOT RESTATED HERE.
# It used to be a second copy of the same list, and the two had already drifted:
# this file carried `LESSONS.md`, the builder did not. The result was a check that
# printed "every document is indexed" while silently excluding one document from
# the question - 138 indexed against "137 on disk" and no alarm. The same class as
# trap 22 (a renamed path the tools did not follow): a policy kept in two places
# drifts, and a gate that consults its own copy stops checking the real thing.
from state_index import DOCS as _DOCS, INFRA  # noqa: E402

assert _DOCS == DOCS, "the builder and the gate disagree about where documents live"


def is_indexed(name: str) -> bool:
    """Exactly the builder's rule, by construction rather than by coincidence."""
    return name not in INFRA and not name.startswith("_")



def main() -> int:
    fails: list[str] = []

    for p, why in ((HEADER, "the hand-written source"),
                   (STATE, "the generated state file"),
                   (BUILDER, "the generator")):
        if not p.exists():
            print(f"FAIL  missing {p} - {why}")
            return 1

    body = HEADER.read_text(encoding="utf-8")
    if ANCHOR not in body:
        fails.append(f"{HEADER.name} has no {ANCHOR} - the index has nowhere to go, "
                     f"so --build appends it to the end and the section order breaks")

    # 1. is the generated file in sync with its source?
    before = STATE.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory():
        r = subprocess.run([PY, str(BUILDER), "--build"],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=300)
        after = STATE.read_text(encoding="utf-8")
        if r.returncode != 0:
            fails.append(f"--build exited {r.returncode}: "
                         f"{r.stdout.strip()} {r.stderr.strip()}")
        elif after != before:
            STATE.write_text(before, encoding="utf-8")   # restore; do not silently fix
            fails.append("RESEARCH_STATE.md does NOT match _STATE_HEADER.md + the "
                         "generated index. Someone edited the generated file "
                         "directly - that edit is destroyed by the next build. "
                         "Edit _STATE_HEADER.md instead. (file left as it was)")

    text = STATE.read_text(encoding="utf-8")
    n_lines = len(text.splitlines())
    if n_lines < MIN_LINES:
        fails.append(f"state file is only {n_lines} lines; expected >= {MIN_LINES}. "
                     f"Check _STATE_HEADER.md.")

    bad = text.count("\ufffd")
    if bad:
        fails.append(f"{bad} U+FFFD replacement characters in the state file - "
                     f"something was written through a non-UTF-8 console")

    # 2. does every document the index links to still exist?
    links = sorted({m for m in LINK_RE.findall(text)})
    dead = [l for l in links if not (DOCS / l).exists()]
    if dead:
        fails.append(f"{len(dead)} of {len(links)} indexed documents do not exist: "
                     + ", ".join(dead[:8]) + (" ..." if len(dead) > 8 else ""))

    # 3. and does every document on disk appear in the index?
    on_disk = {p.name for p in DOCS.glob("*.md") if is_indexed(p.name)}
    missing = sorted(on_disk - set(links))
    if missing:
        fails.append(f"{len(missing)} documents on disk are NOT indexed: "
                     + ", ".join(missing[:8]) + (" ..." if len(missing) > 8 else ""))

    print("STATE GATE: is the index trustworthy?\n")
    print(f"  state file    : {STATE.name}  {n_lines} lines, {len(text)/1024:.0f} KB")
    print(f"  hand-written  : {HEADER.name}  {len(body.splitlines())} lines")
    print(f"  documents     : {len(links)} indexed, {len(on_disk)} on disk, "
          f"{len(dead)} dead links")

    if fails:
        print()
        for f in fails:
            print(f"  FAIL  {f}")
        print("\nVERDICT: the state file cannot be trusted as an index.")
        return 1
    print("\nVERDICT: PASS - the state file is a faithful build of its source, every\n"
          "         document is indexed, and every index link resolves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
