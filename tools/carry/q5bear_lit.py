"""arXiv search for the bear case on crypto perp funding carry. Prints id/title/date/summary."""
import sys
import time
import re
import xml.etree.ElementTree as ET

import requests

NS = {"a": "http://www.w3.org/2005/Atom"}
UA = {"User-Agent": "research/1.0 (mailto:research@example.com)"}


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def search(q, n=12):
    url = ("https://export.arxiv.org/api/query?search_query=" + requests.utils.quote(q)
           + f"&start=0&max_results={n}&sortBy=relevance&sortOrder=descending")
    r = requests.get(url, headers=UA, timeout=40)
    root = ET.fromstring(r.text)
    out = []
    for e in root.findall("a:entry", NS):
        out.append({
            "id": e.find("a:id", NS).text,
            "title": clean(e.find("a:title", NS).text),
            "pub": clean(e.find("a:published", NS).text)[:10],
            "summ": clean(e.find("a:summary", NS).text),
        })
    return out


if __name__ == "__main__":
    for q in sys.argv[1:]:
        print("=" * 100)
        print("QUERY:", q)
        try:
            for r in search(q):
                print("-" * 90)
                print(r["id"], "|", r["pub"], "|", r["title"])
                print("   ", r["summ"][:700])
        except Exception as e:  # noqa: BLE001
            print("  ERR", e)
        time.sleep(3.5)
