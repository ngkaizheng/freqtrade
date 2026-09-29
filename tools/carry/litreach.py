"""Small helper for literature/doc retrieval. Prints raw payloads; no parsing opinions."""
import json
import sys
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}


def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=kw.pop("timeout", 30), **kw)
    return r


def show(label, url, **kw):
    try:
        r = get(url, **kw)
        print(f"===== {label} [{r.status_code}] {url}")
        t = r.text
        print(t[:kw.pop("limit_chars", 12000)] if isinstance(t, str) else t)
    except Exception as e:  # noqa: BLE001
        print(f"===== {label} FAILED {url}: {e}")
    print()


def s2(query, limit=20, year=None, fields=None):
    fields = fields or "title,year,venue,citationCount,externalIds,abstract,authors,publicationTypes,openAccessPdf"
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/search?query="
        + requests.utils.quote(query)
        + f"&fields={fields}&limit={limit}"
    )
    if year:
        url += f"&year={year}"
    for attempt in range(6):
        r = get(url)
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:  # noqa: BLE001
                print(r.text[:500])
                return
            print(f"===== S2: {query}  (total={data.get('total')})")
            for p in data.get("data", []):
                ext = p.get("externalIds") or {}
                print(
                    f"- [{p.get('year')}] {p.get('title')} | venue={p.get('venue')} "
                    f"| cites={p.get('citationCount')} | ids={ext} "
                    f"| types={p.get('publicationTypes')}"
                )
                print(f"    authors={[a['name'] for a in (p.get('authors') or [])][:6]}")
                oa = p.get("openAccessPdf") or {}
                if oa.get("url"):
                    print(f"    pdf={oa['url']}")
                ab = p.get("abstract")
                if ab:
                    print(f"    ABS: {ab[:1400]}")
            print()
            return
        time.sleep(3 * (attempt + 1))
    print(f"===== S2: {query} FAILED {r.status_code} {r.text[:200]}\n")


def oa(query, per_page=25, extra=""):
    url = (
        "https://api.openalex.org/works?search="
        + requests.utils.quote(query)
        + f"&per-page={per_page}&mailto=research@example.com{extra}"
    )
    r = get(url)
    print(f"===== OPENALEX: {query} [{r.status_code}]")
    if r.status_code != 200:
        print(r.text[:400], "\n")
        return
    data = r.json()
    print(f"count={data.get('meta', {}).get('count')}")
    for w in data.get("results", []):
        loc = (w.get("primary_location") or {}).get("source") or {}
        print(
            f"- [{w.get('publication_year')}] {w.get('title')} | {loc.get('display_name')} "
            f"| type={w.get('type')} | cites={w.get('cited_by_count')} | doi={w.get('doi')} "
            f"| oa={(w.get('open_access') or {}).get('oa_url')}"
        )
    print()


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "s2":
        s2(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 20)
    elif cmd == "oa":
        oa(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 25)
    elif cmd == "get":
        show(sys.argv[2], sys.argv[3])
