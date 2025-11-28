"""
Psychological Level Detector Module
Identifies round number levels for EMS zones
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class LevelDetector:
    """Detects psychological price levels (EMS zones)"""

    def __init__(self, level_intervals: List[int] = None):
        """
        Initialize Level Detector

        Args:
            level_intervals: List of point intervals for levels (default: [100])
        """
        self.level_intervals = level_intervals or [100]
        logger.info(f"LevelDetector initialized (intervals={self.level_intervals})")

    def round_to_level(self, price: float, interval: int) -> int:
        """
        Round price to nearest level

        Args:
            price: Price to round
            interval: Level interval (e.g., 100)

        Returns:
            Rounded level as integer
        """
        return int(round(price / interval) * interval)

    def find_nearest_levels(self, current_price: float, interval: int = 100) -> Dict[str, Any]:
        """
        Find nearest psychological levels above and below current price

        Args:
            current_price: Current market price
            interval: Level interval (default: 100)

        Returns:
            Dict with levels above and below
        """
        # Calculate nearest level
        nearest_level = self.round_to_level(current_price, interval)

        # If price is exactly on level, find levels above/below
        if current_price == nearest_level:
            level_above = nearest_level + interval
            level_below = nearest_level - interval
        # If price is below nearest level
        elif current_price < nearest_level:
            level_above = nearest_level
            level_below = nearest_level - interval
        # If price is above nearest level
        else:
            level_above = nearest_level + interval
            level_below = nearest_level

        return {
            'level_above': level_above,
            'distance_above': level_above - current_price,
            'level_below': level_below,
            'distance_below': current_price - level_below,
            'on_level': abs(current_price - nearest_level) < 1.0,  # Within 1 point of level
            'nearest_level': nearest_level
        }

    def find_nearby_levels(self, current_price: float, interval: int = 100, count: int = 3) -> List[int]:
        """
        Find multiple levels above and below current price

        Args:
            current_price: Current market price
            interval: Level interval
            count: Number of levels to find in each direction

        Returns:
            List of levels sorted by proximity
        """
        nearest = self.round_to_level(current_price, interval)
        levels = []

        # Add levels above
        for i in range(count):
            if nearest + (i * interval) >= current_price:
                levels.append(nearest + (i * interval))

        # Add levels below
        for i in range(1, count + 1):
            if nearest - (i * interval) <= current_price:
                levels.append(nearest - (i * interval))

        # Sort by distance from current price
        levels.sort(key=lambda x: abs(x - current_price))
        return levels

    def analyze_level_context(
        self,
        current_price: float,
        fvg_context: Dict[str, Any],
        interval: int = 100
    ) -> Dict[str, Any]:
        """
        Complete level analysis for EMS zones

        Args:
            current_price: Current market price
            fvg_context: Market context from FVGAnalyzer (not used, kept for compatibility)
            interval: Level interval

        Returns:
            Complete level context dictionary
        """
        # Find nearest levels
        levels = self.find_nearest_levels(current_price, interval)

        # Get nearby levels for context
        nearby_levels = self.find_nearby_levels(current_price, interval, count=5)

        context = {
            'current_price': current_price,
            'timestamp': datetime.now().isoformat(),
            'nearest_level_above': levels['level_above'],
            'distance_to_level_above': levels['distance_above'],
            'nearest_level_below': levels['level_below'],
            'distance_to_level_below': levels['distance_below'],
            'on_level': levels['on_level'],
            'nearest_level': levels['nearest_level'],
            'nearby_levels': nearby_levels
        }

        logger.info(f"Level context analyzed: Price={current_price:.2f}, "
                   f"Nearby levels={len(nearby_levels)}")

        return context

    def get_level_summary(self, context: Dict[str, Any]) -> str:
        """
        Generate human-readable summary of level analysis

        Args:
            context: Level context dictionary

        Returns:
            Summary string
        """
        lines = []
        lines.append(f"Current Price: {context['current_price']:.2f}")
        lines.append(f"Nearest Level Above: {context['nearest_level_above']} ({context['distance_to_level_above']:+.2f}pts)")
        lines.append(f"Nearest Level Below: {context['nearest_level_below']} ({context['distance_to_level_below']:+.2f}pts)")

        if context['on_level']:
            lines.append(f"\n*** PRICE ON PSYCHOLOGICAL LEVEL (EMS): {context['nearest_level']} ***")

        lines.append(f"\nNearby EMS Levels: {', '.join(map(str, context['nearby_levels'][:5]))}")

        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Sample FVG context
    sample_context = {
        'current_price': 14685.50,
        'nearest_bullish_fvg': {
            'top': 14715, 'bottom': 14710, 'size': 5.0,
            'distance': 29.50, 'age_bars': 12
        },
        'nearest_bearish_fvg': {
            'top': 14655, 'bottom': 14650, 'size': 5.0,
            'distance': 30.50, 'age_bars': 45
        }
    }

    detector = LevelDetector()
    context = detector.analyze_level_context(14685.50, sample_context)
    print(detector.get_level_summary(context))
