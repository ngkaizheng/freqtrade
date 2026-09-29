"""Item 1 (Ferko et al) and Item 2 (Streltsov & Ruan) -- hard hunt incl. SSRN + DDG."""
import requests, re, html, json, time, urllib.parse
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
E = "research@example.com"
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}

def h2t(h):
    h = re.sub(r"<(script|style)\b.*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h)
    return re.sub(r"\s+", " ", h).strip()

def ddg(q, n=15):
    """DuckDuckGo HTML endpoint via requests."""
    out = []
    for first in (1, 16):
        try:
            r = requests.post("https://html.duckduckgo.com/html/",
                              data={"q": q, "b": first, "kl": "us-en"},
                              headers=UA, timeout=60)
            if r.status_code != 200:
                print("  ddg status", r.status_code); break
            for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
                url, title = m.group(1), h2t(m.group(2))
                out.append((title, url))
        except Exception as ex:
            print("  ddg ERR", type(ex).__name__, ex); break
        time.sleep(2)
    return out

print("#" * 72)
print("# ITEM 1 -- Ferko / Moin / Onur / Penick : what does this paper actually say?")
print("#" * 72)
queries = [
    'Ferko Moin Onur Penick leveraged crypto',
    '"leveraged" crypto ETP premium "Edgeworth" Ferko',
    'site:man.com Ferko crypto',
    'a-team "Ferko" crypto leverage',
    '"A Theory of Perpetual Futures" Streltsov',
    'Streltsov "perpetual futures" funding',
]
for q in queries:
    print(f"\n--- DDG: {q!r}")
    for t, u in ddg(q)[:12]:
        print(f"   * {t[:110]}\n       {u[:170]}")
    time.sleep(2)

print("\n" + "#" * 72)
print("# SSRN search API (sol3)")
print("#" * 72)
for term in ["Ferko crypto", "A Theory of Perpetual Futures", "leveraged cryptocurrency ETP"]:
    try:
        r = requests.get("https://api.ssrn.com/content/v1/papers",
                         params={"query": term, "size": 20, "sort": "date"},
                         headers=UA, timeout=60)
        print(f"\n-- SSRN {term!r} -> {r.status_code} ct={r.headers.get('Content-Type')}")
        if r.status_code == 200:
            print("   ", r.text[:1500])
    except Exception as e:
        print(f"-- SSRN {term!r} ERR {type(e).__name__}: {e}")
    time.sleep(2)

print("\n" + "#" * 72)
print("# Crossref title-only retries (slow, one at a time)")
print("#" * 72)
for q in ["A Theory of Perpetual Futures", "Ferko Onur leveraged crypto exchange traded"]:
    for attempt in range(3):
        r = requests.get("https://api.crossref.org/works",
                         params={"query.title": q, "rows": 8, "mailto": E},
                         headers=M, timeout=60)
        print(f"-- CR title={q!r} attempt={attempt} -> {r.status_code}")
        if r.status_code == 200:
            for it in r.json()["message"]["items"]:
                ti = (it.get("title") or [""])[0]
                au = ", ".join(f"{a.get('given','')} {a.get('family','')}".strip() for a in it.get("author", [])[:6])
                print(f"   * {ti!r} | {au} | {it.get('DOI')} | {(it.get('container-title') or [None])[0]} | {it.get('type')}")
            break
        time.sleep(20)
    time.sleep(5)
