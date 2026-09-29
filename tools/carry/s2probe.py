"""Semantic Scholar search with 429 backoff.

Usage: python tools/carry/s2probe.py "query" ["query" ...] [--n=10]
"""
import json
import sys
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "research-bot"})


def s2(q, n=10, tries=6, pause=9.0):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": q,
        "fields": (
            "title,year,venue,citationCount,externalIds,abstract,authors,"
            "publicationTypes,publicationVenue,openAccessPdf,isOpenAccess"
        ),
        "limit": n,
    }
    r = None
    for a in range(tries):
        try:
            r = S.get(url, params=params, timeout=60)
        except Exception as e:  # noqa: BLE001
            print(f"   !! {type(e).__name__}: {e}")
            time.sleep(pause * (a + 1))
            continue
        if r.status_code == 429:
            time.sleep(pause * (a + 1))
            continue
        break
    print(f"##### S2: {q}")
    if r is None or r.status_code != 200:
        print("   FAILED", None if r is None else (r.status_code, r.text[:200]))
        print()
        return
    d = r.json()
    print("   total=", d.get("total"))
    for p in d.get("data", []):
        oa = p.get("openAccessPdf") or {}
        print(f"- [{p.get('year')}] {p.get('title')}")
        print(f"    venue={p.get('venue')} | pubVenue={((p.get('publicationVenue') or {}).get('name'))}"
              f" | type={p.get('publicationTypes')} | c={p.get('citationCount')}")
        print(f"    extIds={p.get('externalIds')}")
        print(f"    au={[a['name'] for a in (p.get('authors') or [])][:8]}")
        print(f"    pdf={oa.get('url')}")
        ab = p.get("abstract")
        if ab:
            print(f"    ABS: {ab[:1400]}")
        print()
    print()
    time.sleep(4.0)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = 10
    for a in sys.argv[1:]:
        if a.startswith("--n="):
            n = int(a.split("=", 1)[1])
    for q in args:
        s2(q, n)
