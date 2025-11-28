"""
Market Analysis Manager Module
Manages persistent market analysis state across trading sessions
"""

import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class MarketAnalysisManager:
    """Manages persistent market analysis state"""

    def __init__(self, analysis_file: str = "data/market_analysis.json"):
        """
        Initialize Market Analysis Manager

        Args:
            analysis_file: Path to market analysis persistence file
        """
        self.analysis_file = Path(analysis_file)
        self.analysis_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize or load existing analysis
        self.current_analysis = self._load_analysis()

        logger.info(f"MarketAnalysisManager initialized (file={analysis_file})")

    def _get_empty_analysis(self) -> Dict[str, Any]:
        """
        Create empty analysis structure

        Returns:
            Empty analysis dictionary
        """
        return {
            "last_updated": datetime.now().isoformat(),
            "current_bar_index": 0,
            "long_assessment": {
                "status": "none",
                "target_fvg": None,
                "entry_plan": None,
                "stop_plan": None,
                "target_plan": None,
                "reasoning": "No long setup identified yet",
                "confidence": 0.0,
                "setup_age_bars": 0
            },
            "short_assessment": {
                "status": "none",
                "target_fvg": None,
                "entry_plan": None,
                "stop_plan": None,
                "target_plan": None,
                "reasoning": "No short setup identified yet",
                "confidence": 0.0,
                "setup_age_bars": 0
            },
            "overall_bias": "neutral",
            "waiting_for": "Initial market analysis",
            "bars_since_last_trade": 0,
            "bars_since_last_update": 0
        }

    def _load_analysis(self) -> Dict[str, Any]:
        """
        Load existing analysis from file or create new

        Returns:
            Analysis dictionary
        """
        if self.analysis_file.exists():
            try:
                with open(self.analysis_file, 'r') as f:
                    analysis = json.load(f)
                    logger.info(f"Loaded existing analysis (last updated: {analysis.get('last_updated')})")
                    return analysis
            except Exception as e:
                logger.warning(f"Failed to load analysis file: {e}. Creating new analysis.")
                return self._get_empty_analysis()
        else:
            logger.info("No existing analysis found. Creating new analysis.")
            return self._get_empty_analysis()

    def save_analysis(self, analysis: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save analysis to file

        Args:
            analysis: Analysis dictionary to save (uses self.current_analysis if None)

        Returns:
            True if successful, False otherwise
        """
        if analysis is None:
            analysis = self.current_analysis

        try:
            # Update timestamp
            analysis['last_updated'] = datetime.now().isoformat()

            # Write to file
            with open(self.analysis_file, 'w') as f:
                json.dump(analysis, f, indent=2)

            logger.info(f"Analysis saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")
            return False

    def get_previous_analysis(self) -> Dict[str, Any]:
        """
        Get the current analysis state

        Returns:
            Current analysis dictionary
        """
        return self.current_analysis.copy()

    def update_analysis(self, new_analysis: Dict[str, Any]) -> bool:
        """
        Update the current analysis with new data

        Args:
            new_analysis: New analysis data from agent

        Returns:
            True if successful, False otherwise
        """
        try:
            # Increment bars since last update for existing setups
            if self.current_analysis.get('long_assessment', {}).get('status') != 'none':
                new_analysis['long_assessment']['setup_age_bars'] = \
                    self.current_analysis.get('long_assessment', {}).get('setup_age_bars', 0) + 1

            if self.current_analysis.get('short_assessment', {}).get('status') != 'none':
                new_analysis['short_assessment']['setup_age_bars'] = \
                    self.current_analysis.get('short_assessment', {}).get('setup_age_bars', 0) + 1

            # Increment bars since last trade
            new_analysis['bars_since_last_trade'] = \
                self.current_analysis.get('bars_since_last_trade', 0) + 1

            # Reset bars since last update
            new_analysis['bars_since_last_update'] = 0

            # Update current analysis
            self.current_analysis = new_analysis

            # Save to file
            return self.save_analysis()

        except Exception as e:
            logger.error(f"Failed to update analysis: {e}")
            return False

    def mark_trade_executed(self, direction: str):
        """
        Mark that a trade was executed

        Args:
            direction: "LONG" or "SHORT"
        """
        self.current_analysis['bars_since_last_trade'] = 0

        # Reset the executed setup
        if direction == "LONG":
            self.current_analysis['long_assessment']['status'] = 'none'
            self.current_analysis['long_assessment']['setup_age_bars'] = 0
        elif direction == "SHORT":
            self.current_analysis['short_assessment']['status'] = 'none'
            self.current_analysis['short_assessment']['setup_age_bars'] = 0

        self.save_analysis()
        logger.info(f"{direction} trade executed - setup reset")

    def format_previous_analysis_for_prompt(self) -> str:
        """
        Format previous analysis for inclusion in agent prompt

        Returns:
            Formatted string for prompt
        """
        analysis = self.current_analysis

        lines = []
        lines.append("PREVIOUS ANALYSIS STATE:")
        lines.append("=" * 50)
        lines.append(f"Last Updated: {analysis.get('last_updated', 'Unknown')}")
        lines.append(f"Bars Since Last Trade: {analysis.get('bars_since_last_trade', 0)}")
        lines.append(f"Overall Bias: {analysis.get('overall_bias', 'neutral').upper()}")
        lines.append(f"Waiting For: {analysis.get('waiting_for', 'N/A')}")
        lines.append("")

        # Long assessment
        long = analysis.get('long_assessment', {})
        lines.append("LONG ASSESSMENT:")
        lines.append(f"  Status: {long.get('status', 'none').upper()}")
        if long.get('status') != 'none':
            lines.append(f"  Setup Age: {long.get('setup_age_bars', 0)} bars")
            lines.append(f"  Entry Plan: {long.get('entry_plan', 0):.2f}")
            lines.append(f"  Stop Plan: {long.get('stop_plan', 0):.2f}")
            lines.append(f"  Target Plan: {long.get('target_plan', 0):.2f}")
            lines.append(f"  Confidence: {long.get('confidence', 0):.2f}")
            lines.append(f"  Reasoning: {long.get('reasoning', 'N/A')}")
        else:
            lines.append(f"  {long.get('reasoning', 'No setup')}")
        lines.append("")

        # Short assessment
        short = analysis.get('short_assessment', {})
        lines.append("SHORT ASSESSMENT:")
        lines.append(f"  Status: {short.get('status', 'none').upper()}")
        if short.get('status') != 'none':
            lines.append(f"  Setup Age: {short.get('setup_age_bars', 0)} bars")
            lines.append(f"  Entry Plan: {short.get('entry_plan', 0):.2f}")
            lines.append(f"  Stop Plan: {short.get('stop_plan', 0):.2f}")
            lines.append(f"  Target Plan: {short.get('target_plan', 0):.2f}")
            lines.append(f"  Confidence: {short.get('confidence', 0):.2f}")
            lines.append(f"  Reasoning: {short.get('reasoning', 'N/A')}")
        else:
            lines.append(f"  {short.get('reasoning', 'No setup')}")
        lines.append("")

        return "\n".join(lines)

    def get_summary(self) -> str:
        """
        Get human-readable summary of current analysis

        Returns:
            Summary string
        """
        analysis = self.current_analysis

        lines = []
        lines.append("=" * 60)
        lines.append("MARKET ANALYSIS SUMMARY")
        lines.append("=" * 60)
        lines.append(f"Last Updated: {analysis.get('last_updated', 'Unknown')}")
        lines.append(f"Overall Bias: {analysis.get('overall_bias', 'neutral').upper()}")
        lines.append(f"Waiting For: {analysis.get('waiting_for', 'N/A')}")
        lines.append(f"Bars Since Last Trade: {analysis.get('bars_since_last_trade', 0)}")
        lines.append("")

        long = analysis.get('long_assessment', {})
        lines.append(f"LONG: {long.get('status', 'none').upper()} "
                    f"(Age: {long.get('setup_age_bars', 0)} bars, "
                    f"Conf: {long.get('confidence', 0):.2f})")

        short = analysis.get('short_assessment', {})
        lines.append(f"SHORT: {short.get('status', 'none').upper()} "
                    f"(Age: {short.get('setup_age_bars', 0)} bars, "
                    f"Conf: {short.get('confidence', 0):.2f})")
        lines.append("=" * 60)

        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Create manager
    manager = MarketAnalysisManager()

    # Show current state
    print(manager.get_summary())

    # Example update
    new_analysis = manager._get_empty_analysis()
    new_analysis['overall_bias'] = 'bullish'
    new_analysis['waiting_for'] = 'Price to reach 14600 bearish FVG'
    new_analysis['long_assessment'] = {
        'status': 'waiting',
        'target_fvg': {'bottom': 14600, 'top': 14605},
        'entry_plan': 14602,
        'stop_plan': 14590,
        'target_plan': 14700,
        'reasoning': 'Strong bullish trend, waiting for pullback to FVG support',
        'confidence': 0.75,
        'setup_age_bars': 0
    }

    manager.update_analysis(new_analysis)
    print("\nAfter update:")
    print(manager.get_summary())
