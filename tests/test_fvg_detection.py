"""
FVG Detection Diagnostic Script
Checks if FVGs are being detected from historical data
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from FairValueGaps import FVGDisplay


def diagnose_fvg_detection():
    """Check FVG detection from historical data"""

    print("="*60)
    print("FVG DETECTION DIAGNOSTIC")
    print("="*60)

    # Create FVG display instance
    fvg_display = FVGDisplay()

    # Check if historical data exists
    try:
        df = pd.read_csv('data/HistoricalData.csv')
        print(f"\n[OK] Historical data loaded: {len(df)} bars")
        print(f"Date range: {df.iloc[0]['DateTime']} to {df.iloc[-1]['DateTime']}")
    except Exception as e:
        print(f"\n[ERROR] Cannot load historical data: {e}")
        return

    # Load historical FVGs
    print("\n" + "="*60)
    print("LOADING HISTORICAL FVGs")
    print("="*60)

    fvg_display.load_historical_fvgs()

    # Show FVG summary
    total_fvgs = len(fvg_display.active_fvgs)
    bullish_fvgs = [f for f in fvg_display.active_fvgs if f['type'] == 'bullish' and not f.get('filled', False)]
    bearish_fvgs = [f for f in fvg_display.active_fvgs if f['type'] == 'bearish' and not f.get('filled', False)]
    filled_fvgs = [f for f in fvg_display.active_fvgs if f.get('filled', False)]

    print(f"\nTotal FVGs detected: {total_fvgs}")
    print(f"  - Unfilled Bullish: {len(bullish_fvgs)}")
    print(f"  - Unfilled Bearish: {len(bearish_fvgs)}")
    print(f"  - Filled: {len(filled_fvgs)}")

    # Get current price
    try:
        live_df = pd.read_csv('data/LiveFeed.csv')
        current_price = float(live_df.iloc[-1]['Last'])
        print(f"\nCurrent Price: {current_price:.2f}")
    except:
        current_price = df.iloc[-1]['Close']
        print(f"\nCurrent Price (from historical): {current_price:.2f}")

    # Show bullish FVGs (SHORT opportunities - gap UP leaves gap BELOW)
    print("\n" + "="*60)
    print("BULLISH FVGs (SHORT OPPORTUNITIES - BELOW PRICE)")
    print("="*60)

    if bullish_fvgs:
        bullish_below = [f for f in bullish_fvgs if f['top'] < current_price]
        bullish_above = [f for f in bullish_fvgs if f['bottom'] > current_price]
        bullish_at = [f for f in bullish_fvgs if f['bottom'] <= current_price <= f['top']]

        print(f"\nBullish FVGs BELOW current price (valid for SHORT): {len(bullish_below)}")
        # Sort by distance and show closest 10
        bullish_below_sorted = sorted(bullish_below, key=lambda f: abs(f['top'] - current_price))
        for i, fvg in enumerate(bullish_below_sorted[:10], 1):
            distance = fvg['top'] - current_price
            print(f"  {i}. Zone: {fvg['bottom']:.2f}-{fvg['top']:.2f} | "
                  f"Target: {fvg['top']:.2f} | Distance: {distance:+.2f}pts | "
                  f"Size: {fvg['gap_size']:.2f}pts")

        if bullish_above:
            print(f"\nBullish FVGs ABOVE current price (wrong direction - impossible): {len(bullish_above)}")
            for i, fvg in enumerate(bullish_above[:3], 1):
                print(f"  {i}. Zone: {fvg['bottom']:.2f}-{fvg['top']:.2f} (gap UP can't be above)")

        if bullish_at:
            print(f"\nBullish FVGs AT current price: {len(bullish_at)}")
            for i, fvg in enumerate(bullish_at[:3], 1):
                print(f"  {i}. Zone: {fvg['bottom']:.2f}-{fvg['top']:.2f} (price inside)")
    else:
        print("\n[!] NO BULLISH FVGs FOUND")

    # Show bearish FVGs (LONG opportunities - gap DOWN leaves gap ABOVE)
    print("\n" + "="*60)
    print("BEARISH FVGs (LONG OPPORTUNITIES - ABOVE PRICE)")
    print("="*60)

    if bearish_fvgs:
        bearish_above = [f for f in bearish_fvgs if f['bottom'] > current_price]
        bearish_below = [f for f in bearish_fvgs if f['top'] < current_price]
        bearish_at = [f for f in bearish_fvgs if f['bottom'] <= current_price <= f['top']]

        print(f"\nBearish FVGs ABOVE current price (valid for LONG): {len(bearish_above)}")
        # Sort by distance and show closest 10
        bearish_above_sorted = sorted(bearish_above, key=lambda f: abs(f['bottom'] - current_price))
        for i, fvg in enumerate(bearish_above_sorted[:10], 1):
            distance = fvg['bottom'] - current_price
            print(f"  {i}. Zone: {fvg['bottom']:.2f}-{fvg['top']:.2f} | "
                  f"Target: {fvg['bottom']:.2f} | Distance: {distance:+.2f}pts | "
                  f"Size: {fvg['gap_size']:.2f}pts")

        if bearish_below:
            print(f"\nBearish FVGs BELOW current price (wrong direction - impossible): {len(bearish_below)}")
            for i, fvg in enumerate(bearish_below[:3], 1):
                print(f"  {i}. Zone: {fvg['bottom']:.2f}-{fvg['top']:.2f} (gap DOWN can't be below)")

        if bearish_at:
            print(f"\nBearish FVGs AT current price: {len(bearish_at)}")
            for i, fvg in enumerate(bearish_at[:3], 1):
                print(f"  {i}. Zone: {fvg['bottom']:.2f}-{fvg['top']:.2f} (price inside)")
    else:
        print("\n[!] NO BEARISH FVGs FOUND")

    # Summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)

    bullish_below_count = len([f for f in bullish_fvgs if f['top'] < current_price])
    bearish_above_count = len([f for f in bearish_fvgs if f['bottom'] > current_price])

    if bearish_above_count > 0:
        print(f"[OK] {bearish_above_count} valid LONG opportunities (bearish FVGs above price)")
    else:
        print("[!] NO LONG opportunities - no bearish FVGs above current price")

    if bullish_below_count > 0:
        print(f"[OK] {bullish_below_count} valid SHORT opportunities (bullish FVGs below price)")
    else:
        print("[!] NO SHORT opportunities - no bullish FVGs below current price")

    if bearish_above_count == 0 and bullish_below_count == 0:
        print("\n[WARNING] No valid FVG setups detected!")
        print("Possible reasons:")
        print("  1. All FVGs have been filled by price action")
        print("  2. No new FVGs created on recent bars")
        print("  3. Price is between all FVGs (gaps above AND below)")
        print("  4. Minimum gap size (5.0 pts) filters out small gaps")

    print("\n" + "="*60)


if __name__ == "__main__":
    diagnose_fvg_detection()
