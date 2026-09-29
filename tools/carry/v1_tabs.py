import pdfplumber, os
OUT = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(OUT, "_v1_mdpi-res-noV.bin")
ts = {"vertical_strategy": "text", "horizontal_strategy": "text", "snap_tolerance": 3,
      "join_tolerance": 3, "intersection_tolerance": 3}
with pdfplumber.open(src) as pdf:
    for pi in range(8, 16):
        pg = pdf.pages[pi]
        txt = pg.extract_text() or ""
        if "Table 3" in txt or "Rank" in txt and "Avg Spread" in txt or "Table 4" in txt or "Table 8" in txt:
            print(f"\n########## PAGE {pi+1} ##########")
            for tb in pg.extract_tables(ts):
                for row in tb:
                    cells = ["" if c is None else " ".join(c.split()) for c in row]
                    if any(cells): print(" | ".join(cells))
                print("  " + "-"*66)
