import yfinance as yf
import pandas as pd
import os

# The default cache (~/AppData/Local/py-yfinance) may not be writable under the
# current sandbox, so point yfinance at a writable folder inside the workspace.
# Must be called BEFORE any ticker is fetched.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cache_dir = os.path.join(BASE_DIR, ".yfinance_cache")
os.makedirs(cache_dir, exist_ok=True)
yf.set_tz_cache_location(cache_dir)

TICKER = "ADI"
INITIAL_CAPITAL = 10_000

ticker = yf.Ticker(TICKER)
df = ticker.history(
    start="2015-01-01",
    end="2026-09-17",
    auto_adjust=True
)

if df.empty:
    raise SystemExit("ERROR: yfinance returned empty data. Check network connection.")

# Keep only needed columns
df = df[["Open", "Close"]].dropna()

print(f"Data range: {df.index[0].date()} to {df.index[-1].date()}, {len(df)} trading days")

# Moving averages
df["MA20"] = df["Close"].rolling(20).mean()
df["MA50"] = df["Close"].rolling(50).mean()

# Golden cross / Death cross
df["Signal"] = (
    df["MA20"] > df["MA50"]
).astype(int)

df["Trade"] = df["Signal"].diff()

# Simulate trading
cash = INITIAL_CAPITAL
shares = 0.0
trades = []

for i in range(len(df) - 1):
    signal = df["Trade"].iloc[i]

    # Execute on next day's opening price
    next_open = float(df["Open"].iloc[i + 1])
    date = df.index[i + 1]

    if signal == 1 and shares == 0:
        shares = cash / next_open
        cash = 0
        trades.append({
            "Date": date,
            "Action": "BUY",
            "Price": round(next_open, 2)
        })

    elif signal == -1 and shares > 0:
        cash = shares * next_open
        shares = 0
        trades.append({
            "Date": date,
            "Action": "SELL",
            "Price": round(next_open, 2)
        })

# Close any remaining position at last close
if shares > 0:
    final_price = float(df["Close"].iloc[-1])
    cash = shares * final_price

final_value = cash
profit = final_value - INITIAL_CAPITAL
return_pct = profit / INITIAL_CAPITAL * 100

# Buy and hold comparison
buy_hold_return = (
    float(df["Close"].iloc[-1]) /
    float(df["Close"].iloc[0]) - 1
) * 100

print(f"\n{'='*50}")
print(f"Stock: {TICKER}")
print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
print(f"Final Value: ${final_value:,.2f}")
print(f"Profit: ${profit:,.2f}")
print(f"Return: {return_pct:.2f}%")
print(f"Buy & Hold Return: {buy_hold_return:.2f}%")
print(f"Trades: {len(trades)}")
print(f"{'='*50}")

print("\nTrade History:")
trade_df = pd.DataFrame(trades)
if not trade_df.empty:
    print(trade_df.to_string(index=False))
else:
    print("No trades executed.")
