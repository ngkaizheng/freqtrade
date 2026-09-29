"""q4reg_pdflinks.py -- list .pdf links reachable from a page (or two).

Usage: python q4reg_pdflinks.py <url1> [url2 ...]
"""
import re
import sys
import pathlib
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from q4reg_fetch import UA  # noqa: E402


def main():
    for url in sys.argv[1:]:
        try:
            r = requests.get(url, headers=UA, timeout=90, allow_redirects=True)
        except Exception as e:
            print(f"### {url} -> ERR {e}")
            continue
        print(f"### {url}  status={r.status_code} len={len(r.text)}")
        for h in sorted(set(re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', r.text, re.I))):
            print("   ", h)


if __name__ == "__main__":
    main()
