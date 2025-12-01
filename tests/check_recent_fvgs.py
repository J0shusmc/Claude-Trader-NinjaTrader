"""
Check Recent Bars for FVG Formation
Shows last 20 bars to see if gaps should be forming
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd


def check_recent_bars():
    """Check recent bars for potential FVG formation"""

    print("="*80)
    print("RECENT BAR ANALYSIS - FVG Formation Check")
    print("="*80)

    # Load historical data
    df = pd.read_csv('data/HistoricalData.csv')
    df['DateTime'] = pd.to_datetime(df['DateTime'])

    # Get last 20 bars
    recent = df.tail(20).copy()
    recent = recent.reset_index(drop=True)

    print(f"\nShowing last 20 bars (most recent at bottom)")
    print(f"Current (latest) bar: {recent.iloc[-1]['DateTime']}")
    print(f"Price: {recent.iloc[-1]['Close']:.2f}")
    print("\n" + "="*80)

    # Check for FVG formation on each bar
    fvg_count = 0

    for i in range(2, len(recent)):
        candle1 = recent.iloc[i - 2]
        candle2 = recent.iloc[i - 1]
        candle3 = recent.iloc[i]

        bar_time = candle3['DateTime']

        # Check for bullish FVG (gap up)
        if candle3['Low'] > candle1['High']:
            gap_size = candle3['Low'] - candle1['High']
            if gap_size >= 5.0:
                fvg_count += 1
                print(f"[BULLISH FVG] {bar_time}")
                print(f"  Gap: {candle1['High']:.2f} to {candle3['Low']:.2f} = {gap_size:.2f}pts")
                print(f"  Zone: {candle1['High']:.2f} - {candle3['Low']:.2f}")
                print(f"  Current Price: {recent.iloc[-1]['Close']:.2f}")

                # Check if filled
                filled = False
                for j in range(i + 1, len(recent)):
                    if recent.iloc[j]['Low'] <= candle1['High']:
                        filled = True
                        print(f"  STATUS: FILLED on {recent.iloc[j]['DateTime']}")
                        break

                if not filled:
                    relative = "ABOVE" if candle1['High'] > recent.iloc[-1]['Close'] else "BELOW"
                    print(f"  STATUS: UNFILLED - {relative} current price")
                print()

        # Check for bearish FVG (gap down)
        elif candle3['High'] < candle1['Low']:
            gap_size = candle1['Low'] - candle3['High']
            if gap_size >= 5.0:
                fvg_count += 1
                print(f"[BEARISH FVG] {bar_time}")
                print(f"  Gap: {candle3['High']:.2f} to {candle1['Low']:.2f} = {gap_size:.2f}pts")
                print(f"  Zone: {candle3['High']:.2f} - {candle1['Low']:.2f}")
                print(f"  Current Price: {recent.iloc[-1]['Close']:.2f}")

                # Check if filled
                filled = False
                for j in range(i + 1, len(recent)):
                    if recent.iloc[j]['High'] >= candle1['Low']:
                        filled = True
                        print(f"  STATUS: FILLED on {recent.iloc[j]['DateTime']}")
                        break

                if not filled:
                    relative = "ABOVE" if candle3['High'] > recent.iloc[-1]['Close'] else "BELOW"
                    print(f"  STATUS: UNFILLED - {relative} current price")
                print()

    print("="*80)
    print(f"FVGs formed in last 20 bars: {fvg_count}")

    if fvg_count == 0:
        print("\n[!] NO FVGs formed in recent bars!")
        print("This explains why no valid setups exist.")
        print("\nPossible reasons:")
        print("  1. Market consolidating without creating gaps")
        print("  2. Price action too smooth (no violent moves)")
        print("  3. Need to wait for next gap-creating move")

    print("="*80)

    # Show bar details for manual inspection
    print("\nLast 10 Bars Detail:")
    print("-"*80)
    print(f"{'DateTime':<20} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'Range':>8}")
    print("-"*80)

    for i in range(len(recent) - 10, len(recent)):
        bar = recent.iloc[i]
        bar_range = bar['High'] - bar['Low']
        print(f"{str(bar['DateTime']):<20} {bar['Open']:>8.2f} {bar['High']:>8.2f} "
              f"{bar['Low']:>8.2f} {bar['Close']:>8.2f} {bar_range:>8.2f}")


if __name__ == "__main__":
    check_recent_bars()
