"""回归测试：把本工作区已抓到的「跑得通但结论会错」的 bug 固化为自动化测试
================================================================================
用户观察：下一阶段最大的风险不是「找不到好策略」，而是「找到一个其实不存在的策略」。
因此把已踩过的坑做成可重复运行的测试，比继续加策略更重要。

已抓到的 3 类问题：
  Bug 1  NaN 幽灵信号
         (ma_fast > ma_slow).astype(int) 把 NaN 比较结果当 0，
         在 MA 首个有效日凭空产生金叉信号。（ADI 回测，5.45pp 差异）
  Bug 2  object dtype 上的 ~
         ~Series 在 object dtype 上返回 -2/-1（都是真值），
         导致每个 True 都被判为「变化点」。（H2 诊断，1874 vs 107）
  Bug 3  bool 经 json default=str 变成字符串
         'False' 非空即为真，下游读取全部误判。（H2 判定，0/4 被误读为 4/4）

另外验证引擎本身的正确性（复用 quant/engine.py 的自检）。

运行：python test_regressions.py
"""
import os
import sys
import json
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 路径定位：本文件在两种布局下都要能运行
#   (A) 原始研究工作区：<root>/test_regressions.py，数据在 <root>/data/
#   (B) 交接包：        <pkg>/methodology/test_regressions.py，
#                       数据在 <pkg>/data/，代码在 <pkg>/code/
# 自动探测，避免硬编码路径导致换环境即失效。
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATES = [_HERE, os.path.dirname(_HERE)]
BASE = None
for _c in _CANDIDATES:
    if os.path.isdir(os.path.join(_c, "data")):
        BASE = _c
        break
if BASE is None:
    raise SystemExit(
        f"ERROR: 找不到 data/ 目录。已尝试：{_CANDIDATES}\n"
        f"       本测试需要 data/cache_long/SPY.csv 与 data/cache/。")

DATA_LONG = os.path.join(BASE, "data", "cache_long")
DATA_CACHE = os.path.join(BASE, "data", "cache")
OUT_DIR = os.path.join(BASE, "outputs")
if not os.path.isdir(OUT_DIR):
    OUT_DIR = os.path.join(BASE, "backtest_output")

# quant 包可能在 BASE/quant 或 BASE/code/quant
for _p in (os.path.join(BASE, "code"), BASE):
    if os.path.isdir(os.path.join(_p, "quant")):
        sys.path.insert(0, _p)
        break

print(f"  根目录: {BASE}")

RESULTS = []


def check(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {name}" + (f"  — {detail}" if detail else ""))


print("=" * 100)
print("回归测试套件")
print("=" * 100)

# ============================================================ Bug 1
print("\n[1] NaN 幽灵信号：NaN 比较结果转 int 会凭空产生信号")
close = pd.Series([10.0, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
                  index=pd.date_range("2020-01-01", periods=12, freq="D"))
ma_f = close.rolling(3).mean()
ma_s = close.rolling(5).mean()

naive = (ma_f > ma_s).astype(int)
naive_trade = naive.diff().fillna(0)
# MA5 首个有效日在 idx 4；naive 在那里产生 +1（幽灵金叉）
ghost_pos = int(naive_trade[naive_trade == 1].index[0].day - 1) if (naive_trade == 1).any() else -1
first_valid = int(np.argmax(ma_s.notna().values))
has_ghost = bool(naive_trade.iloc[first_valid] == 1)
check("Bug1 复现：朴素写法在 MA 首个有效日产生幽灵 +1 信号", has_ghost,
      f"首个有效日 index={first_valid}, trade={naive_trade.iloc[first_valid]}")

# 正确写法：显式 mask
valid = ma_f.notna() & ma_s.notna()
safe = (ma_f > ma_s).astype(int)
prev_valid = valid.shift(1).fillna(False)
real_cross = pd.Series(0.0, index=close.index)
real_cross[valid & prev_valid & (safe == 1) & (safe.shift(1) == 0)] = 1.0
no_ghost = bool(real_cross.iloc[first_valid] != 1)
check("Bug1 修复：显式 valid mask 后无幽灵信号", no_ghost,
      f"首个有效日 trade={real_cross.iloc[first_valid]}")

# ============================================================ Bug 2
print("\n[2] object dtype 上的 ~ 返回 -2/-1（真值），把每个 True 判为变化点")
s_obj = pd.Series([True, True, False, True], dtype=object)
raw_tilde = ~s_obj
# ~ 在 object dtype 上产生 -1/-2（均为真值），而不是布尔取反
tilde_vals = set(int(v) for v in raw_tilde.values)
check("Bug2 复现：~ 在 object dtype 上产生 -1/-2 而非布尔",
      tilde_vals <= {-1, -2},
      f"~object = {sorted(tilde_vals)}（-1/-2 均为真值，误判为「发生变化」）")

# 正确写法：先 .astype(bool) 再 shift(fill_value=False)
b = pd.Series([True, True, False, True], dtype=bool)
entries = b & ~b.shift(1, fill_value=False)
# index 0（首个 True）与 index 3（False→True）是进入点，正确答案是 2
check("Bug2 修复：.astype(bool) + shift 得到正确的进入点",
      int(entries.sum()) == 2,
      f"entries={int(entries.sum())}（正确为 2：index 0 与 index 3）")

# 实测对比：真实数据上的差异量级
# ⚠️ 复现要点：必须让被取反的对象保持 object dtype。
#    `shift(1).fillna(False)` 会把 object 转回 bool，从而走 bool 语义、无法复现。
#    真实 bug 路径是 object Series 直接取反（NaN 变成 None，~None 得 -1/-2）。
try:
    d = pd.read_csv(os.path.join(DATA_LONG, "SPY.csv"),
                    index_col=0, parse_dates=True)
    cl = d["Close"].astype(float)
    ma200 = cl.rolling(200, min_periods=200).mean()
    below_obj = (cl < ma200).fillna(False).astype(object)
    # 保持 object：不用 fillna(False)，改用 fillna(True) 的语义等价写法会变 bool，
    # 因此这里直接用 map 构造布尔 object 序列来演示取反语义。
    prev_obj = below_obj.shift(1)
    prev_obj = prev_obj.where(prev_obj.notna(), False).astype(object)
    bad_cross = int((below_obj.astype(bool) & ~prev_obj.astype(object)).sum())
    # 正确
    below_b = below_obj.astype(bool)
    good_cross = int((below_b & ~below_b.shift(1, fill_value=False)).sum())
    check("Bug2 量级：object 取反 vs 正确写法在 SPY 上的差异",
          good_cross < 200 and bad_cross > 1000,
          f"object 取反={bad_cross}（≈每个 below 日）, 正确={good_cross}")
except Exception as e:
    check("Bug2 量级验证（需 SPY 数据）", False, str(e))

# ============================================================ Bug 3
print("\n[3] numpy.bool_ 经 json default=str 变成字符串（'False' 为真）")
# ⚠️ 精确说明：default=str 只对 json 无法原生序列化的类型触发。
#    Python bool 可原生序列化 → 不受影响；np.bool_ 不可 → 被转成 'False'。
p = os.path.join(OUT_DIR, "_test_json_bool.json")
os.makedirs(os.path.dirname(p), exist_ok=True)

with open(p, "w", encoding="utf-8") as fh:
    json.dump({"py_false": False}, fh, default=str)
l1 = json.load(open(p, encoding="utf-8"))
check("Bug3 澄清：Python bool 不受 default=str 影响（原生可序列化）",
      l1["py_false"] is False and isinstance(l1["py_false"], bool),
      f"读回 {l1['py_false']!r} (类型 {type(l1['py_false']).__name__})")

with open(p, "w", encoding="utf-8") as fh:
    json.dump({"np_false": np.bool_(False)}, fh, default=str)
l2 = json.load(open(p, encoding="utf-8"))
bad_read = bool(l2["np_false"])   # 'False' 非空 → True
check("Bug3 复现：np.bool_ 经 default=str 变字符串，False 被读为真值",
      bad_read and isinstance(l2["np_false"], str),
      f"写入 np.False_，读回 {l2['np_false']!r}（str），bool() = {bad_read}")

# 正确写法：显式转原生 bool
with open(p, "w", encoding="utf-8") as fh:
    json.dump({"np_false": bool(np.bool_(False))}, fh)
l3 = json.load(open(p, encoding="utf-8"))
check("Bug3 修复：显式 bool() 后类型与值都正确",
      l3["np_false"] is False,
      f"读回 {l3['np_false']!r} (类型 {type(l3['np_false']).__name__})")
os.remove(p)

# 顺带检查本工作区所有决策 JSON 是否还有字符串布尔
print("\n[3b] 扫描工作区决策 JSON，确认无字符串布尔残留")
for fn in ["h2_decision.json"]:
    fp = os.path.join(OUT_DIR, fn)
    if not os.path.exists(fp):
        continue
    j = json.load(open(fp, encoding="utf-8"))
    bad = []
    for layer in ("research", "validation"):
        for t, x in j.get(layer, {}).items():
            for k, v in x.items():
                if isinstance(v, str) and v in ("True", "False"):
                    bad.append(f"{layer}/{t}/{k}={v}")
    check(f"{fn} 无字符串布尔", len(bad) == 0,
          "干净" if not bad else f"发现 {len(bad)} 处：{bad[:3]}")

# ============================================================ 4 未来函数
print("\n[4] 未来函数：截断未来数据后，前段结果必须完全不变")
from quant.data import load_panel
from quant.engine import run_backtest

op2, cl2 = load_panel(["SPY", "QQQ"])
O = op2[["SPY", "QQQ"]].dropna()
w = pd.DataFrame(0.5, index=O.index, columns=["SPY", "QQQ"])
cut = len(O) - 200
full = run_backtest(w, O, cost_bps=0.0, rebalance="M")["equity"]
part = run_backtest(w.iloc[:cut], O.iloc[:cut], cost_bps=0.0, rebalance="M")["equity"]
diff = float((full.iloc[:cut] - part).abs().max())
check("Bug4 未来函数：截断后前段偏差", diff < 1e-12, f"max diff = {diff:.2e}")

# ============================================================ 5 执行时点
print("\n[5] 执行时点：不得在决策当日成交（无 off-by-one 提前）")
w1 = pd.DataFrame(1.0, index=O.index, columns=["SPY", "QQQ"])
r = run_backtest(w1, O, cost_bps=0.0, rebalance="D")
nz = r["weights"].abs().sum(axis=1) > 1e-9
first_hold = r["weights"].index[nz][0]
check("Bug5 首次建仓晚于首个交易日",
      first_hold > O.index[0], f"首次持仓 {first_hold.date()} > 首日 {O.index[0].date()}")

# ============================================================ 6 杠杆护栏
print("\n[6] 杠杆护栏：超配输入必须被归一化，不得产生隐性杠杆")
w3 = pd.DataFrame(0.5, index=O.index, columns=["SPY", "QQQ"])   # 合计 1.0，再叠加一列
op3, _ = load_panel(["SPY", "QQQ", "AAPL", "MSFT", "NVDA"])
O3 = op3.dropna()
w4 = pd.DataFrame(0.5, index=O3.index, columns=O3.columns)     # 5×0.5 = 2.5
r4 = run_backtest(w4, O3, cost_bps=0.0, rebalance="D")
mx = float(r4["weights"].sum(axis=1).max())
check("Bug6 超配被归一化（无杠杆）", mx <= 1.0 + 1e-9, f"最大敞口 = {mx:.6f}")

# ============================================================ 汇总
print("\n" + "=" * 100)
n_pass = sum(1 for _, p, _ in RESULTS if p)
n_tot = len(RESULTS)
print(f"结果：{n_pass}/{n_tot} 通过")
if n_pass < n_tot:
    print("失败项：")
    for n, p, d in RESULTS:
        if not p:
            print(f"  - {n}: {d}")
    sys.exit(1)
print("全部通过")
