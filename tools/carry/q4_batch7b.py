"""Q4 batch 7b: Christin et al. crypto carry trade; cascade / funding-carry evidence."""
import io
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}
MAIL = "research@example.com"


def _get(u, t=60):
    return requests.get(u, headers=UA, timeout=t)


def strip(h):
    h = re.sub(r"(?is)<(script|style|head|nav|footer|math)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


def s2(q, limit=8, tries=6):
    u = ("https://api.semanticscholar.org/graph/v1/paper/search?query="
         + requests.utils.quote(q)
         + f"&fields=title,year,venue,citationCount,externalIds,abstract,authors,openAccessPdf&limit={limit}")
    for i in range(tries):
        try:
            r = _get(u, 40)
        except Exception as e:  # noqa: BLE001
            return f"===== S2 {q} ERR {e}"
        if r.status_code == 200:
            d = r.json()
            o = [f"===== S2: {q} (total={d.get('total')})"]
            for p in d.get("data", []):
                o.append(f"- [{p.get('year')}] {p.get('title')} | {p.get('venue')} "
                         f"| cites={p.get('citationCount')} | ids={p.get('externalIds')}")
                o.append(f"    AU: {[x['name'] for x in (p.get('authors') or [])][:8]}")
                if (p.get("openAccessPdf") or {}).get("url"):
                    o.append(f"    pdf={(p.get('openAccessPdf') or {}).get('url')}")
                if p.get("abstract"):
                    o.append("    ABS: " + " ".join(p["abstract"].split())[:2200])
            return "\n".join(o)
        time.sleep(6 * (i + 1))
    return f"===== S2 {q} FAIL {r.status_code}"


def oa(q, per=12):
    u = ("https://api.openalex.org/works?search=" + requests.utils.quote(q)
         + f"&per-page={per}&mailto={MAIL}")
    try:
        r = _get(u)
        o = [f"===== OA: {q} [{r.status_code}]"]
        if r.status_code != 200:
            return "\n".join(o + [r.text[:200]])
        d = r.json()
        o.append(f"count={d.get('meta', {}).get('count')}")
        for w in d.get("results", []):
            loc = (w.get("primary_location") or {}).get("source") or {}
            au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:5])
            o.append(f"- [{w.get('publication_year')}] {w.get('title')} | {loc.get('display_name')} "
                     f"| {w.get('type')} | cites={w.get('cited_by_count')} | doi={w.get('doi')}"
                     f" | oa={(w.get('open_access') or {}).get('oa_url')}\n    AU: {au}")
        return "\n".join(o)
    except Exception as e:  # noqa: BLE001
        return f"===== OA {q} FAILED {e}"


def get(u, label=None, chars=5000, grep=None):
    try:
        r = _get(u, 90)
    except Exception as e:  # noqa: BLE001
        return f"===== GET {label or u} ERR {e}"
    t = strip(r.text)
    o = [f"===== GET {label or u} [{r.status_code}] chars={len(t)}"]
    if grep:
        for kw in grep:
            hits = list(re.finditer(kw, t, re.I))
            o.append(f"  [{kw}] {len(hits)} hits")
            for m in hits[:4]:
                s = max(0, m.start() - 800)
                o.append(f"  >>> {t[s:m.start()+1300]}")
                o.append("  ---")
    else:
        o.append(t[:chars])
    return "\n".join(o)


TASKS = []


def add(*a):
    TASKS.append(a)


add(s2, "The crypto carry trade")
add(s2, "Christin Routledge Soska Zetlin-Jones crypto carry trade")
add(oa, "The crypto carry trade")
add(get, "https://arxiv.org/abs/2608.03616", "garciaseuma-branching", 5000)
add(get, "https://export.arxiv.org/api/query?search_query=all:%22liquidation%20cascade%22%20AND%20all:%22crypto%22&max_results=25&sortBy=submittedDate&sortOrder=descending", "arxiv-liqcascade", 9000)
add(get, "https://export.arxiv.org/api/query?search_query=all:%22funding%20rate%22%20AND%20all:%22bitcoin%22&max_results=30&sortBy=submittedDate&sortOrder=descending", "arxiv-fundingrate", 12000)
add(oa, "separating event intensity from fixed funding carry perpetual futures credit markets")
add(get, "https://export.arxiv.org/api/query?search_query=all:%22cash-and-carry%22+OR+all:%22cash+and+carry%22&max_results=30&sortBy=submittedDate&sortOrder=descending", "arxiv-cashcarry", 12000)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [(t, ex.submit(t[0], *t[1:])) for t in TASKS]
        for t, f in futs:
            try:
                print(f.result())
            except Exception as e:  # noqa: BLE001
                print(f"===== TASK {t[0].__name__}{t[1:]} FAILED: {e!r}")
            print()
