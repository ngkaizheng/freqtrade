import pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)
C = r"user_data/strategy_factory_runs/v2/20260926-phaseC"
cr = pd.read_csv(C+"/conditional_returns.csv")
h = cr[cr.hypothesis_id.str.startswith("H13_")]
print("=== H13 rows:", len(h), "===")
print(h.to_string())
