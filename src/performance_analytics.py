"""
Enterprise Performance Analytics
Comprehensive trading performance analysis and reporting
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import statistics

from .core.config_manager import ConfigManager
from .core.file_lock import SafeFileHandler
from .core.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class TradeMetrics:
    """Metrics for a single trade"""
    trade_id: str
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    target: float
    quantity: int
    pnl: float
    pnl_points: float
    result: str  # WIN, LOSS, BREAKEVEN
    risk_reward_target: float
    risk_reward_actual: float
    confidence: float
    setup_type: str
    entry_time: datetime
    exit_time: datetime
    bars_held: int
    max_favorable: float = 0.0
    max_adverse: float = 0.0


@dataclass
class PeriodStats:
    """Statistics for a time period"""
    period: str
    start_date: datetime
    end_date: datetime
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    average_rr: float = 0.0
    average_bars_held: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    recovery_factor: float = 0.0


class PerformanceAnalytics:
    """
    Enterprise performance analytics engine

    Features:
    - Real-time P/L tracking
    - Win rate and expectancy calculations
    - Drawdown analysis
    - Risk-adjusted returns (Sharpe ratio)
    - Performance by setup type
    - Time-based analysis (daily, weekly, monthly)
    - Trade journal with full context
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize performance analytics"""
        self.config = config_manager or ConfigManager()
        self._trades: List[TradeMetrics] = []
        self._data_file = Path("data/performance_data.json")

        # Load historical data
        self._load_data()

        logger.info("PerformanceAnalytics initialized")

    def _load_data(self):
        """Load historical performance data"""
        try:
            data = SafeFileHandler.read_json(self._data_file)
            if data and 'trades' in data:
                for trade_data in data['trades']:
                    # Convert datetime strings back to datetime objects
                    trade_data['entry_time'] = datetime.fromisoformat(trade_data['entry_time'])
                    trade_data['exit_time'] = datetime.fromisoformat(trade_data['exit_time'])
                    self._trades.append(TradeMetrics(**trade_data))

                logger.info(f"Loaded {len(self._trades)} historical trades")
        except Exception as e:
            logger.warning(f"Could not load performance data: {e}")

    def _save_data(self):
        """Save performance data"""
        try:
            data = {
                'trades': [
                    {
                        **vars(trade),
                        'entry_time': trade.entry_time.isoformat(),
                        'exit_time': trade.exit_time.isoformat()
                    }
                    for trade in self._trades
                ],
                'last_updated': datetime.now().isoformat()
            }
            SafeFileHandler.write_json(self._data_file, data)
        except Exception as e:
            logger.error(f"Failed to save performance data: {e}")

    def record_trade(
        self,
        trade_id: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        stop_loss: float,
        target: float,
        quantity: int,
        confidence: float,
        setup_type: str,
        entry_time: datetime,
        exit_time: datetime,
        bars_held: int,
        max_favorable: float = 0.0,
        max_adverse: float = 0.0
    ):
        """Record a completed trade"""
        # Calculate P/L
        if direction == "LONG":
            pnl_points = exit_price - entry_price
        else:
            pnl_points = entry_price - exit_price

        pnl = pnl_points * quantity

        # Determine result
        if pnl_points > 0.5:
            result = "WIN"
        elif pnl_points < -0.5:
            result = "LOSS"
        else:
            result = "BREAKEVEN"

        # Calculate risk/reward
        risk = abs(entry_price - stop_loss)
        target_distance = abs(target - entry_price)
        rr_target = target_distance / risk if risk > 0 else 0
        rr_actual = abs(pnl_points) / risk if risk > 0 else 0

        trade = TradeMetrics(
            trade_id=trade_id,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_loss=stop_loss,
            target=target,
            quantity=quantity,
            pnl=pnl,
            pnl_points=pnl_points,
            result=result,
            risk_reward_target=rr_target,
            risk_reward_actual=rr_actual,
            confidence=confidence,
            setup_type=setup_type,
            entry_time=entry_time,
            exit_time=exit_time,
            bars_held=bars_held,
            max_favorable=max_favorable,
            max_adverse=max_adverse
        )

        self._trades.append(trade)
        self._save_data()

        logger.info(f"Trade recorded: {trade_id} - {result} - P/L: {pnl:+.2f}")

    def calculate_stats(self, trades: List[TradeMetrics]) -> PeriodStats:
        """Calculate statistics for a list of trades"""
        if not trades:
            return PeriodStats(
                period="empty",
                start_date=datetime.now(),
                end_date=datetime.now()
            )

        # Sort by entry time
        trades = sorted(trades, key=lambda t: t.entry_time)

        wins = [t for t in trades if t.result == "WIN"]
        losses = [t for t in trades if t.result == "LOSS"]
        breakeven = [t for t in trades if t.result == "BREAKEVEN"]

        total_trades = len(trades)
        win_count = len(wins)
        loss_count = len(losses)
        be_count = len(breakeven)

        # P/L calculations
        total_pnl = sum(t.pnl for t in trades)
        gross_profit = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0

        # Win rate (excluding breakeven)
        completed = win_count + loss_count
        win_rate = win_count / completed if completed > 0 else 0

        # Profit factor
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

        # Averages
        avg_win = statistics.mean([t.pnl for t in wins]) if wins else 0
        avg_loss = statistics.mean([abs(t.pnl) for t in losses]) if losses else 0
        largest_win = max([t.pnl for t in wins]) if wins else 0
        largest_loss = min([t.pnl for t in losses]) if losses else 0

        # Average R/R
        avg_rr = statistics.mean([t.risk_reward_actual for t in trades]) if trades else 0

        # Average bars held
        avg_bars = statistics.mean([t.bars_held for t in trades]) if trades else 0

        # Consecutive wins/losses
        max_consec_wins = self._max_consecutive(trades, "WIN")
        max_consec_losses = self._max_consecutive(trades, "LOSS")

        # Sharpe ratio (simplified)
        if len(trades) > 1:
            returns = [t.pnl for t in trades]
            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe = mean_return / std_return if std_return > 0 else 0
        else:
            sharpe = 0

        # Max drawdown
        max_dd = self._calculate_max_drawdown(trades)

        # Recovery factor
        recovery = total_pnl / max_dd if max_dd > 0 else float('inf') if total_pnl > 0 else 0

        return PeriodStats(
            period=f"{trades[0].entry_time.date()} to {trades[-1].exit_time.date()}",
            start_date=trades[0].entry_time,
            end_date=trades[-1].exit_time,
            total_trades=total_trades,
            wins=win_count,
            losses=loss_count,
            breakeven=be_count,
            total_pnl=total_pnl,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            win_rate=win_rate,
            profit_factor=profit_factor,
            average_win=avg_win,
            average_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            average_rr=avg_rr,
            average_bars_held=avg_bars,
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            recovery_factor=recovery
        )

    def _max_consecutive(self, trades: List[TradeMetrics], result: str) -> int:
        """Calculate maximum consecutive results"""
        max_streak = 0
        current_streak = 0

        for trade in trades:
            if trade.result == result:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        return max_streak

    def _calculate_max_drawdown(self, trades: List[TradeMetrics]) -> float:
        """Calculate maximum drawdown"""
        if not trades:
            return 0

        equity = 0
        peak = 0
        max_dd = 0

        for trade in trades:
            equity += trade.pnl
            peak = max(peak, equity)
            drawdown = peak - equity
            max_dd = max(max_dd, drawdown)

        return max_dd

    def get_daily_stats(self, days: int = 30) -> List[PeriodStats]:
        """Get daily statistics for the last N days"""
        cutoff = datetime.now() - timedelta(days=days)
        daily_trades = defaultdict(list)

        for trade in self._trades:
            if trade.entry_time >= cutoff:
                date_key = trade.entry_time.date()
                daily_trades[date_key].append(trade)

        stats = []
        for date, trades in sorted(daily_trades.items()):
            period_stats = self.calculate_stats(trades)
            period_stats.period = str(date)
            stats.append(period_stats)

        return stats

    def get_stats_by_setup_type(self) -> Dict[str, PeriodStats]:
        """Get statistics grouped by setup type"""
        by_type = defaultdict(list)

        for trade in self._trades:
            by_type[trade.setup_type].append(trade)

        return {
            setup_type: self.calculate_stats(trades)
            for setup_type, trades in by_type.items()
        }

    def get_stats_by_direction(self) -> Dict[str, PeriodStats]:
        """Get statistics grouped by direction"""
        longs = [t for t in self._trades if t.direction == "LONG"]
        shorts = [t for t in self._trades if t.direction == "SHORT"]

        return {
            "LONG": self.calculate_stats(longs),
            "SHORT": self.calculate_stats(shorts)
        }

    def get_overall_stats(self) -> PeriodStats:
        """Get overall statistics for all trades"""
        return self.calculate_stats(self._trades)

    def get_expectancy(self) -> float:
        """Calculate trading expectancy (expected value per trade)"""
        stats = self.get_overall_stats()

        if stats.total_trades == 0:
            return 0

        # Expectancy = (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        loss_rate = 1 - stats.win_rate
        expectancy = (stats.win_rate * stats.average_win) - (loss_rate * stats.average_loss)

        return expectancy

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """Get equity curve data"""
        equity = 0
        curve = []

        for trade in sorted(self._trades, key=lambda t: t.exit_time):
            equity += trade.pnl
            curve.append({
                'timestamp': trade.exit_time.isoformat(),
                'equity': equity,
                'trade_id': trade.trade_id,
                'pnl': trade.pnl
            })

        return curve

    def get_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        overall = self.get_overall_stats()
        by_type = self.get_stats_by_setup_type()
        by_direction = self.get_stats_by_direction()
        daily = self.get_daily_stats(30)

        return {
            'overall': vars(overall),
            'by_setup_type': {k: vars(v) for k, v in by_type.items()},
            'by_direction': {k: vars(v) for k, v in by_direction.items()},
            'daily_stats': [vars(d) for d in daily],
            'expectancy': self.get_expectancy(),
            'equity_curve': self.get_equity_curve(),
            'total_trades': len(self._trades),
            'generated_at': datetime.now().isoformat()
        }

    def get_summary(self) -> str:
        """Get human-readable performance summary"""
        stats = self.get_overall_stats()
        expectancy = self.get_expectancy()

        lines = [
            "=" * 60,
            "PERFORMANCE ANALYTICS SUMMARY",
            "=" * 60,
            f"Period: {stats.period}",
            f"Total Trades: {stats.total_trades}",
            "",
            "WIN/LOSS ANALYSIS:",
            f"  Wins: {stats.wins} | Losses: {stats.losses} | Breakeven: {stats.breakeven}",
            f"  Win Rate: {stats.win_rate:.1%}",
            f"  Profit Factor: {stats.profit_factor:.2f}",
            "",
            "P/L ANALYSIS:",
            f"  Total P/L: {stats.total_pnl:+.2f}",
            f"  Gross Profit: {stats.gross_profit:+.2f}",
            f"  Gross Loss: {stats.gross_loss:.2f}",
            f"  Average Win: {stats.average_win:+.2f}",
            f"  Average Loss: {stats.average_loss:.2f}",
            f"  Largest Win: {stats.largest_win:+.2f}",
            f"  Largest Loss: {stats.largest_loss:.2f}",
            "",
            "RISK METRICS:",
            f"  Average R/R: {stats.average_rr:.2f}:1",
            f"  Max Drawdown: {stats.max_drawdown:.2f}",
            f"  Sharpe Ratio: {stats.sharpe_ratio:.2f}",
            f"  Recovery Factor: {stats.recovery_factor:.2f}",
            f"  Expectancy: {expectancy:+.2f}",
            "",
            "STREAKS:",
            f"  Max Consecutive Wins: {stats.max_consecutive_wins}",
            f"  Max Consecutive Losses: {stats.max_consecutive_losses}",
            f"  Average Bars Held: {stats.average_bars_held:.1f}",
            "=" * 60
        ]

        return "\n".join(lines)

    def export_to_csv(self, file_path: str):
        """Export all trades to CSV"""
        if not self._trades:
            logger.warning("No trades to export")
            return

        fieldnames = [
            'trade_id', 'direction', 'entry_price', 'exit_price',
            'stop_loss', 'target', 'quantity', 'pnl', 'pnl_points',
            'result', 'risk_reward_target', 'risk_reward_actual',
            'confidence', 'setup_type', 'entry_time', 'exit_time',
            'bars_held', 'max_favorable', 'max_adverse'
        ]

        rows = []
        for trade in self._trades:
            row = vars(trade).copy()
            row['entry_time'] = trade.entry_time.isoformat()
            row['exit_time'] = trade.exit_time.isoformat()
            rows.append(row)

        SafeFileHandler.write_csv(file_path, rows, fieldnames)
        logger.info(f"Exported {len(rows)} trades to {file_path}")
