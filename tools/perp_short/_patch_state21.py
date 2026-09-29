"""One-off: record the collector correction and the "it starts != it runs" trap.

This is the only trap in the set that produces NOTHING rather than a confident
wrong number, and that is exactly why it is the one worth writing down twice.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **⚠ THE FORWARD COLLECTOR WAS NOT RUNNING, and I REPORTED IT AS RUNNING "
    "TWICE** | **2026-09-29 — CORRECTED. Three silent config failures; now "
    "verified RUNNING by a check that distinguishes starting from running** | "
    "Correction `CORRECTION_COLLECTOR_NOT_RUNNING_2026-09-29.md`; "
    "`tools/perp_short/{build_forward_collector,verify_collector}.py`; config "
    "`user_data/config_perp_forward_dry.json`; db "
    "`user_data/forward_perp.dryrun.sqlite`. **Rounds 11 and 12 said the forward "
    "collector was 'configured, smoke-tested and running'. It was configured and "
    "smoke-tested for 100 seconds, then killed - and it COULD NOT have been "
    "running**, for three reasons that each failed silently: **(1) the config key "
    "was `database_url`; the key is `db_url` (`configuration.py:153`, "
    "`constants.py:23`), and freqtrade does not reject unknown keys - it silently "
    "falls back to the repo-root default `tradesv3.dryrun.sqlite`; (2) because "
    "of (1) it opened that STALE database, which held two simulated open trades "
    "from an earlier session, and refused to start with a warning that reads like "
    "a market condition rather than a typo; (3) `initial_state` was absent, so the "
    "bot started, created its database, printed a heartbeat EVERY 60 SECONDS - and "
    "sat in state STOPPED waiting for a `/start` RPC nobody was going to send.** "
    "**⚠ THE THIRD ONE IS THE DANGEROUS KIND, AND IT IS NEW FOR THIS REPO. Every "
    "one of the other eleven traps produced a CONFIDENT WRONG NUMBER, which "
    "means it was in principle catchable by checking against another tool. This "
    "one produced NOTHING: a long-lived process that looks healthy by every "
    "external measure - alive, heartbeating, database present, no errors - while "
    "doing nothing. `verify_collector.py` now checks the three things a start-up "
    "smoke test never would: the db file exists and is non-empty; the log contains "
    "`Changing state to: RUNNING` and its LAST state change is RUNNING; and the "
    "last heartbeat CARRIES state RUNNING rather than merely existing. Current "
    "verdict: **db 94,208 bytes, RUNNING x1, last heartbeat state RUNNING.** "
    "**RULE: for anything long-lived, 'no errors' and 'a heartbeat' are not "
    "evidence it is working. The evidence is a record IT produced that only "
    "exists if it is doing the work** - here, a closed trade with the fields the "
    "analysis needs. Until the first one lands, 'it is running' is unverified.** |"
)

CHANGE = (
    "| 2026-09-29 | **CORRECTION: THE FORWARD COLLECTOR WAS NOT RUNNING, AND I "
    "SAID IT WAS - TWICE. This is the first trap in the set that produces "
    "NOTHING instead of a confident wrong number.** "
    "`CORRECTION_COLLECTOR_NOT_RUNNING_2026-09-29.md`. In rounds 11 and 12 I "
    "reported the collector as 'smoke-tested and running'. It was smoke-tested for "
    "100 seconds and then killed, and **it could not have been running**: the "
    "config key was **`database_url` where the key is `db_url`**, and freqtrade "
    "does not reject unknown keys - it silently used the repo-root default, which "
    "held two simulated open trades from an earlier session, and refused to start "
    "with a warning that reads like a market condition. **And `initial_state` was "
    "missing, so after the above the bot started, created its database, and "
    "printed a heartbeat every 60 seconds while sitting in state STOPPED waiting "
    "for a `/start` RPC nobody would send.** ⚠ **That last one is a new failure "
    "mode for this repository. All eleven previous traps produced a confident "
    "wrong NUMBER, so a second tool could in principle catch them. This one "
    "produced nothing: a long-lived process healthy by every external measure - "
    "alive, heartbeating, database present, zero errors - while doing no work.** "
    "**So the rule is: for anything long-lived, 'no errors' and 'a heartbeat' "
    "are not evidence it is working. The evidence is a record IT produced that "
    "only exists if it is doing the work** - here a closed trade carrying the "
    "fields the 6.8-year analysis needs, and not merely a row count. "
    "`verify_collector.py` now asserts the db file, the last STATE change, and "
    "the heartbeat's own state field, and it currently reports RUNNING with a "
    "94,208-byte database. **Until the first trade closes, 'it is running' remains "
    "an unverified claim - and I had already made that claim twice.** |"
)

A = "| **⚠ THE FORWARD COLLECTOR WAS NOT RUNNING"
C = "| 2026-09-29 | **THE LAST MEASURED MECHANISM TRIED AS A FIX"


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
    lines[hdr + 2:hdr + 2] = [ROW]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted the collector correction row and change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
