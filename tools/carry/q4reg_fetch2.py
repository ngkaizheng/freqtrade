"""q4reg_fetch2.py -- fetch with full browser headers (some sites 403 on plain UA).

Usage: python q4reg_fetch2.py <url> <out> [html|pdf]
"""
import sys
import pathlib
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from q4reg_fetch import to_text  # noqa: E402

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
}


def main():
    url, out = sys.argv[1], sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "html"
    r = requests.get(url, headers=HDRS, timeout=90, allow_redirects=True)
    print("status", r.status_code, "bytes", len(r.content), "ct", r.headers.get("content-type", "")[:40])
    if r.content[:4] == b"%PDF":
        pathlib.Path(out).write_bytes(r.content)
    else:
        pathlib.Path(out).write_text(to_text(r.text), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
