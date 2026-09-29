"""DuckDuckGo HTML search via requests (fallback general web search)."""
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
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
)


def ddg(q, tries=4, pause=9.0):
    out = []
    for endpoint in (
        "https://lite.duckduckgo.com/lite/?q=",
        "https://html.duckduckgo.com/html/?q=",
    ):
        r = None
        for a in range(tries):
            try:
                r = S.get(endpoint + quote_plus(q), timeout=60)
            except Exception as e:  # noqa: BLE001
                print("!!", type(e).__name__, e)
                time.sleep(pause)
                continue
            if r.status_code != 200:
                print("!! http", r.status_code, endpoint)
                time.sleep(pause * (a + 1))
                continue
            break
        if r is not None and r.status_code == 200:
            break
    print("##### DDG: " + q + "  [" + str(None if r is None else r.status_code) + "]")
    if r is None or r.status_code != 200:
        return
    t = r.text
    res = re.findall(
        r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>', t, re.S
    )
    if not res:
        res = re.findall(r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S)
    snips = re.findall(r'<a class="result__snippet".*?>(.*?)</a>', t, re.S)
    if not snips:
        snips = re.findall(r'<td class="result-snippet">(.*?)</td>', t, re.S)
    for i, (u, ttl) in enumerate(res[:12]):
        clean = re.sub(r"<[^>]+>", "", ttl)
        clean = html.unescape(clean).strip()
        uu = html.unescape(u)
        m = re.search(r"uddg=([^&]+)", uu)
        if m:
            from urllib.parse import unquote

            uu = unquote(m.group(1))
        print("- %s" % clean)
        print("    %s" % uu)
        if i < len(snips):
            s = re.sub(r"<[^>]+>", "", snips[i])
            print("    > " + html.unescape(s).strip()[:400])
    if not res:
        print("   (no parsed results; len=%d)" % len(t))
    print()
    time.sleep(9.0)


if __name__ == "__main__":
    for q in sys.argv[1:]:
        ddg(q)
