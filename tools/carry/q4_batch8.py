"""Q4 batch 8: Christin et al. crypto carry trade; Gupta-Polson key mechanism sections."""
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


def get(u, label=None, chars=5000, grep=None, wid=1400):
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
                s = max(0, m.start() - 900)
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
            return "\n".join(o + [r.text[:200]])
        for w in r.json()["message"]["items"]:
            ct = (w.get("container-title") or [""])[0]
            yr = (w.get("issued", {}).get("date-parts") or [[None]])[0][0]
            au = ", ".join((a.get("family") or "?") for a in (w.get("author") or [])[:6])
            ab = re.sub(r"<[^>]+>", " ", (w.get("abstract") or ""))[:1500]
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


# Christin et al. -- try many routes
add(cr, "The crypto carry trade Christin Routledge Soska Zetlin-Jones 2022")
add(get, "https://www.semanticscholar.org/search?q=The%20crypto%20carry%20trade", "s2-search-page", 2000)
add(get, "https://scholar.google.com/scholar?q=%22The+crypto+carry+trade%22+Christin", "gscholar", 3000)
add(get, "https://www.researchgate.net/publication/362248401", "rg", 1500)
add(get, "https://arxiv.org/html/2609.05433v1", "gupta-polson-full", 0,
    ["why.{0,80}funding", "the purpose", "design", "short.{0,60}funding", "who pays",
     "peg", "risk premium", "leverage"], 1100)
add(get, "https://www.nber.org/papers/w32936", "nber-ahj", 0, ["funding", "convenience", "premium"], 900)
add(get, "https://arxiv.org/abs/2212.06888", "he-abs", 2000)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [(t, ex.submit(t[0], *t[1:])) for t in TASKS]
        for t, f in futs:
            try:
                print(f.result())
            except Exception as e:  # noqa: BLE001
                print(f"===== TASK {t[0].__name__}{t[1:]} FAILED: {e!r}")
            print()
