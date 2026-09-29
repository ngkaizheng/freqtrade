"""Resolve + fetch Wayback snapshots. Usage:
  python q4vnd_wb.py avail <url>
  python q4vnd_wb.py get <name> <url> [timestamp]
  python q4vnd_wb.py cdx <urlprefix> [filter-regex]
"""
import json
import os
import re
import sys
import time

import requests

from q4vnd_fetch import CACHE, HDRS, decompress, strip_html

S = requests.Session()
S.headers.update(HDRS)


def api(url, tries=3):
    for i in range(tries):
        try:
            r = S.get(url, timeout=(10, 60))
            return r
        except Exception as e:  # noqa: BLE001
            print(f"   retry {i}: {type(e).__name__}")
            time.sleep(4)
    return None


def avail(url):
    r = api("https://archive.org/wayback/available?url=" + requests.utils.quote(url))
    if r is None or r.status_code != 200:
        print("AVAIL FAIL", getattr(r, "status_code", "net"))
        return
    d = r.json()
    s = d.get("archived_snapshots", {}).get("closest")
    if not s:
        print("AVAIL: no snapshot for", url)
        return
    print(f"AVAIL {url}\n  -> {s['timestamp']} {s['url']}  status={s['status']}")


def get(name, url, ts=None, mod=""):
    target = f"https://web.archive.org/web/{ts or ''}{mod}/{url}"
    r = api(target)
    if r is None:
        print(f"[FAIL] {name}")
        return
    body = decompress(r.content, r.headers)
    ct = r.headers.get("content-type", "")
    if "json" in ct or url.endswith(".pdf"):
        out = body
    else:
        out = strip_html(body)
    p = os.path.join(CACHE, name + ".txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"### URL: {target}\n### STATUS: {r.status_code}\n\n{out}")
    print(f"[ok {r.status_code}] {name} {len(out)} chars  (final: {r.url[:120]})")


def cdx(prefix, filt=None, limit=300):
    u = (
        "https://web.archive.org/cdx/search/cdx?url="
        + requests.utils.quote(prefix)
        + f"&output=json&fl=timestamp,original,statuscode&collapse=urlkey&limit={limit}"
    )
    if filt:
        u += "&filter=" + requests.utils.quote(filt)
    r = api(u)
    if r is None or r.status_code != 200:
        print("CDX FAIL", getattr(r, "status_code", "net"))
        return
    try:
        rows = r.json()
    except Exception:  # noqa: BLE001
        print("CDX non-json", r.text[:300])
        return
    for row in rows[1:]:
        print("  ", row[0], row[2], row[1])


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "avail":
        for u in a[1:]:
            avail(u)
    elif a[0] == "get":
        get(a[1], a[2], a[3] if len(a) > 3 else None)
    elif a[0] == "cdx":
        cdx(a[1], a[2] if len(a) > 2 else None)
