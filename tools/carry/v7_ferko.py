"""Final push: Ferko (item 1), Streltsov full text, BCRA full text, Christin carry."""
import requests, time, json, re, os
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}
E = "research@example.com"
OUT = os.path.dirname(os.path.abspath(__file__))

print("#" * 72)
print("# ITEM 1 -- FINAL: is there a Ferko / Moin / Onur / Penick leveraged-crypto-ETP paper?")
print("#" * 72)
# OpenAlex full-text search on the distinctive phrase the requester recalled
for q in ['"Edgeworth complete"', 'Edgeworth model uncertainty leveraged',
          'leveraged ETP crypto premium retail', 'leveraged token premium decay crypto']:
    r = requests.get(f"https://api.openalex.org/works?search={requests.utils.quote(q)}&per-page=8&mailto={E}", headers=M, timeout=60)
    print(f"\n-- OA {q!r} count={r.json()['meta']['count'] if r.status_code==200 else '?'}")
    if r.status_code == 200:
        for w in r.json()["results"][:8]:
            au = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:5])
            print(f"   * [{w.get('publication_year')}] {w.get('display_name')!r} | {au[:90]} | {w.get('doi')}")
    time.sleep(1)

print("\n-- OpenAlex authors named 'Ferko'")
r = requests.get(f"https://api.openalex.org/authors?search=Ferko&mailto={E}", headers=M, timeout=60)
if r.status_code == 200:
    for a in r.json().get("results", [])[:10]:
        inst = (a.get("last_known_institution") or {}).get("display_name")
        print(f"   {a['display_name']:32s} works={a['works_count']:4d} inst={inst} id={a['id'].split('/')[-1]}")

print("\n-- OpenAlex authors 'Moin' (finance/math)")
r = requests.get(f"https://api.openalex.org/authors?search=Deniz%20Moin&mailto={E}", headers=M, timeout=60)
if r.status_code == 200:
    for a in r.json().get("results", [])[:5]:
        print(f"   {a['display_name']:32s} works={a['works_count']:4d} inst={(a.get('last_known_institution') or {}).get('display_name')}")

print("\n-- Direct fetch: Man Institute search + a-team (they publish author pages)")
for u in ["https://www.man.com/insights/edgeworth-complete-or-model-uncertainty",
          "https://www.man.com/author-search?q=Ferko",
          "https://www.ateaminsights.com/"]:
    try:
        r = requests.get(u, headers=UA, timeout=60)
        print(f"   {u[:70]} -> {r.status_code} len={len(r.content)}")
    except Exception as e:
        print(f"   {u[:70]} ERR {type(e).__name__}")
    time.sleep(1)

print("\n" + "#" * 72)
print("# Streltsov & Ruan full text hunt")
print("#" * 72)
r = requests.get(f"https://api.openalex.org/works/doi:10.2139/ssrn.4218907?mailto={E}", headers=M, timeout=60)
if r.status_code == 200:
    d = r.json()
    json.dump(d, open(os.path.join(OUT, "_v7_strel_oa.json"), "w", encoding="utf8"), indent=1, default=str)
    print("  locations:")
    for l in d.get("locations", []):
        print("   ", (l.get("source") or {}).get("display_name"), "|", l.get("pdf_url"), "|", l.get("landing_page_url"), "| ver:", l.get("version"))
    print("  best_oa:", d.get("best_oa_location"))
for u in ["https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4218907_code1881523.pdf?abstractid=4218907&mirid=1",
          "https://deliverypdf.ssrn.com/delivery.php?ID=4218907"]:
    try:
        r = requests.get(u, headers=UA, timeout=90)
        print(f"   SSRN pdf {u[:60]} -> {r.status_code} len={len(r.content)} ct={r.headers.get('Content-Type')}")
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            open(os.path.join(OUT, "_v7_streltsv_ruan.pdf"), "wb").write(r.content)
            import fitz
            d = fitz.open(os.path.join(OUT, "_v7_streltsv_ruan.pdf"))
            s = "".join(f"\n\n=== PAGE {i+1} ===\n" + p.get_text() for i, p in enumerate(d))
            open(os.path.join(OUT, "_v7_streltsv_ruan.txt"), "w", encoding="utf8").write(s)
            print("   *** EXTRACTED", d.page_count, "pages", len(s), "chars")
            break
    except Exception as e:
        print("   ERR", type(e).__name__, e)
    time.sleep(2)
