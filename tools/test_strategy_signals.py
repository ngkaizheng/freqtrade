import importlib.util
import sys
from pathlib import Path
import pandas as pd

# Paths
repo_root = Path(__file__).resolve().parents[1]
strategy_path = repo_root / 'user_data' / 'strategies' / 'always_trade.py'
data_path = repo_root / 'user_data' / 'data' / 'binance' / 'ETH_USDT-1m.feather'

# Load strategy module from file
spec = importlib.util.spec_from_file_location('always_trade', str(strategy_path))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Find strategy class
StrategyClass = None
for attr in dir(mod):
    obj = getattr(mod, attr)
    try:
        if hasattr(obj, '__mro__') and any(c.__name__ == 'IStrategy' for c in obj.__mro__):
            StrategyClass = obj
            break
    except Exception:
        pass

if StrategyClass is None:
    print('Strategy class not found in module')
    sys.exit(2)

# Read data
if not data_path.exists():
    print('Data file not found:', data_path)
    sys.exit(2)

df = pd.read_feather(str(data_path))

# Ensure expected columns exist
print('Columns sample:', df.columns[:10])

# Instantiate strategy
strategy = StrategyClass()

# Simulate strategy methods
df2 = strategy.populate_indicators(df.copy(), {})
df2 = strategy.populate_entry_trend(df2, {})
df2 = strategy.populate_exit_trend(df2, {})

# Print signal sums and first few rows with signals
for col in ['enter_long', 'exit_long', 'enter_short', 'exit_short']:
    if col in df2.columns:
        print(f"{col}: total={int(df2[col].sum())}")
    else:
        print(f"{col}: MISSING")

print('\nRows with enter_long (first 10):')
print(df2.loc[df2.get('enter_long', 0) == 1, ['date', 'open', 'high', 'low', 'close', 'volume']].head(10))
print('\nRows with exit_long (first 10):')
print(df2.loc[df2.get('exit_long', 0) == 1, ['date', 'open', 'high', 'low', 'close', 'volume']].head(10))
