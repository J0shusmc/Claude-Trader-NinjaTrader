"""
Memory Manager Module
Handles trade history storage and retrieval using file-based system
(MCP integration can be added later for distributed memory)
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages trade history and performance tracking"""

    def __init__(self, data_dir: str = "data"):
        """
        Initialize Memory Manager

        Args:
            data_dir: Directory for storing trade history
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.trade_history_file = self.data_dir / "trade_history.json"
        self.performance_log_file = self.data_dir / "performance_log.json"

        # Load existing history
        self.trade_history = self._load_trade_history()
        self.performance_log = self._load_performance_log()

        logger.info(f"MemoryManager initialized (trades loaded: {len(self.trade_history)})")

    def _load_trade_history(self) -> List[Dict[str, Any]]:
        """Load trade history from file"""
        if not self.trade_history_file.exists():
            return []

        try:
            with open(self.trade_history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading trade history: {e}")
            return []

    def _save_trade_history(self):
        """Save trade history to file"""
        try:
            with open(self.trade_history_file, 'w') as f:
                json.dump(self.trade_history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")

    def _load_performance_log(self) -> Dict[str, Any]:
        """Load performance log from file"""
        if not self.performance_log_file.exists():
            return {'sessions': [], 'summary': {}}

        try:
            with open(self.performance_log_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading performance log: {e}")
            return {'sessions': [], 'summary': {}}

    def _save_performance_log(self):
        """Save performance log to file"""
        try:
            with open(self.performance_log_file, 'w') as f:
                json.dump(self.performance_log, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving performance log: {e}")

    def store_trade(self, trade_data: Dict[str, Any]) -> str:
        """
        Store a completed trade

        Args:
            trade_data: Trade data dictionary

        Returns:
            Trade ID
        """
        trade_id = trade_data.get('trade_id') or f"{datetime.now().isoformat()}"
        trade_data['trade_id'] = trade_id
        trade_data['stored_at'] = datetime.now().isoformat()

        self.trade_history.append(trade_data)
        self._save_trade_history()

        logger.info(f"Trade stored: {trade_id} - {trade_data.get('outcome', {}).get('result', 'UNKNOWN')}")
        return trade_id

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific trade by ID

        Args:
            trade_id: Trade ID to retrieve

        Returns:
            Trade data or None
        """
        for trade in self.trade_history:
            if trade.get('trade_id') == trade_id:
                return trade
        return None

    def query_trades(self, filters: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        """
        Query trades with filters

        Args:
            filters: Dictionary of filter criteria
            limit: Maximum number of trades to return

        Returns:
            List of matching trades
        """
        results = []

        for trade in reversed(self.trade_history):  # Most recent first
            match = True

            # Apply filters
            if 'setup_type' in filters:
                if trade.get('setup', {}).get('type') != filters['setup_type']:
                    match = False

            if 'direction' in filters:
                if trade.get('setup', {}).get('direction') != filters['direction']:
                    match = False

            if 'result' in filters:
                if trade.get('outcome', {}).get('result') != filters['result']:
                    match = False

            if 'min_confidence' in filters:
                if trade.get('decision', {}).get('confidence', 0) < filters['min_confidence']:
                    match = False

            if match:
                results.append(trade)
                if len(results) >= limit:
                    break

        return results

    def calculate_stats(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate performance statistics for a list of trades

        Args:
            trades: List of trade dictionaries

        Returns:
            Statistics dictionary
        """
        if not trades:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'breakeven': 0,
                'win_rate': 0.0,
                'avg_rr': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0
            }

        wins = 0
        losses = 0
        breakeven = 0
        total_pnl = 0.0
        total_rr = 0.0

        for trade in trades:
            outcome = trade.get('outcome', {})
            result = outcome.get('result', 'UNKNOWN')

            if result == 'WIN':
                wins += 1
            elif result == 'LOSS':
                losses += 1
            elif result == 'BREAKEVEN':
                breakeven += 1

            total_pnl += outcome.get('profit_loss', 0.0)
            total_rr += outcome.get('risk_reward_achieved', 0.0)

        total_trades = len(trades)
        completed_trades = wins + losses  # Exclude breakeven from win rate calc

        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'breakeven': breakeven,
            'win_rate': wins / completed_trades if completed_trades > 0 else 0.0,
            'avg_rr': total_rr / total_trades if total_trades > 0 else 0.0,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / total_trades if total_trades > 0 else 0.0
        }

    def get_memory_context(self) -> Dict[str, Any]:
        """
        Generate memory context for Claude analysis

        Returns:
            Memory context dictionary with recent performance stats
        """
        # Get recent FVG-only trades
        fvg_trades = self.query_trades({'setup_type': 'fvg_only'}, limit=20)
        fvg_stats = self.calculate_stats(fvg_trades)

        # Get recent level-only trades
        level_trades = self.query_trades({'setup_type': 'level_only'}, limit=20)
        level_stats = self.calculate_stats(level_trades)

        # Overall recent performance
        recent_trades = self.trade_history[-50:] if len(self.trade_history) > 0 else []
        overall_stats = self.calculate_stats(recent_trades)

        context = {
            'fvg_only_stats': fvg_stats,
            'level_only_stats': level_stats,
            'overall_recent_stats': overall_stats,
            'total_trades_all_time': len(self.trade_history),
            'last_updated': datetime.now().isoformat()
        }

        return context

    def log_session(self, session_data: Dict[str, Any]):
        """
        Log a trading session

        Args:
            session_data: Session data dictionary
        """
        session_data['timestamp'] = datetime.now().isoformat()
        self.performance_log['sessions'].append(session_data)
        self._save_performance_log()

        logger.info(f"Session logged: {session_data.get('mode', 'unknown')} mode")

    def update_summary(self):
        """Update overall performance summary"""
        all_stats = self.calculate_stats(self.trade_history)
        self.performance_log['summary'] = {
            **all_stats,
            'last_updated': datetime.now().isoformat()
        }
        self._save_performance_log()

    def get_performance_summary(self) -> str:
        """
        Generate human-readable performance summary

        Returns:
            Summary string
        """
        stats = self.calculate_stats(self.trade_history)

        lines = []
        lines.append("=== OVERALL PERFORMANCE ===")
        lines.append(f"Total Trades: {stats['total_trades']}")
        lines.append(f"Wins: {stats['wins']} | Losses: {stats['losses']} | Breakeven: {stats['breakeven']}")
        lines.append(f"Win Rate: {stats['win_rate']:.1%}")
        lines.append(f"Average R/R: {stats['avg_rr']:.2f}:1")
        lines.append(f"Total P&L: {stats['total_pnl']:+.2f} points")
        lines.append(f"Average P&L: {stats['avg_pnl']:+.2f} points")

        # By setup type
        memory_context = self.get_memory_context()

        lines.append("\n=== BY SETUP TYPE ===")

        fvg_stats = memory_context['fvg_only_stats']
        lines.append(f"\nFVG-Only Trades: {fvg_stats['total_trades']}")
        if fvg_stats['total_trades'] > 0:
            lines.append(f"  Win Rate: {fvg_stats['win_rate']:.1%}")
            lines.append(f"  Avg R/R: {fvg_stats['avg_rr']:.2f}:1")

        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    manager = MemoryManager()

    # Sample trade
    sample_trade = {
        'trade_id': '2025-11-25_14:30:00',
        'setup': {
            'type': 'fvg_only',
            'direction': 'SHORT',
            'entry': 14712,
            'stop': 14730,
            'target': 14650
        },
        'outcome': {
            'result': 'WIN',
            'exit_price': 14651.00,
            'profit_loss': 61.00,
            'risk_reward_achieved': 3.39,
            'bars_held': 8
        },
        'decision': {
            'confidence': 0.78,
            'reasoning': 'FVG setup near EMS level'
        }
    }

    # Store trade
    # manager.store_trade(sample_trade)

    # Get context
    context = manager.get_memory_context()
    print(json.dumps(context, indent=2))

    # Print summary
    print("\n" + manager.get_performance_summary())
