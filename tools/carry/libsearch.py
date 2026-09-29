"""Robust multi-API bibliographic search with retries/backoff.

Usage:  python tools/carry/libsearch.py oa|cr|s2 "query" ["query" ...]
"""
import json
import sys
import time
from urllib.parse import quote

import requests

UA = {"User-Agent": "research-bot (mailto:research@example.com)"}
SEMI = {"User-Agent": "research-bot", "x-api-key": ""}


def _get(url, headers=UA, tries=5, pause=4.0):
    for a in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=45)
        except Exception as e:  # noqa: BLE001
            print(f"   !! {e}")
            time.sleep(pause * (a + 1))
            continue
        if r.status_code in (429, 500, 502, 503):
            time.sleep(pause * (a + 1))
            continue
        return r
    return None


def oa(q, n=8):
    url = (
        "https://api.openalex.org/works?search="
        + quote(q)
        + f"&per-page={n}&mailto=research@example.com"
    )
    r = _get(url)
    print(f"##### OA: {q}")
    if r is None or r.status_code != 200:
        print("   FAILED", None if r is None else r.status_code)
        print()
        return
    for w in r.json().get("results", []):
        loc = (w.get("primary_location") or {}).get("source") or {}
        auth = ", ".join(
            a.get("author", {}).get("display_name", "?") for a in (w.get("authorships") or [])[:6]
        )
        print(
            f"- [{w.get('publication_year')}] {w.get('title')}\n"
            f"    au: {auth}\n"
            f"    src={loc.get('display_name')} | {w.get('type')} | c={w.get('cited_by_count')}"
            f" | doi={w.get('doi')}\n"
            f"    oa={(w.get('open_access') or {}).get('oa_url')}"
            f" | pdf={((w.get('best_oa_location') or {}).get('pdf_url'))}"
        )
    print()
    time.sleep(0.5)


def cr(q, n=8):
    url = (
        "https://api.crossref.org/works?query="
        + quote(q)
        + f"&rows={n}&mailto=research@example.com"
    )
    r = _get(url, pause=6.0)
    print(f"##### CR: {q}")
    if r is None or r.status_code != 200:
        print("   FAILED", None if r is None else r.status_code)
        print()
        return
    for it in r.json().get("message", {}).get("items", []):
        ttl = " ".join(it.get("title") or [])
        cont = it.get("container-title") or []
        yr = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        print(f"- [{yr}] {ttl} | {cont} | {it.get('type')} | doi={it.get('DOI')}")
    print()
    time.sleep(3.0)


def s2(q, n=10):
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/search?query="
        + quote(q)
        + "&fields=title,year,venue,citationCount,externalIds,abstract,authors,publicationTypes,openAccessPdf"
        + f"&limit={n}"
    )
    r = _get(url, pause=8.0, tries=6)
    print(f"##### S2: {q}")
    if r is None or r.status_code != 200:
        print("   FAILED", None if r is None else r.status_code)
        print()
        return
    d = r.json()
    print(f"   total={d.get('total')}")
    for p in d.get("data", []):
        oa = p.get("openAccessPdf") or {}
        print(
            f"- [{p.get('year')}] {p.get('title')} | venue={p.get('venue')} "
            f"| c={p.get('citationCount')} | {p.get('externalIds')}"
            f"\n    types={p.get('publicationTypes')}"
            f"\n    au={[a['name'] for a in (p.get('authors') or [])][:6]}"
            f"\n    pdf={oa.get('url')}"
        )
        ab = p.get("abstract")
        if ab:
            print(f"    ABS: {ab[:1100]}")
    print()
    time.sleep(4.0)


if __name__ == "__main__":
    mode = sys.argv[1]
    fn = {"oa": oa, "cr": cr, "s2": s2}[mode]
    for q in sys.argv[2:]:
        fn(q)
