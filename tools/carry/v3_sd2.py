import requests, re, os, html, time, json
OUT = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
s = requests.Session()
s.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin", "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
})
# Warm the session
for warm in ["https://www.sciencedirect.com/", "https://www.sciencedirect.com/journal/blockchain-research-and-applications"]:
    try:
        r = s.get(warm, timeout=90)
        print("warm", warm[:60], r.status_code, len(r.content), "cookies:", len(s.cookies))
    except Exception as e:
        print("warm ERR", type(e).__name__, e)
    time.sleep(2)

targets = [
    "https://www.sciencedirect.com/science/article/pii/S2096720925000818",
    "https://www.sciencedirect.com/science/article/pii/S2096720925000818?via%3Dihub",
    "https://www.sciencedirect.com/science/article/abs/pii/S2096720925000818",
    "https://doi.org/10.1016/j.bcra.2025.100354",
]
for i, u in enumerate(targets):
    try:
        r = s.get(u, timeout=120, allow_redirects=True)
        print(f"=== [{i}] {r.status_code} len={len(r.content)} {r.url[:110]}")
        if r.status_code == 200:
            open(os.path.join(OUT, f"_v3_sd_{i}.html"), "wb").write(r.content)
            b = r.text
            for k in ["115.9", "Sharpe", "Table 4", "Results", "funding rate"]:
                print(f"      {k!r} at {b.find(k)}")
    except Exception as e:
        print(f"=== [{i}] ERR {type(e).__name__}: {e}")
    time.sleep(3)

# S2 open access pdf
print("\n=== S2 ===")
for a in range(6):
    r = requests.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1016/j.bcra.2025.100354",
                     params={"fields": "title,year,venue,abstract,openAccessPdf,externalIds,isOpenAccess,authors"},
                     headers={"User-Agent": UA}, timeout=60)
    if r.status_code == 200:
        print(json.dumps(r.json(), indent=1)[:2500]); break
    print(" attempt", a, r.status_code); time.sleep(9)
