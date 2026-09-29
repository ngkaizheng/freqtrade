import requests, re, json, time
E = "research@example.com"
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}

def raw(u, h=M):
    r = requests.get(u, headers=h, timeout=60)
    return r

print("=== OpenAlex raw, title.search:Edgeworth complete ===")
u = ("https://api.openalex.org/works?filter=title.search:"
     + requests.utils.quote("Edgeworth complete") + f"&per-page=5&mailto={E}")
r = raw(u); print(r.status_code, r.url[:200]); print(r.text[:900])

print("\n=== OpenAlex raw, plain ?search= ===")
u = f"https://api.openalex.org/works?search=leveraged+crypto+exchange+traded+products&per-page=5&mailto={E}"
r = raw(u); print(r.status_code); print(r.text[:400])

print("\n=== arXiv raw: Streltsov ===")
u = "https://export.arxiv.org/api/query?search_query=au:Streltsov&max_results=20"
r = raw(u, UA); print(r.status_code, len(r.text)); print(r.text[:1500])

print("\n=== arXiv raw: all:perpetual futures theory ===")
u = "https://export.arxiv.org/api/query?search_query=all:%22perpetual+futures%22&max_results=20"
r = raw(u, UA); print(r.status_code, len(r.text)); print(r.text[:1200])
