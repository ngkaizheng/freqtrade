"""q4reg_links.py -- list links on a page, filtered by a substring."""
import sys
import re
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}


def main():
    url = sys.argv[1]
    filt = sys.argv[2] if len(sys.argv) > 2 else ""
    r = requests.get(url, headers=UA, timeout=90)
    sys.stdout.reconfigure(encoding="utf-8")
    print("status", r.status_code, "len", len(r.text))
    hrefs = sorted(set(re.findall(r'href=["\']([^"\']+)["\']', r.text)))
    for h in hrefs:
        if filt.lower() in h.lower():
            print(h)


if __name__ == "__main__":
    main()
