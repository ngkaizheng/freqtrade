"""q4reg_mojeek.py -- locate URLs via Mojeek (bot-friendly). Locator only.

Usage: python q4reg_mojeek.py "query" ["query2" ...]
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
        url = "https://www.mojeek.com/search?q=" + requests.utils.quote(q)
        try:
            r = requests.get(url, headers=UA, timeout=60)
        except Exception as e:
            print(f"### {q} -> ERR {e}")
            continue
        print(f"### {q}  status={r.status_code} len={len(r.text)}")
        seen = set()
        n = 0
        for m in re.finditer(r'<a href="(https?://[^"]+)"[^>]*class="ob"', r.text):
            u = m.group(1)
            if u in seen:
                continue
            seen.add(u)
            print("   ", u)
            n += 1
        if n == 0:
            for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.{0,200}?)</a>', r.text, re.S):
                u = m.group(1)
                if "mojeek" in u or u in seen:
                    continue
                t = _html.unescape(re.sub(r"<[^>]+>", "", m.group(2)).strip())
                if len(t) < 12:
                    continue
                seen.add(u)
                print("   ", t[:100], "\n      ", u)
                n += 1
                if n > 25:
                    break


if __name__ == "__main__":
    main()
