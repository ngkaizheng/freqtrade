"""q4reg_ddglite.py -- locate URLs via DuckDuckGo LITE (form POST). Locator only.

Usage: python q4reg_ddglite.py "query" ["query2" ...]
"""
import sys
import re
import html as _html
import requests

sys.stdout.reconfigure(encoding="utf-8")
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://lite.duckduckgo.com",
    "Referer": "https://lite.duckduckgo.com/",
    "Content-Type": "application/x-www-form-urlencoded",
}


def main():
    for q in sys.argv[1:]:
        s = requests.Session()
        try:
            r = s.post("https://lite.duckduckgo.com/lite/", data={"q": q}, headers=HDRS, timeout=60)
        except Exception as e:
            print(f"### {q} -> ERR {e}")
            continue
        print(f"### {q}  status={r.status_code} len={len(r.text)}")
        seen = set()
        for m in re.finditer(r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
            u, t = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
            if "uddg=" in u:
                u = requests.utils.unquote(u.split("uddg=")[1].split("&")[0])
            if u in seen:
                continue
            seen.add(u)
            print("   ", _html.unescape(t.strip())[:110], "\n      ", u)
        if not seen:
            txt = re.sub(r"<[^>]+>", " ", r.text)
            print("    ", re.sub(r"\s+", " ", txt)[:400])


if __name__ == "__main__":
    main()
