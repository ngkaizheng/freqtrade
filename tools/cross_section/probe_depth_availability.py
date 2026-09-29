"""Probe Binance Vision bookDepth availability WITHOUT the throttling artefact.

WHY THIS FILE EXISTS. A first attempt at this probe fired ~130 sequential HEAD
requests against S3 and reported bookDepth as "absent for every symbol and
date" — including 2026-09-20, which returns 200 on a single request. S3 rate-limits
aggressive clients, and a throttled HEAD is indistinguishable from a 404 unless
you control for it. A single false negative is enough to invent a data boundary
that does not exist.

THE RULE THIS ENCODES. **An availability scan must carry a positive control and
must retry.** A date is only "absent" if, in the same session, a known-present
probe succeeded and the absent-probe returned a clean 404 more than once.

Usage:
    .venv\\Scripts\\python.exe tools\\cross_section\\probe_depth_availability.py
"""

from __future__ import annotations

import sys
import time

import requests

V = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/data/futures/um/daily/bookDepth"
DELAY = 1.2          # seconds between probes; S3 tolerates this comfortably
RETRIES = 3


def probe(symbol: str, date: str) -> tuple[str, int | None]:
    """Return ('present'|'absent'|'unknown', http_status).

    'unknown' means every attempt failed in a way that is not a clean 404, which
    is what throttling looks like. Only 'absent' is allowed to become evidence.

    A 404 is NOT trusted on first sight. S3 answers 404 NoSuchKey under client
    throttling as well as for genuinely missing keys, and an earlier version of
    this probe reported every cell as absent — including a URL it had itself
    confirmed present at the top of the same run. So absence must be confirmed
    by two independent 404s separated by a delay before it is recorded.
    """
    url = f"{V}/{symbol}/{symbol}-bookDepth-{date}.zip"
    consecutive_404 = 0
    last: int | None = None
    for attempt in range(RETRIES):
        try:
            r = requests.head(url, timeout=45)
            last = r.status_code
            if r.status_code == 200:
                return "present", 200
            if r.status_code == 404:
                consecutive_404 += 1
                if consecutive_404 >= 2:
                    return "absent", 404
            else:
                # 403 / 429 / 5xx are rate limiting, not absence
                consecutive_404 = 0
        except requests.RequestException:
            consecutive_404 = 0
        time.sleep(DELAY * (attempt + 2))
    return "unknown", last


def main() -> int:
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "LINKUSDT"]
    # Straddle the suspected boundary, plus two stress dates.
    dates = ["2020-03-12", "2022-11-08", "2022-12-31", "2023-01-01",
             "2023-06-15", "2024-08-05", "2025-10-10", "2026-09-20"]

    print("=" * 78)
    print("bookDepth availability, with a positive control on every run")
    print("=" * 78)

    ctrl_state, ctrl_code = probe("BTCUSDT", "2026-09-20")
    print(f"CONTROL  BTCUSDT 2026-09-20 -> {ctrl_state} ({ctrl_code})")
    if ctrl_state != "present":
        print("\nCONTROL FAILED. S3 is rate-limiting or unreachable from here.\n"
              "No absence reported in this run may be believed.\n")
        return 2
    print("control passed; absence results below are meaningful\n")

    print(f"{'symbol':<11}" + "".join(f"{d[2:]:>11}" for d in dates))
    grid: dict[tuple[str, str], str] = {}
    for s in symbols:
        cells = []
        for d in dates:
            state, _ = probe(s, d)
            grid[(s, d)] = state
            # NB: state is a STRING. An earlier version of this line compared it
            # with `is True`, which is never true for a str, so "present" and
            # "absent" both rendered as '-' and the grid looked uniformly absent
            # while the control reported present. The assertion below now fails
            # the run instead of drawing that conclusion.
            mark = {"present": "Y", "absent": "-", "unknown": "?"}[state]
            cells.append(mark)
            time.sleep(DELAY)
        print(f"{s:<11}" + "".join(f"{c:>11}" for c in cells))

    # Self-consistency: the grid cell for the control URL must agree with the
    # control probe. If these ever disagree, the grid is lying about something.
    if grid[("BTCUSDT", "2026-09-20")] != "present":
        print(f"\nINCONSISTENT: control says BTCUSDT 2026-09-20 is present but the "
              f"grid recorded {grid[('BTCUSDT', '2026-09-20')]!r}. Do not read this grid.")
        return 2
    if not any(v == "present" for v in grid.values()):
        print("\nINCONSISTENT: the grid contains no 'Y' at all while the control "
              "passed. The renderer or the probe is broken.")
        return 2
    print("\nself-consistency OK: control cell and control probe agree.")

    print("\nlegend: Y present   - absent (2x confirmed 404)   ? unknown (throttled/failed)")

    # The control is re-checked at the END. If it now fails, every '-' above is
    # void, because it means the session degraded mid-run and the absences are
    # indistinguishable from the throttling that produced them.
    post_state, post_code = probe("BTCUSDT", "2026-09-20")
    print(f"\nCONTROL RE-CHECK BTCUSDT 2026-09-20 -> {post_state} ({post_code})")
    if post_state != "present":
        print("CONTROL DEGRADED MID-RUN. The '-' cells above are NOT evidence of "
              "absence; re-run with a longer DELAY.")
        return 2
    print("control held for the whole run; the '-' cells are real absences.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
