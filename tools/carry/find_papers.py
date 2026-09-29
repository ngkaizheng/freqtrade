"""Batch bibliographic search over OpenAlex + Crossref for the funding-carry review."""
import json
import sys
import time
from urllib.parse import quote

import requests

UA = {"User-Agent": "research-bot (mailto:research@example.com)"}


def oa(q, n=8, extra=""):
    url = (
        "https://api.openalex.org/works?search="
        + quote(q)
        + f"&per-page={n}&mailto=research@example.com{extra}"
    )
    try:
        r = requests.get(url, headers=UA, timeout=40)
    except Exception as e:  # noqa: BLE001
        print(f"!! {q}: {e}")
        return
    print(f"##### OPENALEX: {q} [{r.status_code}]")
    if r.status_code != 200:
        print(r.text[:300])
        print()
        return
    d = r.json()
    print(f"    count={d.get('meta', {}).get('count')}")
    for w in d.get("results", []):
        loc = (w.get("primary_location") or {}).get("source") or {}
        auth = ", ".join(
            a.get("author", {}).get("display_name", "?") for a in (w.get("authorships") or [])[:5]
        )
        print(
            f"- [{w.get('publication_year')}] {w.get('title')}\n"
            f"    authors: {auth}\n"
            f"    source={loc.get('display_name')} type={w.get('type')} "
            f"cites={w.get('cited_by_count')} doi={w.get('doi')}\n"
            f"    oa={(w.get('open_access') or {}).get('oa_url')}\n"
            f"    best_oa_pdf={((w.get('best_oa_location') or {}).get('pdf_url'))}"
        )
    print()
    time.sleep(0.4)


def cr(q, n=8):
    url = "https://api.crossref.org/works?query=" + quote(q) + f"&rows={n}&mailto=research@example.com"
    try:
        r = requests.get(url, headers=UA, timeout=40)
    except Exception as e:  # noqa: BLE001
        print(f"!! cr {q}: {e}")
        return
    print(f"##### CROSSREF: {q} [{r.status_code}]")
    if r.status_code != 200:
        print(r.text[:300])
        print()
        return
    for it in r.json().get("message", {}).get("items", []):
        ttl = " ".join(it.get("title") or [])
        cont = it.get("container-title") or []
        yr = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        print(
            f"- [{yr}] {ttl} | {cont} | type={it.get('type')} "
            f"| doi={it.get('DOI')} | url={(it.get('URL') or '')[:90]}"
        )
    print()
    time.sleep(0.4)


if __name__ == "__main__":
    mode = sys.argv[1]
    fn = {"oa": oa, "cr": cr}[mode]
    for q in sys.argv[2:]:
        fn(q)
