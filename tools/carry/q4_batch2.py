"""Q4 literature batch 2: locate specific works + pull primary abstracts."""
import io
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UA = {"User-Agent": "Mozilla/5.0 (research; contact via local repo)"}
MAIL = "research@example.com"


def _get(url, timeout=45):
    return requests.get(url, headers=UA, timeout=timeout)


def s2(query, limit=12, retry=4):
    url = ("https://api.semanticscholar.org/graph/v1/paper/search?query="
           + requests.utils.quote(query)
           + f"&fields=title,year,venue,citationCount,externalIds,abstract,authors,openAccessPdf&limit={limit}")
    for a in range(retry):
        try:
            r = _get(url, 40)
        except Exception as e:  # noqa: BLE001
            return f"===== S2: {query} ERR {e}"
        if r.status_code == 200:
            d = r.json()
            out = [f"===== S2: {query}  (total={d.get('total')})"]
            for p in d.get("data", []):
                ext = p.get("externalIds") or {}
                out.append(f"- [{p.get('year')}] {p.get('title')} | venue={p.get('venue')} "
                           f"| cites={p.get('citationCount')} | ids={ext}")
                out.append(f"    authors={[x['name'] for x in (p.get('authors') or [])][:8]}")
                oa = p.get("openAccessPdf") or {}
                if oa.get("url"):
                    out.append(f"    pdf={oa['url']}")
                if p.get("abstract"):
                    out.append(f"    ABS: {' '.join(p['abstract'].split())[:1600]}")
            return "\n".join(out)
        time.sleep(4 * (a + 1))
    return f"===== S2: {query} FAIL {r.status_code}"


def oa_title(title, per_page=5):
    url = ("https://api.openalex.org/works?filter=title.search:"
           + requests.utils.quote(title) + f"&per-page={per_page}&mailto={MAIL}")
    try:
        r = _get(url)
        out = [f"===== OA-TITLE: {title} [{r.status_code}]"]
        if r.status_code != 200:
            return "\n".join(out + [r.text[:300]])
        for w in r.json().get("results", []):
            loc = (w.get("primary_location") or {}).get("source") or {}
            au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:6])
            out.append(f"- [{w.get('publication_year')}] {w.get('title')} | {loc.get('display_name')}"
                       f" | {w.get('type')} | cites={w.get('cited_by_count')} | doi={w.get('doi')}"
                       f" | oa={(w.get('open_access') or {}).get('oa_url')}\n    AUTH: {au}")
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        return f"===== OA-TITLE: {title} FAILED {e}"


def crossref_exact(title, rows=6):
    url = ("https://api.crossref.org/works?query.bibliographic=" + requests.utils.quote(title)
           + f"&rows={rows}&mailto={MAIL}")
    try:
        r = _get(url)
        out = [f"===== CR: {title} [{r.status_code}]"]
        if r.status_code != 200:
            return "\n".join(out + [r.text[:300]])
        for w in r.json()["message"]["items"]:
            ct = (w.get("container-title") or [""])[0]
            yr = (w.get("issued", {}).get("date-parts") or [[None]])[0][0]
            au = ", ".join((a.get("family") or "?") for a in (w.get("author") or [])[:6])
            out.append(f"- [{yr}] {(w.get('title') or [''])[0]} | {ct} | {w.get('type')} "
                       f"| doi={w.get('DOI')} | {au}")
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        return f"===== CR: {title} FAILED {e}"


def arxiv_abs(aid):
    url = f"https://export.arxiv.org/api/query?id_list={aid}"
    try:
        r = _get(url, 45)
        if r.status_code != 200:
            return f"===== ARXIV-ABS {aid} [{r.status_code}] {r.text[:200]}"
        t = re.search(r"<entry>.*?<title>(.*?)</title>", r.text, re.S)
        s = re.search(r"<summary>(.*?)</summary>", r.text, re.S)
        pub = re.search(r"<published>(.*?)</published>", r.text, re.S)
        upd = re.search(r"<updated>(.*?)</updated>", r.text, re.S)
        au = re.findall(r"<name>(.*?)</name>", r.text)
        return (f"===== ARXIV-ABS {aid}\nTITLE: {' '.join(t.group(1).split()) if t else '?'}\n"
                f"published={pub.group(1) if pub else '?'} updated={upd.group(1) if upd else '?'}\n"
                f"authors: {', '.join(au)}\nABS: {' '.join(s.group(1).split()) if s else '?'}")
    except Exception as e:  # noqa: BLE001
        return f"===== ARXIV-ABS {aid} FAILED {e}"


def nber(num):
    url = f"https://www.nber.org/papers/{num}"
    try:
        r = _get(url, 45)
        txt = r.text
        t = re.search(r'<meta name="citation_title" content="(.*?)"', txt)
        ab = re.search(r'<div class="page-header__intro-inner">(.*?)</div>', txt, re.S)
        au = re.findall(r'<meta name="citation_author" content="(.*?)"', txt)
        out = [f"===== NBER w{num} [{r.status_code}]"]
        if t:
            out.append(f"TITLE: {t.group(1)}")
        out.append(f"authors: {au}")
        if ab:
            body = re.sub(r"<[^>]+>", " ", ab.group(1))
            out.append("ABS: " + " ".join(body.split())[:2500])
        else:
            m = re.search(r'citation_abstract" content="(.*?)"', txt)
            if m:
                out.append("ABS: " + " ".join(m.group(1).split())[:2500])
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        return f"===== NBER w{num} FAILED {e}"


TASKS = [
    (s2, ("Tokenomics of perpetual futures",)),
    (s2, ("Crypto Carry Schmeling Schrimpf Todorov",)),
    (s2, ("Christin Routledge Soska Zetlin-Jones cryptocurrency premium",)),
    (s2, ("A Theory of the On-Chain and Off-Chain Design of Permissionless Blockchains",)),
    (s2, ("Angeris Chitra Evans Lorig can (crypto) tokens trade custody",)),
    (s2, ("Bitcoin pricing adoption and usage sentiment risk premia Alexander",)),
    (oa_title, ("Tokenomics of perpetual futures",)),
    (oa_title, ("Crypto Carry",)),
    (oa_title, ("Transaction Convenience Yield: Uncovered Interest Parity",)),
    (oa_title, ("Anatomy of a Crypto Cascade",)),
    (crossref_exact, ("A Comparison of Cryptocurrency Returns Christin Routledge Soska Zetlin-Jones",)),
    (crossref_exact, ("A Theory of the On-Chain and Off-Chain Design of Permissionless Blockchains Leveraged Trading",)),
    (crossref_exact, ("Exploring risk and return profiles of funding rate arbitrage on CEX and DEX",)),
    (crossref_exact, ("Tokenomics of perpetual futures",)),
    (arxiv_abs, ("2212.06888",)),
    (arxiv_abs, ("2609.05433",)),
    (arxiv_abs, ("2310.11771",)),
    (arxiv_abs, ("2607.27070",)),
    (nber, ("w32936",)),
    (nber, ("w33640",)),
]

with ThreadPoolExecutor(max_workers=8) as ex:
    futs = [ex.submit(fn, *a) for fn, a in TASKS]
    for f in futs:
        print(f.result())
        print()
