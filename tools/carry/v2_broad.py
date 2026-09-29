import requests, re, time, json, sys
E = "research@example.com"
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}

def g(u, h=M, tries=4, wait=6):
    for a in range(tries):
        try:
            r = requests.get(u, headers=h, timeout=60)
            if r.status_code in (429, 503):
                print(f"   [{a}] {r.status_code} -> sleep"); time.sleep(wait + 4 * a); continue
            return r
        except Exception as ex:
            print("   ERR", type(ex).__name__, ex); time.sleep(3)
    return None

def oa_search(q, n=10, field="search"):
    u = f"https://api.openalex.org/works?{field}={requests.utils.quote(q)}&per-page={n}&mailto={E}"
    r = g(u)
    if not r or r.status_code != 200:
        print(f"   OA[{field}:{q}] status={r.status_code if r else None}"); return []
    return r.json().get("results", [])

def pr(w, tag=""):
    au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:5])
    src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    oa = (w.get("open_access") or {})
    print(f"  {tag}* [{w.get('publication_year')}] {w.get('display_name')!r}")
    print(f"      {au}")
    print(f"      doi={w.get('doi')} | venue={src} | type={w.get('type')} | cited={w.get('cited_by_count')} | OA={oa.get('oa_status')} {oa.get('oa_url')}")
    return w

def cr(q, rows=5):
    u = f"https://api.crossref.org/works?query.bibliographic={requests.utils.quote(q)}&rows={rows}&mailto={E}"
    r = g(u)
    if not r or r.status_code != 200:
        print(f"   CR[{q}] status={r.status_code if r else None}"); return []
    return r.json()["message"]["items"]

print("#" * 72); print("# ITEM 1 -- Ferko / Moin / Onur / Penick  (leveraged crypto ETP)"); print("#" * 72)
for q in ["leveraged crypto exchange traded products premium discount Edgeworth",
          "leveraged trade in crypto markets",
          "Ferko Moin Onur Penick"]:
    print(f"\n-- OA search {q!r}")
    for w in oa_search(q, 8): pr(w)
    time.sleep(1)
print("\n-- OA author search 'David Ferko'")
r = g(f"https://api.openalex.org/authors?search={requests.utils.quote('David Ferko')}&mailto={E}")
if r and r.status_code == 200:
    for a in r.json().get("results", [])[:5]:
        print(f"  AUTHOR {a['display_name']} id={a['id'].split('/')[-1]} works={a['works_count']} inst={(a.get('last_known_institution') or {}).get('display_name')}")
        time.sleep(1)
        rr = g(f"https://api.openalex.org/works?filter=author.id:{a['id'].split('/')[-1]}&per-page=25&mailto={E}&sort=publication_date:desc")
        if rr and rr.status_code == 200:
            for w in rr.json().get("results", []): pr(w, "   -> ")
        time.sleep(1)

print("\n" + "#" * 72); print("# ITEM 2 -- 'A Theory of Perpetual Futures'"); print("#" * 72)
for q in ["A Theory of Perpetual Futures", "Streltsov perpetual futures funding",
          "perpetual futures funding rate model Ruan"]:
    print(f"\n-- OA search {q!r}")
    for w in oa_search(q, 8): pr(w)
    time.sleep(1)
    print(f"-- Crossref {q!r}")
    for it in cr(q, 5):
        print(f"  CR* [{it.get('issued',{}).get('date-parts',[[None]])[0][0]}] {(it.get('title') or [''])[0]!r}")
        print(f"      doi={it.get('DOI')} venue={(it.get('container-title') or [None])[0]} type={it.get('type')}")
    time.sleep(2)

print("\n" + "#" * 72); print("# ITEM 3 -- BCRA funding rate arbitrage CEX vs DEX"); print("#" * 72)
DOI = "10.1016/j.bcra.2025.100354"
for label, u in [("CROSSREF", f"https://api.crossref.org/works/{DOI}"),
                 ("OA-by-doi", f"https://api.openalex.org/works/doi:{DOI}?mailto={E}"),
                 ("UNPAYWALL", f"https://api.unpaywall.org/v2/{DOI}?email={E}")]:
    r = g(u)
    print(f"\n-- {label}: {r.status_code if r else None}")
    if r is None or r.status_code != 200: continue
    if label == "CROSSREF":
        m = r.json()["message"]
        for k in ("title","container-title","volume","issue","page","published","author","abstract","license","link","URL","type","publisher"):
            v = m.get(k)
            if k == "author" and v: v = [(a.get("given"),a.get("family")) for a in v]
            if k == "link" and v: v = [(l.get("URL"),l.get("content-type")) for l in v]
            print(f"   {k}: {v}")
        json.dump(m, open("tools/carry/_v3_crossref.json","w",encoding="utf8"), indent=1, default=str)
    elif label == "OA-by-doi":
        d = r.json()
        print("   title:", d.get("title"), "| date:", d.get("publication_date"), "| type:", d.get("type"))
        print("   OA:", d.get("open_access"))
        for l in d.get("locations", []):
            print("    loc:", (l.get("source") or {}).get("display_name"), "|", l.get("pdf_url"), "|", l.get("landing_page_url"))
        ab = d.get("abstract_inverted_index")
        if ab:
            pos = {}
            for w, ps in ab.items():
                for p in ps: pos[p] = w
            print("   ABSTRACT:", " ".join(pos[k] for k in sorted(pos)))
        json.dump(d, open("tools/carry/_v3_openalex.json","w",encoding="utf8"), indent=1, default=str)
    else:
        d = r.json()
        print("   is_oa:", d.get("is_oa"), "| status:", d.get("oa_status"))
        for l in d.get("oa_locations", []) or []:
            print("    loc:", l.get("host_type"), "|", l.get("url_for_pdf") or l.get("url"))
    time.sleep(2)
