"""Mojeek / marginalia style general web search fallback via requests."""
import html
import re
import sys
import time
from urllib.parse import quote_plus

import requests

S = requests.Session()
S.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.9",
    }
)


def mojeek(q, tries=3, pause=6.0):
    url = "https://www.mojeek.com/search?q=" + quote_plus(q)
    r = None
    for a in range(tries):
        try:
            r = S.get(url, timeout=60)
        except Exception as e:  # noqa: BLE001
            print("!!", type(e).__name__, e)
            time.sleep(pause)
            continue
        if r.status_code != 200:
            print("!! http", r.status_code)
            time.sleep(pause * (a + 1))
            continue
        break
    print("##### MOJEEK: " + q + "  [" + str(None if r is None else r.status_code) + "]")
    if r is None or r.status_code != 200:
        return
    t = r.text
    blocks = re.findall(r'<a class="ob"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S)
    if not blocks:
        blocks = re.findall(r'<h2><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h2>', t, re.S)
    if not blocks:
        blocks = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>\s*<h2[^>]*>(.*?)</h2>', t, re.S)
    snippets = re.findall(r'<p class="s">(.*?)</p>', t, re.S)
    for i, (u, ttl) in enumerate(blocks[:14]):
        clean = html.unescape(re.sub(r"<[^>]+>", "", ttl)).strip()
        print("- %s" % clean)
        print("    %s" % html.unescape(u))
        if i < len(snippets):
            print("    > " + html.unescape(re.sub(r"<[^>]+>", "", snippets[i])).strip()[:400])
    if not blocks:
        print("   (no parsed results; len=%d)" % len(t))
    print()
    time.sleep(5.0)


if __name__ == "__main__":
    for q in sys.argv[1:]:
        mojeek(q)
