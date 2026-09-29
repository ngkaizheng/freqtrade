"""Resolve exact/near-exact paper titles via OpenAlex title.search + Crossref + S2.

Usage: python tools/carry/bytitle.py "title one" "title two" ...
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


def dump(w):
    loc = (w.get("primary_location") or {}).get("source") or {}
    auth = ", ".join(
        a.get("author", {}).get("display_name", "?") for a in (w.get("authorships") or [])[:7]
    )
    print(
        f"  - [{w.get('publication_year')}] {w.get('title')}\n"
        f"      au: {auth}\n"
        f"      src={loc.get('display_name')} | {w.get('type')} | c={w.get('cited_by_count')}"
        f" | doi={w.get('doi')}\n"
        f"      oa={(w.get('open_access') or {}).get('oa_url')}"
        f" | pdf={((w.get('best_oa_location') or {}).get('pdf_url'))}"
    )


def title_oa(t, n=5):
    print(f"##### TITLE-OA: {t}")
    url = (
        "https://api.openalex.org/works?filter=title.search:"
        + quote(t)
        + f"&per-page={n}&mailto=research@example.com"
    )
    r = _get(url)
    if r is None or r.status_code != 200:
        print("   FAILED")
    else:
        for w in r.json().get("results", []):
            dump(w)
    print()
    time.sleep(0.5)


def title_cr(t, n=4):
    print(f"##### TITLE-CR: {t}")
    url = (
        "https://api.crossref.org/works?query.bibliographic="
        + quote(t)
        + f"&rows={n}&mailto=research@example.com"
    )
    r = _get(url, pause=6.0)
    if r is None or r.status_code != 200:
        print("   FAILED")
    else:
        for it in r.json().get("message", {}).get("items", []):
            print(
                f"  - [{((it.get('issued') or {}).get('date-parts') or [[None]])[0][0]}] "
                f"{' '.join(it.get('title') or [])} | {it.get('container-title')}"
                f" | {it.get('type')} | doi={it.get('DOI')}"
            )
    print()
    time.sleep(3.0)


if __name__ == "__main__":
    fn = {"oa": title_oa, "cr": title_cr}[sys.argv[1]]
    for t in sys.argv[2:]:
        fn(t)
