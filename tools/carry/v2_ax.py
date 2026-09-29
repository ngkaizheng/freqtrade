import requests, re, time, sys, json
import xml.etree.ElementTree as ET
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
E = "research@example.com"
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

def arxiv(sq, mx=25):
    # spaces -> '+', phrases quoted
    q = sq.replace('"', '%22').replace(' ', '+')
    u = f"https://export.arxiv.org/api/query?search_query={q}&max_results={mx}&sortBy=relevance"
    r = requests.get(u, headers=UA, timeout=90)
    root = ET.fromstring(r.text)
    out = []
    for e in root.findall("a:entry", NS):
        out.append({
            "id": e.findtext("a:id", "", NS).split("/abs/")[-1],
            "title": " ".join(e.findtext("a:title", "", NS).split()),
            "pub": e.findtext("a:published", "", NS)[:10],
            "upd": e.findtext("a:updated", "", NS)[:10],
            "authors": "; ".join(a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)),
            "abs": " ".join(e.findtext("a:summary", "", NS).split()),
            "comment": " ".join((e.findtext("arxiv:comment", "", NS) or "").split()),
            "doi": e.findtext("arxiv:doi", "", NS),
        })
    tot = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults", "?")
    return tot, out

def show(sq, mx=25, brief=False):
    tot, res = arxiv(sq, mx)
    print(f"\n=== arXiv [{sq}]  total={tot} returned={len(res)}")
    for w in res:
        print(f"  * {w['id']:16s} [{w['pub']}] {w['title']}")
        print(f"      {w['authors'][:130]}")
        if w['comment']: print(f"      COMMENT: {w['comment'][:200]}")
        if w['doi']:      print(f"      DOI: {w['doi']}")
        if not brief:     print(f"      {w['abs'][:700]}")
    time.sleep(3)
    return res

print("#" * 72)
print("# ITEM 2 -- Streltsov & Ruan")
print("#" * 72)
show('au:"Streltsov" AND all:"perpetual futures"', 20)
show('ti:"Perpetual Futures"', 20, brief=True)
show('all:"perpetual futures" AND all:"funding rate"', 25, brief=True)
