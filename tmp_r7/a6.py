import pandas as pd, numpy as np
D = r"user_data/strategy_factory_runs/v2/phase-d-validation-20260926"
print("=== validation_by_symbol.csv ==="); print(pd.read_csv(D+"/validation_by_symbol.csv").to_string())
print(); print("=== uncertainty_diagnostics.csv ==="); print(pd.read_csv(D+"/uncertainty_diagnostics.csv").to_string())
print(); print("=== regime_attribution.csv ==="); print(pd.read_csv(D+"/regime_attribution.csv").to_string())
