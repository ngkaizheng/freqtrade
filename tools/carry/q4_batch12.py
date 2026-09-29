"""Q4 batch 12: final gaps - delta-neutral drawdown studies, Cong-He-Tang carry numbers."""
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


def cr(q, rows=6):
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
            ab = re.sub(r"<[^>]+>", " ", (w.get("abstract") or ""))[:1600]
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


add(cr, "delta neutral cryptocurrency funding rate strategy drawdown tail risk")
add(cr, "funding rate arbitrage cryptocurrency leverage risk adjusted return")
add(get, "https://www.nber.org/system/files/working_papers/w33640/w33640.pdf", "nber-33640-pdf", 0,
    ["carry premi", "convenience yield", "UIP violation", "funding"], 1200)
add(get, "https://www.semanticscholar.org/arxiv/2203.07733", "s2-x", 500)
add(get, "https://www.bing.com/search?q=%22crypto+carry+trade%22+Christin+Routledge+Soska+Zetlin-Jones", "bing-ccarry", 4000)
add(get, "https://lite.duckduckgo.com/lite/?q=%22The+crypto+carry+trade%22+Christin+Routledge+Soska", "ddglite-ccarry", 4000)
add(get, "https://search.marcia.io/search?q=test", "x", 100)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [(t, ex.submit(t[0], *t[1:])) for t in TASKS]
        for t, f in futs:
            try:
                print(f.result())
            except Exception as e:  # noqa: BLE001
                print(f"===== TASK {t[0].__name__}{t[1:]} FAILED: {e!r}")
            print()
