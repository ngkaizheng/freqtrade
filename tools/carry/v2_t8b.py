import pdfplumber, os, re
OUT = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(OUT, "_v2_he_fundamentals_2212.06888.pdf")
with pdfplumber.open(src) as pdf:
    n = len(pdf.pages)
    print("pages", n)
    for pi in range(35, 45):
        if pi >= n: break
        t = pdf.pages[pi].extract_text() or ""
        print(f"\n##### PDF PAGE {pi+1} #####")
        print(t[:1800])
