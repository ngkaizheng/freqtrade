"""Multi-source literature search: OpenAlex + Crossref + arXiv. Staggered, robust to 429."""
import sys
import time

import requests

UA = {"User-Agent": "research-agent/1.0 (mailto:research@example.com)"}


def oa(q, n=12):
    url = ("https://api.openalex.org/works?search=" + requests.utils.quote(q)
           + f"&per-page={n}&mailto=research@example.com")
    try:
        r = requests.get(url, headers=UA, timeout=35)
    except Exception as e:  # noqa: BLE001
        print("OA FAIL", q, e)
        return
    print(f"\n===== OPENALEX: {q}  [{r.status_code}]")
    if r.status_code != 200:
        print(r.text[:200])
        return
    for w in r.json().get("results", []):
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        oa_url = (w.get("open_access") or {}).get("oa_url")
        print(f"- [{w.get('publication_year')}] {w.get('title')}")
        print(f"    venue={src} type={w.get('type')} cites={w.get('cited_by_count')}")
        print(f"    doi={w.get('doi')} oa={oa_url}")


def cr(q, n=10):
    url = ("https://api.crossref.org/works?query=" + requests.utils.quote(q)
           + f"&rows={n}&select=title,container-title,issued,DOI,type,is-referenced-by-count"
           + "&mailto=research@example.com")
    try:
        r = requests.get(url, headers=UA, timeout=35)
    except Exception as e:  # noqa: BLE001
        print("CR FAIL", q, e)
        return
    print(f"\n===== CROSSREF: {q}  [{r.status_code}]")
    if r.status_code != 200:
        print(r.text[:200])
        return
    for it in r.json()["message"]["items"]:
        t = (it.get("title") or ["?"])[0]
        c = (it.get("container-title") or ["?"])
        print(f"- [{it.get('issued', {}).get('date-parts', [['?']])[0][0]}] {t} | "
              f"{(c[0] if c else '?')} | type={it.get('type')} | cites={it.get('is-referenced-by-count')}")


def arx(q, n=12):
    url = ("http://export.arxiv.org/api/query?search_query=all:"
           + requests.utils.quote(q) + f"&max_results={n}")
    try:
        r = requests.get(url, headers=UA, timeout=40)
    except Exception as e:  # noqa: BLE001
        print("ARXIV FAIL", q, e)
        return
    import re
    txt = r.text
    print(f"\n===== ARXIV: {q}  [{r.status_code}]")
    for ent in re.findall(r"(?s)<entry>(.*?)</entry>", txt):
        ti = re.search(r"(?s)<title>(.*?)</title>", ent)
        idm = re.search(r"<id>(.*?)</id>", ent)
        pub = re.search(r"<published>(.*?)</published>", ent)
        summ = re.search(r"(?s)<summary>(.*?)</summary>", ent)
        print(f"- [{pub.group(1)[:10] if pub else '?'}] "
              f"{(ti.group(1).strip().replace(chr(10),' ') if ti else '?')}")
        print(f"    {idm.group(1) if idm else ''}")
        if summ:
            s = " ".join(summ.group(1).split())
            print(f"    ABS: {s[:900]}")


if __name__ == "__main__":
    queries = sys.argv[1:]
    for i, q in enumerate(queries):
        oa(q)
        time.sleep(1.2)
        cr(q, 8)
        time.sleep(1.2)
        arx(q, 8)
        time.sleep(2.0)
