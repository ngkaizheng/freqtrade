"""Item 3: BCRA full text. Gold OA, CC-BY, Elsevier."""
import requests, os, re, html, json, time
OUT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
      "Accept-Language": "en-US,en;q=0.9"}

def h2t(h):
    h = re.sub(r"<(script|style|math)\b.*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"</(p|div|li|h[1-6]|tr|section)>", "\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t\xa0]+", " ", h)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", h).strip()

urls = [
    ("sd_pii", "https://www.sciencedirect.com/science/article/pii/S2096720925000818"),
    ("elsevier_txt", "https://api.elsevier.com/content/article/PII:S2096720925000818?httpAccept=text/plain"),
    ("elsevier_xml", "https://api.elsevier.com/content/article/PII:S2096720925000818?httpAccept=text/xml"),
    ("sd_pdf", "https://www.sciencedirect.com/science/article/pii/S2096720925000818/pdfft?isDTMRedir=true&download=true"),
    ("linkinghub", "https://linkinghub.elsevier.com/retrieve/pii/S2096720925000818"),
]
for name, u in urls:
    try:
        r = requests.get(u, headers=UA, timeout=120)
        print(f"=== {name:14s} {r.status_code} len={len(r.content)} ct={r.headers.get('Content-Type')}")
        if r.status_code == 200:
            open(os.path.join(OUT, f"_v3_{name}.bin"), "wb").write(r.content)
            if r.content[:4] == b"%PDF":
                print("      PDF saved")
            else:
                t = h2t(r.text)
                open(os.path.join(OUT, f"_v3_{name}.txt"), "w", encoding="utf8").write(t)
                print(f"      text {len(t)} chars; head: {t[:400]!r}")
    except Exception as e:
        print(f"=== {name} ERR {type(e).__name__}: {e}")
    time.sleep(2)
