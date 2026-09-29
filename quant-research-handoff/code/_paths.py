"""
路径解析 —— 让研究脚本在两种布局下都能运行
=============================================
  (A) 原始研究工作区：<root>/run_h1.py        → <root>/backtest_output, <root>/data
  (B) 交接包：        <pkg>/code/run_h1.py    → <pkg>/outputs,         <pkg>/data

用法（在研究脚本顶部）：
    from _paths import PKG_ROOT, DATA_CACHE, DATA_LONG, OUT_DIR
"""
import os
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))


def _find_root_and_dirs():
    """向上探测包含 data/ 的根目录，并解析输出目录名。"""
    cands = [_HERE, os.path.dirname(_HERE)]
    for c in cands:
        if os.path.isdir(os.path.join(c, "data")):
            out = os.path.join(c, "outputs")
            if not os.path.isdir(out):
                out = os.path.join(c, "backtest_output")
            return (c,
                    os.path.join(c, "data", "cache"),
                    os.path.join(c, "data", "cache_long"),
                    out)
    raise SystemExit(
        f"ERROR: 找不到 data/ 目录。已尝试：{cands}\n"
        f"       _paths.py 需位于工作区根目录或其 code/ 子目录内。")


PKG_ROOT, DATA_CACHE, DATA_LONG, OUT_DIR = _find_root_and_dirs()
os.makedirs(OUT_DIR, exist_ok=True)


def ensure_quant_importable():
    """把含 quant/ 的目录加入 sys.path（交接包中为 code/）。"""
    import sys
    for p in (os.path.join(PKG_ROOT, "code"), PKG_ROOT):
        if os.path.isdir(os.path.join(p, "quant")):
            if p not in sys.path:
                sys.path.insert(0, p)
            return p
    return None


if __name__ == "__main__":
    print(f"PKG_ROOT   = {PKG_ROOT}")
    print(f"DATA_CACHE = {DATA_CACHE}  ({len(glob.glob(os.path.join(DATA_CACHE,'*.csv')))} csv)")
    print(f"DATA_LONG  = {DATA_LONG}  ({len(glob.glob(os.path.join(DATA_LONG,'*.csv')))} csv)")
    print(f"OUT_DIR    = {OUT_DIR}")
    q = ensure_quant_importable()
    print(f"quant 路径 = {q}")
