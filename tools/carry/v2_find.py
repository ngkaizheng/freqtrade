"""Item 1: Ferko/Moin/Onur/Penick. Item 2: Streltsov & Ruan."""
import requests, time, json, re, os
OUT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}
E = "research@example.com"

def get(u, headers=M, **kw):
    for a in range(4):
        try:
            r = requests.get(u, headers=headers, timeout=60, **kw)
            if r.status_code == 429:
                time.sleep(9); continue
            return r
        except Exception as e:
            print("   ERR", type(e).__name__, e); time.sleep(4)
    return None

print("#" * 70)
print("# ITEM 1: Ferko, Moin, Onur, Penick -- leveraged crypto ETP premium")
print("#" * 70)
titles = [
    "Edgeworth complete or model uncertainty leveraged trade in crypto markets",
    "Leveraged trade in crypto markets",
    "Leveraged cryptocurrency exchange traded products premium",
]
for t in titles:
    u = f"https://api.openalex.org/works?filter=title.search:{requests.utils.quote(t)}&per-page=10&mailto={E}"
    r = get(u)
    print(f"\n--- OA title.search: {t!r} -> {r.status_code if r else None}")
    if r is not None and r.status_code == 200:
        for w in r.json().get("results", []):
            au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:6])
            print(f"  * [{w.get('publication_year')}] {w.get('display_name')!r}")
            print(f"      doi={w.get('doi')} type={w.get('type')} cited={w.get('cited_by_count')}")
            print(f"      authors: {au}")
            loc = (w.get("primary_location") or {}).get("source") or {}
            print(f"      venue: {loc.get('display_name')}  oa={w.get('open_access',{}).get('oa_url')}")
    time.sleep(1)

print("\n\n--- OA search (free) for the authors' known 2022 work ---")
r = get("https://api.openalex.org/works?search=leveraged%20crypto%20ETP%20premium%20Edgeworth&per-page=10&mailto=" + E)
if r and r.status_code == 200:
    for w in r.json().get("results", []):
        au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:5])
        print(f"  * [{w.get('publication_year')}] {w.get('display_name')!r}\n      {au}\n      {w.get('doi')}")
time.sleep(1)

print("\n" + "#" * 70)
print("# ITEM 2: Streltsov & Ruan -- A Theory of Perpetual Futures")
print("#" * 70)
for q in ['au:"Streltsov" AND all:"perpetual"', 'ti:"A Theory of Perpetual Futures"', 'all:"perpetual futures" AND au:"Ruan"']:
    u = "https://export.arxiv.org/api/query?search_query=" + requests.utils.quote(q, safe=':"()AND+') + "&max_results=20"
    r = get(u, headers=UA)
    print(f"\n--- arXiv {q!r} -> {r.status_code if r else None}")
    if r and r.status_code == 200:
        x = r.text
        entries = re.findall(r"<entry>(.*?)</entry>", x, re.S)
        print(f"    {len(entries)} entries")
        for e in entries:
            def g(tag):
                m = re.search(rf"<{tag}>(.*?)</{tag}>", e, re.S)
                return " ".join(m.group(1).split()) if m else ""
            print(f"  * {g('title')}")
            print(f"      id={g('id')} pub={g('published')} authors={g('name')[:200]}")
            print(f"      abs: {g('summary')[:900]}")
    time.sleep(3)
