"""q4reg_probe.py -- probe candidate URLs from a manifest; report status/type/size.

Manifest lines: <url> [label]
"""
import sys
import pathlib
import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from q4reg_fetch import UA  # noqa: E402


def main():
    man = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    for line in man:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        url = parts[0]
        label = parts[1] if len(parts) > 1 else ""
        try:
            r = requests.get(url, headers=UA, timeout=90, allow_redirects=True)
            ct = r.headers.get("content-type", "")[:35]
            print(f"{r.status_code} {len(r.content):>9} {ct:<36} pdf={r.content[:4]!r} {label or url}")
        except Exception as e:
            print(f"ERR {type(e).__name__:<18} {label or url}: {e}")


if __name__ == "__main__":
    main()
