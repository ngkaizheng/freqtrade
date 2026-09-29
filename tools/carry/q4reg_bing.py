"""q4reg_bing.py -- locate URLs via Bing HTML (locator only; always fetch the
primary document before quoting it).

Usage: python q4reg_bing.py "query" ["query2" ...]
"""
import sys
import re
import html as _html
import requests

sys.stdout.reconfigure(encoding="utf-8")
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def main():
    for q in sys.argv[1:]:
        url = "https://www.bing.com/search?q=" + requests.utils.quote(q) + "&count=20"
        try:
            r = requests.get(url, headers=UA, timeout=60)
        except Exception as e:
            print(f"### {q} -> ERR {e}")
            continue
        print(f"### {q}  status={r.status_code} len={len(r.text)}")
        seen = set()
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
            u, t = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
            t = _html.unescape(t.strip())
            if "bing.com" in u or "microsoft" in u or u in seen:
                continue
            if len(t) < 12:
                continue
            seen.add(u)
            print("   ", t[:110], "\n      ", u)


if __name__ == "__main__":
    main()
