"""
Q5.2: exact collateral requirement / liquidation price for a SHORT USD-M perp,
derived from Binance's own published definitions.

Official source (both quoted verbatim in the report):
  "Maintenance Margin = Notional Position Value * Maintenance Margin Rate
                        - Maintenance Amount"
  https://www.binance.com/en/support/faq/360033162192
  tiers: https://www.binance.com/en/futures/trading-rules/perpetual/leverage-margin

Model: single-currency cross account, ONE short of size Q entered at P, wallet
balance WB, no other positions.  Equity after the mark moves to X is
  E(X) = WB + (P - X) * Q
Liquidation when E(X) = MaintenanceMargin(X) = X*Q*MMR - MA.
Everything below is arithmetic from those two official lines, not a quoted claim.
"""

TIERS = [  # (notional_lo, notional_hi, max_lev, mmr, maint_amount)
    (0, 300_000, 150, 0.0040, 0),
    (300_000, 800_000, 100, 0.0050, 300),
    (800_000, 3_000_000, 75, 0.0065, 1_500),
    (3_000_000, 12_000_000, 50, 0.0100, 12_000),
    (12_000_000, 70_000_000, 25, 0.0200, 132_000),
]


def liq_price_short(px: float, wb: float, mmr: float, ma: float = 0.0) -> float:
    """Liquidation mark price for a short, derived from the official MM definition."""
    q = wb * 0 + 1.0  # per unit of position; caller supplies WB per unit below
    raise NotImplementedError


def liq_for_position(P: float, N: float, mmr: float, ma: float, lev: float) -> float:
    """Liquidation mark price. N = notional, P = entry, lev = chosen leverage,
    WB = N/lev. Returns the liquidation MARK price."""
    Q = N / P
    WB = N / lev
    # WB + (P - X)Q = X*Q*mmr - ma   ->   X(1+mmr) = (WB + P*Q + ma)/Q
    return (WB / Q + P + ma / Q) / (1.0 + mmr)


def collateral_for_move(P: float, N: float, mmr: float, ma: float, d: float) -> float:
    """Wallet balance (USDT) required in the FUTURES account for a SHORT to survive
    an adverse move of d (fraction) with the mark reaching P*(1+d)."""
    Q = N / P
    X = P * (1.0 + d)
    return Q * (X * (1.0 + mmr) - P) - ma


def main() -> None:
    P = 84_000.0
    print("Assumed entry mark P = USD 84,000 (the live BTCUSDT mark at time of writing).")
    print()
    print("A) LIQUIDATION MARK PRICE OF A SHORT vs LEVERAGE  (Tier 1: MMR=0.40%, MA=0)")
    print(f"{'leverage':>9} {'wallet bal (pct of N)':>22} {'liq mark':>12} "
          f"{'move to liq':>13} {'liq dist from entry':>21}")
    for lev in (150, 125, 100, 75, 50, 25, 20, 10, 5, 3, 2):
        x = liq_for_position(P, P, 0.0040, 0.0, lev)
        print(f"{lev:>8}x {100.0 / lev:>21.4f}% {x:>12,.0f} "
              f"{100 * (x / P - 1):>12.2f}% {100 * (x / P - 1):>20.2f}%")

    print()
    print("B) COLLATERAL NEEDED IN THE USD-M ACCOUNT TO SURVIVE AN ADVERSE MOVE")
    print("   (short, Tier 1: MMR=0.40%, MA=0; N = 1,000,000 USDT notional)")
    N = 1_000_000.0
    print(f"{'adverse move':>14} {'collateral needed':>19} {'as % of notional':>18} "
          f"{'= leverage you can run':>25}")
    for d in (0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.80, 1.00):
        c = collateral_for_move(P, N, 0.0040, 0.0, d)
        print(f"{100 * d:>13.0f}% {c:>19,.0f} {100 * c / N:>17.2f}% "
              f"{N / c:>24.2f}x")

    print()
    print("C) SAME, BUT THE SPOT LEG IS 1,000,000 USDT AND THE PERP IS 1,000,000 USDT")
    print("   (equal notional). The spot leg sits in a SEPARATE account and does NOT")
    print("   reduce the number above.  Only Portfolio Margin netting does.")
    print(f"{'adverse move':>14} {'futures collateral needed':>26} "
          f"{'+ spot leg value':>17} {'effective leverage':>18}")
    for d in (0.10, 0.20, 0.30, 0.50):
        c = collateral_for_move(P, N, 0.0040, 0.0, d)
        spot = N * d
        print(f"{100 * d:>13.0f}% {c:>26,.0f} {spot:>17,.0f} "
              f"{(N + c) / (spot + c):>17.2f}x")

    print()
    print("D) MARGIN ASSET DE-PENGSION: collateral is quoted in USDT/USDC, the short")
    print("   is not. A short of NOTIONAL N still owes N USDT-equivalent of cover.")
    print("   Measured on the live account, same Tier-1 maths:")
    for depeg in (0.0, 0.05, 0.10, 0.15, 0.25):
        # effective notional in good-collateral units rises by 1/(1-depeg)
        neff = N / (1 - depeg)
        c = collateral_for_move(P, neff, 0.0040, 0.0, 0.30)
        print(f"   margin asset at {100 * depeg:>4.0f}% discount -> 30% adverse move "
              f"needs {c:>12,.0f} USDT ({100 * c / N:>6.2f}% of N, "
              f"was {100 * collateral_for_move(P, N, 0.0040, 0.0, 0.30) / N:>5.2f}%)")

    print()
    print("E) THE ONE-SETTLEMENT FUNDING SHOCK (funding deducted from position margin)")
    print("   Official: 'If your account balance is insufficient, the funding fees (if")
    print("   any) will be deducted from your position margin, which may affect your")
    print("   liquidation price.'")
    for fr in (0.0001, 0.003, 0.0075, 0.02, -0.02):
        pay = N * fr
        c = collateral_for_move(P, N, 0.0040, 0.0, 0.30) + max(pay, 0.0)
        print(f"   funding {100 * fr:>+6.2f}%/8h -> one payment {pay:>10,.0f} USDT; "
              f"collat for a 30% adverse move rises to {c:>10,.0f} "
              f"({100 * c / N:.2f}% of N)")


if __name__ == "__main__":
    main()
