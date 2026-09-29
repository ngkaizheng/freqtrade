"""Q4 batch 6: direct DOI/title lookups for abstracts of remaining key works."""
import io
import json
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


def cr_doi(doi):
    u = f"https://api.crossref.org/works/{doi}?mailto={MAIL}"
    try:
        r = _get(u)
        if r.status_code != 200:
            return f"===== CR-DOI {doi} [{r.status_code}] {r.text[:200]}"
        w = r.json()["message"]
        au = ", ".join((a.get('family') or '?') + " " + (a.get('given') or '') for a in (w.get("author") or [])[:8])
        ab = re.sub(r"<[^>]+>", " ", (w.get("abstract") or ""))
        out = [f"===== CR-DOI {doi}",
               f"TITLE: {(w.get('title') or [''])[0]}",
               f"VENUE: {(w.get('container-title') or [''])[0]} | {(w.get('issued', {}).get('date-parts') or [[None]])[0]}",
               f"AUTHORS: {au}",
               f"URL: {w.get('URL')}"]
        if ab:
            out.append("ABSTRACT: " + " ".join(ab.split())[:3000])
        else:
            out.append("ABSTRACT: (none in crossref)")
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        return f"===== CR-DOI {doi} FAILED {e}"


def oa_doi(doi):
    u = f"https://api.openalex.org/works/doi:{doi}?mailto={MAIL}"
    try:
        r = _get(u)
        if r.status_code != 200:
            return f"===== OA-DOI {doi} [{r.status_code}] {r.text[:200]}"
        w = r.json()
        loc = (w.get("primary_location") or {}).get("source") or {}
        inv = w.get("abstract_inverted_index")
        ab = ""
        if inv:
            pos = {}
            for k, vs in inv.items():
                for v in vs:
                    pos[v] = k
            ab = " ".join(pos[i] for i in sorted(pos))
        au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:8])
        return (f"===== OA-DOI {doi}\nTITLE: {w.get('title')}\nVENUE: {loc.get('display_name')} | "
                f"{w.get('publication_year')} | {w.get('type')}\nAUTHORS: {au}\ncites={w.get('cited_by_count')}\n"
                f"OA: {(w.get('open_access') or {}).get('oa_url')}\n"
                f"PRIMARY: {(w.get('primary_location') or {}).get('landing_page_url')}\n"
                f"ABSTRACT: {ab[:3000]}")
    except Exception as e:  # noqa: BLE001
        return f"===== OA-DOI {doi} FAILED {e}"


def s2_doi(doi, tries=5):
    u = (f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
         f"?fields=title,year,venue,citationCount,externalIds,abstract,authors,openAccessPdf")
    for i in range(tries):
        try:
            r = _get(u, 40)
        except Exception as e:  # noqa: BLE001
            return f"===== S2-DOI {doi} ERR {e}"
        if r.status_code == 200:
            p = r.json()
            o = [f"===== S2-DOI {doi}",
                 f"TITLE: {p.get('title')} | {p.get('venue')} | {p.get('year')} | cites={p.get('citationCount')}",
                 f"AU: {[x['name'] for x in (p.get('authors') or [])][:8]}"]
            if (p.get("openAccessPdf") or {}).get("url"):
                o.append("PDF: " + p["openAccessPdf"]["url"])
            o.append("ABS: " + " ".join((p.get("abstract") or "(none)").split())[:3000])
            return "\n".join(o)
        if r.status_code == 404:
            return f"===== S2-DOI {doi} 404 not found"
        time.sleep(5 * (i + 1))
    return f"===== S2-DOI {doi} FAIL {r.status_code}"


def get(u, label=None, chars=5000, grep=None, wait=1):
    time.sleep(wait)
    try:
        r = _get(u, 80)
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
                o.append(f"  >>> {t[s:m.start()+1200]}")
                o.append("  ---")
    else:
        o.append(t[:chars])
    return "\n".join(o)


if __name__ == "__main__":
    T = [
        (cr_doi, ("10.1016/j.bcra.2025.100354",)),        # funding rate arbitrage CEX/DEX
        (oa_doi, ("10.1016/j.bcra.2025.100354",)),
        (s2_doi, ("10.1016/j.bcra.2025.100354",)),
        (oa_doi, ("10.1002/fut.22050",)),                 # Alexander Choi Park Sohn
        (oa_doi, ("10.1016/j.gfj.2022.100778",)),         # Ferko et al.
        (oa_doi, ("10.1287/mnsc.2024.05069",)),           # Crypto Carry, Management Science
        (cr_doi, ("10.1287/mnsc.2024.05069",)),
        (oa_doi, ("10.1137/22M1520931",)),                # A Primer on Perpetuals
        (oa_doi, ("10.1504/IJBC.2026.10081004",)),        # Anatomy of a crypto cascade
        (cr_doi, ("10.1002/fut.22332",)),                 # Trading behaviour in bitcoin futures smart money
        # working papers by DOI
        (s2_doi, ("10.2139/ssrn.4268371",)),             # Crypto Carry SSRN
        (get, ("https://www.aqr.com/Insights/Research/Crypto-Carry", "AQR-CryptoCarry", 9000)),
        (get, ("https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4268371", "SSRN-CryptoCarry", 4000)),
        (get, ("https://www.nber.org/papers/w30783", "nber30783-wash", 3000)),
    ]
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in [ex.submit(fn, *a) for fn, a in T]:
            print(f.result())
            print()
