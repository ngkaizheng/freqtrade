import requests, json, time, os, re
OUT = os.path.dirname(os.path.abspath(__file__))
DOI = "10.3390/math14020346"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
MAIL = {"User-Agent": "research/1.0 (mailto:research@example.com)"}

def j(u, **kw):
    try:
        r = requests.get(u, timeout=60, headers=kw.pop("headers", MAIL), **kw)
        return r
    except Exception as e:
        print("  ERR", type(e).__name__, e); return None

print("========== 1. CROSSREF FULL RECORD ==========")
r = j(f"https://api.crossref.org/works/{DOI}")
if r is not None and r.status_code == 200:
    m = r.json()["message"]
    for k in ("title", "container-title", "volume", "issue", "page", "published", "issued",
              "created", "author", "license", "link", "URL", "abstract", "subject",
              "publisher", "type"):
        v = m.get(k)
        if k == "author" and v:
            v = [(a.get("given"), a.get("family"), a.get("ORCID")) for a in v]
        if k == "link" and v:
            v = [(l.get("URL"), l.get("content-type"), l.get("content-version")) for l in v]
        print(f"  {k}: {v}")
    json.dump(m, open(os.path.join(OUT, "_v1_crossref.json"), "w", encoding="utf8"), indent=1, default=str)
time.sleep(2)

print("\n========== 2. UNPAYWALL ==========")
r = j(f"https://api.unpaywall.org/v2/{DOI}?email=research@example.com")
if r is not None and r.status_code == 200:
    d = r.json()
    print("  is_oa:", d.get("is_oa"), "| title:", d.get("title"))
    print("  best:", json.dumps(d.get("best_oa_location"), indent=1)[:800])
    for l in d.get("oa_locations", []) or []:
        print("   loc:", l.get("host_type"), "|", l.get("url_for_pdf") or l.get("url"))
else:
    print("  status", r.status_code if r else None, (r.text[:200] if r else ""))
time.sleep(2)

print("\n========== 3. OPENALEX ==========")
r = j(f"https://api.openalex.org/works/doi:{DOI}?mailto=research@example.com")
if r is not None and r.status_code == 200:
    d = r.json()
    print("  title:", d.get("title"), "| date:", d.get("publication_date"),
          "| type:", d.get("type"), "| cited:", d.get("cited_by_count"))
    print("  venue:", (d.get("primary_location") or {}).get("source", {}) and
          (d["primary_location"]["source"] or {}).get("display_name"))
    print("  is_oa:", (d.get("open_access") or {}))
    for l in d.get("locations", []):
        print("   loc:", (l.get("source") or {}).get("display_name"), "|", l.get("pdf_url"), "|", l.get("landing_page_url"))
    ab = d.get("abstract_inverted_index")
    if ab:
        pos = {}
        for w, ps in ab.items():
            for p in ps: pos[p] = w
        print("  ABSTRACT:", " ".join(pos[k] for k in sorted(pos))[:3000])
    json.dump(d, open(os.path.join(OUT, "_v1_openalex.json"), "w", encoding="utf8"), indent=1, default=str)
else:
    print("  status", r.status_code if r else None)
time.sleep(2)

print("\n========== 4. SEMANTIC SCHOLAR ==========")
for attempt in range(6):
    r = j(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{DOI}"
          f"?fields=title,year,venue,citationCount,externalIds,abstract,authors,openAccessPdf,publicationTypes,journal")
    if r is not None and r.status_code == 200:
        print(json.dumps(r.json(), indent=1)[:4000])
        break
    print("  attempt", attempt, "status", r.status_code if r else None)
    time.sleep(9)
