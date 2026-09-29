import re
checks = {
 "tools/strategy_factory_v2/discovery.py": [(145,147),(316,318)],
 "tools/strategy_factory_v2/discovery_engine.py": [(208,236),(307,320),(360,370),(418,421),(119,150)],
 "tools/strategy_factory_v2/phase_c.py": [(57,59),(345,350)],
 "tools/strategy_factory_v2/phase_d.py": [(52,66),(210,216)],
 "tools/strategy_factory_v2/phase_d_main.py": [(92,94),(115,120)],
}
for f, rngs in checks.items():
    lines = open(r"E:\FreqTrader\freqtrade\\"+f.replace("/","\\"), encoding="utf-8").read().splitlines()
    print("#####", f)
    for a,b in rngs:
        for i in range(a-1, min(b, len(lines))):
            print(f"{i+1:5d}| {lines[i]}")
        print("  ...")
