"""Batch doc fetch with jina / wayback / direct fallbacks. Prints first N chars of each."""
import json
import sys
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"}


def try_urls(url, label, limit=6000, timeout=45):
    cands = [url]
    try:
        w = requests.get("http://archive.org/wayback/available?url=" + requests.utils.quote(url, safe=""),
                         headers=UA, timeout=25).json()
        snap = ((w.get("archived_snapshots") or {}).get("closest") or {})
        if snap.get("timestamp"):
            cands.append(f"https://web.archive.org/web/{snap['timestamp']}id_/{url}")
    except Exception as e:  # noqa: BLE001
        print(f"  wayback lookup failed: {e}")
    cands.append("https://r.jina.ai/" + url)
    for c in cands:
        if c == url:
            continue
        cands.insert(0, c)
    cands = [url, "https://r.jina.ai/" + url] + cands[2:]
    for c in cands:
        try:
            r = requests.get(c, headers=UA, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            print(f"##### {label} FAIL {c[:110]} :: {e}")
            continue
        body = r.text
        ok = r.status_code == 200 and len(body.strip()) > 400
        print(f"##### {label} [{r.status_code}] len={len(body)} via {c[:130]}")
        if ok:
            print(body[:limit])
            print()
            return body
    return None


if __name__ == "__main__":
    label, url = sys.argv[1], sys.argv[2]
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else 6000
    try_urls(url, label, lim)
