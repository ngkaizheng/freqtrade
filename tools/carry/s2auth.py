"""Semantic Scholar AUTHOR search, patient retries.

Usage: python tools/carry/s2auth.py "<name>" ["<name>" ...]
"""
import sys
import time

import requests

S = requests.Session()
S.headers.update({"User-Agent": "research-bot"})


def author_search(q, tries=7, pause=14.0):
    url = "https://api.semanticscholar.org/graph/v1/author/search"
    r = None
    for a in range(tries):
        try:
            r = S.get(url, params={"query": q, "fields": "name,paperCount,affiliations,url"}, timeout=60)
        except Exception as e:  # noqa: BLE001
            print("   !!", type(e).__name__, e)
            time.sleep(pause)
            continue
        if r.status_code == 429:
            time.sleep(pause * (a + 1))
            continue
        break
    print("### S2 authors: " + q + "  [" + (str(None if r is None else r.status_code)) + "]")
    if r is None or r.status_code != 200:
        print("   FAIL")
        return
    for a in r.json().get("data", []):
        print(
            "  - %s | papers=%s | %s | %s"
            % (a.get("name"), a.get("paperCount"), a.get("affiliations"), a.get("url"))
        )
    print()


def author_papers(aid, n=50):
    url = (
        "https://api.semanticscholar.org/graph/v1/author/"
        + str(aid)
        + "/papers"
    )
    r = None
    for a in range(7):
        try:
            r = S.get(
                url,
                params={
                    "fields": "title,year,venue,citationCount,externalIds,publicationTypes,openAccessPdf,abstract",
                    "limit": n,
                },
                timeout=60,
            )
        except Exception as e:  # noqa: BLE001
            print("   !!", type(e).__name__, e)
            time.sleep(14)
            continue
        if r.status_code == 429:
            time.sleep(14 * (a + 1))
            continue
        break
    print("### S2 author papers: " + str(aid) + "  [" + (str(None if r is None else r.status_code)) + "]")
    if r is None or r.status_code != 200:
        print("   FAIL")
        return
    for p in r.json().get("data", []):
        oa = p.get("openAccessPdf") or {}
        print("- [%s] %s" % (p.get("year"), p.get("title")))
        print(
            "    venue=%s | types=%s | c=%s | ext=%s"
            % (p.get("venue"), p.get("publicationTypes"), p.get("citationCount"), p.get("externalIds"))
        )
        print("    pdf=%s" % oa.get("url"))
        if p.get("abstract"):
            print("    ABS: " + p["abstract"][:800])
        print()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--id":
        author_papers(args[1])
    else:
        for q in args:
            author_search(q)
            time.sleep(6)
