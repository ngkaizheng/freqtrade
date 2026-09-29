"""Q4 batch 5: pin down correct citations + get real claims/numbers."""
import io
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}
MAIL = "research@example.com"


def _get(u, t=50):
    return requests.get(u, headers=UA, timeout=t)


def strip(h):
    h = re.sub(r"(?is)<(script|style|head|nav|footer|math)\b.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = re.sub(r"&[a-z#0-9]+;", " ", h)
    return " ".join(h.split())


def cr(q, rows=6):
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
            ab = re.sub(r"<[^>]+>", " ", (w.get("abstract") or ""))[:1200]
            o.append(f"- [{yr}] {(w.get('title') or [''])[0]} | {ct} | {w.get('type')} "
                     f"| doi={w.get('DOI')} | {au}")
            if ab:
                o.append("    ABS: " + " ".join(ab.split()))
        return "\n".join(o)
    except Exception as e:  # noqa: BLE001
        return f"===== CR {q} FAILED {e}"


def oa_t(t, per=4):
    u = ("https://api.openalex.org/works?filter=title.search:" + requests.utils.quote(t)
         + f"&per-page={per}&mailto={MAIL}")
    try:
        r = _get(u)
        o = [f"===== OAT: {t} [{r.status_code}]"]
        if r.status_code != 200:
            return "\n".join(o + [r.text[:200]])
        for w in r.json().get("results", []):
            loc = (w.get("primary_location") or {}).get("source") or {}
            au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:6])
            o.append(f"- [{w.get('publication_year')}] {w.get('title')} | {loc.get('display_name')} "
                     f"| {w.get('type')} | cites={w.get('cited_by_count')} | doi={w.get('doi')} "
                     f"| oa={(w.get('open_access') or {}).get('oa_url')}\n    AUTH: {au}")
        return "\n".join(o)
    except Exception as e:  # noqa: BLE001
        return f"===== OAT {t} FAILED {e}"


def s2(q, limit=8, tries=5):
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
                o.append(f"    AU: {[x['name'] for x in (p.get('authors') or [])][:7]}")
                if (p.get("openAccessPdf") or {}).get("url"):
                    o.append(f"    pdf={(p.get('openAccessPdf') or {}).get('url')}")
                if p.get("abstract"):
                    o.append("    ABS: " + " ".join(p["abstract"].split())[:1500])
            return "\n".join(o)
        time.sleep(5 * (i + 1))
    return f"===== S2 {q} FAIL {r.status_code}"


def get(u, label=None, chars=5000, grep=None):
    try:
        r = _get(u, 70)
    except Exception as e:  # noqa: BLE001
        return f"===== GET {label or u} ERR {e}"
    t = strip(r.text)
    o = [f"===== GET {label or u} [{r.status_code}] chars={len(t)}"]
    if grep:
        for kw in grep:
            hits = list(re.finditer(kw, t, re.I))
            o.append(f"  [{kw}] {len(hits)} hits")
            for m in hits[:4]:
                s = max(0, m.start() - 700)
                o.append(f"  >>> {t[s:m.start()+1100]}")
                o.append("  ---")
    else:
        o.append(t[:chars])
    return "\n".join(o)


if __name__ == "__main__":
    T = [
        (cr, ("The crypto carry trade Christin Routledge Soska Zetlin-Jones",)),
        (oa_t, ("The crypto carry trade",)),
        (cr, ("Staking token pricing and crypto carry Cong He Tang",)),
        (cr, ("Transaction convenience yield uncovered interest parity Cong He Tang",)),
        (oa_t, ("Staking token pricing and crypto carry",)),
        (cr, ("Who trades bitcoin futures and why Ferko Moin Onur Penick",)),
        (cr, ("Bitmex bitcoin derivatives price discovery informational efficiency hedging effectiveness",)),
        (cr, ("Angeris Chitra Evans Lorig perpetual futures security design",)),
        (cr, ("Can crypto tokens trade custody",)),
        (oa_t, ("Who trades bitcoin futures and why",)),
        (oa_t, ("Perpetual price discovery and crypto market quality",)),
        (get, ("https://www.nber.org/papers/w33640", "nber33640", 0, ["convenience", "carry", "UIP", "premi"])),
        (get, ("https://doi.org/10.1016/j.bcra.2025.100354", "werapun-bcra", 0,
               ["funding", "risk", "drawdown", "sharp", "tail", "regime"])),
        (get, ("https://www.sciencedirect.com/science/article/pii/S2096720925001301", "werapun-scidir", 4000)),
        (s2, ("perpetual futures funding rate risk premium liquidity premium",)),
        (s2, ("crypto liquidation cascade forced selling price impact",)),
    ]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f in [ex.submit(fn, *a) for fn, a in T]:
            print(f.result())
            print()
