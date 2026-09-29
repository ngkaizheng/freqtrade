"""Item 6: The crypto carry trade papers with real funding/basis numbers."""
import requests, os, time, re, json
import fitz
OUT = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}
E = "research@example.com"

def grab(name, url):
    txt = os.path.join(OUT, f"_v6_{name}.txt")
    if os.path.exists(txt):
        print(f"=== {name} cached"); return
    try:
        r = requests.get(url, headers=UA, timeout=180)
        print(f"=== {name} {r.status_code} len={len(r.content)} ct={r.headers.get('Content-Type')}")
        if r.status_code != 200: return
        pdf = os.path.join(OUT, f"_v6_{name}.pdf")
        open(pdf, "wb").write(r.content)
        d = fitz.open(pdf)
        s = "".join(f"\n\n===== PAGE {i+1} =====\n" + p.get_text() for i, p in enumerate(d))
        open(txt, "w", encoding="utf8").write(s)
        print(f"    pages={d.page_count} chars={len(s)}")
    except Exception as e:
        print(f"=== {name} ERR {type(e).__name__}: {e}")

# Christin, Routledge, Soska, Zetlin-Jones -- The Crypto Carry Trade
grab("christin_carry", "https://gerbil.life/papers/CarryTrade.v1.2.pdf")
grab("christin_carry_v1", "http://gerbil.life/papers/CarryTrade.v1.2.pdf")
time.sleep(2)

print("\n=== find Schmeling/Schrimpf/Todorov 'Crypto Carry' ===")
for q in ["Crypto Carry Schmeling Schrimpf Todorov", "crypto carry trade futures basis Schmeling"]:
    r = requests.get(f"https://api.crossref.org/works?query.bibliographic={requests.utils.quote(q)}&rows=6&mailto={E}", headers=M, timeout=60)
    print(f"-- CR {q!r} -> {r.status_code if r else None}")
    if r and r.status_code == 200:
        for it in r.json()["message"]["items"]:
            au = ", ".join(f"{a.get('given','')} {a.get('family','')}".strip() for a in it.get("author", [])[:6])
            print(f"   * {(it.get('title') or [''])[0]!r} | {au} | {it.get('DOI')} | {(it.get('container-title') or [None])[0]} | {it.get('type')}")
    time.sleep(6)
    if r and r.status_code == 200: break

print("\n=== SSRN abstract pages ===")
for aid, tag in [("4301150", "he_fundamentals"), ("5323703", "mkt_quality")]:
    u = f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={aid}"
    try:
        r = requests.get(u, headers=UA, timeout=90)
        print(f"-- SSRN {tag} {aid}: {r.status_code} len={len(r.content)}")
        if r.status_code == 200:
            t = re.sub(r"<[^>]+>", " ", r.text)
            t = re.sub(r"\s+", " ", t)
            open(os.path.join(OUT, f"_v6_ssrn_{tag}.txt"), "w", encoding="utf8").write(t)
            i = t.lower().find("abstract")
            print("   ", t[i:i+1400] if i >= 0 else t[:800])
    except Exception as e:
        print(f"-- SSRN {tag} ERR {type(e).__name__}: {e}")
    time.sleep(3)
