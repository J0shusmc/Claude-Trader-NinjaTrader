"""
Enterprise Risk Manager
Comprehensive risk management with circuit breakers, position limits, and real-time monitoring
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .core.config_manager import ConfigManager
from .core.file_lock import SafeFileHandler
from .core.exceptions import RiskLimitError, CircuitBreakerError
from .core.logging_setup import get_logger, LogContext

logger = get_logger(__name__)


class RiskState(Enum):
    """Risk management states"""
    NORMAL = "normal"
    WARNING = "warning"
    HALTED = "halted"
    COOLDOWN = "cooldown"


@dataclass
class TradeRecord:
    """Record of a completed trade"""
    trade_id: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    result: str  # WIN, LOSS, BREAKEVEN
    timestamp: datetime
    bars_held: int = 0


@dataclass
class RiskMetrics:
    """Current risk metrics"""
    daily_trades: int = 0
    daily_pnl: float = 0.0
    daily_wins: int = 0
    daily_losses: int = 0
    consecutive_losses: int = 0
    current_drawdown: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    open_positions: int = 0
    daily_volume: int = 0
    last_trade_time: Optional[datetime] = None
    last_loss_time: Optional[datetime] = None
    state: RiskState = RiskState.NORMAL
    state_reason: str = ""


class EnterpriseRiskManager:
    """
    Enterprise-grade risk management system

    Features:
    - Real-time risk limit monitoring
    - Circuit breaker for consecutive losses
    - Position size limits
    - Daily loss limits
    - Drawdown monitoring
    - Cooldown periods after losses
    - Time-based trading restrictions
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize risk manager"""
        self.config = config_manager or ConfigManager()
        self.metrics = RiskMetrics()
        self._today_trades: List[TradeRecord] = []
        self._state_file = Path(self.config.get('file_paths.performance_log', 'data/risk_state.json'))

        # Load persisted state
        self._load_state()

        logger.info("EnterpriseRiskManager initialized")

    def _load_state(self):
        """Load persisted risk state"""
        try:
            state_data = SafeFileHandler.read_json(self._state_file)

            if state_data:
                # Check if state is from today
                last_date = state_data.get('date')
                today = datetime.now().strftime('%Y-%m-%d')

                if last_date == today:
                    self.metrics.daily_trades = state_data.get('daily_trades', 0)
                    self.metrics.daily_pnl = state_data.get('daily_pnl', 0.0)
                    self.metrics.daily_wins = state_data.get('daily_wins', 0)
                    self.metrics.daily_losses = state_data.get('daily_losses', 0)
                    self.metrics.consecutive_losses = state_data.get('consecutive_losses', 0)
                    self.metrics.peak_equity = state_data.get('peak_equity', 0.0)
                    self.metrics.daily_volume = state_data.get('daily_volume', 0)

                    if state_data.get('state'):
                        self.metrics.state = RiskState(state_data['state'])
                        self.metrics.state_reason = state_data.get('state_reason', '')

                    logger.info(f"Loaded risk state: {self.metrics.daily_trades} trades, "
                              f"P/L: {self.metrics.daily_pnl:+.2f}")
                else:
                    # New day - reset daily counters
                    self._reset_daily_counters()
                    logger.info("New trading day - counters reset")

        except Exception as e:
            logger.warning(f"Could not load risk state: {e}")

    def _save_state(self):
        """Persist risk state"""
        try:
            state_data = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'daily_trades': self.metrics.daily_trades,
                'daily_pnl': self.metrics.daily_pnl,
                'daily_wins': self.metrics.daily_wins,
                'daily_losses': self.metrics.daily_losses,
                'consecutive_losses': self.metrics.consecutive_losses,
                'peak_equity': self.metrics.peak_equity,
                'daily_volume': self.metrics.daily_volume,
                'state': self.metrics.state.value,
                'state_reason': self.metrics.state_reason,
                'last_updated': datetime.now().isoformat()
            }

            SafeFileHandler.write_json(self._state_file, state_data)

        except Exception as e:
            logger.error(f"Failed to save risk state: {e}")

    def _reset_daily_counters(self):
        """Reset daily counters"""
        self.metrics.daily_trades = 0
        self.metrics.daily_pnl = 0.0
        self.metrics.daily_wins = 0
        self.metrics.daily_losses = 0
        self.metrics.daily_volume = 0
        self._today_trades = []

        # Don't reset consecutive losses - they carry over
        if self.metrics.state == RiskState.HALTED:
            # Check if we can resume
            self.metrics.state = RiskState.NORMAL
            self.metrics.state_reason = ""

    def check_pre_trade(
        self,
        direction: str,
        entry: float,
        stop: float,
        target: float,
        quantity: int,
        confidence: float
    ) -> Tuple[bool, str]:
        """
        Pre-trade risk check - validates all risk rules before signal generation

        Args:
            direction: LONG or SHORT
            entry: Entry price
            stop: Stop loss price
            target: Target price
            quantity: Number of contracts
            confidence: Confidence level (0-1)

        Returns:
            Tuple of (allowed, reason)
        """
        with LogContext.correlation_scope():
            # Check state
            if self.metrics.state == RiskState.HALTED:
                return False, f"Trading halted: {self.metrics.state_reason}"

            # Check cooldown
            if self.metrics.state == RiskState.COOLDOWN:
                cooldown_remaining = self._get_cooldown_remaining()
                if cooldown_remaining > 0:
                    return False, f"Cooldown active: {cooldown_remaining:.0f}s remaining"
                else:
                    self.metrics.state = RiskState.NORMAL
                    self.metrics.state_reason = ""

            # Check daily trade limit
            if self.metrics.daily_trades >= self.config.risk.max_daily_trades:
                return False, f"Daily trade limit reached ({self.config.risk.max_daily_trades})"

            # Check daily loss limit
            if self.metrics.daily_pnl <= -self.config.risk.max_daily_loss:
                self._halt_trading("Daily loss limit reached")
                return False, f"Daily loss limit reached ({self.config.risk.max_daily_loss}pts)"

            # Check consecutive losses
            if self.metrics.consecutive_losses >= self.config.risk.max_consecutive_losses:
                self._halt_trading("Consecutive loss limit reached")
                return False, f"Consecutive loss limit ({self.config.risk.max_consecutive_losses})"

            # Check position size
            if quantity > self.config.risk.max_position_size:
                return False, f"Position size {quantity} exceeds max {self.config.risk.max_position_size}"

            # Check stop loss range
            stop_distance = abs(entry - stop)
            if stop_distance < self.config.risk.stop_loss_min:
                return False, f"Stop too tight: {stop_distance:.1f}pts (min: {self.config.risk.stop_loss_min})"

            if stop_distance > self.config.risk.stop_loss_max:
                return False, f"Stop too wide: {stop_distance:.1f}pts (max: {self.config.risk.stop_loss_max})"

            # Check risk/reward
            target_distance = abs(target - entry)
            risk_reward = target_distance / stop_distance if stop_distance > 0 else 0

            if risk_reward < self.config.trading.min_risk_reward:
                return False, f"R/R {risk_reward:.2f} below min {self.config.trading.min_risk_reward}"

            # Check confidence threshold
            if confidence < self.config.trading.confidence_threshold:
                return False, f"Confidence {confidence:.2%} below threshold {self.config.trading.confidence_threshold:.0%}"

            # Check stop direction
            if direction == "LONG" and stop >= entry:
                return False, "LONG stop must be below entry"
            if direction == "SHORT" and stop <= entry:
                return False, "SHORT stop must be above entry"

            # Check target direction
            if direction == "LONG" and target <= entry:
                return False, "LONG target must be above entry"
            if direction == "SHORT" and target >= entry:
                return False, "SHORT target must be below entry"

            # Check daily volume
            if self.metrics.daily_volume + quantity > 50:  # Max daily volume
                return False, f"Daily volume limit would be exceeded"

            # All checks passed
            logger.info(f"Pre-trade check PASSED: {direction} {quantity}x @ {entry}")
            return True, "OK"

    def record_trade_entry(self, trade_id: str, direction: str, quantity: int):
        """Record trade entry"""
        self.metrics.daily_trades += 1
        self.metrics.daily_volume += quantity
        self.metrics.open_positions += 1
        self.metrics.last_trade_time = datetime.now()

        LogContext.set_trade_id(trade_id)
        logger.info(f"Trade entry recorded: {trade_id} - {direction} {quantity}x")

        self._check_warning_thresholds()
        self._save_state()

    def record_trade_exit(
        self,
        trade_id: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        quantity: int,
        result: str
    ):
        """Record trade exit and update metrics"""
        # Calculate P/L
        if direction == "LONG":
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity

        # Update metrics
        self.metrics.daily_pnl += pnl
        self.metrics.open_positions = max(0, self.metrics.open_positions - 1)

        if result == "WIN":
            self.metrics.daily_wins += 1
            self.metrics.consecutive_losses = 0
        elif result == "LOSS":
            self.metrics.daily_losses += 1
            self.metrics.consecutive_losses += 1
            self.metrics.last_loss_time = datetime.now()

            # Start cooldown after loss
            self._start_cooldown()

        # Update equity tracking
        self.metrics.current_equity += pnl
        if self.metrics.current_equity > self.metrics.peak_equity:
            self.metrics.peak_equity = self.metrics.current_equity

        # Calculate drawdown
        if self.metrics.peak_equity > 0:
            self.metrics.current_drawdown = (
                (self.metrics.peak_equity - self.metrics.current_equity)
                / self.metrics.peak_equity * 100
            )

        # Record trade
        trade = TradeRecord(
            trade_id=trade_id,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            pnl=pnl,
            result=result,
            timestamp=datetime.now()
        )
        self._today_trades.append(trade)

        logger.trade_closed(direction, entry_price, exit_price, pnl, result)

        # Check for state changes
        self._check_risk_limits()
        self._save_state()

    def _start_cooldown(self):
        """Start cooldown period after loss"""
        cooldown_minutes = self.config.risk.cool_down_after_loss_minutes
        if cooldown_minutes > 0 and self.metrics.state != RiskState.HALTED:
            self.metrics.state = RiskState.COOLDOWN
            self.metrics.state_reason = f"Cooldown after loss ({cooldown_minutes} min)"
            logger.warning(f"Cooldown started: {cooldown_minutes} minutes")

    def _get_cooldown_remaining(self) -> float:
        """Get remaining cooldown time in seconds"""
        if self.metrics.last_loss_time is None:
            return 0

        cooldown_duration = timedelta(minutes=self.config.risk.cool_down_after_loss_minutes)
        cooldown_end = self.metrics.last_loss_time + cooldown_duration
        remaining = (cooldown_end - datetime.now()).total_seconds()

        return max(0, remaining)

    def _halt_trading(self, reason: str):
        """Halt trading"""
        self.metrics.state = RiskState.HALTED
        self.metrics.state_reason = reason
        logger.error(f"TRADING HALTED: {reason}")

    def _check_warning_thresholds(self):
        """Check and emit warnings for approaching limits"""
        # Daily trades warning
        if self.metrics.daily_trades >= self.config.risk.max_daily_trades - 1:
            logger.risk_warning(
                "daily_trades",
                self.metrics.daily_trades,
                self.config.risk.max_daily_trades
            )

        # Daily loss warning (80% of limit)
        loss_threshold = self.config.risk.max_daily_loss * 0.8
        if abs(self.metrics.daily_pnl) >= loss_threshold and self.metrics.daily_pnl < 0:
            logger.risk_warning(
                "daily_loss",
                abs(self.metrics.daily_pnl),
                self.config.risk.max_daily_loss
            )

        # Consecutive losses warning
        if self.metrics.consecutive_losses >= self.config.risk.max_consecutive_losses - 1:
            logger.risk_warning(
                "consecutive_losses",
                self.metrics.consecutive_losses,
                self.config.risk.max_consecutive_losses
            )

        # Drawdown warning
        drawdown_threshold = self.config.risk.max_drawdown_percent * 0.7
        if self.metrics.current_drawdown >= drawdown_threshold:
            logger.risk_warning(
                "drawdown",
                self.metrics.current_drawdown,
                self.config.risk.max_drawdown_percent
            )

    def _check_risk_limits(self):
        """Check if any risk limits have been breached"""
        # Daily loss limit
        if self.metrics.daily_pnl <= -self.config.risk.max_daily_loss:
            self._halt_trading("Daily loss limit reached")
            return

        # Consecutive losses
        if self.metrics.consecutive_losses >= self.config.risk.max_consecutive_losses:
            self._halt_trading("Consecutive loss limit reached")
            return

        # Drawdown limit
        if self.metrics.current_drawdown >= self.config.risk.max_drawdown_percent:
            self._halt_trading("Maximum drawdown reached")
            return

    def get_position_size(self, base_size: int) -> int:
        """
        Get adjusted position size based on current risk state

        Args:
            base_size: Requested position size

        Returns:
            Adjusted position size
        """
        # Cap at max position size
        size = min(base_size, self.config.risk.max_position_size)

        # Reduce size after consecutive losses
        if self.metrics.consecutive_losses >= 2:
            size = max(1, size // 2)
            logger.info(f"Position size reduced due to {self.metrics.consecutive_losses} consecutive losses")

        # Reduce size when approaching limits
        if self.metrics.daily_trades >= self.config.risk.max_daily_trades - 1:
            size = max(1, size // 2)

        return size

    def can_trade(self) -> Tuple[bool, str]:
        """Quick check if trading is allowed"""
        if self.metrics.state == RiskState.HALTED:
            return False, self.metrics.state_reason

        if self.metrics.state == RiskState.COOLDOWN:
            remaining = self._get_cooldown_remaining()
            if remaining > 0:
                return False, f"Cooldown: {remaining:.0f}s remaining"

        if self.metrics.daily_trades >= self.config.risk.max_daily_trades:
            return False, "Daily trade limit reached"

        return True, "OK"

    def resume_trading(self) -> bool:
        """Manually resume trading after halt"""
        if self.metrics.state == RiskState.HALTED:
            logger.info("Trading resumed by manual intervention")
            self.metrics.state = RiskState.NORMAL
            self.metrics.state_reason = ""
            self._save_state()
            return True
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics as dictionary"""
        return {
            'state': self.metrics.state.value,
            'state_reason': self.metrics.state_reason,
            'daily_trades': self.metrics.daily_trades,
            'max_daily_trades': self.config.risk.max_daily_trades,
            'daily_pnl': self.metrics.daily_pnl,
            'max_daily_loss': self.config.risk.max_daily_loss,
            'daily_wins': self.metrics.daily_wins,
            'daily_losses': self.metrics.daily_losses,
            'win_rate': self.metrics.daily_wins / max(1, self.metrics.daily_trades),
            'consecutive_losses': self.metrics.consecutive_losses,
            'max_consecutive_losses': self.config.risk.max_consecutive_losses,
            'current_drawdown': self.metrics.current_drawdown,
            'max_drawdown': self.config.risk.max_drawdown_percent,
            'open_positions': self.metrics.open_positions,
            'daily_volume': self.metrics.daily_volume,
            'can_trade': self.can_trade()[0]
        }

    def get_summary(self) -> str:
        """Get human-readable risk summary"""
        metrics = self.get_metrics()

        lines = [
            "=" * 50,
            "RISK MANAGEMENT STATUS",
            "=" * 50,
            f"State: {metrics['state'].upper()}",
            f"Daily Trades: {metrics['daily_trades']}/{metrics['max_daily_trades']}",
            f"Daily P/L: {metrics['daily_pnl']:+.2f}pts (max loss: {metrics['max_daily_loss']})",
            f"Win Rate: {metrics['win_rate']:.1%} ({metrics['daily_wins']}W/{metrics['daily_losses']}L)",
            f"Consecutive Losses: {metrics['consecutive_losses']}/{metrics['max_consecutive_losses']}",
            f"Drawdown: {metrics['current_drawdown']:.2f}% (max: {metrics['max_drawdown']}%)",
            f"Can Trade: {'YES' if metrics['can_trade'] else 'NO'}",
        ]

        if metrics['state_reason']:
            lines.append(f"Reason: {metrics['state_reason']}")

        lines.append("=" * 50)

        return "\n".join(lines)
