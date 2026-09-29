"""Verify the CTREND citation against Crossref / OpenAlex metadata.

The adversarial review's most load-bearing claim is a JFQA 2025 paper. Web
search credits were exhausted, so this checks bibliographic metadata directly
against the registries. Metadata confirms the paper exists and says what its
title, authors and abstract claim; it does NOT independently reproduce the
t-statistics, so anything numeric taken from the abstract stays second-hand
until the full text is read.
"""

import json
import urllib.request

UA = {"User-Agent": "freqtrade-verify/1.0 (mailto:noreply@example.com)"}
DOI = "10.1017/S0022109024000747"


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
        return json.loads(r.read())


print("=" * 72)
print("CROSSREF")
print("=" * 72)
try:
    m = get(f"https://api.crossref.org/works/{DOI}")["message"]
    print("DOI     :", m.get("DOI"))
    print("title   :", (m.get("title") or ["?"])[0])
    print("journal :", (m.get("container-title") or ["?"])[0],
          m.get("volume"), m.get("issue"), m.get("page"))
    print("issued  :", m.get("issued", {}).get("date-parts"))
    print("authors :", [f"{a.get('given','')} {a.get('family','')}".strip()
                        for a in m.get("author", [])])
    print("refs    :", m.get("reference-count"))
    ab = m.get("abstract") or ""
    if ab:
        print("abstract:", ab[:1800])
    else:
        print("abstract: (not supplied by Crossref -- full text needed for the numbers)")
except Exception as exc:
    print("FAILED:", type(exc).__name__, exc)

print()
print("=" * 72)
print("OPENALEX  (citation counts / publication status)")
print("=" * 72)
try:
    w = get(f"https://api.openalex.org/works/doi:{DOI}")
    print("title            :", w.get("title"))
    print("cited_by_count   :", w.get("cited_by_count"))
    print("is_published     :", w.get("is_published"))
    print("referenced_works :", w.get("referenced_works_count"))
    print("type             :", w.get("type"))
    loc = (w.get("primary_location") or {}).get("source") or {}
    print("source           :", loc.get("display_name"))
    oa = w.get("open_access") or {}
    print("open access      :", oa.get("oa_status"), oa.get("oa_url"))
    print("year             :", w.get("publication_year"))
except Exception as exc:
    print("FAILED:", type(exc).__name__, exc)
