"""Q4 batch 7: Christin et al. crypto carry trade; liquidation/cascade evidence."""
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
                    o.append("    ABS: " + " ".join(p["abstract"].split())[:2000])
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


def get(u, label=None, chars=5000, grep=None, wait=0):
    if wait:
        time.sleep(wait)
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


if __name__ == "__main__":
    T = [
        (s2, ("The crypto carry trade",)),
        (s2, ("Christin Routledge Soska Zetlin-Jones crypto carry trade differences of opinion",)),
        (get, ("https://nick-soska.github.io/", "soska-home", 3000)),
        (get, ("https://www.nick-soska.com/crypto-carry-trade.pdf", "soska-ccarry", 0,
               ["differences of opinion", "leverage", "funding", "premium", "abstract", "Abstract"])),
        (oa, ("funding rate arbitrage perpetual futures drawdown tail risk"), 10),
        (oa, ("bitcoin perpetual futures funding rate bear market bull market procyclical"), 10),
        (oa, ("October 2025 crypto flash crash liquidation"), 10),
        (s2, ("bitcoin flash crash October 2025 liquidation cascade",)),
        (oa, ("leveraged crypto futures default risk creditors"), 8),
        (get, ("https://arxiv.org/abs/2506.08573", "kim-park-funding", 4000)),
    ]
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = []
        for item in T:
            fn = item[0]
            futs.append((item, ex.submit(fn, *item[1:])))
        for item, f in futs:
            try:
                print(f.result())
            except Exception as e:  # noqa: BLE001
                print(f"===== TASK {item[0].__name__}{item[1:]} FAILED: {e!r}")
            print()
