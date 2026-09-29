import pdfplumber, os
OUT = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(OUT, "_v2_he_fundamentals_2212.06888.pdf")
ts = {"vertical_strategy": "text", "horizontal_strategy": "text",
      "snap_tolerance": 3, "join_tolerance": 3, "intersection_tolerance": 3}
want = ["Return Decomposition", "Comparison of Different Arbitrage Trading Strategies",
        "The clamp versus a linear funding rate", "Sample Descriptions"]
with pdfplumber.open(src) as pdf:
    for pi, pg in enumerate(pdf.pages):
        t = pg.extract_text() or ""
        if any(w in t for w in want):
            print(f"\n########## PDF PAGE {pi+1} ##########")
            for tb in pg.extract_tables(ts):
                for row in tb:
                    cells = ["" if c is None else " ".join(c.split()) for c in row]
                    if any(cells):
                        print(" | ".join(cells))
                print("  " + "-"*70)
