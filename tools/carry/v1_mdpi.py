"""Fetch the MDPI Mathematics 14(2):346 paper. Try landing page + PDF."""
import sys, io, re, os
import requests

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
OUT = os.path.dirname(os.path.abspath(__file__))

targets = [
    ("landing", "https://www.mdpi.com/2227-7390/14/2/346"),
    ("pdf", "https://www.mdpi.com/2227-7390/14/2/346/pdf"),
]
for name, url in targets:
    try:
        r = requests.get(url, headers=H, timeout=60, allow_redirects=True)
        print(f"=== {name} {url} -> {r.status_code} len={len(r.content)} ct={r.headers.get('Content-Type')}")
        print("  final:", r.url)
        fn = os.path.join(OUT, f"_v1_mdpi_{name}.bin")
        with open(fn, "wb") as f:
            f.write(r.content)
        if name == "landing":
            txt = r.text
            for m in re.finditer(r'<meta[^>]+(?:name|property)="([^"]+)"[^>]+content="([^"]{0,400})"', txt):
                if m.group(1) in ("citation_title", "citation_pdf_url", "description",
                                  "citation_date", "citation_doi", "citation_journal_title",
                                  "citation_author", "og:description"):
                    print(f"  META {m.group(1)} = {m.group(2)[:350]}")
            # abstract block
            m = re.search(r'<div[^>]+class="[^"]*art-abstract[^"]*"[^>]*>(.*?)</div>\s*</div>', txt, re.S)
            if m:
                t = re.sub(r"<[^>]+>", " ", m.group(1))
                print("  ABSTRACT:", re.sub(r"\s+", " ", t).strip()[:3000])
    except Exception as e:
        print(f"=== {name} FAILED: {type(e).__name__}: {e}")
