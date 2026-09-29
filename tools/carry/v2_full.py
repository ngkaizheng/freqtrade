"""Pull full text of empirical perp-funding arXiv papers via ar5iv."""
import requests, re, os, time, html
OUT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}

def h2t(h):
    h = re.sub(r"<(script|style|math)\b.*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    h = re.sub(r"</(p|div|li|h[1-6]|tr|section)>", "\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t\xa0]+", " ", h)
    h = re.sub(r"\n\s*\n\s*\n+", "\n\n", h)
    return h.strip()

ids = {
    "he_fundamentals_2212.06888": "https://ar5iv.labs.arxiv.org/html/2212.06888",
    "kim_park_2506.08573":        "https://ar5iv.labs.arxiv.org/html/2506.08573",
    "ackerer_2310.11771":         "https://ar5iv.labs.arxiv.org/html/2310.11771",
}
for name, url in ids.items():
    try:
        r = requests.get(url, headers=UA, timeout=180)
        print(f"=== {name} {r.status_code} len={len(r.content)}")
        if r.status_code == 200:
            t = h2t(r.text)
            p = os.path.join(OUT, f"_v2_{name}.txt")
            open(p, "w", encoding="utf8").write(t)
            print(f"    text {len(t)} chars -> {p}")
    except Exception as e:
        print(f"=== {name} ERR {type(e).__name__}: {e}")
    time.sleep(2)
