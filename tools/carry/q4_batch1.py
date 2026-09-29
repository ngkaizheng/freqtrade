"""Q4 literature batch 1: locate the key works via OpenAlex / arXiv / Crossref."""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}
MAIL = "research@example.com"


def _get(url, timeout=40):
    return requests.get(url, headers=UA, timeout=timeout)


def openalex(query, per_page=10):
    url = ("https://api.openalex.org/works?search=" + requests.utils.quote(query)
           + f"&per-page={per_page}&mailto={MAIL}")
    try:
        r = _get(url)
        out = [f"===== OPENALEX: {query} [{r.status_code}]"]
        if r.status_code != 200:
            return "\n".join(out + [r.text[:300]])
        data = r.json()
        out.append(f"count={data.get('meta', {}).get('count')}")
        for w in data.get("results", []):
            loc = (w.get("primary_location") or {}).get("source") or {}
            out.append(
                f"- [{w.get('publication_year')}] {w.get('title')} | {loc.get('display_name')}"
                f" | type={w.get('type')} | cites={w.get('cited_by_count')}"
                f" | doi={w.get('doi')}"
                f" | oa={(w.get('open_access') or {}).get('oa_url')}"
            )
            bib = w.get("bibtex")
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        return f"===== OPENALEX: {query} FAILED {e}"


def crossref(query, rows=8):
    url = ("https://api.crossref.org/works?query=" + requests.utils.quote(query)
           + f"&rows={rows}&mailto={MAIL}&select=title,author,issued,container-title,DOI,type,abstract,URL")
    try:
        r = _get(url)
        out = [f"===== CROSSREF: {query} [{r.status_code}]"]
        if r.status_code != 200:
            return "\n".join(out + [r.text[:300]])
        for w in r.json()["message"]["items"]:
            ct = (w.get("container-title") or [""])[0]
            yr = (w.get("issued", {}).get("date-parts") or [[None]])[0][0]
            au = ", ".join((a.get("family") or "?") for a in (w.get("author") or [])[:5])
            out.append(f"- [{yr}] {(w.get('title') or [''])[0]} | {ct} | type={w.get('type')} | doi={w.get('DOI')} | {au}")
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        return f"===== CROSSREF: {query} FAILED {e}"


def arxiv(query, max_results=15, sort="relevance"):
    url = ("https://export.arxiv.org/api/query?search_query=" + query
           + f"&max_results={max_results}&sortBy={sort}&sortOrder=descending")
    try:
        r = _get(url, timeout=50)
        out = [f"===== ARXIV: {query} [{r.status_code}]"]
        if r.status_code != 200:
            return "\n".join(out + [r.text[:300]])
        import re
        txt = r.text
        entries = txt.split("<entry>")[1:]
        for e in entries:
            t = re.search(r"<title>(.*?)</title>", e, re.S)
            i = re.search(r"<id>(.*?)</id>", e, re.S)
            p = re.search(r"<published>(.*?)</published>", e, re.S)
            au = re.findall(r"<name>(.*?)</name>", e)
            s = re.search(r"<summary>(.*?)</summary>", e, re.S)
            title = " ".join(t.group(1).split()) if t else "?"
            summ = " ".join(s.group(1).split())[:900] if s else ""
            out.append(f"- [{p.group(1)[:10] if p else '?'}] {title}")
            out.append(f"    {i.group(1) if i else ''}")
            out.append(f"    authors: {', '.join(au[:8])}")
            out.append(f"    ABS: {summ}")
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        return f"===== ARXIV: {query} FAILED {e}"


TASKS = []


def add(fn, *a, **kw):
    TASKS.append((fn, a, kw))


# --- A: tokenization / conveyance of leverage
add(openalex, "Tokenomics of perpetual futures")
add(openalex, "Transaction Convenience Yield Uncovered Interest Parity cryptocurrency")
add(openalex, "Crypto Carry Schmeling Schrimpf Todorov")
add(crossref, "Tokenomics of perpetual futures Cong")
add(crossref, "Transaction Convenience Yield Uncovered Interest Parity crypto perpetual futures")
# --- B: liquidations
add(openalex, "cryptocurrency perpetual futures liquidations cascade")
add(openalex, "crypto leverage liquidation risk margin calls")
add(crossref, "liquidations cryptocurrency perpetual futures forced selling")
# --- C: retail / sentiment premium
add(openalex, "cryptocurrency funding rate returns differences of opinion leverage constraints")
add(openalex, "bitcoin premium alternative currency risk Christin Routledge Soska Zetlin-Jones")
add(openalex, "A Theory of the On-Chain and Off-Chain Design of Permissionless Blockchains Ferko Moin Onur Penick")
add(crossref, "Exploring risk and return profiles of funding rate arbitrage on CEX and DEX")
# --- D: clamp theory
add(arxiv, 'all:"perpetual futures" AND all:"funding rate"', 20)
add(arxiv, 'all:"Crypto Carry"', 8)
add(arxiv, 'all:"perpetual futures" AND all:"liquidation"', 20)
# --- E: funding arbitrage risk
add(openalex, "funding rate arbitrage crypto exchanges risk return")
add(openalex, "perpetual futures funding rate manipulation price discovery")
# --- misc
add(openalex, "bitcoin futures basis sentiment risk premium Alexander Choi Park Sohn")
add(openalex, "perpetual futures pricing Ackerer Hugonnier Jermann")
add(openalex, "perpetual futures for stocks Gupta Polson")
add(arxiv, 'all:"perpetual futures" AND all:"volatility risk premium"', 15)

if __name__ == "__main__":
    import io
    import sys as _sys
    _sys.stdout = io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(fn, *a, **kw) for fn, a, kw in TASKS]
        for f in futs:
            print(f.result())
            print()
