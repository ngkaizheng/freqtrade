"""Crossref probes with param dicts.

Usage: python tools/carry/crprobe.py "<json params list>"
"""
import json
import sys
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "research-bot (mailto:research@example.com)"})


def cr(params, rows=8, tries=5, pause=7.0):
    p = dict(params)
    p["rows"] = rows
    p["mailto"] = "research@example.com"
    r = None
    for a in range(tries):
        try:
            r = S.get("https://api.crossref.org/works", params=p, timeout=60)
        except Exception as e:  # noqa: BLE001
            print("   !!", e)
            time.sleep(pause)
            continue
        if r.status_code in (429, 500, 502, 503):
            print("   !!", r.status_code)
            time.sleep(pause * (a + 1))
            continue
        break
    print("###", json.dumps(params, ensure_ascii=False))
    if r is None or r.status_code != 200:
        print("   FAIL", None if r is None else (r.status_code, r.text[:150]))
        print()
        return
    for it in r.json()["message"]["items"]:
        ttl = " ".join(it.get("title") or [])
        cont = it.get("container-title") or []
        yr = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        au = ", ".join(
            (a.get("given", "") + " " + a.get("family", "")).strip()
            for a in (it.get("author") or [])[:6]
        )
        doi = it.get("DOI")
        print("- [%s] %s" % (yr, ttl))
        print("    au: " + au)
        print("    cont=%s | type=%s | doi=%s" % (cont, it.get("type"), doi))
    print()


if __name__ == "__main__":
    for spec in sys.argv[1:]:
        # spec format:  key=value~key=value
        params = {}
        for kv in spec.split("~"):
            if not kv:
                continue
            k, v = kv.split("=", 1)
            params[k] = v
        cr(params)
        time.sleep(2.5)
