import requests, time, json, re
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}
E = "research@example.com"

def s2(u, params, tries=6):
    for a in range(tries):
        try:
            r = requests.get(u, params=params, headers=UA, timeout=60)
            if r.status_code == 429:
                time.sleep(9 + 3 * a); continue
            return r
        except Exception as ex:
            print("   ERR", type(ex).__name__, ex); time.sleep(4)
    return None

def cr(u, tries=4):
    for a in range(tries):
        try:
            r = requests.get(u, headers=M, timeout=60)
            if r.status_code == 429:
                time.sleep(15 + 8 * a); continue
            return r
        except Exception as ex:
            print("   ERR", type(ex).__name__, ex); time.sleep(5)
    return None

print("#" * 72)
print("# ITEM 2 -- does 'A Theory of Perpetual Futures' by Streltsov & Ruan exist?")
print("#" * 72)
for q in ["A Theory of Perpetual Futures", "perpetual futures Streltsov", "funding rate perpetual futures theory"]:
    r = s2("https://api.semanticscholar.org/graph/v1/paper/search",
           {"query": q, "fields": "title,year,venue,citationCount,externalIds,authors,publicationTypes", "limit": 10})
    print(f"\n-- S2 search {q!r} -> {r.status_code if r else None}")
    if r and r.status_code == 200:
        for w in r.json().get("data", []):
            au = ", ".join(a["name"] for a in (w.get("authors") or [])[:5])
            print(f"   * [{w.get('year')}] {w.get('title')!r} | {au} | venue={w.get('venue')} | {w.get('externalIds',{}).get('DOI')}")
    time.sleep(3)

r = cr(f"https://api.crossref.org/works?query.author={requests.utils.quote('Streltsov')}&query.bibliographic=perpetual+futures&rows=10&mailto={E}")
print(f"\n-- CR author=Streltsov + perp futures -> {r.status_code if r else None}")
if r and r.status_code == 200:
    for it in r.json()["message"]["items"]:
        au = ", ".join(f"{a.get('given','')} {a.get('family','')}".strip() for a in it.get("author", [])[:6])
        print(f"   * {(it.get('title') or [''])[0]!r} | {au} | {it.get('DOI')}")
time.sleep(4)

r = requests.get(f"https://api.openalex.org/works?filter=title.search:Theory+of+Perpetual+Futures&per-page=10&mailto={E}", headers=M, timeout=60)
print(f"\n-- OA title.search 'Theory of Perpetual Futures' count={r.json()['meta']['count'] if r.status_code==200 else '?'}")
if r.status_code == 200:
    for w in r.json()["results"]:
        print("   *", w.get("display_name"), "|", w.get("doi"))
time.sleep(3)

print("\n" + "#" * 72)
print("# ITEM 1 -- Ferko et al : Semantic Scholar + OpenAlex author")
print("#" * 72)
for q in ["leveraged crypto ETP premium", "Edgeworth complete model uncertainty leveraged trade crypto",
          "leveraged cryptocurrency exchange traded products"]:
    r = s2("https://api.semanticscholar.org/graph/v1/paper/search",
           {"query": q, "fields": "title,year,venue,citationCount,externalIds,authors", "limit": 10})
    print(f"\n-- S2 {q!r} -> {r.status_code if r else None}")
    if r and r.status_code == 200:
        for w in r.json().get("data", []):
            au = ", ".join(a["name"] for a in (w.get("authors") or [])[:5])
            print(f"   * [{w.get('year')}] {w.get('title')!r}\n       {au}\n       venue={w.get('venue')} {w.get('externalIds',{}).get('DOI')} cited={w.get('citationCount')}")
    time.sleep(3)

for name in ["David Ferko", "Matthew Penick", "James Penick", "Deniz Moin", "Ozan Onur", "Can Onur"]:
    r = requests.get(f"https://api.openalex.org/authors?search={requests.utils.quote(name)}&mailto={E}", headers=M, timeout=60)
    if r.status_code == 200:
        rs = r.json().get("results", [])[:3]
        for a in rs:
            inst = (a.get("last_known_institution") or {}).get("display_name")
            print(f"   AUTHOR {a['display_name']:34s} works={a['works_count']:4d} inst={inst} id={a['id'].split('/')[-1]}")
    time.sleep(1)

print("\n" + "#" * 72)
print("# PUBLICATION VENUE check for the real papers we DID find")
print("#" * 72)
for doi in ["10.2139/ssrn.4301150", "10.1111/mafi.70018", "10.48550/arxiv.2212.06888"]:
    r = cr(f"https://api.crossref.org/works/{doi}")
    if r and r.status_code == 200:
        m = r.json()["message"]
        au = ", ".join(f"{a.get('given','')} {a.get('family','')}".strip() for a in m.get("author", []))
        print(f"\n-- {doi}\n   title={(m.get('title') or [''])[0]!r}\n   venue={(m.get('container-title') or [None])[0]} type={m.get('type')} issued={m.get('issued',{}).get('date-parts')}\n   authors={au}")
    else:
        print(f"\n-- {doi} -> {r.status_code if r else None}")
    time.sleep(4)
