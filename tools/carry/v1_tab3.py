import pdfplumber, os
OUT = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(OUT, "_v1_mdpi-res-noV.bin")
with pdfplumber.open(src) as pdf:
    for pi in (9, 10):   # pages 10-11 (0-indexed) hold Tables 3 and 4
        t = pdf.pages[pi].extract_tables()
        print(f"\n########## PAGE {pi+1} : {len(t)} tables ##########")
        for tb in t:
            for row in tb:
                cells = ["" if c is None else " ".join(c.split()) for c in row]
                print(" | ".join(cells))
            print("  " + "-"*70)
