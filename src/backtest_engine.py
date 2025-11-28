"""
Backtest Engine Module
Tests trading strategy on historical data
"""

import pandas as pd
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from .fvg_analyzer import FVGAnalyzer
from .level_detector import LevelDetector
from .trading_agent import TradingAgent
from .memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Backtests trading strategy on historical data"""

    def __init__(
        self,
        config: Dict[str, Any],
        historical_data_path: str = "data/HistoricalData.csv"
    ):
        """
        Initialize Backtest Engine

        Args:
            config: Configuration dictionary
            historical_data_path: Path to historical OHLC data
        """
        self.config = config
        self.historical_data_path = Path(historical_data_path)

        # Initialize components
        self.fvg_analyzer = FVGAnalyzer(
            min_gap_size=config['trading_params']['min_gap_size'],
            max_gap_age=config['trading_params']['max_gap_age_bars']
        )
        self.level_detector = LevelDetector(
            level_intervals=config['levels']['psychological_intervals']
        )
        self.memory_manager = MemoryManager()

        # Note: TradingAgent requires API key, will initialize in run()

        # Backtest results
        self.trades = []
        self.current_position = None

        logger.info(f"BacktestEngine initialized")

    def load_historical_data(self, days: Optional[int] = None) -> pd.DataFrame:
        """
        Load historical OHLC data

        Args:
            days: Number of days to load (None = all)

        Returns:
            DataFrame with historical data
        """
        logger.info(f"Loading historical data from {self.historical_data_path}")

        df = pd.read_csv(self.historical_data_path)
        df['DateTime'] = pd.to_datetime(df['DateTime'])
        df = df.sort_values('DateTime').reset_index(drop=True)

        if days:
            # Calculate how many bars = days (assuming 1hr bars, ~24 bars per day)
            bars_to_load = days * 24
            df = df.tail(bars_to_load)
            logger.info(f"Loaded last {days} days ({len(df)} bars)")
        else:
            logger.info(f"Loaded all historical data ({len(df)} bars)")

        return df

    def detect_fvgs_historical(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect FVGs in historical data

        Args:
            df: Historical OHLC DataFrame

        Returns:
            List of FVG dictionaries with bar indices
        """
        fvgs = []

        for i in range(2, len(df)):
            candle1 = df.iloc[i - 2]
            candle2 = df.iloc[i - 1]
            candle3 = df.iloc[i]

            # Bullish FVG
            if candle3['Low'] > candle1['High']:
                gap_size = candle3['Low'] - candle1['High']
                if gap_size >= self.config['trading_params']['min_gap_size']:
                    fvgs.append({
                        'type': 'bullish',
                        'top': candle3['Low'],
                        'bottom': candle1['High'],
                        'gap_size': gap_size,
                        'datetime': candle3['DateTime'],
                        'index': i,
                        'filled': False,
                        'age_bars': 0
                    })

            # Bearish FVG
            elif candle3['High'] < candle1['Low']:
                gap_size = candle1['Low'] - candle3['High']
                if gap_size >= self.config['trading_params']['min_gap_size']:
                    fvgs.append({
                        'type': 'bearish',
                        'top': candle1['Low'],
                        'bottom': candle3['High'],
                        'gap_size': gap_size,
                        'datetime': candle3['DateTime'],
                        'index': i,
                        'filled': False,
                        'age_bars': 0
                    })

        logger.info(f"Detected {len(fvgs)} FVGs in historical data")
        return fvgs

    def update_fvg_status(self, fvgs: List[Dict], current_bar: pd.Series, current_index: int):
        """
        Update FVG filled status and age

        Args:
            fvgs: List of FVG dictionaries
            current_bar: Current bar data
            current_index: Current bar index
        """
        for fvg in fvgs:
            if fvg['filled']:
                continue

            # Update age
            fvg['age_bars'] = current_index - fvg['index']

            # Check if filled (only when price touches the FAR side)
            # Bullish FVG: filled when price goes UP and touches TOP
            if fvg['type'] == 'bullish' and current_bar['High'] >= fvg['top']:
                fvg['filled'] = True
            # Bearish FVG: filled when price goes DOWN and touches BOTTOM
            elif fvg['type'] == 'bearish' and current_bar['Low'] <= fvg['bottom']:
                fvg['filled'] = True

    def get_active_fvgs(self, fvgs: List[Dict], current_index: int) -> List[Dict]:
        """
        Get active (unfilled, not too old) FVGs

        Args:
            fvgs: List of all FVGs
            current_index: Current bar index

        Returns:
            List of active FVGs
        """
        active = []
        max_age = self.config['trading_params']['max_gap_age_bars']

        for fvg in fvgs:
            if fvg['filled']:
                continue
            if fvg['index'] > current_index:  # FVG from future
                continue
            if fvg['age_bars'] > max_age:
                continue

            active.append(fvg)

        return active

    def check_exit_conditions(self, position: Dict, current_bar: pd.Series) -> Optional[Dict]:
        """
        Check if position should be exited

        Args:
            position: Current position dictionary
            current_bar: Current bar data

        Returns:
            Exit data if position closed, None otherwise
        """
        entry = position['entry']
        stop = position['stop']
        target = position['target']
        direction = position['direction']

        # Check stop loss
        if direction == 'LONG':
            if current_bar['Low'] <= stop:
                return {
                    'exit_price': stop,
                    'exit_reason': 'stop_loss',
                    'result': 'LOSS'
                }
            elif current_bar['High'] >= target:
                return {
                    'exit_price': target,
                    'exit_reason': 'target_hit',
                    'result': 'WIN'
                }

        elif direction == 'SHORT':
            if current_bar['High'] >= stop:
                return {
                    'exit_price': stop,
                    'exit_reason': 'stop_loss',
                    'result': 'LOSS'
                }
            elif current_bar['Low'] <= target:
                return {
                    'exit_price': target,
                    'exit_reason': 'target_hit',
                    'result': 'WIN'
                }

        return None

    def run_backtest(
        self,
        days: Optional[int] = None,
        use_claude: bool = True,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run backtest on historical data

        Args:
            days: Number of days to backtest (None = all)
            use_claude: Use Claude for decisions (False = simple logic for testing)
            api_key: Anthropic API key (required if use_claude=True)

        Returns:
            Backtest results dictionary
        """
        logger.info(f"Starting backtest (days={days}, use_claude={use_claude})")

        # Load data
        df = self.load_historical_data(days)

        # Detect all FVGs
        all_fvgs = self.detect_fvgs_historical(df)

        # Initialize Claude agent if needed
        trading_agent = None
        if use_claude:
            if not api_key:
                raise ValueError("API key required for Claude-based backtest")
            trading_agent = TradingAgent(self.config, api_key=api_key)

        # Track trades
        trades = []
        current_position = None
        bars_in_position = 0

        # Iterate through bars
        for i in range(3, len(df)):  # Start at bar 3 (need history for FVG detection)
            current_bar = df.iloc[i]
            current_price = current_bar['Close']
            current_index = i

            # Update FVG status
            self.update_fvg_status(all_fvgs, current_bar, current_index)

            # Get active FVGs
            active_fvgs = self.get_active_fvgs(all_fvgs, current_index)

            # Check if in position
            if current_position:
                bars_in_position += 1

                # Check exit conditions
                exit_data = self.check_exit_conditions(current_position, current_bar)

                if exit_data:
                    # Close position
                    profit_loss = (exit_data['exit_price'] - current_position['entry']) * \
                                  (-1 if current_position['direction'] == 'SHORT' else 1)

                    risk = abs(current_position['entry'] - current_position['stop'])
                    rr_achieved = abs(profit_loss) / risk if risk > 0 else 0

                    if profit_loss < -0.5:  # Small buffer for slippage
                        exit_data['result'] = 'LOSS'
                    elif profit_loss > 0.5:
                        exit_data['result'] = 'WIN'
                    else:
                        exit_data['result'] = 'BREAKEVEN'

                    trade_record = {
                        **current_position,
                        'exit_bar': i,
                        'exit_datetime': current_bar['DateTime'],
                        'exit_price': exit_data['exit_price'],
                        'exit_reason': exit_data['exit_reason'],
                        'result': exit_data['result'],
                        'profit_loss': profit_loss,
                        'risk_reward_achieved': rr_achieved if exit_data['result'] == 'WIN' else -1.0,
                        'bars_held': bars_in_position
                    }

                    trades.append(trade_record)
                    logger.info(f"Trade closed: {exit_data['result']} - P/L: {profit_loss:+.2f}")

                    current_position = None
                    bars_in_position = 0

                continue  # Skip signal generation while in position

            # Not in position - look for setups
            if not active_fvgs:
                continue

            # Log active FVGs every 50 bars
            if i % 50 == 0:
                logger.info(f"Bar {i}: {len(active_fvgs)} active FVGs")

            # Analyze market context
            fvg_context = self.fvg_analyzer.analyze_market_context(current_price, active_fvgs)

            # Extract market indicators from current bar
            market_data = {
                'ema21': current_bar.get('EMA21', 0),
                'ema75': current_bar.get('EMA75', 0),
                'ema150': current_bar.get('EMA150', 0),
                'stochastic': current_bar.get('StochD', 50)
            }

            # Check for trade signals
            if use_claude and trading_agent:
                # Use Claude for decision (full discretion)
                memory_context = self.memory_manager.get_memory_context()
                result = trading_agent.analyze_setup(fvg_context, market_data, memory_context)

                if result['success'] and result['decision']['decision'] != 'NONE':
                    decision = result['decision']
                    current_position = {
                        'trade_id': f"{current_bar['DateTime']}",
                        'entry_bar': i,
                        'entry_datetime': current_bar['DateTime'],
                        'direction': decision['decision'],
                        'entry': decision['entry'],
                        'stop': decision['stop'],
                        'target': decision['target'],
                        'setup_type': decision['setup_type'],
                        'confidence': decision['confidence'],
                        'reasoning': decision['reasoning']
                    }
                    logger.info(f"Position opened: {decision['decision']} @ {decision['entry']:.2f}")

            else:
                # Simple logic for testing (without Claude)
                # Take trades based on FVG + EMA alignment
                ema21 = market_data['ema21']
                ema75 = market_data['ema75']

                trade_taken = False

                # Uptrend + bullish FVG above = LONG
                if ema21 > ema75 and fvg_context.get('nearest_bullish_fvg'):
                    fvg = fvg_context['nearest_bullish_fvg']
                    if abs(current_price - fvg['bottom']) < 100:  # Within 100pts
                        entry = current_price
                        stop = entry - 20
                        target = fvg['top']
                        trade_taken = True
                        logger.info(f"Bar {i}: LONG entry - EMA uptrend + bullish FVG target")

                        current_position = {
                            'trade_id': f"{current_bar['DateTime']}",
                            'entry_bar': i,
                            'entry_datetime': current_bar['DateTime'],
                            'direction': 'LONG',
                            'entry': entry,
                            'stop': stop,
                            'target': target,
                            'setup_type': 'fvg_ema_aligned',
                            'confidence': 0.6,
                            'reasoning': 'Uptrend + bullish FVG above'
                        }

                # Downtrend + bearish FVG below = SHORT
                if not trade_taken and ema21 < ema75 and fvg_context.get('nearest_bearish_fvg'):
                    fvg = fvg_context['nearest_bearish_fvg']
                    if abs(current_price - fvg['top']) < 100:  # Within 100pts
                        entry = current_price
                        stop = entry + 20
                        target = fvg['bottom']
                        logger.info(f"Bar {i}: SHORT entry - EMA downtrend + bearish FVG target")

                        current_position = {
                            'trade_id': f"{current_bar['DateTime']}",
                            'entry_bar': i,
                            'entry_datetime': current_bar['DateTime'],
                            'direction': 'SHORT',
                            'entry': entry,
                            'stop': stop,
                            'target': target,
                            'setup_type': 'fvg_ema_aligned',
                            'confidence': 0.6,
                            'reasoning': 'Downtrend + bearish FVG below'
                        }

        # Calculate statistics
        results = self.calculate_backtest_stats(trades, df)
        results['trades'] = trades
        results['total_bars'] = len(df)
        results['backtest_period'] = f"{df.iloc[0]['DateTime']} to {df.iloc[-1]['DateTime']}"

        logger.info(f"Backtest complete: {results['total_trades']} trades, "
                   f"{results['win_rate']:.1%} win rate")

        return results

    def calculate_backtest_stats(self, trades: List[Dict], df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate backtest performance statistics

        Args:
            trades: List of trade dictionaries
            df: Historical data DataFrame

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
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'avg_bars_held': 0.0
            }

        wins = sum(1 for t in trades if t['result'] == 'WIN')
        losses = sum(1 for t in trades if t['result'] == 'LOSS')
        breakeven = sum(1 for t in trades if t['result'] == 'BREAKEVEN')

        pnls = [t['profit_loss'] for t in trades]
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / len(trades)

        bars_held = [t['bars_held'] for t in trades]
        avg_bars = sum(bars_held) / len(trades)

        # By setup type
        by_type = {}
        for setup_type in ['fvg_only', 'level_only']:
            type_trades = [t for t in trades if t.get('setup_type') == setup_type]
            if type_trades:
                type_wins = sum(1 for t in type_trades if t['result'] == 'WIN')
                type_pnl = sum(t['profit_loss'] for t in type_trades)
                by_type[setup_type] = {
                    'trades': len(type_trades),
                    'wins': type_wins,
                    'losses': sum(1 for t in type_trades if t['result'] == 'LOSS'),
                    'win_rate': type_wins / len(type_trades),
                    'total_pnl': type_pnl,
                    'avg_pnl': type_pnl / len(type_trades)
                }

        return {
            'total_trades': len(trades),
            'wins': wins,
            'losses': losses,
            'breakeven': breakeven,
            'win_rate': wins / (wins + losses) if (wins + losses) > 0 else 0.0,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'max_win': max(pnls) if pnls else 0.0,
            'max_loss': min(pnls) if pnls else 0.0,
            'avg_bars_held': avg_bars,
            'by_setup_type': by_type
        }

    def export_results(self, results: Dict[str, Any], output_file: str = "backtest_results.json"):
        """
        Export backtest results to JSON

        Args:
            results: Results dictionary
            output_file: Output file path
        """
        output_path = Path("data") / output_file

        # Convert datetime objects to strings
        results_copy = json.loads(json.dumps(results, default=str))

        with open(output_path, 'w') as f:
            json.dump(results_copy, f, indent=2)

        logger.info(f"Results exported to {output_path}")


# Example usage
if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    # Load config
    with open('config/agent_config.json', 'r') as f:
        config = json.load(f)

    # Run backtest (without Claude for testing)
    engine = BacktestEngine(config)
    results = engine.run_backtest(days=30, use_claude=False)

    print(json.dumps({k: v for k, v in results.items() if k != 'trades'}, indent=2))
    engine.export_results(results)
