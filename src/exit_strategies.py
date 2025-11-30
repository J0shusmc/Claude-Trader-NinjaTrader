"""
Exit Strategies Module
Implements intelligent exit management for profit maximization
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ExitType(Enum):
    """Types of exits"""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    PARTIAL_PROFIT = "partial_profit"
    TIME_EXIT = "time_exit"
    BREAKEVEN = "breakeven"
    REVERSAL = "reversal"


@dataclass
class ExitPlan:
    """Complete exit plan for a trade"""
    initial_stop: float
    target_1: float          # First target (partial)
    target_2: float          # Second target (partial)
    target_3: float          # Final target (runner)
    trailing_trigger: float  # Price at which trailing starts
    trailing_offset: float   # Points to trail behind price
    breakeven_trigger: float # Price at which to move stop to breakeven
    time_limit_bars: int     # Max bars to hold
    partial_sizes: Tuple[float, float, float]  # Size % for each target


class ExitManager:
    """
    Intelligent exit management system

    Strategies:
    1. Scaled exits - Take partial profits at multiple targets
    2. Trailing stop - Lock in profits as trade moves favorably
    3. Breakeven stop - Eliminate risk once trade is profitable
    4. Time-based exit - Don't hold losing trades indefinitely
    5. Reversal detection - Exit if market structure breaks
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize exit manager"""
        self.config = config or {}

        # Default exit settings
        self.partial_at_1r = 0.33    # Take 33% at 1R
        self.partial_at_2r = 0.33    # Take 33% at 2R
        self.runner_size = 0.34      # Let 34% run

        self.breakeven_trigger_r = 1.5  # Move to BE at 1.5R
        self.trailing_trigger_r = 2.0   # Start trailing at 2R
        self.trailing_offset_r = 0.5    # Trail 0.5R behind

        self.max_hold_bars = 20  # Exit after 20 bars if not hitting targets

        logger.info("ExitManager initialized")

    def create_exit_plan(
        self,
        direction: str,
        entry: float,
        stop: float,
        target: float,
        quantity: int
    ) -> ExitPlan:
        """
        Create a complete exit plan with scaled targets

        Args:
            direction: LONG or SHORT
            entry: Entry price
            stop: Initial stop loss
            target: Original target price
            quantity: Total position size

        Returns:
            ExitPlan with all exit levels
        """
        risk = abs(entry - stop)
        reward = abs(target - entry)

        if direction == "LONG":
            # Calculate scaled targets
            target_1 = entry + (risk * 1.0)      # 1R
            target_2 = entry + (risk * 2.0)      # 2R
            target_3 = entry + (risk * 3.5)      # 3.5R (let it run)

            breakeven_trigger = entry + (risk * self.breakeven_trigger_r)
            trailing_trigger = entry + (risk * self.trailing_trigger_r)
            trailing_offset = risk * self.trailing_offset_r

        else:  # SHORT
            target_1 = entry - (risk * 1.0)
            target_2 = entry - (risk * 2.0)
            target_3 = entry - (risk * 3.5)

            breakeven_trigger = entry - (risk * self.breakeven_trigger_r)
            trailing_trigger = entry - (risk * self.trailing_trigger_r)
            trailing_offset = risk * self.trailing_offset_r

        # Calculate partial sizes
        qty_1 = max(1, int(quantity * self.partial_at_1r))
        qty_2 = max(1, int(quantity * self.partial_at_2r))
        qty_3 = quantity - qty_1 - qty_2

        return ExitPlan(
            initial_stop=stop,
            target_1=target_1,
            target_2=target_2,
            target_3=target_3,
            trailing_trigger=trailing_trigger,
            trailing_offset=trailing_offset,
            breakeven_trigger=breakeven_trigger,
            time_limit_bars=self.max_hold_bars,
            partial_sizes=(qty_1, qty_2, qty_3)
        )

    def calculate_trailing_stop(
        self,
        direction: str,
        current_price: float,
        entry: float,
        current_stop: float,
        highest_price: float,
        lowest_price: float,
        trailing_offset: float
    ) -> Optional[float]:
        """
        Calculate new trailing stop level

        Args:
            direction: LONG or SHORT
            current_price: Current market price
            entry: Original entry price
            current_stop: Current stop loss level
            highest_price: Highest price since entry (for longs)
            lowest_price: Lowest price since entry (for shorts)
            trailing_offset: Points to trail behind

        Returns:
            New stop level if should be updated, None otherwise
        """
        if direction == "LONG":
            # Trail below the highest price
            new_stop = highest_price - trailing_offset

            # Only move stop UP, never down
            if new_stop > current_stop and new_stop < current_price:
                logger.info(f"Trailing stop updated: {current_stop:.2f} -> {new_stop:.2f}")
                return new_stop

        else:  # SHORT
            # Trail above the lowest price
            new_stop = lowest_price + trailing_offset

            # Only move stop DOWN, never up
            if new_stop < current_stop and new_stop > current_price:
                logger.info(f"Trailing stop updated: {current_stop:.2f} -> {new_stop:.2f}")
                return new_stop

        return None

    def should_move_to_breakeven(
        self,
        direction: str,
        current_price: float,
        entry: float,
        current_stop: float,
        breakeven_trigger: float
    ) -> bool:
        """
        Check if stop should be moved to breakeven

        Returns:
            True if stop should be moved to entry (breakeven)
        """
        # Already at or past breakeven
        if direction == "LONG" and current_stop >= entry:
            return False
        if direction == "SHORT" and current_stop <= entry:
            return False

        # Check if trigger hit
        if direction == "LONG":
            if current_price >= breakeven_trigger:
                logger.info(f"Moving stop to breakeven: {current_stop:.2f} -> {entry:.2f}")
                return True
        else:
            if current_price <= breakeven_trigger:
                logger.info(f"Moving stop to breakeven: {current_stop:.2f} -> {entry:.2f}")
                return True

        return False

    def check_partial_exit(
        self,
        direction: str,
        current_price: float,
        exit_plan: ExitPlan,
        partials_taken: int
    ) -> Optional[Tuple[float, int]]:
        """
        Check if a partial exit should be taken

        Args:
            direction: LONG or SHORT
            current_price: Current price
            exit_plan: The exit plan
            partials_taken: Number of partials already taken (0, 1, or 2)

        Returns:
            Tuple of (exit_price, quantity) if partial should be taken, None otherwise
        """
        if partials_taken >= 2:
            return None  # All partials taken, only runner left

        targets = [exit_plan.target_1, exit_plan.target_2]
        sizes = exit_plan.partial_sizes

        target = targets[partials_taken]
        size = sizes[partials_taken]

        if direction == "LONG":
            if current_price >= target:
                logger.info(f"Partial {partials_taken + 1} triggered at {target:.2f}")
                return (target, size)
        else:
            if current_price <= target:
                logger.info(f"Partial {partials_taken + 1} triggered at {target:.2f}")
                return (target, size)

        return None

    def check_time_exit(
        self,
        bars_in_trade: int,
        current_pnl: float,
        exit_plan: ExitPlan
    ) -> bool:
        """
        Check if trade should be exited due to time

        Time exit rules:
        - Exit at market if held too long AND in profit
        - Exit at market if held too long AND at small loss (cut it)
        - Hold through max time if trade is working (trending)
        """
        if bars_in_trade >= exit_plan.time_limit_bars:
            if current_pnl >= 0:
                logger.info(f"Time exit: {bars_in_trade} bars, taking profit {current_pnl:.2f}")
                return True
            elif current_pnl > -10:  # Small loss
                logger.info(f"Time exit: {bars_in_trade} bars, cutting small loss {current_pnl:.2f}")
                return True

        return False

    def detect_reversal(
        self,
        direction: str,
        current_price: float,
        ema21: float,
        ema75: float,
        recent_bars: List[Dict[str, float]]
    ) -> bool:
        """
        Detect if market structure has reversed against the trade

        Reversal signals:
        - Price crosses key EMA against trade direction
        - Strong momentum bar against position
        - Break of structure (lower low in uptrend, higher high in downtrend)
        """
        if not recent_bars or len(recent_bars) < 3:
            return False

        last_bar = recent_bars[-1]

        if direction == "LONG":
            # Bearish reversal signals
            # 1. Price closes below 75 EMA
            if current_price < ema75 and recent_bars[-2].get('Close', 0) > ema75:
                logger.warning("Reversal detected: Price broke below 75 EMA")
                return True

            # 2. Strong bearish bar (>75% body, closes on low)
            bar_range = last_bar['High'] - last_bar['Low']
            if bar_range > 0:
                body = abs(last_bar['Close'] - last_bar['Open'])
                if (last_bar['Close'] < last_bar['Open'] and
                    body / bar_range > 0.75 and
                    bar_range > 15):  # Significant move
                    logger.warning("Reversal detected: Strong bearish momentum")
                    return True

        else:  # SHORT
            # Bullish reversal signals
            if current_price > ema75 and recent_bars[-2].get('Close', 0) < ema75:
                logger.warning("Reversal detected: Price broke above 75 EMA")
                return True

            bar_range = last_bar['High'] - last_bar['Low']
            if bar_range > 0:
                body = abs(last_bar['Close'] - last_bar['Open'])
                if (last_bar['Close'] > last_bar['Open'] and
                    body / bar_range > 0.75 and
                    bar_range > 15):
                    logger.warning("Reversal detected: Strong bullish momentum")
                    return True

        return False

    def get_exit_recommendation(
        self,
        direction: str,
        entry: float,
        current_price: float,
        current_stop: float,
        exit_plan: ExitPlan,
        partials_taken: int,
        bars_in_trade: int,
        highest_since_entry: float,
        lowest_since_entry: float,
        market_data: Dict[str, float],
        recent_bars: List[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive exit recommendation

        Returns:
            Dictionary with exit actions to take
        """
        actions = {
            'move_stop': None,
            'take_partial': None,
            'close_position': False,
            'close_reason': None
        }

        # Current P/L
        if direction == "LONG":
            current_pnl = current_price - entry
        else:
            current_pnl = entry - current_price

        # 1. Check for reversal (highest priority exit)
        if recent_bars and self.detect_reversal(
            direction, current_price,
            market_data.get('ema21', 0),
            market_data.get('ema75', 0),
            recent_bars
        ):
            actions['close_position'] = True
            actions['close_reason'] = "Reversal detected"
            return actions

        # 2. Check time-based exit
        if self.check_time_exit(bars_in_trade, current_pnl, exit_plan):
            actions['close_position'] = True
            actions['close_reason'] = f"Time exit after {bars_in_trade} bars"
            return actions

        # 3. Check partial exits
        partial = self.check_partial_exit(
            direction, current_price, exit_plan, partials_taken
        )
        if partial:
            actions['take_partial'] = {
                'price': partial[0],
                'quantity': partial[1]
            }

        # 4. Check breakeven move
        if self.should_move_to_breakeven(
            direction, current_price, entry, current_stop, exit_plan.breakeven_trigger
        ):
            actions['move_stop'] = entry + (1 if direction == "LONG" else -1)  # 1 point buffer

        # 5. Check trailing stop (only after breakeven)
        elif current_stop >= entry if direction == "LONG" else current_stop <= entry:
            # Already at breakeven, check trailing
            if (direction == "LONG" and current_price >= exit_plan.trailing_trigger) or \
               (direction == "SHORT" and current_price <= exit_plan.trailing_trigger):

                new_stop = self.calculate_trailing_stop(
                    direction, current_price, entry, current_stop,
                    highest_since_entry, lowest_since_entry,
                    exit_plan.trailing_offset
                )
                if new_stop:
                    actions['move_stop'] = new_stop

        return actions

    def get_exit_plan_summary(self, exit_plan: ExitPlan, direction: str, entry: float) -> str:
        """Get human-readable exit plan summary"""
        lines = [
            "=" * 50,
            "EXIT PLAN",
            "=" * 50,
            f"Initial Stop: {exit_plan.initial_stop:.2f}",
            "",
            "SCALED TARGETS:",
            f"  Target 1 (1R):   {exit_plan.target_1:.2f} - Exit {exit_plan.partial_sizes[0]} contracts",
            f"  Target 2 (2R):   {exit_plan.target_2:.2f} - Exit {exit_plan.partial_sizes[1]} contracts",
            f"  Target 3 (3.5R): {exit_plan.target_3:.2f} - Exit {exit_plan.partial_sizes[2]} contracts (runner)",
            "",
            "MANAGEMENT LEVELS:",
            f"  Breakeven at: {exit_plan.breakeven_trigger:.2f}",
            f"  Trail starts: {exit_plan.trailing_trigger:.2f}",
            f"  Trail offset: {exit_plan.trailing_offset:.2f} points",
            "",
            f"Time Limit: {exit_plan.time_limit_bars} bars",
            "=" * 50
        ]
        return "\n".join(lines)
