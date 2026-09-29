"""q4reg_alllinks.py -- list all links on pages whose href OR anchor text matches a regex.

Usage: python q4reg_alllinks.py <regex> <url> [url2 ...]
"""
import re
import sys
import pathlib
import html as _html
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from q4reg_fetch import UA  # noqa: E402


def main():
    pat = re.compile(sys.argv[1], re.I)
    for url in sys.argv[2:]:
        try:
            r = requests.get(url, headers=UA, timeout=90, allow_redirects=True)
        except Exception as e:
            print(f"### {url} -> ERR {e}")
            continue
        print(f"### {url}  status={r.status_code} len={len(r.text)}")
        out = []
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S | re.I):
            href, txt = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
            txt = re.sub(r"\s+", " ", _html.unescape(txt)).strip()
            if pat.search(href) or (txt and pat.search(txt)):
                out.append((txt[:100], href))
        seen = set()
        for t, h in out:
            if h in seen:
                continue
            seen.add(h)
            print("   ", t, "\n      ", h)
        if not out:
            print("    [no matching links]")


if __name__ == "__main__":
    main()
