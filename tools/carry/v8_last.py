import pdfplumber, os, re, requests, time
OUT = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(OUT, "_v2_he_fundamentals_2212.06888.pdf")
with pdfplumber.open(src) as pdf:
    for pi in (39, 40):
        t = pdf.pages[pi].extract_text() or ""
        print(f"\n##### PAGE {pi+1} #####\n{t[:1400]}")

print("\n\n" + "#" * 70)
print("# ITEM 3 last routes for BCRA full text")
print("#" * 70)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
cands = [
    ("core", "https://core.ac.uk/search?q=%22Exploring%20risk%20and%20return%20profiles%20of%20funding%20rate%20arbitrage%22"),
    ("openaire", "https://api.openaire.eu/search/publications?title=Exploring%20risk%20and%20return%20profiles%20of%20funding%20rate%20arbitrage&format=json"),
    ("browzine", "https://www.browzine.com/system/query?query=Exploring+risk+and+return+profiles+of+funding+rate+arbitrage"),
    ("ou_prd", "https://ou.princeofsongkla.ac.th/"),
    ("scilit", "https://www.scilit.com/publications?q=%22funding+rate+arbitrage%22"),
    ("typeset_io", "https://typeset.io/search?q=Exploring+risk+and+return+profiles+of+funding+rate+arbitrage"),
    ("colab.ws", "https://colab.ws/articles/10.1016%2Fj.bcra.2025.100354"),
    ("scite", "https://api.scite.ai/tallies/10.1016/j.bcra.2025.100354"),
    ("oa_mg", "https://api.marginalia.nu/public/search/Exploring+risk+and+return+profiles+of+funding+rate+arbitrage"),
]
for tag, u in cands:
    try:
        r = requests.get(u, headers=UA, timeout=45)
        print(f"  {tag:12s} {r.status_code} len={len(r.content)}  {u[:60]}")
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            fn = os.path.join(OUT, f"_v3_bcra_{tag}.pdf")
            open(fn, "wb").write(r.content)
            print("      *** PDF SAVED", fn)
    except Exception as e:
        print(f"  {tag:12s} ERR {type(e).__name__}")
    time.sleep(1)
