"""Try several public search front-ends via requests; print the first that works."""
import html
import re
import sys
import time
from urllib.parse import quote_plus

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HDRS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

ENGINES = [
    ("bing", "https://www.bing.com/search?q={q}&count=30"),
    ("ecosia", "https://www.ecosia.org/search?q={q}"),
    ("searxng-json", "https://searx.be/search?q={q}&format=json"),
    ("searxng-html", "https://searx.tiekoetter.com/search?q={q}"),
    ("marginalia", "https://search.marginalia.nu/search?query={q}"),
    ("yandex", "https://yandex.com/search/?text={q}"),
    ("brave", "https://search.brave.com/search?q={q}"),
]


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


def parse(name, t):
    out = []
    if name == "bing":
        for m in re.finditer(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>', t, re.S):
            out.append((m.group(1), m.group(2), ""))
        if not out:
            for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.{5,160}?)</a>', t, re.S):
                out.append((m.group(1), m.group(2), ""))
    elif name in ("searxng-json",):
        return out
    else:
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', t, re.S):
            out.append((m.group(1), m.group(2), ""))
    return out


def run(q):
    for name, tmpl in ENGINES:
        url = tmpl.format(q=quote_plus(q))
        try:
            r = requests.get(url, headers=HDRS, timeout=45)
        except Exception as e:  # noqa: BLE001
            print("  [%s] !! %s" % (name, type(e).__name__))
            continue
        print("  [%s] http %s len=%d" % (name, r.status_code, len(r.text)))
        if r.status_code != 200:
            continue
        if name == "searxng-json":
            try:
                d = r.json()
            except Exception:  # noqa: BLE001
                continue
            print("### SEARXNG: " + q)
            for res in d.get("results", [])[:12]:
                print("- " + clean(res.get("title", "")))
                print("    " + (res.get("url") or ""))
                print("    > " + clean(res.get("content", ""))[:400])
            print()
            return True
        res = parse(name, r.text)
        if not res:
            continue
        print("### " + name.upper() + ": " + q)
        for u, ttl, sn in res[:14]:
            ttl = clean(ttl)
            if not ttl or "javascript" in ttl.lower():
                continue
            print("- " + ttl)
            print("    " + html.unescape(u))
            s = clean(sn)
            if s:
                print("    > " + s[:400])
        print()
        return True
    print("  (no engine worked)")
    return False


if __name__ == "__main__":
    for q in sys.argv[1:]:
        print("==== " + q)
        ok = run(q)
        time.sleep(6 if ok else 2)
