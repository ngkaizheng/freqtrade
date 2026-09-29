"""arXiv API search helper.

Usage: python tools/carry/arxiv.py "au:Shamshuddeen" ["all:funding rate AND all:crypto"]
"""
import sys
import time
from urllib.parse import quote
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "research-bot (mailto:research@example.com)"}
NS = {"a": "http://www.w3.org/2005/Atom"}


def search(sq, n=40, brief=False):
    q = quote(sq).replace("%20", "+").replace("%3A", ":").replace("%22", "%22")
    url = (
        "https://export.arxiv.org/api/query?search_query="
        + q
        + f"&max_results={n}&sortBy=submittedDate&sortOrder=descending"
    )
    try:
        r = requests.get(url, headers=UA, timeout=45)
    except Exception as e:  # noqa: BLE001
        print(f"!! {sq}: {e}")
        return
    print(f"##### ARXIV: {sq} [{r.status_code}]")
    if r.status_code != 200:
        print(r.text[:300])
        print()
        return
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        print(f"   parse error {e}")
        print(r.text[:400])
        print()
        return
    ents = root.findall("a:entry", NS)
    print(f"   n={len(ents)}  raw='{r.text[:0]}'")
    for e in ents:
        title = " ".join((e.findtext("a:title", "", NS)).split())
        pub = e.findtext("a:published", "", NS)[:10]
        aid = e.findtext("a:id", "", NS)
        summ = " ".join((e.findtext("a:summary", "", NS)).split())
        auths = [a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)]
        print(f"- [{pub}] {title}  | {aid} | au={auths[:7]}")
        if not brief:
            print(f"    ABS: {summ[:700]}")
    print()
    time.sleep(3.0)


if __name__ == "__main__":
    brief = "--brief" in sys.argv
    for q in [a for a in sys.argv[1:] if not a.startswith("--")]:
        search(q, brief=brief)
