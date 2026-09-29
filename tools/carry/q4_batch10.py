"""Q4 batch 10: last academic gaps via Crossref / ACM / arXiv."""
import io
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}
MAIL = "research@example.com"


def _get(u, t=70):
    return requests.get(u, headers=UA, timeout=t)


def strip(h):
    h = re.sub(r"(?is)<(script|style|head|nav|footer|math)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


def get(u, label=None, chars=5000, grep=None, wid=1200):
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
            for m in hits[:3]:
                s = max(0, m.start() - 800)
                o.append(f"  >>> {t[s:m.start()+wid]}")
                o.append("  ---")
    else:
        o.append(t[:chars])
    return "\n".join(o)


def cr(q, rows=8):
    u = ("https://api.crossref.org/works?query.bibliographic=" + requests.utils.quote(q)
         + f"&rows={rows}&mailto={MAIL}")
    try:
        r = _get(u)
        o = [f"===== CR: {q} [{r.status_code}]"]
        if r.status_code != 200:
            return "\n".join(o + [r.text[:150]])
        for w in r.json()["message"]["items"]:
            ct = (w.get("container-title") or [""])[0]
            yr = (w.get("issued", {}).get("date-parts") or [[None]])[0][0]
            au = ", ".join((a.get("family") or "?") for a in (w.get("author") or [])[:7])
            ab = re.sub(r"<[^>]+>", " ", (w.get("abstract") or ""))[:1800]
            o.append(f"- [{yr}] {(w.get('title') or [''])[0]} | {ct} | {w.get('type')} "
                     f"| doi={w.get('DOI')} | {au}")
            if ab:
                o.append("    ABS: " + " ".join(ab.split()))
        return "\n".join(o)
    except Exception as e:  # noqa: BLE001
        return f"===== CR {q} FAILED {e}"


TASKS = []


def add(*a):
    TASKS.append(a)


add(cr, "Anatomy of Cryptocurrency Perpetual Futures Returns Cao Luo Cheng Dong")
add(cr, "A Real Edge that Loses Anatomy of a Backtest-to-Live Gap in Cryptocurrency Perpetual Futures")
add(cr, "Fundamentals of Cryptocurrency Perpetual Futures and Swaps Neubert Rams Gruhn")
add(cr, "crypto futures trader characteristics retail investor position Ferko Penick")
add(get, "https://dl.acm.org/doi/10.1145/3442381.3450059", "soska-www2021-bitmex", 0,
    ["funding", "retail", "leverage", "liquidat"], 1100)
add(get, "https://export.arxiv.org/api/query?search_query=all:%22perpetual%20futures%22%20AND%20all:%22convenience%20yield%22&max_results=20&sortBy=submittedDate&sortOrder=descending", "arxiv-convyield", 9000)
add(get, "https://export.arxiv.org/api/query?search_query=all:%22perpetual%20futures%22%20AND%20all:%22basis%20trade%22&max_results=20&sortBy=submittedDate&sortOrder=descending", "arxiv-basistrade", 9000)
add(get, "https://arxiv.org/html/2212.06888v7", "he-clamp", 0,
    ["the clamp", "manipulat", "insurance", "backstop", "premium index"], 1300)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [(t, ex.submit(t[0], *t[1:])) for t in TASKS]
        for t, f in futs:
            try:
                print(f.result())
            except Exception as e:  # noqa: BLE001
                print(f"===== TASK {t[0].__name__}{t[1:]} FAILED: {e!r}")
            print()
