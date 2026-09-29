import requests, re, json, os, sys
OUT = os.path.dirname(os.path.abspath(__file__))
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# 1. What did the 403 say?
p = os.path.join(OUT, "_v1_mdpi_landing.bin")
if os.path.exists(p):
    print("--- 403 body ---")
    print(open(p, "rb").read().decode("utf8", "replace")[:1200])

print("\n--- Crossref lookup for MDPI Mathematics 14(2):346 ---")
import time
for q in ["10.3390/math14020346", "The Two-Tiered Structure of Cryptocurrency Funding Rate Markets"]:
    try:
        u = ("https://api.crossref.org/works?query.bibliographic="
             + requests.utils.quote(q) + "&rows=5&mailto=research@example.com")
        r = requests.get(u, timeout=60, headers={"User-Agent": "research/1.0 (mailto:research@example.com)"})
        print(f"[{q}] {r.status_code}")
        if r.status_code == 200:
            for it in r.json()["message"]["items"]:
                print("  *", it.get("title"), "|", it.get("container-title"),
                      "|", it.get("DOI"), "|", it.get("published", {}).get("date-parts"),
                      "| type:", it.get("type"))
        else:
            print("  body:", r.text[:200])
    except Exception as e:
        print(f"[{q}] ERR {e}")
    time.sleep(3)
