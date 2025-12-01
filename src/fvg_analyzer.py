"""
FVG Analyzer Module
Parses Fair Value Gap data and prepares it for Claude analysis
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class FVGAnalyzer:
    """Analyzes Fair Value Gaps and calculates trading context"""

    def __init__(self, min_gap_size: float = 5.0, max_gap_age: int = 100):
        """
        Initialize FVG Analyzer

        Args:
            min_gap_size: Minimum gap size in points to consider
            max_gap_age: Maximum age in bars before gap is considered stale
        """
        self.min_gap_size = min_gap_size
        self.max_gap_age = max_gap_age
        logger.info(f"FVGAnalyzer initialized (min_gap_size={min_gap_size}, max_gap_age={max_gap_age})")

    def parse_fvg_zones(self, active_fvgs: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Parse FVG zones and separate by type

        Args:
            active_fvgs: List of active FVG zones from FairValueGaps.py

        Returns:
            Dict with 'bullish' and 'bearish' FVG lists
        """
        bullish_fvgs = []
        bearish_fvgs = []

        for fvg in active_fvgs:
            if fvg.get('filled', False):
                continue

            fvg_data = {
                'top': fvg['top'],
                'bottom': fvg['bottom'],
                'size': fvg['gap_size'],
                'datetime': fvg['datetime'],
                'age_bars': fvg.get('age_bars', 0),
                'index': fvg.get('index', 0)
            }

            if fvg['type'] == 'bullish':
                bullish_fvgs.append(fvg_data)
            elif fvg['type'] == 'bearish':
                bearish_fvgs.append(fvg_data)

        return {
            'bullish': bullish_fvgs,
            'bearish': bearish_fvgs
        }

    def calculate_distance(self, current_price: float, fvg: Dict, fvg_type: str) -> float:
        """
        Calculate distance from current price to FVG target (the gap to fill)

        Args:
            current_price: Current market price
            fvg: FVG data dictionary
            fvg_type: 'bullish' or 'bearish'

        Returns:
            Distance in points (positive = target above, negative = target below)
        """
        if fvg_type == 'bullish':
            # Bullish FVG (gap UP) leaves gap BELOW = SHORT opportunity (price drawn down to fill)
            # Target: top of the gap (where price will fill from above)
            return fvg['top'] - current_price  # negative = target is below
        else:  # bearish
            # Bearish FVG (gap DOWN) leaves gap ABOVE = LONG opportunity (price drawn up to fill)
            # Target: bottom of the gap (where price will fill from below)
            return fvg['bottom'] - current_price  # positive = target is above

    def find_nearest_fvgs(self, current_price: float, fvg_zones: Dict[str, List[Dict]]) -> Dict[str, Optional[Dict]]:
        """
        Find nearest bullish and bearish FVGs to current price
        Only considers FVGs in the correct direction (targets price can move toward)

        Args:
            current_price: Current market price
            fvg_zones: Dictionary of bullish and bearish FVG zones

        Returns:
            Dict with nearest_bullish and nearest_bearish FVGs
        """
        result = {
            'nearest_bullish': None,
            'nearest_bearish': None
        }

        # Find nearest bullish FVG BELOW current price (for SHORT setups)
        # Bullish FVG = gap created by UP move, leaves gap BELOW
        # Price will be drawn downward to fill the gap
        if fvg_zones['bullish']:
            bullish_below = [
                fvg for fvg in fvg_zones['bullish']
                if fvg['top'] < current_price  # Gap must be BELOW current price
            ]
            if bullish_below:
                bullish_with_distance = [
                    {
                        **fvg,
                        'distance': self.calculate_distance(current_price, fvg, 'bullish'),
                        'distance_abs': abs(self.calculate_distance(current_price, fvg, 'bullish'))
                    }
                    for fvg in bullish_below
                ]
                bullish_with_distance.sort(key=lambda x: x['distance_abs'])
                result['nearest_bullish'] = bullish_with_distance[0]

        # Find nearest bearish FVG ABOVE current price (for LONG setups)
        # Bearish FVG = gap created by DOWN move, leaves gap ABOVE
        # Price will be drawn upward to fill the gap
        if fvg_zones['bearish']:
            bearish_above = [
                fvg for fvg in fvg_zones['bearish']
                if fvg['bottom'] > current_price  # Gap must be ABOVE current price
            ]
            if bearish_above:
                bearish_with_distance = [
                    {
                        **fvg,
                        'distance': self.calculate_distance(current_price, fvg, 'bearish'),
                        'distance_abs': abs(self.calculate_distance(current_price, fvg, 'bearish'))
                    }
                    for fvg in bearish_above
                ]
                bearish_with_distance.sort(key=lambda x: x['distance_abs'])
                result['nearest_bearish'] = bearish_with_distance[0]

        return result

    def check_price_in_zone(self, current_price: float, fvg: Dict) -> bool:
        """
        Check if current price is inside an FVG zone

        Args:
            current_price: Current market price
            fvg: FVG data dictionary

        Returns:
            True if price is in zone, False otherwise
        """
        return fvg['bottom'] <= current_price <= fvg['top']

    def find_active_zone(self, current_price: float, fvg_zones: Dict[str, List[Dict]]) -> Optional[Dict]:
        """
        Check if price is currently inside any FVG zone

        Args:
            current_price: Current market price
            fvg_zones: Dictionary of bullish and bearish FVG zones

        Returns:
            FVG data if price is in zone, None otherwise
        """
        # Check bullish zones
        for fvg in fvg_zones['bullish']:
            if self.check_price_in_zone(current_price, fvg):
                return {'type': 'bullish', **fvg}

        # Check bearish zones
        for fvg in fvg_zones['bearish']:
            if self.check_price_in_zone(current_price, fvg):
                return {'type': 'bearish', **fvg}

        return None

    def filter_quality_fvgs(self, fvg_zones: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """
        Filter FVGs based on quality criteria

        Args:
            fvg_zones: Dictionary of bullish and bearish FVG zones

        Returns:
            Filtered FVG zones meeting quality criteria
        """
        filtered = {
            'bullish': [],
            'bearish': []
        }

        for fvg_type in ['bullish', 'bearish']:
            for fvg in fvg_zones[fvg_type]:
                # Check gap size
                if fvg['size'] < self.min_gap_size:
                    continue

                # Check gap age
                if fvg.get('age_bars', 0) > self.max_gap_age:
                    continue

                filtered[fvg_type].append(fvg)

        return filtered

    def analyze_market_context(self, current_price: float, active_fvgs: List[Dict]) -> Dict[str, Any]:
        """
        Complete market analysis combining all FVG data

        Args:
            current_price: Current market price
            active_fvgs: List of active FVG zones

        Returns:
            Complete market context dictionary
        """
        # Parse and separate FVG zones
        fvg_zones = self.parse_fvg_zones(active_fvgs)

        # Filter by quality
        quality_zones = self.filter_quality_fvgs(fvg_zones)

        # Find nearest FVGs
        nearest = self.find_nearest_fvgs(current_price, quality_zones)

        # Check if price is in any zone
        active_zone = self.find_active_zone(current_price, quality_zones)

        context = {
            'current_price': current_price,
            'timestamp': datetime.now().isoformat(),
            'total_bullish_fvgs': len(quality_zones['bullish']),
            'total_bearish_fvgs': len(quality_zones['bearish']),
            'nearest_bullish_fvg': nearest['nearest_bullish'],
            'nearest_bearish_fvg': nearest['nearest_bearish'],
            'price_in_zone': active_zone,
            'all_fvgs': quality_zones
        }

        logger.info(f"Market context analyzed: Price={current_price:.2f}, "
                   f"Bullish FVGs={context['total_bullish_fvgs']}, "
                   f"Bearish FVGs={context['total_bearish_fvgs']}")

        return context

    def get_fvg_summary(self, context: Dict[str, Any]) -> str:
        """
        Generate human-readable summary of FVG analysis

        Args:
            context: Market context dictionary

        Returns:
            Summary string
        """
        lines = []
        lines.append(f"Current Price: {context['current_price']:.2f}")
        lines.append(f"Active Bullish FVGs: {context['total_bullish_fvgs']}")
        lines.append(f"Active Bearish FVGs: {context['total_bearish_fvgs']}")

        if context['nearest_bullish_fvg']:
            fvg = context['nearest_bullish_fvg']
            lines.append(f"\nNearest Bullish FVG BELOW (SHORT setup - price drawn down to fill gap):")
            lines.append(f"  Zone: {fvg['bottom']:.2f} - {fvg['top']:.2f}")
            lines.append(f"  Size: {fvg['size']:.2f}pts")
            lines.append(f"  Distance to target: {fvg['distance']:+.2f}pts")
            lines.append(f"  Age: {fvg.get('age_bars', 0)} bars")

        if context['nearest_bearish_fvg']:
            fvg = context['nearest_bearish_fvg']
            lines.append(f"\nNearest Bearish FVG ABOVE (LONG setup - price drawn up to fill gap):")
            lines.append(f"  Zone: {fvg['bottom']:.2f} - {fvg['top']:.2f}")
            lines.append(f"  Size: {fvg['size']:.2f}pts")
            lines.append(f"  Distance to target: {fvg['distance']:+.2f}pts")
            lines.append(f"  Age: {fvg.get('age_bars', 0)} bars")

        if context['price_in_zone']:
            zone = context['price_in_zone']
            lines.append(f"\n*** PRICE IN ZONE ***")
            lines.append(f"Type: {zone['type'].upper()}")
            lines.append(f"Zone: {zone['bottom']:.2f} - {zone['top']:.2f}")

        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Sample FVG data
    sample_fvgs = [
        {'type': 'bullish', 'top': 14715, 'bottom': 14710, 'gap_size': 5.0,
         'datetime': '2025-11-25 14:00:00', 'filled': False, 'age_bars': 12},
        {'type': 'bearish', 'top': 14655, 'bottom': 14650, 'gap_size': 5.0,
         'datetime': '2025-11-25 13:00:00', 'filled': False, 'age_bars': 45},
    ]

    analyzer = FVGAnalyzer()
    context = analyzer.analyze_market_context(14685.50, sample_fvgs)
    print(analyzer.get_fvg_summary(context))
