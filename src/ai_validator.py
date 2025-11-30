"""
AI Decision Validator
Validates and cross-checks AI trading decisions to catch errors
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of AI decision validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    adjusted_decision: Optional[Dict[str, Any]]
    override_reason: Optional[str]


class AIDecisionValidator:
    """
    Validates AI trading decisions against objective rules

    The AI is NOT trusted blindly. Every decision must pass:
    1. Mathematical validation (stop/target make sense)
    2. Rule-based checks (matches market conditions)
    3. Consistency checks (not contradicting itself)
    4. Sanity checks (prices are reasonable)

    If validation fails, the trade is BLOCKED regardless of AI confidence.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize validator"""
        self.config = config or {}
        self.recent_decisions: List[Dict[str, Any]] = []
        self.max_history = 10

        logger.info("AIDecisionValidator initialized - AI decisions will be validated")

    def validate_decision(
        self,
        ai_decision: Dict[str, Any],
        current_price: float,
        market_data: Dict[str, float],
        fvg_context: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate an AI trading decision

        Args:
            ai_decision: The decision from Claude
            current_price: Current market price
            market_data: EMA and indicator values
            fvg_context: FVG zone information

        Returns:
            ValidationResult with pass/fail and reasons
        """
        errors = []
        warnings = []

        # Extract decision components
        direction = ai_decision.get('primary_decision', 'NONE')

        if direction == 'NONE':
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                adjusted_decision=None,
                override_reason=None
            )

        # Get the chosen setup
        if direction == 'LONG':
            setup = ai_decision.get('long_setup', {})
        else:
            setup = ai_decision.get('short_setup', {})

        entry = setup.get('entry', 0)
        stop = setup.get('stop', 0)
        target = setup.get('target', 0)
        confidence = setup.get('confidence', 0)

        # === VALIDATION 1: Basic Math ===
        math_errors = self._validate_math(direction, entry, stop, target, current_price)
        errors.extend(math_errors)

        # === VALIDATION 2: Price Sanity ===
        sanity_errors = self._validate_price_sanity(entry, stop, target, current_price)
        errors.extend(sanity_errors)

        # === VALIDATION 3: Trend Alignment ===
        trend_warnings = self._validate_trend_alignment(direction, market_data)
        warnings.extend(trend_warnings)

        # === VALIDATION 4: FVG Relevance ===
        fvg_warnings = self._validate_fvg_relevance(direction, entry, fvg_context)
        warnings.extend(fvg_warnings)

        # === VALIDATION 5: Consistency Check ===
        consistency_warnings = self._check_consistency(direction, confidence)
        warnings.extend(consistency_warnings)

        # === VALIDATION 6: Risk/Reward Check ===
        rr_errors = self._validate_risk_reward(entry, stop, target)
        errors.extend(rr_errors)

        # Store decision for consistency tracking
        self._record_decision(ai_decision, current_price)

        # Determine if valid
        is_valid = len(errors) == 0

        if not is_valid:
            logger.error(f"AI decision REJECTED: {', '.join(errors)}")

        if warnings:
            logger.warning(f"AI decision warnings: {', '.join(warnings)}")

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            adjusted_decision=None,
            override_reason=f"Failed validation: {errors[0]}" if errors else None
        )

    def _validate_math(
        self,
        direction: str,
        entry: float,
        stop: float,
        target: float,
        current_price: float
    ) -> List[str]:
        """Validate basic mathematical relationships"""
        errors = []

        if direction == "LONG":
            if stop >= entry:
                errors.append(f"LONG stop ({stop}) must be BELOW entry ({entry})")
            if target <= entry:
                errors.append(f"LONG target ({target}) must be ABOVE entry ({entry})")
            if stop >= current_price:
                errors.append(f"LONG stop ({stop}) above current price ({current_price})")

        elif direction == "SHORT":
            if stop <= entry:
                errors.append(f"SHORT stop ({stop}) must be ABOVE entry ({entry})")
            if target >= entry:
                errors.append(f"SHORT target ({target}) must be BELOW entry ({entry})")
            if stop <= current_price:
                errors.append(f"SHORT stop ({stop}) below current price ({current_price})")

        return errors

    def _validate_price_sanity(
        self,
        entry: float,
        stop: float,
        target: float,
        current_price: float
    ) -> List[str]:
        """Validate prices are within reasonable range"""
        errors = []

        # Check for zero/negative prices
        if entry <= 0:
            errors.append(f"Invalid entry price: {entry}")
        if stop <= 0:
            errors.append(f"Invalid stop price: {stop}")
        if target <= 0:
            errors.append(f"Invalid target price: {target}")

        # Check entry is near current price (within 2%)
        if current_price > 0:
            entry_distance_pct = abs(entry - current_price) / current_price * 100
            if entry_distance_pct > 2:
                errors.append(f"Entry ({entry}) too far from current price ({current_price}) - {entry_distance_pct:.1f}%")

        # Check stop distance is reasonable (not too tight or too wide)
        stop_distance = abs(entry - stop)
        if stop_distance < 10:
            errors.append(f"Stop too tight: {stop_distance:.1f} points (min 10)")
        if stop_distance > 100:
            errors.append(f"Stop too wide: {stop_distance:.1f} points (max 100)")

        return errors

    def _validate_trend_alignment(
        self,
        direction: str,
        market_data: Dict[str, float]
    ) -> List[str]:
        """Check if trade aligns with trend (warning only)"""
        warnings = []

        ema21 = market_data.get('ema21', 0)
        ema75 = market_data.get('ema75', 0)
        ema150 = market_data.get('ema150', 0)

        if ema21 == 0 or ema75 == 0:
            return warnings

        # Check EMA alignment
        if direction == "LONG":
            if ema21 < ema75 < ema150:
                warnings.append("LONG trade against strong downtrend (all EMAs bearish)")
            elif ema21 < ema75:
                warnings.append("LONG trade against short-term downtrend (EMA21 < EMA75)")

        elif direction == "SHORT":
            if ema21 > ema75 > ema150:
                warnings.append("SHORT trade against strong uptrend (all EMAs bullish)")
            elif ema21 > ema75:
                warnings.append("SHORT trade against short-term uptrend (EMA21 > EMA75)")

        return warnings

    def _validate_fvg_relevance(
        self,
        direction: str,
        entry: float,
        fvg_context: Dict[str, Any]
    ) -> List[str]:
        """Check if entry is actually near an FVG zone"""
        warnings = []

        if direction == "LONG":
            nearest_fvg = fvg_context.get('nearest_bearish_fvg')  # LONG targets bearish FVGs
            if nearest_fvg:
                zone_bottom = nearest_fvg.get('bottom', 0)
                zone_top = nearest_fvg.get('top', 0)
                distance = nearest_fvg.get('distance', 999)

                if distance > 50:
                    warnings.append(f"Entry far from nearest FVG ({distance:.1f} points)")

        elif direction == "SHORT":
            nearest_fvg = fvg_context.get('nearest_bullish_fvg')  # SHORT targets bullish FVGs
            if nearest_fvg:
                distance = nearest_fvg.get('distance', 999)

                if distance > 50:
                    warnings.append(f"Entry far from nearest FVG ({distance:.1f} points)")

        return warnings

    def _validate_risk_reward(
        self,
        entry: float,
        stop: float,
        target: float
    ) -> List[str]:
        """Validate risk/reward meets minimum requirements"""
        errors = []

        risk = abs(entry - stop)
        reward = abs(target - entry)

        if risk == 0:
            errors.append("Risk is zero (stop = entry)")
            return errors

        rr_ratio = reward / risk

        if rr_ratio < 3.0:
            errors.append(f"R/R ratio {rr_ratio:.2f} below minimum 3.0")

        return errors

    def _check_consistency(
        self,
        direction: str,
        confidence: float
    ) -> List[str]:
        """Check for flip-flopping decisions"""
        warnings = []

        if len(self.recent_decisions) < 2:
            return warnings

        # Check if we're flip-flopping
        last_decision = self.recent_decisions[-1]
        last_direction = last_decision.get('direction', 'NONE')

        if last_direction != 'NONE' and last_direction != direction:
            time_diff = (datetime.now() - last_decision.get('timestamp', datetime.now())).total_seconds()

            if time_diff < 3600:  # Within 1 hour
                warnings.append(f"Direction changed from {last_direction} to {direction} within {time_diff/60:.0f} minutes")

        return warnings

    def _record_decision(self, decision: Dict[str, Any], current_price: float):
        """Record decision for consistency tracking"""
        record = {
            'timestamp': datetime.now(),
            'direction': decision.get('primary_decision', 'NONE'),
            'price': current_price,
            'confidence': decision.get('long_setup', {}).get('confidence', 0) or
                         decision.get('short_setup', {}).get('confidence', 0)
        }

        self.recent_decisions.append(record)

        # Keep only recent history
        if len(self.recent_decisions) > self.max_history:
            self.recent_decisions.pop(0)

    def get_validation_summary(self, result: ValidationResult) -> str:
        """Get human-readable validation summary"""
        lines = [
            "=" * 50,
            "AI DECISION VALIDATION",
            "=" * 50,
            f"Status: {'PASSED' if result.is_valid else 'FAILED'}",
        ]

        if result.errors:
            lines.append("")
            lines.append("ERRORS (trade blocked):")
            for error in result.errors:
                lines.append(f"  X {error}")

        if result.warnings:
            lines.append("")
            lines.append("WARNINGS (proceed with caution):")
            for warning in result.warnings:
                lines.append(f"  ! {warning}")

        if result.is_valid and not result.warnings:
            lines.append("")
            lines.append("All validations passed")

        lines.append("=" * 50)

        return "\n".join(lines)


class AIConfidenceCalibrator:
    """
    Tracks AI confidence vs actual outcomes to calibrate trust

    The AI's confidence scores mean nothing until we prove otherwise.
    This class tracks whether high-confidence trades actually win more.
    """

    def __init__(self):
        """Initialize calibrator"""
        self.outcomes: List[Dict[str, Any]] = []
        self.confidence_buckets = {
            'low': {'range': (0, 0.6), 'wins': 0, 'total': 0},
            'medium': {'range': (0.6, 0.75), 'wins': 0, 'total': 0},
            'high': {'range': (0.75, 0.9), 'wins': 0, 'total': 0},
            'very_high': {'range': (0.9, 1.0), 'wins': 0, 'total': 0},
        }

    def record_outcome(self, confidence: float, result: str):
        """Record trade outcome for calibration"""
        self.outcomes.append({
            'confidence': confidence,
            'result': result,
            'timestamp': datetime.now()
        })

        # Update bucket
        for bucket_name, bucket in self.confidence_buckets.items():
            low, high = bucket['range']
            if low <= confidence < high:
                bucket['total'] += 1
                if result == 'WIN':
                    bucket['wins'] += 1
                break

    def get_calibration_report(self) -> str:
        """Get calibration report showing confidence vs reality"""
        lines = [
            "=" * 50,
            "AI CONFIDENCE CALIBRATION",
            "=" * 50,
            "",
            "Does higher AI confidence = higher win rate?",
            "",
        ]

        for bucket_name, bucket in self.confidence_buckets.items():
            if bucket['total'] > 0:
                actual_rate = bucket['wins'] / bucket['total']
                low, high = bucket['range']
                lines.append(
                    f"{bucket_name.upper()} ({low*100:.0f}-{high*100:.0f}%): "
                    f"{actual_rate*100:.1f}% actual win rate "
                    f"({bucket['wins']}/{bucket['total']} trades)"
                )
            else:
                lines.append(f"{bucket_name.upper()}: No data yet")

        lines.extend([
            "",
            "If win rates are similar across buckets,",
            "AI confidence scores are NOT predictive.",
            "=" * 50
        ])

        return "\n".join(lines)

    def should_trust_confidence(self) -> Tuple[bool, str]:
        """Determine if AI confidence is actually predictive"""
        if sum(b['total'] for b in self.confidence_buckets.values()) < 20:
            return False, "Insufficient data (need 20+ trades)"

        # Calculate win rates for each bucket
        rates = {}
        for name, bucket in self.confidence_buckets.items():
            if bucket['total'] >= 3:
                rates[name] = bucket['wins'] / bucket['total']

        if len(rates) < 2:
            return False, "Need data in multiple confidence levels"

        # Check if higher confidence = higher win rate
        if 'very_high' in rates and 'low' in rates:
            if rates['very_high'] > rates['low'] + 0.1:  # 10% better
                return True, "High confidence trades do perform better"

        return False, "Confidence scores not predictive - treat all trades equally"
