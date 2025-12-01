"""
Signal Generator Module
Outputs trade signals to CSV for NinjaTrader
"""

import csv
import logging
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates trade signals in NinjaTrader CSV format"""

    def __init__(self, output_file: str = "data/trade_signals.csv"):
        """
        Initialize Signal Generator

        Args:
            output_file: Path to trade signals CSV file
        """
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(exist_ok=True)

        # Check if header needs fixing
        needs_init = False
        if not self.output_file.exists() or self.output_file.stat().st_size == 0:
            needs_init = True
        else:
            # Verify header is correct
            try:
                with open(self.output_file, 'r') as f:
                    header = f.readline().strip()
                    if header != 'DateTime,Direction,Entry_Price,Stop_Loss,Target':
                        logger.warning(f"Invalid header detected: {header}")
                        needs_init = True
            except Exception:
                needs_init = True

        if needs_init:
            self._initialize_csv()

        logger.info(f"SignalGenerator initialized (output={self.output_file})")

    def _initialize_csv(self):
        """Initialize CSV file with headers"""
        try:
            with open(self.output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['DateTime', 'Direction', 'Entry_Price', 'Stop_Loss', 'Target'])
            logger.info("Trade signals CSV initialized")
        except Exception as e:
            logger.error(f"Error initializing CSV: {e}")
            raise

    def validate_decision(self, decision: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate decision data before generating signal

        Args:
            decision: Decision dictionary from TradingAgent

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check decision type
        if decision.get('decision') not in ['LONG', 'SHORT']:
            return False, f"Invalid decision type: {decision.get('decision')}"

        # Check required fields
        required_fields = ['entry', 'stop', 'target']
        for field in required_fields:
            if field not in decision:
                return False, f"Missing required field: {field}"
            if not isinstance(decision[field], (int, float)):
                return False, f"Invalid {field} value: {decision[field]}"

        # Validate price relationships
        entry = decision['entry']
        stop = decision['stop']
        target = decision['target']

        if decision['decision'] == 'LONG':
            if stop >= entry:
                return False, f"LONG stop ({stop}) must be below entry ({entry})"
            if target <= entry:
                return False, f"LONG target ({target}) must be above entry ({entry})"

        elif decision['decision'] == 'SHORT':
            if stop <= entry:
                return False, f"SHORT stop ({stop}) must be above entry ({entry})"
            if target >= entry:
                return False, f"SHORT target ({target}) must be below entry ({entry})"

        # Validate 5pt buffer was applied correctly (if raw_target exists)
        if 'raw_target' in decision and decision['raw_target'] is not None:
            raw_target = decision['raw_target']

            if decision['decision'] == 'LONG':
                # LONG: Final target should be 5pts BELOW raw target
                expected_target = raw_target - 5
                if abs(target - expected_target) > 0.1:  # Allow 0.1pt tolerance
                    return False, f"LONG buffer error: target ({target}) should be raw_target - 5 ({expected_target})"

            elif decision['decision'] == 'SHORT':
                # SHORT: Final target should be 5pts ABOVE raw target
                expected_target = raw_target + 5
                if abs(target - expected_target) > 0.1:  # Allow 0.1pt tolerance
                    return False, f"SHORT buffer error: target ({target}) should be raw_target + 5 ({expected_target})"

        # Calculate and validate R:R ratio with final target (after buffer)
        risk = abs(entry - stop)
        reward = abs(target - entry)

        if risk == 0:
            return False, "Risk cannot be zero (entry == stop)"

        rr_ratio = reward / risk

        # Minimum R:R requirement: 1.3:1
        min_rr = 1.3
        if rr_ratio < min_rr:
            return False, f"R:R too low: {rr_ratio:.2f}:1 (minimum {min_rr}:1 required after 5pt buffer)"

        logger.info(f"Validation passed: {decision['decision']} | R:R = {rr_ratio:.2f}:1 | "
                    f"Risk: {risk:.2f}pts | Reward: {reward:.2f}pts")

        return True, ""

    def generate_signal(self, decision: Dict[str, Any], timestamp: datetime = None) -> bool:
        """
        Generate trade signal and append to CSV

        Args:
            decision: Decision dictionary from TradingAgent
            timestamp: Optional timestamp (defaults to now)

        Returns:
            True if signal generated successfully
        """
        # Validate decision
        is_valid, error_msg = self.validate_decision(decision)
        if not is_valid:
            logger.error(f"Signal validation failed: {error_msg}")
            return False

        # Format timestamp
        if timestamp is None:
            timestamp = datetime.now()
        time_str = timestamp.strftime('%m/%d/%Y %H:%M:%S')

        # Prepare row data
        row = [
            time_str,
            decision['decision'],
            f"{decision['entry']:.2f}",
            f"{decision['stop']:.2f}",
            f"{decision['target']:.2f}"
        ]

        # Append to CSV
        try:
            with open(self.output_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)

            logger.info(f"Signal generated: {decision['decision']} @ {decision['entry']:.2f}")
            logger.info(f"  Stop: {decision['stop']:.2f} | Target: {decision['target']:.2f}")

            return True

        except Exception as e:
            logger.error(f"Error writing signal to CSV: {e}")
            return False

    def get_signal_summary(self, decision: Dict[str, Any]) -> str:
        """
        Generate human-readable signal summary

        Args:
            decision: Decision dictionary

        Returns:
            Summary string
        """
        entry = decision['entry']
        stop = decision['stop']
        target = decision['target']

        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr_ratio = reward / risk if risk > 0 else 0

        lines = []
        lines.append(f"=== TRADE SIGNAL GENERATED ===")
        lines.append(f"Direction: {decision['decision']}")

        # Show setup type if available
        if 'setup_type' in decision and decision['setup_type']:
            lines.append(f"Setup Type: {decision['setup_type']}")

        lines.append(f"Entry: {entry:.2f}")
        lines.append(f"Stop Loss: {stop:.2f} ({risk:.2f}pts risk)")

        # Show raw target and buffer calculation if available
        if 'raw_target' in decision and decision['raw_target'] is not None:
            raw_target = decision['raw_target']
            buffer_direction = "+" if decision['decision'] == 'SHORT' else "-"
            lines.append(f"Raw Target: {raw_target:.2f}")
            lines.append(f"Final Target: {target:.2f} ({raw_target:.2f} {buffer_direction} 5pt buffer)")
        else:
            lines.append(f"Target: {target:.2f} ({reward:.2f}pts reward)")

        lines.append(f"Risk/Reward: {rr_ratio:.2f}:1")

        # Show confidence if available
        if 'confidence' in decision:
            lines.append(f"Confidence: {decision['confidence']:.0%}")

        # Show reasoning if available
        if 'reasoning' in decision and decision['reasoning']:
            lines.append(f"\nReasoning: {decision['reasoning']}")

        lines.append(f"\nSignal written to: {self.output_file}")

        return "\n".join(lines)

    def count_signals_today(self) -> int:
        """
        Count number of signals generated today

        Returns:
            Number of signals today
        """
        today = datetime.now().strftime('%m/%d/%Y')
        count = 0

        try:
            with open(self.output_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['DateTime'].startswith(today):
                        count += 1
        except Exception as e:
            logger.error(f"Error counting signals: {e}")
            return 0

        return count

    def get_recent_signals(self, limit: int = 10) -> list:
        """
        Get most recent signals

        Args:
            limit: Number of signals to retrieve

        Returns:
            List of signal dictionaries
        """
        signals = []

        try:
            with open(self.output_file, 'r') as f:
                reader = csv.DictReader(f)
                all_signals = list(reader)
                signals = all_signals[-limit:] if len(all_signals) > limit else all_signals
        except Exception as e:
            logger.error(f"Error reading signals: {e}")
            return []

        return signals

    def clear_signals(self):
        """Clear all signals (reinitialize CSV)"""
        self._initialize_csv()
        logger.info("Trade signals cleared")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    generator = SignalGenerator("data/trade_signals.csv")

    # Sample decision
    sample_decision = {
        'decision': 'SHORT',
        'entry': 14712.00,
        'stop': 14730.00,
        'target': 14650.00,
        'risk_reward': 3.44,
        'confidence': 0.78
    }

    # Generate signal
    success = generator.generate_signal(sample_decision)

    if success:
        print(generator.get_signal_summary(sample_decision))
        print(f"\nSignals today: {generator.count_signals_today()}")
