"""Fetch a URL and print only lines matching keywords (keeps context small)."""
import re
import sys

import requests

HDR = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                   " (KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def strip_html(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</(p|div|li|h[1-6]|tr|section)>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&#39;", "'").replace("&quot;", '"')
                .replace("&lt;", "<").replace("&gt;", ">"))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text)


def main():
    url = sys.argv[1]
    kws = [k.lower() for k in sys.argv[2:]]
    r = requests.get(url, headers=HDR, timeout=45)
    body = r.text
    print("HTTP", r.status_code, "len", len(body), url)
    text = body if url.endswith(".json") else strip_html(body)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not kws:
        print("\n".join(lines[:200]))
        return
    hits = 0
    for i, ln in enumerate(lines):
        low = ln.lower()
        if any(k in low for k in kws):
            ctx = " | ".join(lines[max(0, i - 1):i + 2])
            print("---", ctx[:1400])
            hits += 1
            if hits > 60:
                print("...more matches truncated")
                break
    print("### matches:", hits)


if __name__ == "__main__":
    main()
