import requests, time, json, re, os
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}
E = "research@example.com"
OUT = os.path.dirname(os.path.abspath(__file__))

def cr(u, tries=5):
    for a in range(tries):
        r = requests.get(u, headers=M, timeout=60)
        if r.status_code == 429:
            time.sleep(14 + 9 * a); continue
        return r
    return None

print("#" * 72)
print("# ITEM 2 CORRECTED: Streltsov & Ruan = 'Perpetual Price Discovery and Crypto Market Quality'")
print("#" * 72)
r = cr("https://api.crossref.org/works/10.2139/ssrn.4218907")
if r and r.status_code == 200:
    m = r.json()["message"]
    for k in ("title","container-title","published","issued","author","abstract","type","URL","link"):
        v = m.get(k)
        if k == "author" and v: v = [(a.get("given"),a.get("family")) for a in v]
        if k == "link" and v: v = [l.get("URL") for l in v]
        print(f"  {k}: {v}")
time.sleep(5)

for u, tag in [("https://api.openalex.org/works/doi:10.2139/ssrn.4218907?mailto="+E, "OA"),
               ("https://api.unpaywall.org/v2/10.2139/ssrn.4218907?email="+E, "UPW")]:
    r = requests.get(u, headers=M, timeout=60)
    print(f"\n-- {tag} {r.status_code if r else None}")
    if r.status_code == 200:
        d = r.json()
        if tag == "OA":
            print("   title:", d.get("title"), "| year:", d.get("publication_date"), "| type:", d.get("type"),
                  "| cited:", d.get("cited_by_count"))
            print("   venue:", ((d.get("primary_location") or {}).get("source") or {}).get("display_name"))
            print("   OA:", d.get("open_access"))
            ab = d.get("abstract_inverted_index")
            if ab:
                pos = {}
                for w, ps in ab.items():
                    for p in ps: pos[p] = w
                print("   ABSTRACT:", " ".join(pos[k] for k in sorted(pos)))
        else:
            print("   is_oa:", d.get("is_oa"), d.get("oa_status"))
            for l in d.get("oa_locations", []) or []:
                print("    loc:", l.get("host_type"), l.get("url_for_pdf") or l.get("url"))
    time.sleep(2)

# SSRN abstract page
u = "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4218907"
try:
    r = requests.get(u, headers=UA, timeout=90)
    print(f"\n-- SSRN page {r.status_code} len={len(r.content)}")
    if r.status_code == 200:
        t = re.sub(r"<[^>]+>", " ", r.text); t = re.sub(r"\s+", " ", t)
        i = t.lower().find("abstract")
        print(t[i:i+2500])
        open(os.path.join(OUT, "_v5_ssrn_streltsv.txt"), "w", encoding="utf8").write(t)
except Exception as e:
    print("  ERR", type(e).__name__, e)

print("\n" + "#" * 72)
print("# ITEM 6: Pindza 2026, Digital Finance -- CEX-DEX funding rate arb as basis trade")
print("#" * 72)
DOI = "10.1007/s42521-026-00213-3"
for u, tag in [(f"https://api.crossref.org/works/{DOI}", "CR"),
               (f"https://api.openalex.org/works/doi:{DOI}?mailto={E}", "OA"),
               (f"https://api.unpaywall.org/v2/{DOI}?email={E}", "UPW")]:
    r = requests.get(u, headers=M, timeout=60)
    print(f"\n-- {tag} {r.status_code if r else None}")
    if r.status_code == 200:
        d = r.json()
        if tag == "CR":
            m = d["message"]
            print("   title:", (m.get("title") or [""])[0], "|", (m.get("container-title") or [None])[0])
            print("   vol/iss/page:", m.get("volume"), m.get("issue"), m.get("page"), "| issued:", m.get("issued", {}).get("date-parts"))
            print("   authors:", [f"{a.get('given')} {a.get('family')}" for a in m.get("author", [])])
            print("   license:", [l.get("URL") for l in m.get("license", [])])
        elif tag == "OA":
            print("   title:", d.get("title"), "| date:", d.get("publication_date"), "| type:", d.get("type"),
                  "| cited:", d.get("cited_by_count"))
            print("   OA:", d.get("open_access"))
            for l in d.get("locations", []):
                print("    loc:", (l.get("source") or {}).get("display_name"), "|", l.get("pdf_url"), "|", l.get("landing_page_url"))
            ab = d.get("abstract_inverted_index")
            if ab:
                pos = {}
                for w, ps in ab.items():
                    for p in ps: pos[p] = w
                print("   ABSTRACT:", " ".join(pos[k] for k in sorted(pos)))
            json.dump(d, open(os.path.join(OUT, "_v6_pindza_oa.json"), "w", encoding="utf8"), indent=1, default=str)
        else:
            print("   is_oa:", d.get("is_oa"), d.get("oa_status"))
            for l in d.get("oa_locations", []) or []:
                print("    loc:", l.get("host_type"), l.get("url_for_pdf") or l.get("url"))
    time.sleep(2)
