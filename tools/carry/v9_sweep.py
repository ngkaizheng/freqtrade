import requests, time, re, os
M = {"User-Agent": "research/1.0 (mailto:research@example.com)"}
E = "research@example.com"

def cr(params, tries=3):
    for a in range(tries):
        try:
            r = requests.get("https://api.crossref.org/works", params={**params, "mailto": E}, headers=M, timeout=45)
            if r.status_code == 429:
                time.sleep(10 + 8 * a); continue
            return r
        except Exception as e:
            print("  ERR", type(e).__name__); time.sleep(3)
    return None

print("#" * 70)
print("# ITEM 6 -- Crossref sweep for 2024-2026 PEER-REVIEWED funding-rate papers")
print("#" * 70)
seen = set()
for q in ["perpetual futures funding rate arbitrage returns cryptocurrency",
          "funding rate arbitrage cryptocurrency decentralized exchange basis",
          "average funding rate perpetual swap cryptocurrency empirical"]:
    r = cr({"query.bibliographic": q, "rows": 20,
            "filter": "from-pub-date:2024-01-01,type:journal-article"})
    print(f"\n-- CR {q!r} -> {r.status_code if r else None}")
    if r and r.status_code == 200:
        for it in r.json()["message"]["items"]:
            t = (it.get("title") or [""])[0]
            doi = it.get("DOI")
            if doi in seen: continue
            seen.add(doi)
            au = ", ".join(f"{a.get('given','')} {a.get('family','')}".strip() for a in it.get("author", [])[:4])
            ven = (it.get("container-title") or [None])[0]
            yr = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
            ab = (it.get("abstract") or "")
            ab = re.sub(r"<[^>]+>", " ", ab); ab = re.sub(r"\s+", " ", ab).strip()
            print(f"   * [{yr}] {t!r}\n       {au}\n       {ven} | {doi}")
            if any(ch.isdigit() for ch in ab) and len(ab) > 120:
                print(f"       AB: {ab[:700]}")
    time.sleep(4)
