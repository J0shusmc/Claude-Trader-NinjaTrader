"""
Edge Filters Module
Implements statistical edge through entry confirmation, market regime detection,
and optimal timing filters to improve trade probability.
"""

import logging
from datetime import datetime, time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification"""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    RANGING = "ranging"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    VOLATILE = "volatile"


class SessionType(Enum):
    """Trading session classification"""
    PREMARKET = "premarket"
    OPEN_DRIVE = "open_drive"        # First 30 min - volatile
    MORNING = "morning"              # 10:00-12:00 - best trends
    LUNCH = "lunch"                  # 12:00-14:00 - choppy
    AFTERNOON = "afternoon"          # 14:00-15:30 - second best
    CLOSE = "close"                  # Last 30 min - volatile
    AFTER_HOURS = "after_hours"


@dataclass
class SetupQuality:
    """Quality assessment of a trade setup"""
    score: float              # 0-100 quality score
    grade: str                # A, B, C, D, F
    edge_factors: List[str]   # Positive factors
    risk_factors: List[str]   # Negative factors
    recommendation: str       # TAKE, WAIT, SKIP
    adjusted_size: float      # Position size multiplier (0.5-1.5)


class EdgeFilters:
    """
    Edge filter system to improve trade probability

    Key Principles:
    1. Only trade when multiple factors align (confluence)
    2. Avoid low-probability conditions (lunch, high volatility)
    3. Require price action confirmation at zones
    4. Adjust position size based on setup quality
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize edge filters"""
        self.config = config or {}

        # Session times (Eastern Time)
        self.sessions = {
            SessionType.PREMARKET: (time(4, 0), time(9, 30)),
            SessionType.OPEN_DRIVE: (time(9, 30), time(10, 0)),
            SessionType.MORNING: (time(10, 0), time(12, 0)),
            SessionType.LUNCH: (time(12, 0), time(14, 0)),
            SessionType.AFTERNOON: (time(14, 0), time(15, 30)),
            SessionType.CLOSE: (time(15, 30), time(16, 0)),
            SessionType.AFTER_HOURS: (time(16, 0), time(20, 0)),
        }

        # Session quality scores (based on typical NQ behavior)
        self.session_scores = {
            SessionType.PREMARKET: 40,
            SessionType.OPEN_DRIVE: 50,      # Volatile but tradeable
            SessionType.MORNING: 90,          # Best session
            SessionType.LUNCH: 30,            # Avoid - choppy
            SessionType.AFTERNOON: 80,        # Good trends
            SessionType.CLOSE: 50,            # Volatile
            SessionType.AFTER_HOURS: 20,      # Low liquidity
        }

        logger.info("EdgeFilters initialized")

    def get_current_session(self, current_time: datetime = None) -> SessionType:
        """Determine current trading session"""
        if current_time is None:
            current_time = datetime.now()

        current = current_time.time()

        for session, (start, end) in self.sessions.items():
            if start <= current < end:
                return session

        return SessionType.AFTER_HOURS

    def detect_market_regime(
        self,
        ema21: float,
        ema75: float,
        ema150: float,
        current_price: float,
        atr: float = None,
        recent_range: float = None
    ) -> Tuple[MarketRegime, float]:
        """
        Detect current market regime

        Returns:
            Tuple of (regime, strength 0-100)
        """
        # EMA alignment analysis
        ema_bull = ema21 > ema75 > ema150
        ema_bear = ema21 < ema75 < ema150

        # Price position relative to EMAs
        above_all = current_price > ema21 > ema75 > ema150
        below_all = current_price < ema21 < ema75 < ema150

        # EMA spreads (trend strength)
        spread_21_75 = abs(ema21 - ema75)
        spread_75_150 = abs(ema75 - ema150)

        # Strong trend: wide spreads + aligned
        if above_all and spread_21_75 > 20:
            return MarketRegime.STRONG_UPTREND, 90
        elif below_all and spread_21_75 > 20:
            return MarketRegime.STRONG_DOWNTREND, 90
        elif ema_bull:
            return MarketRegime.UPTREND, 70
        elif ema_bear:
            return MarketRegime.DOWNTREND, 70
        else:
            # EMAs tangled = ranging
            return MarketRegime.RANGING, 50

    def check_entry_confirmation(
        self,
        direction: str,
        current_price: float,
        fvg_zone: Dict[str, float],
        recent_bars: List[Dict[str, float]]
    ) -> Tuple[bool, str, float]:
        """
        Check for price action confirmation at FVG zone

        Confirmation signals:
        - Rejection wick at zone
        - Engulfing candle
        - Pin bar / hammer
        - Break and retest

        Returns:
            Tuple of (confirmed, reason, confidence_boost)
        """
        if not recent_bars or len(recent_bars) < 2:
            return False, "Insufficient data", 0

        last_bar = recent_bars[-1]
        prev_bar = recent_bars[-2]

        zone_top = fvg_zone.get('top', 0)
        zone_bottom = fvg_zone.get('bottom', 0)
        zone_mid = (zone_top + zone_bottom) / 2

        # Check if price is actually at the zone
        in_zone = zone_bottom <= current_price <= zone_top
        near_zone = abs(current_price - zone_mid) < (zone_top - zone_bottom) * 2

        if not (in_zone or near_zone):
            return False, "Price not at zone", 0

        # Calculate bar metrics
        bar_range = last_bar['High'] - last_bar['Low']
        bar_body = abs(last_bar['Close'] - last_bar['Open'])

        if bar_range == 0:
            return False, "Zero range bar", 0

        body_ratio = bar_body / bar_range

        # Upper and lower wicks
        if last_bar['Close'] > last_bar['Open']:  # Bullish bar
            upper_wick = last_bar['High'] - last_bar['Close']
            lower_wick = last_bar['Open'] - last_bar['Low']
        else:  # Bearish bar
            upper_wick = last_bar['High'] - last_bar['Open']
            lower_wick = last_bar['Close'] - last_bar['Low']

        # === LONG CONFIRMATION ===
        if direction == "LONG":
            # 1. Rejection wick (long lower wick showing buyers)
            if lower_wick > bar_range * 0.6 and body_ratio < 0.3:
                return True, "Hammer/Pin bar rejection", 0.15

            # 2. Bullish engulfing
            if (last_bar['Close'] > last_bar['Open'] and
                last_bar['Close'] > prev_bar['High'] and
                last_bar['Open'] < prev_bar['Low']):
                return True, "Bullish engulfing", 0.20

            # 3. Strong bullish close in zone
            if (last_bar['Close'] > last_bar['Open'] and
                body_ratio > 0.6 and
                last_bar['Low'] >= zone_bottom):
                return True, "Strong bullish momentum", 0.10

            # 4. Failed breakdown (wick below zone, close inside)
            if (last_bar['Low'] < zone_bottom and
                last_bar['Close'] > zone_bottom):
                return True, "Failed breakdown", 0.15

        # === SHORT CONFIRMATION ===
        elif direction == "SHORT":
            # 1. Rejection wick (long upper wick showing sellers)
            if upper_wick > bar_range * 0.6 and body_ratio < 0.3:
                return True, "Shooting star rejection", 0.15

            # 2. Bearish engulfing
            if (last_bar['Close'] < last_bar['Open'] and
                last_bar['Close'] < prev_bar['Low'] and
                last_bar['Open'] > prev_bar['High']):
                return True, "Bearish engulfing", 0.20

            # 3. Strong bearish close in zone
            if (last_bar['Close'] < last_bar['Open'] and
                body_ratio > 0.6 and
                last_bar['High'] <= zone_top):
                return True, "Strong bearish momentum", 0.10

            # 4. Failed breakout (wick above zone, close inside)
            if (last_bar['High'] > zone_top and
                last_bar['Close'] < zone_top):
                return True, "Failed breakout", 0.15

        return False, "No confirmation pattern", 0

    def calculate_setup_quality(
        self,
        direction: str,
        entry: float,
        stop: float,
        target: float,
        confidence: float,
        fvg_zone: Dict[str, float],
        market_data: Dict[str, float],
        recent_bars: List[Dict[str, float]] = None
    ) -> SetupQuality:
        """
        Calculate comprehensive setup quality score

        Scoring factors:
        - Session timing (0-25 points)
        - Market regime alignment (0-25 points)
        - Entry confirmation (0-25 points)
        - Risk/reward quality (0-25 points)
        """
        edge_factors = []
        risk_factors = []
        score = 0

        # === 1. SESSION TIMING (0-25 points) ===
        session = self.get_current_session()
        session_score = self.session_scores.get(session, 50) / 4  # Max 25

        if session == SessionType.MORNING:
            edge_factors.append("Prime trading session (morning)")
            score += 25
        elif session == SessionType.AFTERNOON:
            edge_factors.append("Good session (afternoon)")
            score += 20
        elif session == SessionType.LUNCH:
            risk_factors.append("Lunch session - typically choppy")
            score += 7
        elif session in [SessionType.OPEN_DRIVE, SessionType.CLOSE]:
            risk_factors.append("Volatile session period")
            score += 12
        else:
            risk_factors.append("Suboptimal trading hours")
            score += 5

        # === 2. MARKET REGIME (0-25 points) ===
        regime, regime_strength = self.detect_market_regime(
            market_data.get('ema21', 0),
            market_data.get('ema75', 0),
            market_data.get('ema150', 0),
            entry
        )

        # Check if direction aligns with regime
        regime_aligned = (
            (direction == "LONG" and regime in [MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND]) or
            (direction == "SHORT" and regime in [MarketRegime.DOWNTREND, MarketRegime.STRONG_DOWNTREND])
        )

        if regime_aligned:
            edge_factors.append(f"Trade aligns with {regime.value}")
            score += 25
        elif regime == MarketRegime.RANGING:
            risk_factors.append("Ranging market - breakout/breakdown risk")
            score += 10
        else:
            risk_factors.append(f"Counter-trend trade ({regime.value})")
            score += 5

        # === 3. ENTRY CONFIRMATION (0-25 points) ===
        if recent_bars:
            confirmed, reason, boost = self.check_entry_confirmation(
                direction, entry, fvg_zone, recent_bars
            )

            if confirmed:
                edge_factors.append(f"Entry confirmed: {reason}")
                score += 25
            else:
                risk_factors.append("No price action confirmation")
                score += 8
        else:
            risk_factors.append("Cannot verify entry confirmation")
            score += 10

        # === 4. RISK/REWARD QUALITY (0-25 points) ===
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr_ratio = reward / risk if risk > 0 else 0

        if rr_ratio >= 4:
            edge_factors.append(f"Excellent R/R ({rr_ratio:.1f}:1)")
            score += 25
        elif rr_ratio >= 3:
            edge_factors.append(f"Good R/R ({rr_ratio:.1f}:1)")
            score += 20
        elif rr_ratio >= 2:
            score += 12
        else:
            risk_factors.append(f"Low R/R ({rr_ratio:.1f}:1)")
            score += 5

        # === CALCULATE GRADE AND RECOMMENDATION ===
        if score >= 85:
            grade = "A"
            recommendation = "TAKE"
            adjusted_size = 1.5
        elif score >= 70:
            grade = "B"
            recommendation = "TAKE"
            adjusted_size = 1.0
        elif score >= 55:
            grade = "C"
            recommendation = "WAIT"
            adjusted_size = 0.5
        elif score >= 40:
            grade = "D"
            recommendation = "SKIP"
            adjusted_size = 0.0
        else:
            grade = "F"
            recommendation = "SKIP"
            adjusted_size = 0.0

        return SetupQuality(
            score=score,
            grade=grade,
            edge_factors=edge_factors,
            risk_factors=risk_factors,
            recommendation=recommendation,
            adjusted_size=adjusted_size
        )

    def should_take_trade(
        self,
        direction: str,
        entry: float,
        stop: float,
        target: float,
        confidence: float,
        fvg_zone: Dict[str, float],
        market_data: Dict[str, float],
        recent_bars: List[Dict[str, float]] = None
    ) -> Tuple[bool, SetupQuality]:
        """
        Main method: Determine if trade should be taken

        Returns:
            Tuple of (should_take, quality_assessment)
        """
        quality = self.calculate_setup_quality(
            direction=direction,
            entry=entry,
            stop=stop,
            target=target,
            confidence=confidence,
            fvg_zone=fvg_zone,
            market_data=market_data,
            recent_bars=recent_bars
        )

        should_take = quality.recommendation == "TAKE"

        # Log the assessment
        logger.info(f"Setup Quality: {quality.grade} ({quality.score}/100)")
        logger.info(f"Edge Factors: {', '.join(quality.edge_factors)}")
        if quality.risk_factors:
            logger.info(f"Risk Factors: {', '.join(quality.risk_factors)}")
        logger.info(f"Recommendation: {quality.recommendation}")

        return should_take, quality

    def get_quality_summary(self, quality: SetupQuality) -> str:
        """Get human-readable quality summary"""
        lines = [
            "=" * 50,
            f"SETUP QUALITY: {quality.grade} ({quality.score}/100)",
            "=" * 50,
            "",
            "EDGE FACTORS (+):",
        ]

        for factor in quality.edge_factors:
            lines.append(f"  + {factor}")

        if quality.risk_factors:
            lines.append("")
            lines.append("RISK FACTORS (-):")
            for factor in quality.risk_factors:
                lines.append(f"  - {factor}")

        lines.extend([
            "",
            f"RECOMMENDATION: {quality.recommendation}",
            f"POSITION SIZE: {quality.adjusted_size}x normal",
            "=" * 50
        ])

        return "\n".join(lines)
