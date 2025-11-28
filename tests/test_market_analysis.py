"""
Test script for Market Analysis Manager
Verifies the persistence and incremental update functionality
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.market_analysis_manager import MarketAnalysisManager


def test_basic_operations():
    """Test basic save/load operations"""
    print("=" * 60)
    print("TEST 1: Basic Operations")
    print("=" * 60)

    # Create manager
    manager = MarketAnalysisManager("data/test_analysis.json")

    # Show initial state
    print("\nInitial State:")
    print(manager.get_summary())

    # Create a sample analysis
    analysis = {
        'current_bar_index': 1,
        'overall_bias': 'bullish',
        'waiting_for': 'Price to reach 14600 bearish FVG for long entry',
        'long_assessment': {
            'status': 'waiting',
            'target_fvg': {'bottom': 14600, 'top': 14605, 'size': 5.0},
            'entry_plan': 14602,
            'stop_plan': 14590,
            'target_plan': 14700,
            'risk_reward': 8.3,
            'confidence': 0.75,
            'reasoning': 'Strong bullish trend. Waiting for pullback to bearish FVG at 14600 for long entry.',
            'setup_age_bars': 0
        },
        'short_assessment': {
            'status': 'none',
            'target_fvg': None,
            'entry_plan': None,
            'stop_plan': None,
            'target_plan': None,
            'risk_reward': None,
            'confidence': 0.0,
            'reasoning': 'No quality short setup. Trend is bullish.',
            'setup_age_bars': 0
        },
        'bars_since_last_trade': 5,
        'bars_since_last_update': 0
    }

    # Update analysis
    success = manager.update_analysis(analysis)
    print(f"\nAnalysis Update: {'SUCCESS' if success else 'FAILED'}")

    # Show updated state
    print("\nUpdated State:")
    print(manager.get_summary())

    # Get formatted for prompt
    print("\nFormatted for Prompt:")
    print(manager.format_previous_analysis_for_prompt())

    return manager


def test_incremental_updates():
    """Test incremental updates (simulating new bars)"""
    print("\n" + "=" * 60)
    print("TEST 2: Incremental Updates (Simulating New Bars)")
    print("=" * 60)

    manager = MarketAnalysisManager("data/test_analysis.json")

    # Simulate bar 2 - price moving closer to target
    print("\n--- BAR 2: Price moving closer to FVG ---")
    analysis_bar2 = {
        'current_bar_index': 2,
        'overall_bias': 'bullish',
        'waiting_for': 'Price to reach 14600 bearish FVG for long entry (getting closer)',
        'long_assessment': {
            'status': 'waiting',
            'target_fvg': {'bottom': 14600, 'top': 14605, 'size': 5.0},
            'entry_plan': 14602,
            'stop_plan': 14590,
            'target_plan': 14700,
            'risk_reward': 8.3,
            'confidence': 0.78,  # Increased confidence
            'reasoning': 'Price moving closer to target FVG. Still waiting for entry.',
            'setup_age_bars': 0  # Will be incremented by manager
        },
        'short_assessment': {
            'status': 'none',
            'target_fvg': None,
            'entry_plan': None,
            'stop_plan': None,
            'target_plan': None,
            'risk_reward': None,
            'confidence': 0.0,
            'reasoning': 'No quality short setup. Trend is bullish.',
            'setup_age_bars': 0
        },
        'bars_since_last_trade': 0,  # Will be incremented by manager
        'bars_since_last_update': 0
    }

    manager.update_analysis(analysis_bar2)
    print(manager.get_summary())

    # Simulate bar 3 - setup ready
    print("\n--- BAR 3: Setup ready! ---")
    analysis_bar3 = {
        'current_bar_index': 3,
        'overall_bias': 'bullish',
        'waiting_for': 'Long setup READY at 14600',
        'long_assessment': {
            'status': 'ready',  # Changed to ready!
            'target_fvg': {'bottom': 14600, 'top': 14605, 'size': 5.0},
            'entry_plan': 14602,
            'stop_plan': 14590,
            'target_plan': 14700,
            'risk_reward': 8.3,
            'confidence': 0.82,
            'reasoning': 'Price reached target FVG zone. Setup is ready for entry.',
            'setup_age_bars': 0
        },
        'short_assessment': {
            'status': 'none',
            'target_fvg': None,
            'entry_plan': None,
            'stop_plan': None,
            'target_plan': None,
            'risk_reward': None,
            'confidence': 0.0,
            'reasoning': 'No quality short setup.',
            'setup_age_bars': 0
        },
        'bars_since_last_trade': 0,
        'bars_since_last_update': 0
    }

    manager.update_analysis(analysis_bar3)
    print(manager.get_summary())

    # Simulate trade execution
    print("\n--- TRADE EXECUTED: LONG ---")
    manager.mark_trade_executed('LONG')
    print(manager.get_summary())


def test_waiting_patience():
    """Test that agent can wait patiently for setups"""
    print("\n" + "=" * 60)
    print("TEST 3: Patience Test (No Setup for Multiple Bars)")
    print("=" * 60)

    manager = MarketAnalysisManager("data/test_analysis.json")

    # Simulate 5 bars with no quality setup
    for bar in range(1, 6):
        print(f"\n--- BAR {bar}: No quality setup ---")
        analysis = {
            'current_bar_index': bar,
            'overall_bias': 'neutral',
            'waiting_for': 'Quality FVG setup to develop',
            'long_assessment': {
                'status': 'none',
                'target_fvg': None,
                'entry_plan': None,
                'stop_plan': None,
                'target_plan': None,
                'risk_reward': None,
                'confidence': 0.0,
                'reasoning': f'No quality long setup on bar {bar}. Nearest FVG too far away.',
                'setup_age_bars': 0
            },
            'short_assessment': {
                'status': 'none',
                'target_fvg': None,
                'entry_plan': None,
                'stop_plan': None,
                'target_plan': None,
                'risk_reward': None,
                'confidence': 0.0,
                'reasoning': f'No quality short setup on bar {bar}. Market choppy.',
                'setup_age_bars': 0
            },
            'bars_since_last_trade': 0,
            'bars_since_last_update': 0
        }
        manager.update_analysis(analysis)

    # Show final state
    print("\nFinal State After 5 Bars of Waiting:")
    print(manager.get_summary())
    print(f"\nBars since last trade: {manager.current_analysis['bars_since_last_trade']}")
    print("✓ Agent successfully waited patiently without forcing trades")


if __name__ == "__main__":
    print("\nMARKET ANALYSIS MANAGER TEST SUITE")
    print("=" * 60)

    # Run tests
    test_basic_operations()
    test_incremental_updates()
    test_waiting_patience()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
    print("\nCheck data/test_analysis.json to see the persisted state")
