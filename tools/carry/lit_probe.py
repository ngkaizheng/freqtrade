"""Robust OpenAlex / Crossref probing with TLS retry.

Usage:
  python tools/carry/lit_probe.py oa-title "<exact-ish title>" [<n>]
  python tools/carry/lit_probe.py oa-auth "<name>" [<n>]
  python tools/carry/lit_probe.py oa-search "<query>" [<n>]
  python tools/carry/lit_probe.py oa-raw "<filter or search expr>"   # e.g. "filter=authorships.author.id:W123"
  python tools/carry/lit_probe.py cr "<query>" [<rows>]
"""
import sys
import time
from urllib.parse import quote

import requests

UA = {"User-Agent": "research-bot (mailto:research@example.com)"}
S = requests.Session()
S.headers.update(UA)


def get(url, params=None, tries=6, pause=3.0, timeout=60):
    for a in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            print(f"   !! {type(e).__name__}: {e}")
            time.sleep(pause * (a + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"   !! http {r.status_code}, backing off")
            time.sleep(pause * (a + 1))
            continue
        return r
    return None


def show_works(items, n=None):
    for w in (items[:n] if n else items):
        loc = (w.get("primary_location") or {}).get("source") or {}
        au = ", ".join(
            a.get("author", {}).get("display_name", "?") for a in (w.get("authorships") or [])[:8]
        )
        ids = w.get("ids") or {}
        print(f"- [{w.get('publication_year')}] {w.get('title')}")
        print(f"    au: {au}")
        print(f"    src={loc.get('display_name')} | {w.get('type')} | c={w.get('cited_by_count')}")
        print(f"    doi={w.get('doi')} | pmid={ids.get('pmid')} | openalex={w.get('id','').rsplit('/',1)[-1]}")
        print(f"    oa_url={(w.get('open_access') or {}).get('oa_url')}")
        print(f"    pdf={((w.get('best_oa_location') or {}).get('pdf_url'))}")
        ab = w.get("abstract_inverted_index")
        if ab:
            try:
                pos = {}
                for word, idxs in ab.items():
                    for i in idxs:
                        pos[i] = word
                txt = " ".join(pos[i] for i in sorted(pos))
                print(f"    ABS: {txt[:900]}")
            except Exception:  # noqa: BLE001
                pass
        print()


def oa_works(params, n=None):
    params = dict(params)
    params["mailto"] = "research@example.com"
    r = get("https://api.openalex.org/works", params=params)
    if r is None or r.status_code != 200:
        print("   FAILED", None if r is None else (r.status_code, r.text[:200]))
        return
    d = r.json()
    print(f"   count={d.get('meta',{}).get('count')}")
    show_works(d.get("results", []), n)


def cr(q, rows=6):
    r = get(
        "https://api.crossref.org/works",
        params={"query.bibliographic": q, "rows": rows, "mailto": "research@example.com"},
        pause=6.0,
    )
    print(f"##### CR: {q}")
    if r is None or r.status_code != 200:
        print("   FAILED", None if r is None else (r.status_code, r.text[:200]))
        return
    for it in r.json().get("message", {}).get("items", []):
        ttl = " ".join(it.get("title") or [])
        cont = it.get("container-title") or []
        yr = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        au = ", ".join(
            f"{a.get('given','')} {a.get('family','')}".strip() for a in (it.get("author") or [])[:8]
        )
        print(f"- [{yr}] {ttl}")
        print(f"    au: {au}")
        print(f"    cont={cont} | type={it.get('type')} | publisher={it.get('publisher')}")
        print(f"    doi={it.get('DOI')} | url={it.get('URL')}")
    print()


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "oa-title":
        for t in sys.argv[2:]:
            print(f"##### OA title.search: {t}")
            oa_works({"filter": f"title.search:{t}", "per-page": 6}, 6)
            time.sleep(0.4)
    elif mode == "oa-search":
        for q in sys.argv[2:]:
            print(f"##### OA search: {q}")
            oa_works({"search": q, "per-page": 8}, 8)
            time.sleep(0.4)
    elif mode == "oa-auth":
        for nm in sys.argv[2:]:
            r = get(
                "https://api.openalex.org/authors",
                params={"search": nm, "per-page": 6, "mailto": "research@example.com"},
            )
            print(f"##### OA authors: {nm}  {None if r is None else r.status_code}")
            if r is None or r.status_code != 200:
                continue
            for a in r.json().get("results", []):
                inst = [i.get("display_name") for i in (a.get("last_known_institutions") or [])]
                print(f"  - {a['display_name']} | {a['id'].rsplit('/',1)[-1]} | works={a.get('works_count')} | {inst}")
            time.sleep(0.4)
    elif mode == "oa-raw":
        # args: "<param>:<value>" pairs
        params = {}
        for kv in sys.argv[2:]:
            k, v = kv.split("=", 1)
            params[k] = v
        params.setdefault("per-page", "10")
        oa_works(params, int(params["per-page"]))
    elif mode == "cr":
        for q in sys.argv[2:]:
            cr(q)
            time.sleep(2.0)
