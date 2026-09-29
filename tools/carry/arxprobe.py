"""arXiv query probe (reads query specs from a file or argv, one per line).

Query syntax uses  DQUOTE  for a literal double quote and  PLUS  for a literal
plus, so the shell never has to quote anything.

Usage: python tools/carry/arxprobe.py file.txt
"""
import pathlib
import sys
import time
from urllib.parse import quote, unquote

import requests
import xml.etree.ElementTree as ET

NS = {"a": "http://www.w3.org/2005/Atom"}
S = requests.Session()
S.headers.update({"User-Agent": "research-bot (mailto:research@example.com)"})


def enc(sq: str) -> str:
    s = sq.replace("DQUOTE", '"').replace("SQUOTE", "'").replace("PLUS", "+")
    s = quote(s, safe=":()+\"")
    return s


def search(sq, n=30, brief=False, sort="relevance"):
    url = (
        "https://export.arxiv.org/api/query?search_query="
        + enc(sq)
        + f"&max_results={n}&sortBy={sort}&sortOrder=descending"
    )
    r = None
    for a in range(5):
        try:
            r = S.get(url, timeout=60)
        except Exception as e:  # noqa: BLE001
            print("   !!", type(e).__name__, e)
            time.sleep(4)
            continue
        if r.status_code in (429, 500, 502, 503):
            time.sleep(6)
            continue
        break
    print("##### ARXIV: %s  [%s]" % (sq, None if r is None else r.status_code))
    if r is None or r.status_code != 200:
        print("   FAILED", None if r is None else r.text[:200])
        print()
        return
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        print("   parse error", e)
        print()
        return
    ents = root.findall("a:entry", NS)
    tot = root.find("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
    print("   n=%s total=%s" % (len(ents), None if tot is None else tot.text))
    for e in ents:
        title = " ".join(e.findtext("a:title", "", NS).split())
        pub = e.findtext("a:published", "", NS)[:10]
        aid = e.findtext("a:id", "", NS)
        summ = " ".join(e.findtext("a:summary", "", NS).split())
        auths = [a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)]
        jr = e.findtext("{http://arxiv.org/schemas/atom}journal_ref", "", NS)
        doi = e.findtext("{http://arxiv.org/schemas/atom}doi", "", NS)
        print("- [%s] %s" % (pub, title))
        print("    id=%s | journal_ref=%s | doi=%s" % (aid, jr, doi))
        print("    au=%s" % (auths[:8],))
        if not brief:
            print("    ABS: %s" % summ[:900])
        print()
    print()
    time.sleep(3.0)


if __name__ == "__main__":
    for src in sys.argv[1:]:
        p = pathlib.Path(src)
        if p.exists():
            lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        else:
            lines = [src]
        for ln in lines:
            if ln.startswith("#"):
                continue
            search(ln)
