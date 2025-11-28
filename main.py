"""
Claude NQ Trading Agent - Main Orchestrator
Coordinates all system components for live trading, backtesting, and monitoring
"""

import argparse
import json
import logging
import sys
import time
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Import modules
from src.fvg_analyzer import FVGAnalyzer
from src.level_detector import LevelDetector
from src.trading_agent import TradingAgent
from src.memory_manager import MemoryManager
from src.signal_generator import SignalGenerator
from src.backtest_engine import BacktestEngine
from src.market_analysis_manager import MarketAnalysisManager

# Load environment variables
load_dotenv()

# Configure logging
def setup_logging(log_level: str = "INFO", log_file: str = None):
    """Setup logging configuration"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        handlers.append(logging.FileHandler(log_dir / log_file))

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=handlers
    )

logger = logging.getLogger(__name__)


class TradingOrchestrator:
    """Main orchestrator for trading system"""

    def __init__(self, config_path: str = "config/agent_config.json"):
        """
        Initialize Trading Orchestrator

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Setup logging
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        log_file = self.config.get('logging', {}).get('log_file', 'trading_agent.log')
        setup_logging(log_level, log_file)

        # Initializing silently
        pass

        # Initialize components
        self.fvg_analyzer = FVGAnalyzer(
            min_gap_size=self.config['trading_params']['min_gap_size'],
            max_gap_age=self.config['trading_params']['max_gap_age_bars']
        )

        self.level_detector = LevelDetector(
            level_intervals=self.config['levels']['psychological_intervals']
        )

        self.memory_manager = MemoryManager()
        self.signal_generator = SignalGenerator()
        self.analysis_manager = MarketAnalysisManager()

        # Trading agent (requires API key)
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            self.trading_agent = TradingAgent(self.config, api_key=api_key)
        else:
            self.trading_agent = None
            logger.warning("No API key found - trading agent not initialized")

        # State tracking
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.trading_paused = False

        # Initialization complete

    def check_risk_limits(self) -> tuple[bool, str]:
        """
        Check if risk management limits allow trading

        Returns:
            Tuple of (can_trade, reason)
        """
        max_daily_trades = self.config['risk_management']['max_daily_trades']
        max_daily_loss = self.config['risk_management']['max_daily_loss']
        max_consecutive_losses = self.config['risk_management']['max_consecutive_losses']

        if self.trading_paused:
            return False, "Trading is paused (manual intervention required)"

        if self.daily_trades >= max_daily_trades:
            return False, f"Daily trade limit reached ({max_daily_trades})"

        if abs(self.daily_pnl) >= max_daily_loss and self.daily_pnl < 0:
            return False, f"Daily loss limit reached ({max_daily_loss} points)"

        if self.consecutive_losses >= max_consecutive_losses:
            return False, f"Consecutive loss limit reached ({max_consecutive_losses})"

        return True, ""

    def run_live_mode(self):
        """Run in live trading mode"""
        # Starting live mode silently

        if not self.trading_agent:
            logger.error("Trading agent not initialized - API key required")
            return

        # Import FairValueGaps display to access its state
        import sys
        import pandas as pd
        import os
        sys.path.insert(0, str(Path.cwd()))
        from FairValueGaps import FVGDisplay

        # Create FVG display instance (but don't run its main loop)
        fvg_display = FVGDisplay()

        # Load historical FVGs
        fvg_display.load_historical_fvgs()

        logger.info(f"Loaded {len(fvg_display.active_fvgs)} active FVGs")
        logger.info("="*60)

        # Track last processed bar and result
        last_bar_time = None
        last_result = None

        try:
            while True:
                # Reload historical data to check for updates
                historical_df = pd.read_csv('data/HistoricalData.csv')
                historical_df['DateTime'] = pd.to_datetime(historical_df['DateTime'])

                # Get latest bar timestamp
                current_bar_time = historical_df.iloc[-1]['DateTime']

                # Check if new bar arrived
                if current_bar_time != last_bar_time:
                    # NEW BAR DETECTED - Run full analysis
                    logger.info(f"\n{'='*60}")
                    logger.info(f"NEW BAR: {current_bar_time}")
                    logger.info(f"{'='*60}")

                    # Update last processed time
                    last_bar_time = current_bar_time

                    # Check for new hourly bars
                    if fvg_display.check_historical_updated():
                        fvg_display.process_historical_bars()

                    # Get current price
                    current_price = fvg_display.read_current_price()

                    if current_price is None:
                        logger.warning("No current price available")
                        time.sleep(5)
                        continue

                    # Check live FVG fills
                    fvg_display.check_live_fvg_fills(current_price)

                    # Get active FVGs
                    active_fvgs = [fvg for fvg in fvg_display.active_fvgs if not fvg.get('filled', False)]

                    if not active_fvgs:
                        logger.info("No active FVGs - waiting...")
                        time.sleep(5)
                        continue

                    # Analyze market context
                    fvg_context = self.fvg_analyzer.analyze_market_context(current_price, active_fvgs)

                    # Get latest bar from historical data for EMA/Stochastic values
                    current_bar = historical_df.iloc[-1]

                    # Extract market data (EMA and Stochastic indicators)
                    market_data = {
                        'ema21': current_bar.get('EMA21', 0),
                        'ema75': current_bar.get('EMA75', 0),
                        'ema150': current_bar.get('EMA150', 0),
                        'stochastic': current_bar.get('StochD', 50)
                    }

                    # Check risk limits
                    can_trade, reason = self.check_risk_limits()
                    if not can_trade:
                        logger.warning(f"Trading blocked: {reason}")
                        time.sleep(60)
                        continue

                    # Get memory context
                    memory_context = self.memory_manager.get_memory_context()

                    # Get previous analysis for incremental updates
                    previous_analysis = self.analysis_manager.format_previous_analysis_for_prompt()

                    # Analyze with Claude (only on new bar)
                    try:
                        result = self.trading_agent.analyze_setup(
                            fvg_context,
                            market_data,
                            memory_context,
                            previous_analysis
                        )
                        last_result = result

                        # Check if we have a tradeable decision
                        if result['success']:
                            decision_data = result['decision']

                            # Save updated analysis state
                            if 'long_assessment' in decision_data and 'short_assessment' in decision_data:
                                # Build analysis update from decision
                                analysis_update = {
                                    'current_bar_index': decision_data.get('current_bar_index', 0),
                                    'overall_bias': decision_data.get('overall_bias', 'neutral'),
                                    'waiting_for': decision_data.get('waiting_for', 'Analyzing market'),
                                    'long_assessment': decision_data['long_assessment'],
                                    'short_assessment': decision_data['short_assessment'],
                                    'bars_since_last_update': 0
                                }
                                self.analysis_manager.update_analysis(analysis_update)
                                logger.info(f"Analysis state saved: {decision_data.get('waiting_for', 'N/A')}")

                            primary = decision_data['primary_decision']

                            if primary != 'NONE':
                                # Get the chosen setup
                                chosen_setup = decision_data['long_setup'] if primary == 'LONG' else decision_data['short_setup']

                                # Build signal format for legacy signal generator
                                signal = {
                                    'decision': primary,
                                    'entry': chosen_setup['entry'],
                                    'stop': chosen_setup['stop'],
                                    'target': chosen_setup['target'],
                                    'risk_reward': chosen_setup['risk_reward'],
                                    'confidence': chosen_setup['confidence'],
                                    'reasoning': decision_data['overall_reasoning'],
                                    'setup_type': 'fvg_only'
                                }

                                # Log signal generation attempt
                                logger.info(f"GENERATING TRADE SIGNAL: {primary} @ {signal['entry']:.0f}")
                                logger.info(f"R:R {signal['risk_reward']:.2f}:1 | Confidence: {signal['confidence']:.2f}")

                                # Generate signal
                                try:
                                    success = self.signal_generator.generate_signal(signal)

                                    if success:
                                        self.daily_trades += 1
                                        # Mark trade as executed in analysis manager
                                        self.analysis_manager.mark_trade_executed(primary)
                                        logger.info(f"SIGNAL WRITTEN TO CSV: {primary} trade signal saved")
                                    else:
                                        logger.warning(f"SIGNAL GENERATION FAILED: Could not write to CSV")
                                except Exception as e:
                                    logger.error(f"ERROR WRITING SIGNAL: {e}")
                                    import traceback
                                    logger.error(traceback.format_exc())
                            else:
                                logger.info("NO TRADE: Primary decision is NONE")
                        else:
                            logger.error(f"VALIDATION FAILED: {result.get('validation_error', 'Unknown error')}")
                            logger.error(f"Full result: {result}")

                    except Exception as e:
                        logger.error(f"ERROR IN ANALYSIS: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        # Create error result so display doesn't crash
                        last_result = {
                            'success': False,
                            'error': str(e),
                            'decision': {}
                        }

                    # Clear screen and show response
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(self.trading_agent.format_decision_display(result, current_price))
                    print("\nWaiting for next bar")

                    # Brief pause to show result
                    time.sleep(2)

                else:
                    # WAITING FOR NEW BAR - Show live updates
                    current_price = fvg_display.read_current_price()

                    # Clear screen
                    os.system('cls' if os.name == 'nt' else 'clear')

                    # Show last decision with current price
                    if last_result:
                        print(self.trading_agent.format_decision_display(last_result, current_price))

                    # Static waiting message
                    print("\nWaiting for next bar")

                    # Wait 5 seconds before refreshing
                    time.sleep(5)

        except KeyboardInterrupt:
            logger.info("\nLive trading stopped by user")
        except Exception as e:
            logger.error(f"Error in live trading: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def run_backtest_mode(self, days: int = 30, output_file: str = "backtest_results.json"):
        """
        Run in backtest mode

        Args:
            days: Number of days to backtest
            output_file: Output file for results
        """
        logger.info(f"Starting BACKTEST mode ({days} days)")

        api_key = os.getenv('ANTHROPIC_API_KEY')
        use_claude = api_key is not None

        if not use_claude:
            logger.warning("No API key - running backtest with simple logic")

        engine = BacktestEngine(self.config)
        results = engine.run_backtest(days=days, use_claude=use_claude, api_key=api_key)

        # Print summary
        logger.info("="*60)
        logger.info("BACKTEST RESULTS")
        logger.info("="*60)
        logger.info(f"Period: {results['backtest_period']}")
        logger.info(f"Total Bars: {results['total_bars']}")
        logger.info(f"Total Trades: {results['total_trades']}")
        logger.info(f"Wins: {results['wins']} | Losses: {results['losses']} | Breakeven: {results['breakeven']}")
        logger.info(f"Win Rate: {results['win_rate']:.1%}")
        logger.info(f"Total P&L: {results['total_pnl']:+.2f} points")
        logger.info(f"Average P&L: {results['avg_pnl']:+.2f} points")
        logger.info(f"Max Win: {results['max_win']:+.2f} points")
        logger.info(f"Max Loss: {results['max_loss']:+.2f} points")
        logger.info(f"Average Bars Held: {results['avg_bars_held']:.1f}")

        if results.get('by_setup_type'):
            logger.info("\nBy Setup Type:")
            for setup_type, stats in results['by_setup_type'].items():
                logger.info(f"  {setup_type}: {stats['trades']} trades, {stats['win_rate']:.1%} win rate, "
                          f"{stats['avg_pnl']:+.2f}pts avg")

        logger.info("="*60)

        # Export results
        engine.export_results(results, output_file)

    def run_monitor_mode(self):
        """Run in monitoring/dashboard mode"""
        logger.info("Starting MONITOR mode")

        # Display performance summary
        print("\n" + "="*60)
        print(self.memory_manager.get_performance_summary())
        print("="*60)

        # Display current signals
        recent_signals = self.signal_generator.get_recent_signals(10)
        if recent_signals:
            print("\nRECENT SIGNALS:")
            print("-"*60)
            for signal in recent_signals:
                print(f"{signal['DateTime']} | {signal['Direction']:<5} | "
                      f"Entry: {signal['Entry_Price']:<8} | "
                      f"Stop: {signal['Stop_Loss']:<8} | "
                      f"Target: {signal['Target']}")
            print("="*60)

        print(f"\nSignals today: {self.signal_generator.count_signals_today()}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Claude NQ Trading Agent')
    parser.add_argument('--mode', choices=['live', 'backtest', 'monitor'],
                       default='monitor', help='Operating mode')
    parser.add_argument('--days', type=int, default=30,
                       help='Number of days for backtest (default: 30)')
    parser.add_argument('--config', type=str, default='config/agent_config.json',
                       help='Path to configuration file')
    parser.add_argument('--output', type=str, default='backtest_results.json',
                       help='Output file for backtest results')

    args = parser.parse_args()

    # Initialize orchestrator
    orchestrator = TradingOrchestrator(config_path=args.config)

    # Run in selected mode
    if args.mode == 'live':
        orchestrator.run_live_mode()
    elif args.mode == 'backtest':
        orchestrator.run_backtest_mode(days=args.days, output_file=args.output)
    elif args.mode == 'monitor':
        orchestrator.run_monitor_mode()


if __name__ == "__main__":
    main()
