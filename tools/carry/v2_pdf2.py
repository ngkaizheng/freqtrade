"""Pull full text of empirical perp-funding arXiv papers from arxiv.org PDFs."""
import requests, os, time
import fitz
OUT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}

ids = {
    "he_fundamentals_2212.06888": "2212.06888v7",
    "kim_park_2506.08573":        "2506.08573v1",
    "ackerer_2310.11771":         "2310.11771v2",
    "chen_dex_2402.03953":        "2402.03953v4",
}
for name, aid in ids.items():
    out_pdf = os.path.join(OUT, f"_v2_{name}.pdf")
    out_txt = os.path.join(OUT, f"_v2_{name}.txt")
    if os.path.exists(out_txt):
        print(f"=== {name} already have text"); continue
    try:
        r = requests.get(f"https://arxiv.org/pdf/{aid}", headers=UA, timeout=180)
        print(f"=== {name} {r.status_code} len={len(r.content)} {r.headers.get('Content-Type')}")
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            open(out_pdf, "wb").write(r.content)
            d = fitz.open(out_pdf)
            txt = "".join(f"\n\n===== PAGE {i+1} =====\n" + p.get_text() for i, p in enumerate(d))
            open(out_txt, "w", encoding="utf8").write(txt)
            print(f"    pages={d.page_count} chars={len(txt)}")
    except Exception as e:
        print(f"=== {name} ERR {type(e).__name__}: {e}")
    time.sleep(3)
