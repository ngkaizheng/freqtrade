import json
import sys
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}


def s2(q, n=8, tries=6):
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/search?query="
        + requests.utils.quote(q)
        + "&fields=title,year,venue,citationCount,externalIds,abstract,authors,openAccessPdf"
        + f"&limit={n}"
    )
    for a in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=45)
            if r.status_code == 200:
                d = r.json()
                print(f"##### S2: {q}  total={d.get('total')}")
                for p in d.get("data", []):
                    oa = p.get("openAccessPdf") or {}
                    print(
                        f"- [{p.get('year')}] {p.get('title')}\n"
                        f"    venue={p.get('venue')} c={p.get('citationCount')} "
                        f"ids={p.get('externalIds')}\n"
                        f"    au={[x['name'] for x in (p.get('authors') or [])][:8]}\n"
                        f"    pdf={oa.get('url')}"
                    )
                    ab = p.get("abstract")
                    if ab:
                        print(f"    ABS: {ab}")
                print()
                return
            print(f"   [{r.status_code}] retry {a}")
        except Exception as e:  # noqa: BLE001
            print(f"   !! {e}")
        time.sleep(9 * (a + 1))
    print(f"##### S2 FAILED: {q}\n")


if __name__ == "__main__":
    for q in sys.argv[1:]:
        s2(q)
