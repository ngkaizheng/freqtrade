"""q4reg_batch.py -- fetch many docs (pdf or html) in one process, writing .txt.

Manifest lines:  <mode>\t<url>\t<outbase>
"""
import sys
import io
import traceback
import pathlib
import requests
from pypdf import PdfReader

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from q4reg_fetch import UA, to_text  # noqa: E402


def get(url, timeout=180):
    r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
    print(f"    status={r.status_code} bytes={len(r.content)} ct={r.headers.get('content-type','')[:35]}")
    r.raise_for_status()
    return r


def main():
    man = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    outdir = pathlib.Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    for line in man:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        mode, url, base = line.split("\t")
        out = outdir / f"{base}.txt"
        if out.exists() and out.stat().st_size > 2000:
            print(f"[skip] {out.name}")
            continue
        print(f"[get] {url}")
        try:
            r = get(url)
            if r.content[:4] == b"%PDF" or mode == "pdf":
                if r.content[:4] != b"%PDF":
                    print("    !! not a PDF, head:", r.content[:100])
                    continue
                rd = PdfReader(io.BytesIO(r.content))
                print(f"    pages={len(rd.pages)}")
                parts = []
                for i, pg in enumerate(rd.pages):
                    try:
                        parts.append(f"\n\n=== PAGE {i+1} ===\n" + (pg.extract_text() or ""))
                    except Exception as e:
                        parts.append(f"\n\n=== PAGE {i+1} ===\n[extract error: {e}]")
                txt = "".join(parts)
            else:
                txt = to_text(r.text)
            out.write_text(txt, encoding="utf-8")
            print(f"    wrote {out.name} ({len(txt)} chars)")
        except Exception as e:
            print("    FAILED:", e)
            traceback.print_exc(limit=2)


if __name__ == "__main__":
    main()
