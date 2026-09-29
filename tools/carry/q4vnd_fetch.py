"""Scratch fetch harness for the Q4VND vendor-literature review.

Usage:
    python q4vnd_fetch.py <name> <url> [...]
    python q4vnd_fetch.py --find <regex> <name> [...]   # grep cached text
"""
import hashlib
import os
import re
import sys
import time

import requests

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "q4vnd_cache")
os.makedirs(CACHE, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HDRS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # Wayback `id_` snapshots arrive brotli-encoded with no usable decoder here;
    # asking for identity makes the plain replay path return real HTML.
    "Accept-Encoding": "identity",
    "Connection": "close",
}


def decompress(raw: bytes, hdrs) -> str:
    """Wayback id_ snapshots often arrive compressed with no Content-Encoding."""
    enc = (hdrs.get("Content-Encoding") or "").lower()
    orders = []
    if "br" in enc:
        orders = ["br", "zlib", "gzip"]
    elif "gzip" in enc:
        orders = ["gzip", "zlib"]
    else:
        orders = ["br", "gzip", "zlib"]
    for how in orders:
        try:
            if how == "br":
                import brotli  # type: ignore

                return brotli.decompress(raw).decode("utf-8", "replace")
            if how == "gzip":
                import gzip

                return gzip.decompress(raw).decode("utf-8", "replace")
            import zlib

            return zlib.decompress(raw).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            continue
    return raw.decode("utf-8", "replace")


def strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<!--.*?-->", " ", raw)
    # keep block structure
    raw = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr|/section)[^>]*>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    import html as _html

    raw = _html.unescape(raw)
    raw = re.sub(r"[ \t\r\f\v\xa0]+", " ", raw)
    raw = re.sub(r"\n\s*\n\s*\n+", "\n\n", raw)
    return raw.strip()


def key(name):
    return os.path.join(CACHE, name + ".txt")


def do_fetch(name, url, refresh=False):
    p = key(name)
    if os.path.exists(p) and not refresh:
        print(f"[cache] {name}  {os.path.getsize(p)} bytes")
        return p
    try:
        r = requests.get(url, headers=HDRS, timeout=(8, 20), allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {name} {type(e).__name__}: {e}")
        return None
    ct = r.headers.get("content-type", "")
    if r.status_code != 200:
        print(f"[HTTP {r.status_code}] {name} {url}  ct={ct}")
    body = decompress(r.content, r.headers)
    if "json" in ct:
        try:
            body = r.json()
            import json

            body = json.dumps(body, indent=1, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            pass
    else:
        body = strip_html(body)
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"### URL: {url}\n### STATUS: {r.status_code} CT: {ct}\n\n")
        f.write(body)
    print(f"[ok {r.status_code}] {name}  {len(body)} chars  <- {url}")
    return p


def do_find(rx, names):
    cre = re.compile(rx, re.I)
    for n in names:
        p = key(n)
        if not os.path.exists(p):
            print(f"-- {n}: NOT CACHED")
            continue
        txt = open(p, encoding="utf-8").read()
        print(f"\n===== {n} =====")
        lines = txt.split("\n")
        hits = 0
        for i, ln in enumerate(lines):
            if cre.search(ln):
                lo = max(0, i - 1)
                hi = min(len(lines), i + 3)
                print(f"  [L{i}] " + " | ".join(x.strip() for x in lines[lo:hi] if x.strip()))
                hits += 1
                if hits > 60:
                    print("  ...(truncated)")
                    break
        if not hits:
            print("  (no match)")


def do_search(q, engine="ddg"):
    """DuckDuckGo / Bing HTML endpoints - avoids the web_search tool entirely."""
    if engine == "bing":
        url = "https://www.bing.com/search?q=" + requests.utils.quote(q) + "&count=30"
        try:
            r = requests.get(url, headers=HDRS, timeout=(8, 25))
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] bing {type(e).__name__}: {e}")
            return
        print(f"[bing {r.status_code}] {q}")
        n = 0
        for m in re.finditer(r'<h2><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h2>', r.text, re.S):
            href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
            print(f"  {title.strip()}\n    {href}")
            n += 1
        if not n:
            print("  (no bing parse hits)")
        return
    url = "https://html.duckduckgo.com/html/?q=" + requests.utils.quote(q)
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": q},
            headers=HDRS,
            timeout=40,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] search {type(e).__name__}: {e}")
        return
    print(f"[search {r.status_code}] {q}")
    if r.status_code != 200:
        print("  (rate limited)")
        return
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
        href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        if "uddg=" in href:
            href = requests.utils.unquote(href.split("uddg=")[1].split("&")[0])
        print(f"  {title.strip()}\n    {href}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--find":
        do_find(a[1], a[2:])
    elif a and a[0] == "--search-bing":
        for q in a[1:]:
            do_search(q, "bing")
            time.sleep(2)
    elif a and a[0] == "--search":
        for q in a[1:]:
            do_search(q)
            time.sleep(6)
    else:
        for i in range(0, len(a) - 1, 2):
            do_fetch(a[i], a[i + 1])
            time.sleep(1)
