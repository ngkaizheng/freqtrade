"""Nail down freqtrade's leveraged accounting from a single exported trade,
rather than inferring it. The question: what is stake_amount (margin or
notional), and what price does a -3.6 stoploss become at 20x?
"""

import glob
import json
import zipfile

import pandas as pd

pd.set_option("display.max_columns", None)


def load(cell):
    f = glob.glob(f"user_data/backtest_results/matrix/{cell}/backtest-result-*.zip")[0]
    z = zipfile.ZipFile(f)
    st = json.loads(z.read(z.namelist()[0]))["strategy"]["ShortBreakout4hLev"]
    return pd.DataFrame(st["trades"])


for cell in ("base_c500_l1", "base_c500_l20"):
    t = load(cell)
    r = t[t["exit_reason"] == "stop_loss"].iloc[0]
    lev = float(r["leverage"])
    o = float(r["open_rate"])
    c = float(r["close_rate"])
    amount = float(r["amount"])
    stake = float(r["stake_amount"])
    notional = amount * o
    print(f"--- {cell} (leverage={lev:g}) ---")
    print(f"  open={o}  close={c}  amount={amount:.6f}  stake={stake:.4f}")
    print(f"  notional = amount*open = {notional:.4f}   stake*lev = {stake*lev:.4f}")
    print(f"  price move (short) = {(c/o - 1)*100:+.4f}%")
    print(f"  price move * leverage          = {(c/o - 1)*lev*100:+.4f}%")
    print(f"  reported profit_ratio          = {float(r['profit_ratio'])*100:+.4f}%")
    print(f"  reported profit_abs            = {float(r['profit_abs']):+.4f}")
    print(f"  notional*price_move            = {notional*(o-c)/o:+.4f}")
    print(f"  stake*lev*price_move           = {stake*lev*(o-c)/o:+.4f}")
    print(f"  stop price implied by -0.036   = {o*(1 + 0.036/lev):.6f}  vs close={c:.6f}")
    print()
