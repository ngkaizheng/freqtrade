import re, os, json, html, requests, time
OUT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

p = os.path.join(OUT, "_v3_sd_pii.bin")
if os.path.exists(p):
    b = open(p, "rb").read().decode("utf8", "replace")
    print("len", len(b))
    print("has 'Just a moment':", "Just a moment" in b, "| has 'abstract':", "abstract" in b.lower())
    for key in ["__NEXT_DATA__", "funding rate arbitrage", "115.9", "1.92", "Sharpe", "window.__"]:
        i = b.find(key)
        print(f"  {key!r} at {i}")
    m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]{0,600})"', b)
    if m: print("DESC:", html.unescape(m.group(1))[:600])

print("\n=== DOAJ API article lookup ===")
for u in ["https://doaj.org/api/search/articles/doi%3A10.1016%2Fj.bcra.2025.100354",
          "https://doaj.org/api/v2/articles/0eb836836ad245358a08055d2e545ce6"]:
    try:
        r = requests.get(u, headers=UA, timeout=60)
        print(f"-- {u[:70]} -> {r.status_code} {len(r.content)}")
        if r.status_code == 200:
            d = r.json()
            open(os.path.join(OUT, "_v3_doaj.json"), "w", encoding="utf8").write(json.dumps(d, indent=1))
            print(json.dumps(d, indent=1)[:4000])
    except Exception as e:
        print("  ERR", type(e).__name__, e)
    time.sleep(2)

print("\n=== S2 ===")
for a in range(6):
    r = requests.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1016/j.bcra.2025.100354",
                     params={"fields": "title,year,venue,citationCount,abstract,openAccessPdf,externalIds,authors,journal,publicationTypes,isOpenAccess,fieldsOfStudy"},
                     headers=UA, timeout=60)
    if r.status_code == 200:
        print(json.dumps(r.json(), indent=1)[:3000]); break
    print(" attempt", a, r.status_code); time.sleep(9)

print("\n=== OpenAIRE / CORE-ish alternatives ===")
for u in ["https://api.openalex.org/works/doi:10.1016/j.bcra.2025.100354?mailto=research@example.com"]:
    r = requests.get(u, headers=UA, timeout=60)
    d = r.json()
    print(json.dumps(d.get("best_oa_location"), indent=1))
