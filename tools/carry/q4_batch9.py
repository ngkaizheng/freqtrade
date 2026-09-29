"""Q4 batch 9: final gaps - Christin carry trade, liquidation-risk economics, procyclicality."""
import io
import re
import sys
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


def oa_doi(doi):
    u = f"https://api.openalex.org/works/doi:{doi}?mailto={MAIL}"
    try:
        r = _get(u)
        if r.status_code != 200:
            return f"===== OA-DOI {doi} [{r.status_code}] {r.text[:150]}"
        w = r.json()
        inv = w.get("abstract_inverted_index")
        ab = ""
        if inv:
            pos = {}
            for k, vs in inv.items():
                for v in vs:
                    pos[v] = k
            ab = " ".join(pos[i] for i in sorted(pos))
        loc = (w.get("primary_location") or {}).get("source") or {}
        au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:8])
        return (f"===== OA-DOI {doi}\nTITLE: {w.get('title')}\nVENUE: {loc.get('display_name')} | "
                f"{w.get('publication_year')} | {w.get('type')}\nAU: {au}\ncites={w.get('cited_by_count')}\n"
                f"OA: {(w.get('open_access') or {}).get('oa_url')}\nABSTRACT: {ab[:3000]}")
    except Exception as e:  # noqa: BLE001
        return f"===== OA-DOI {doi} FAILED {e}"


def oa_q(q, per=10):
    u = f"https://api.openalex.org/works?search={requests.utils.quote(q)}&per-page={per}&mailto={MAIL}"
    try:
        r = _get(u)
        o = [f"===== OA: {q} [{r.status_code}]"]
        if r.status_code != 200:
            return "\n".join(o + [r.text[:150]])
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


TASKS = []


def add(*a):
    TASKS.append(a)


add(get, "https://ideas.repec.org/cgi-bin/htsearch?q=crypto+carry+trade+Christin", "repec-search", 5000)
add(get, "https://econpapers.repec.org/scripts/search.pf?ft=crypto+carry+trade+christin", "econpapers", 5000)
add(get, "https://www.auburn.edu/~bkroutle/", "routledge", 2000)
add(get, "https://faculty.uchicago.edu/directory/ariel-zetlin-jones", "zetlinjones", 2000)
add(oa_doi, "10.1016/j.ejor.2022.07.037")
add(oa_doi, "10.62127/aijmr.2026.v04i04.1493")
add(oa_q, "Anatomy of Cryptocurrency Perpetual Futures Returns")
add(get, "https://api.openalex.org/works?search=cryptocurrency%20perpetual%20futures%20systematic%20literature%20review&per-page=5&mailto=research@example.com", "oa-sysrev", 2000)
add(oa_q, "bitcoin perpetual futures funding rate momentum reversal premium predictive")
add(get, "https://www.bis.org/publ/arpdf/ar2021e3.htm", "BIS2021-ch3", 0,
    ["leverag", "perpetual", "not own", "right to", "short"], 900)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [(t, ex.submit(t[0], *t[1:])) for t in TASKS]
        for t, f in futs:
            try:
                print(f.result())
            except Exception as e:  # noqa: BLE001
                print(f"===== TASK {t[0].__name__}{t[1:]} FAILED: {e!r}")
            print()
