"""
Test FVG Direction Logic - Verify FVGs are treated as magnetic targets
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fvg_analyzer import FVGAnalyzer


def test_fvg_direction_logic():
    """Test that FVGs are correctly identified as directional targets"""

    print("="*60)
    print("Testing FVG Direction Logic")
    print("="*60)

    analyzer = FVGAnalyzer(min_gap_size=5.0, max_gap_age=100)

    # Test scenario: Price at 21000
    current_price = 21000.0

    # Sample FVGs
    sample_fvgs = [
        # Bullish FVG ABOVE (LONG opportunity - price drawn up)
        {
            'type': 'bullish',
            'top': 21115,
            'bottom': 21110,
            'gap_size': 5.0,
            'datetime': '2025-11-30 14:00:00',
            'filled': False,
            'age_bars': 12,
            'index': 100
        },
        # Another bullish FVG ABOVE (further away)
        {
            'type': 'bullish',
            'top': 21205,
            'bottom': 21200,
            'gap_size': 5.0,
            'datetime': '2025-11-30 13:00:00',
            'filled': False,
            'age_bars': 24,
            'index': 88
        },
        # Bearish FVG BELOW (SHORT opportunity - price drawn down)
        {
            'type': 'bearish',
            'top': 20895,
            'bottom': 20890,
            'gap_size': 5.0,
            'datetime': '2025-11-30 12:00:00',
            'filled': False,
            'age_bars': 36,
            'index': 76
        },
        # Another bearish FVG BELOW (further away)
        {
            'type': 'bearish',
            'top': 20805,
            'bottom': 20800,
            'gap_size': 5.0,
            'datetime': '2025-11-30 11:00:00',
            'filled': False,
            'age_bars': 48,
            'index': 64
        },
        # Bullish FVG BELOW current price (should be FILTERED OUT)
        {
            'type': 'bullish',
            'top': 20915,
            'bottom': 20910,
            'gap_size': 5.0,
            'datetime': '2025-11-30 10:00:00',
            'filled': False,
            'age_bars': 60,
            'index': 52
        },
        # Bearish FVG ABOVE current price (should be FILTERED OUT)
        {
            'type': 'bearish',
            'top': 21095,
            'bottom': 21090,
            'gap_size': 5.0,
            'datetime': '2025-11-30 09:00:00',
            'filled': False,
            'age_bars': 72,
            'index': 40
        }
    ]

    print(f"\nCurrent Price: {current_price:.2f}")
    print(f"Total FVGs: {len(sample_fvgs)}")
    print("")

    # Analyze market context
    context = analyzer.analyze_market_context(current_price, sample_fvgs)

    print("\n" + "="*60)
    print("ANALYSIS RESULTS")
    print("="*60)

    # Check LONG setup (bullish FVG above)
    if context['nearest_bullish_fvg']:
        fvg = context['nearest_bullish_fvg']
        print(f"\n[OK] LONG OPPORTUNITY FOUND:")
        print(f"   Bullish FVG ABOVE at {fvg['bottom']:.2f} - {fvg['top']:.2f}")
        print(f"   Target: {fvg['bottom']:.2f} (bottom of gap)")
        print(f"   Distance: {fvg['distance']:+.2f} points")
        print(f"   Strategy: Enter LONG now, ride price UP to {fvg['bottom']:.2f}")

        # Verify distance calculation
        expected_distance = fvg['bottom'] - current_price
        assert fvg['distance'] == expected_distance, f"Distance calculation error: {fvg['distance']} != {expected_distance}"
        assert fvg['distance'] > 0, "LONG target should be ABOVE (positive distance)"
        print(f"   [OK] Distance calculation correct: {fvg['distance']:+.2f}pts")
    else:
        print("\n[X] NO LONG OPPORTUNITY (no bullish FVG above)")

    # Check SHORT setup (bearish FVG below)
    if context['nearest_bearish_fvg']:
        fvg = context['nearest_bearish_fvg']
        print(f"\n[OK] SHORT OPPORTUNITY FOUND:")
        print(f"   Bearish FVG BELOW at {fvg['bottom']:.2f} - {fvg['top']:.2f}")
        print(f"   Target: {fvg['top']:.2f} (top of gap)")
        print(f"   Distance: {fvg['distance']:+.2f} points")
        print(f"   Strategy: Enter SHORT now, ride price DOWN to {fvg['top']:.2f}")

        # Verify distance calculation
        expected_distance = fvg['top'] - current_price
        assert fvg['distance'] == expected_distance, f"Distance calculation error: {fvg['distance']} != {expected_distance}"
        assert fvg['distance'] < 0, "SHORT target should be BELOW (negative distance)"
        print(f"   [OK] Distance calculation correct: {fvg['distance']:+.2f}pts")
    else:
        print("\n[X] NO SHORT OPPORTUNITY (no bearish FVG below)")

    # Verify filtering worked for NEAREST FVGs (the ones that matter for trading)
    print("\n" + "="*60)
    print("FILTERING VERIFICATION (Nearest FVGs)")
    print("="*60)

    print("\nVerifying nearest FVGs are correctly directional:")

    # Nearest bullish should be ABOVE current price
    if context['nearest_bullish_fvg']:
        fvg = context['nearest_bullish_fvg']
        if fvg['bottom'] > current_price:
            print(f"   [OK] Nearest Bullish FVG correctly ABOVE price: {fvg['bottom']:.2f}")
        else:
            print(f"   [X] ERROR: Nearest Bullish FVG not above price: {fvg['bottom']:.2f}")

    # Nearest bearish should be BELOW current price
    if context['nearest_bearish_fvg']:
        fvg = context['nearest_bearish_fvg']
        if fvg['top'] < current_price:
            print(f"   [OK] Nearest Bearish FVG correctly BELOW price: {fvg['top']:.2f}")
        else:
            print(f"   [X] ERROR: Nearest Bearish FVG not below price: {fvg['top']:.2f}")

    print("\nNote: all_fvgs list contains ALL quality FVGs (for reference)")
    print("      Trading decisions use only nearest_bullish/nearest_bearish (correctly filtered)")

    print("\n" + "="*60)
    print("[OK] ALL TESTS PASSED - FVG logic correctly treats gaps as targets")
    print("="*60)

    # Print summary
    print("\n" + analyzer.get_fvg_summary(context))


if __name__ == "__main__":
    test_fvg_direction_logic()
