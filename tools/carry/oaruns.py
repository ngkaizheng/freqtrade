"""Run a list of OpenAlex / Crossref / arXiv probes from a spec file, paced.

Spec file lines (blank / '#' lines ignored):
  oa-t   <filter-or-search>       -> works?filter=title_and_abstract.search:<x>
  oa-s   <query>                  -> works?search=<q>
  oa-a   <name>                   -> authors?search=<name>
  cr     <key>=<val>~<key>=<val>  -> crossref works
  s2     <query>                  -> semanticscholar paper search
"""
import json
import sys
import time
from urllib.parse import quote

import requests

S = requests.Session()
S.headers.update({"User-Agent": "research-bot (mailto:research@example.com)"})


def get(url, params, tries=5, pause=12.0):
    for a in range(tries):
        try:
            r = S.get(url, params=params, timeout=60)
        except Exception as e:  # noqa: BLE001
            print("   !!", type(e).__name__, e)
            time.sleep(pause * (a + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            print("   !! http", r.status_code)
            time.sleep(pause * (a + 1))
            continue
        return r
    return None


def show(items):
    for w in items:
        loc = (w.get("primary_location") or {}).get("source") or {}
        au = ", ".join(
            a.get("author", {}).get("display_name", "?") for a in (w.get("authorships") or [])[:8]
        )
        print("- [%s] %s" % (w.get("publication_year"), w.get("title")))
        print("    au: " + au)
        print(
            "    src=%s | %s | c=%s | doi=%s | oa=%s"
            % (
                loc.get("display_name"),
                w.get("type"),
                w.get("cited_by_count"),
                w.get("doi"),
                (w.get("open_access") or {}).get("oa_url"),
            )
        )
        ab = w.get("abstract_inverted_index")
        if ab:
            pos = {}
            for word, idxs in ab.items():
                for i in idxs:
                    pos[i] = word
            print("    ABS: " + " ".join(pos[i] for i in sorted(pos))[:700])
        print()


def main(path):
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        kind, _, arg = line.partition(" ")
        arg = arg.strip()
        if kind == "oa-t":
            print("### OA title_and_abstract.search: " + arg)
            r = get(
                "https://api.openalex.org/works",
                {
                    "filter": "title_and_abstract.search:" + arg,
                    "per-page": 8,
                    "mailto": "research@example.com",
                },
            )
            if r is not None and r.status_code == 200:
                print("   count=", r.json()["meta"]["count"])
                show(r.json().get("results", []))
            else:
                print("   FAIL", None if r is None else r.status_code)
            print()
        elif kind == "oa-s":
            print("### OA search: " + arg)
            r = get(
                "https://api.openalex.org/works",
                {"search": arg, "per-page": 8, "mailto": "research@example.com"},
            )
            if r is not None and r.status_code == 200:
                print("   count=", r.json()["meta"]["count"])
                show(r.json().get("results", []))
            else:
                print("   FAIL", None if r is None else r.status_code)
            print()
        elif kind == "oa-a":
            print("### OA authors: " + arg)
            r = get(
                "https://api.openalex.org/authors",
                {"search": arg, "per-page": 8, "mailto": "research@example.com"},
            )
            if r is not None and r.status_code == 200:
                for a in r.json().get("results", []):
                    inst = [i.get("display_name") for i in (a.get("last_known_institutions") or [])]
                    print(
                        "  - %s | %s | works=%s | %s"
                        % (a["display_name"], a["id"].rsplit("/", 1)[-1], a.get("works_count"), inst)
                    )
            else:
                print("   FAIL", None if r is None else r.status_code)
            print()
        elif kind == "oa-raw":
            print("### OA raw: " + arg)
            params = {}
            for kv in arg.split("~"):
                if kv:
                    k, v = kv.split("=", 1)
                    params[k] = v
            params.setdefault("per-page", "8")
            params.setdefault("mailto", "research@example.com")
            r = get("https://api.openalex.org/works", params)
            if r is not None and r.status_code == 200:
                print("   count=", r.json()["meta"]["count"])
                show(r.json().get("results", []))
            else:
                print("   FAIL", None if r is None else (r.status_code, r.text[:200]))
            print()
        elif kind == "cr":
            print("### CR: " + arg)
            params = {}
            for kv in arg.split("~"):
                if kv:
                    k, v = kv.split("=", 1)
                    params[k] = v
            params.setdefault("rows", "8")
            params["mailto"] = "research@example.com"
            r = get("https://api.crossref.org/works", params)
            if r is not None and r.status_code == 200:
                for it in r.json()["message"]["items"]:
                    ttl = " ".join(it.get("title") or [])
                    au = ", ".join(
                        (a.get("given", "") + " " + a.get("family", "")).strip()
                        for a in (it.get("author") or [])[:6]
                    )
                    yr = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
                    print("- [%s] %s" % (yr, ttl))
                    print("    au: " + au)
                    print("    cont=%s | doi=%s" % (it.get("container-title"), it.get("DOI")))
                print()
            else:
                print("   FAIL", None if r is None else (r.status_code, r.text[:200]))
            print()
        elif kind == "s2":
            print("### S2: " + arg)
            r = get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                {
                    "query": arg,
                    "fields": "title,year,venue,citationCount,externalIds,abstract,authors,publicationTypes,openAccessPdf",
                    "limit": 8,
                },
                tries=6,
                pause=15.0,
            )
            if r is not None and r.status_code == 200:
                d = r.json()
                print("   total=", d.get("total"))
                for p in d.get("data", []):
                    oa = p.get("openAccessPdf") or {}
                    print("- [%s] %s" % (p.get("year"), p.get("title")))
                    print("    venue=%s | types=%s | c=%s" % (p.get("venue"), p.get("publicationTypes"), p.get("citationCount")))
                    print("    extIds=%s" % p.get("externalIds"))
                    print("    au=%s" % [a["name"] for a in (p.get("authors") or [])][:8])
                    print("    pdf=%s" % oa.get("url"))
                    if p.get("abstract"):
                        print("    ABS: " + p["abstract"][:1000])
                    print()
            else:
                print("   FAIL", None if r is None else (r.status_code, r.text[:160]))
            print()
        time.sleep(3.0)


if __name__ == "__main__":
    main(sys.argv[1])
