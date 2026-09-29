"""Author-centric OpenAlex work listing.

Usage: python tools/carry/authorworks.py "Author Name" ["Author Name" ...]
"""
import sys
import time
from urllib.parse import quote

import requests

UA = {"User-Agent": "research-bot (mailto:research@example.com)"}


def _get(url, tries=5, pause=4.0):
    for a in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=45)
        except Exception as e:  # noqa: BLE001
            print(f"   !! {e}")
            time.sleep(pause)
            continue
        if r.status_code in (429, 500, 502, 503):
            time.sleep(pause * (a + 1))
            continue
        return r
    return None


def works_for(name, n=60, sort="cited_by_count:desc"):
    url = (
        "https://api.openalex.org/authors?search="
        + quote(name)
        + f"&per-page=5&mailto=research@example.com"
    )
    r = _get(url)
    if r is None or r.status_code != 200:
        print(f"!! author lookup failed for {name}")
        return
    auths = r.json().get("results", [])
    if not auths:
        print(f"!! no author match: {name}")
        return
    a = auths[0]
    print(
        f"===== {name} -> {a['display_name']} ({a['id']}) "
        f"works={a.get('works_count')} inst={(a.get('last_known_institutions') or [{}])[0].get('display_name')}"
    )
    wid = a["id"].rsplit("/", 1)[-1]
    wurl = (
        f"https://api.openalex.org/works?filter=author.id:{wid}"
        f"&per-page={n}&sort={sort}&mailto=research@example.com"
    )
    r2 = _get(wurl)
    if r2 is None or r2.status_code != 200:
        print("   works FAILED")
        return
    for w in r2.json().get("results", []):
        loc = (w.get("primary_location") or {}).get("source") or {}
        print(
            f"- [{w.get('publication_year')}] {w.get('title')}\n"
            f"    src={loc.get('display_name')} | {w.get('type')} | c={w.get('cited_by_count')}"
            f" | doi={w.get('doi')}\n"
            f"    oa={(w.get('open_access') or {}).get('oa_url')}"
            f" | pdf={((w.get('best_oa_location') or {}).get('pdf_url'))}"
        )
    print()
    time.sleep(0.6)


if __name__ == "__main__":
    for nm in sys.argv[1:]:
        works_for(nm)
