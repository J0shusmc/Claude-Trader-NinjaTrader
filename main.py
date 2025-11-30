"""
Claude NQ Trading Agent - Enterprise Main Orchestrator
Production-grade trading system with comprehensive risk management,
health monitoring, and performance analytics.
"""

import argparse
import sys
import time
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Import enterprise core modules
from src.core.config_manager import ConfigManager
from src.core.logging_setup import setup_enterprise_logging, get_logger, LogContext
from src.core.retry import retry_with_backoff, RetryConfig, CircuitBreaker
from src.core.exceptions import TradingError, RiskLimitError, ConfigurationError

# Import trading modules
from src.fvg_analyzer import FVGAnalyzer
from src.level_detector import LevelDetector
from src.trading_agent import TradingAgent
from src.memory_manager import MemoryManager
from src.signal_generator import SignalGenerator
from src.backtest_engine import BacktestEngine
from src.market_analysis_manager import MarketAnalysisManager
from src.risk_manager import EnterpriseRiskManager
from src.health_monitor import HealthMonitor
from src.performance_analytics import PerformanceAnalytics

# Import profitability modules
from src.enhanced_ai_agent import EnhancedTradingAgent
from src.edge_filters import EdgeFilters, SetupQuality
from src.exit_strategies import ExitManager, ExitPlan
from src.ai_validator import AIDecisionValidator, AIConfidenceCalibrator


class EnterpriseTradingOrchestrator:
    """
    Enterprise-grade trading orchestrator

    Features:
    - Centralized configuration management
    - Comprehensive risk management
    - Health monitoring with alerts
    - Performance analytics
    - Structured logging with correlation IDs
    - Circuit breaker for external services
    - Graceful error handling and recovery
    """

    def __init__(self, config_path: str = "config/agent_config.json"):
        """Initialize Enterprise Trading Orchestrator"""

        # Initialize configuration
        try:
            self.config = ConfigManager(config_path=config_path)
        except ConfigurationError as e:
            print(f"FATAL: Configuration error - {e}")
            sys.exit(1)

        # Setup enterprise logging
        log_config = self.config.get('logging', {})
        self.logger = setup_enterprise_logging(
            log_level=log_config.get('level', 'INFO'),
            log_file=log_config.get('log_file'),
            enable_console=log_config.get('enable_console', True),
            enable_json=log_config.get('enable_json_logging', True),
            max_size_mb=log_config.get('max_log_size_mb', 50),
            backup_count=log_config.get('backup_count', 5)
        )

        self.log = get_logger(__name__)
        self.log.info("=" * 60)
        self.log.info("CLAUDE TRADING SYSTEM - ENTERPRISE EDITION")
        self.log.info("=" * 60)

        # Initialize enterprise components
        self._init_components()

        self.log.info("Enterprise Trading Orchestrator initialized")

    def _init_components(self):
        """Initialize all system components"""

        # Risk Manager (must be first for all risk checks)
        self.risk_manager = EnterpriseRiskManager(self.config)

        # Health Monitor
        self.health_monitor = HealthMonitor(self.config)
        self.health_monitor.register_alert_callback(self._handle_alert)

        # Performance Analytics
        self.performance = PerformanceAnalytics(self.config)

        # Edge Filters (for setup quality scoring)
        self.edge_filters = EdgeFilters(self.config._raw_config)

        # Exit Manager (for intelligent profit taking)
        self.exit_manager = ExitManager(self.config._raw_config)

        # AI Decision Validator (validates all AI decisions)
        self.ai_validator = AIDecisionValidator(self.config._raw_config)

        # AI Confidence Calibrator (tracks AI accuracy)
        self.confidence_calibrator = AIConfidenceCalibrator()

        # FVG Analyzer
        self.fvg_analyzer = FVGAnalyzer(
            min_gap_size=self.config.trading.min_gap_size,
            max_gap_age=self.config.get('trading_params.max_gap_age_bars', 1000)
        )

        # Level Detector
        self.level_detector = LevelDetector(
            level_intervals=self.config.get('levels.psychological_intervals', [100])
        )

        # Memory Manager
        self.memory_manager = MemoryManager()

        # Signal Generator
        self.signal_generator = SignalGenerator(
            output_file=str(self.config.get_file_path('signals_file'))
        )

        # Analysis Manager
        self.analysis_manager = MarketAnalysisManager(
            analysis_file=str(self.config.get_file_path('market_analysis'))
        )

        # Trading Agent (requires API key)
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            # Create circuit breaker for API calls
            self.api_circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                success_threshold=2,
                timeout=60.0,
                name="claude_api"
            )

            # Standard trading agent (backward compatible)
            self.trading_agent = TradingAgent(
                self.config._raw_config,
                api_key=api_key
            )

            # Enhanced trading agent with structured prompts
            self.enhanced_agent = EnhancedTradingAgent(
                api_key=api_key,
                config=self.config._raw_config
            )

            self.log.info("Trading agents initialized (standard + enhanced)")
        else:
            self.trading_agent = None
            self.enhanced_agent = None
            self.api_circuit_breaker = None
            self.log.warning("No API key found - trading agents not available")

    def _handle_alert(self, alert_type: str, message: str):
        """Handle system alerts"""
        self.log.error(f"SYSTEM ALERT [{alert_type}]: {message}")
        # In production, could send to Slack, email, SMS, etc.

    def run_live_mode(self):
        """Run in live trading mode with full enterprise features"""
        import pandas as pd
        from FairValueGaps import FVGDisplay

        with LogContext.correlation_scope() as correlation_id:
            self.log.info(f"Starting LIVE mode [correlation_id={correlation_id}]")

            if not self.trading_agent:
                self.log.error("Trading agent not initialized - API key required")
                return

            # Start health monitoring
            self.health_monitor.start_monitoring()

            # Initialize FVG display
            fvg_display = FVGDisplay()
            fvg_display.load_historical_fvgs()
            self.log.info(f"Loaded {len(fvg_display.active_fvgs)} active FVGs")

            # Track last processed bar
            last_bar_time = None
            last_result = None

            try:
                while True:
                    # Check system health
                    if self.health_monitor.get_overall_status().value == "unhealthy":
                        self.log.error("System unhealthy - pausing trading")
                        time.sleep(30)
                        continue

                    # Check if trading is allowed
                    can_trade, reason = self.risk_manager.can_trade()
                    if not can_trade:
                        self.log.warning(f"Trading blocked: {reason}")
                        self._display_status(last_result, None, reason)
                        time.sleep(60)
                        continue

                    # Load historical data
                    historical_path = self.config.get_file_path('historical_data')
                    try:
                        historical_df = pd.read_csv(historical_path)
                        historical_df['DateTime'] = pd.to_datetime(historical_df['DateTime'])
                    except Exception as e:
                        self.log.error(f"Failed to load historical data: {e}")
                        time.sleep(5)
                        continue

                    current_bar_time = historical_df.iloc[-1]['DateTime']

                    # Check if new bar arrived
                    if current_bar_time != last_bar_time:
                        last_bar_time = current_bar_time
                        self.log.info(f"NEW BAR: {current_bar_time}")

                        # Process new bar
                        result = self._process_bar(
                            fvg_display,
                            historical_df,
                            current_bar_time
                        )

                        if result:
                            last_result = result
                            self.health_monitor.record_signal()

                    # Update display
                    current_price = fvg_display.read_current_price()
                    self._display_status(last_result, current_price)

                    time.sleep(5)

            except KeyboardInterrupt:
                self.log.info("Live trading stopped by user")
            finally:
                self.health_monitor.stop_monitoring()
                self._shutdown()

    def _process_bar(self, fvg_display, historical_df, bar_time):
        """Process a single bar for trading signals"""
        with LogContext.correlation_scope() as correlation_id:
            try:
                # Update FVGs
                if fvg_display.check_historical_updated():
                    fvg_display.process_historical_bars()

                # Get current price
                current_price = fvg_display.read_current_price()
                if current_price is None:
                    return None

                # Check live FVG fills
                fvg_display.check_live_fvg_fills(current_price)

                # Get active FVGs
                active_fvgs = [f for f in fvg_display.active_fvgs if not f.get('filled', False)]
                if not active_fvgs:
                    self.log.info("No active FVGs")
                    return None

                # Analyze market context
                fvg_context = self.fvg_analyzer.analyze_market_context(current_price, active_fvgs)

                # Get market data
                current_bar = historical_df.iloc[-1]
                market_data = {
                    'ema21': current_bar.get('EMA21', 0),
                    'ema75': current_bar.get('EMA75', 0),
                    'ema150': current_bar.get('EMA150', 0),
                    'stochastic': current_bar.get('StochD', 50)
                }

                # Get memory and previous analysis
                memory_context = self.memory_manager.get_memory_context()
                previous_analysis = self.analysis_manager.format_previous_analysis_for_prompt()

                # Analyze with Claude (with circuit breaker)
                result = self._analyze_with_retry(
                    fvg_context,
                    market_data,
                    memory_context,
                    previous_analysis
                )

                if not result or not result.get('success'):
                    return result

                # Process decision
                decision_data = result['decision']

                # Save analysis state
                if 'long_assessment' in decision_data and 'short_assessment' in decision_data:
                    analysis_update = {
                        'current_bar_index': decision_data.get('current_bar_index', 0),
                        'overall_bias': decision_data.get('overall_bias', 'neutral'),
                        'waiting_for': decision_data.get('waiting_for', 'Analyzing market'),
                        'long_assessment': decision_data['long_assessment'],
                        'short_assessment': decision_data['short_assessment'],
                        'bars_since_last_update': 0
                    }
                    self.analysis_manager.update_analysis(analysis_update)

                primary = decision_data.get('primary_decision', 'NONE')

                if primary != 'NONE':
                    chosen_setup = decision_data['long_setup'] if primary == 'LONG' else decision_data['short_setup']

                    # === VALIDATION LAYER 1: AI Decision Validator ===
                    validation_result = self.ai_validator.validate_decision(
                        ai_decision=decision_data,
                        current_price=current_price,
                        market_data=market_data,
                        fvg_context=fvg_context
                    )

                    if not validation_result.is_valid:
                        self.log.warning(f"AI decision REJECTED by validator: {validation_result.errors}")
                        self.log.info(self.ai_validator.get_validation_summary(validation_result))
                        return result

                    if validation_result.warnings:
                        self.log.warning(f"AI decision warnings: {validation_result.warnings}")

                    # === VALIDATION LAYER 2: Edge Filters (Setup Quality) ===
                    # Get nearest FVG for the chosen direction
                    if primary == 'LONG':
                        fvg_zone = fvg_context.get('nearest_bearish_fvg', {})
                    else:
                        fvg_zone = fvg_context.get('nearest_bullish_fvg', {})

                    # Get recent bars for confirmation check
                    recent_bars = []
                    if len(historical_df) >= 5:
                        for i in range(-5, 0):
                            bar = historical_df.iloc[i]
                            recent_bars.append({
                                'Open': bar.get('Open', 0),
                                'High': bar.get('High', 0),
                                'Low': bar.get('Low', 0),
                                'Close': bar.get('Close', 0)
                            })

                    should_take, setup_quality = self.edge_filters.should_take_trade(
                        direction=primary,
                        entry=chosen_setup['entry'],
                        stop=chosen_setup['stop'],
                        target=chosen_setup['target'],
                        confidence=chosen_setup['confidence'],
                        fvg_zone=fvg_zone,
                        market_data=market_data,
                        recent_bars=recent_bars
                    )

                    self.log.info(self.edge_filters.get_quality_summary(setup_quality))

                    if not should_take:
                        self.log.warning(f"Setup quality too low: Grade {setup_quality.grade} ({setup_quality.score}/100)")
                        return result

                    # === VALIDATION LAYER 3: Pre-trade Risk Check ===
                    # Adjust position size based on setup quality
                    adjusted_size = max(1, int(self.config.trading.position_size * setup_quality.adjusted_size))

                    allowed, reason = self.risk_manager.check_pre_trade(
                        direction=primary,
                        entry=chosen_setup['entry'],
                        stop=chosen_setup['stop'],
                        target=chosen_setup['target'],
                        quantity=adjusted_size,
                        confidence=chosen_setup['confidence']
                    )

                    if not allowed:
                        self.log.warning(f"Trade rejected by risk manager: {reason}")
                        return result

                    # === CREATE EXIT PLAN ===
                    exit_plan = self.exit_manager.create_exit_plan(
                        direction=primary,
                        entry=chosen_setup['entry'],
                        stop=chosen_setup['stop'],
                        target=chosen_setup['target'],
                        quantity=adjusted_size
                    )
                    self.log.info(self.exit_manager.get_exit_plan_summary(exit_plan, primary, chosen_setup['entry']))

                    # Generate signal with enhanced data
                    signal = {
                        'decision': primary,
                        'entry': chosen_setup['entry'],
                        'stop': chosen_setup['stop'],
                        'target': chosen_setup['target'],
                        'risk_reward': chosen_setup['risk_reward'],
                        'confidence': chosen_setup['confidence'],
                        'reasoning': decision_data.get('overall_reasoning', ''),
                        'setup_type': 'fvg_only',
                        'setup_grade': setup_quality.grade,
                        'setup_score': setup_quality.score,
                        'adjusted_size': adjusted_size,
                        'exit_plan': {
                            'target_1': exit_plan.target_1,
                            'target_2': exit_plan.target_2,
                            'target_3': exit_plan.target_3,
                            'breakeven_trigger': exit_plan.breakeven_trigger,
                            'trailing_trigger': exit_plan.trailing_trigger
                        }
                    }

                    success = self.signal_generator.generate_signal(signal)

                    if success:
                        trade_id = f"{bar_time}_{primary}"
                        self.risk_manager.record_trade_entry(
                            trade_id=trade_id,
                            direction=primary,
                            quantity=adjusted_size
                        )
                        self.analysis_manager.mark_trade_executed(primary)
                        self.health_monitor.record_trade()

                        # Log comprehensive trade info
                        self.log.trade_signal(
                            direction=primary,
                            entry=chosen_setup['entry'],
                            stop=chosen_setup['stop'],
                            target=chosen_setup['target'],
                            confidence=chosen_setup['confidence']
                        )
                        self.log.info(f"Setup Grade: {setup_quality.grade} | Size: {adjusted_size} | "
                                     f"Exit targets: T1={exit_plan.target_1:.2f}, T2={exit_plan.target_2:.2f}, T3={exit_plan.target_3:.2f}")

                return result

            except Exception as e:
                self.log.error(f"Error processing bar: {e}", exc_info=True)
                return None

    def _analyze_with_retry(self, fvg_context, market_data, memory_context, previous_analysis):
        """Analyze with circuit breaker protection"""
        if self.api_circuit_breaker and not self.api_circuit_breaker.can_execute():
            self.log.warning("API circuit breaker open - skipping analysis")
            return None

        try:
            result = self.trading_agent.analyze_setup(
                fvg_context,
                market_data,
                memory_context,
                previous_analysis
            )
            if self.api_circuit_breaker:
                self.api_circuit_breaker.record_success()
            return result
        except Exception as e:
            if self.api_circuit_breaker:
                self.api_circuit_breaker.record_failure(e)
            raise

    def _display_status(self, result, current_price, blocked_reason=None):
        """Display current status"""
        os.system('cls' if os.name == 'nt' else 'clear')

        # Show risk status
        print(self.risk_manager.get_summary())
        print()

        # Show blocked reason if any
        if blocked_reason:
            print(f"TRADING BLOCKED: {blocked_reason}")
            print()

        # Show last analysis result
        if result and self.trading_agent:
            print(self.trading_agent.format_decision_display(result, current_price))

        print("\nWaiting for next bar...")

    def run_backtest_mode(self, days: int = 30, output_file: str = "backtest_results.json"):
        """Run in backtest mode"""
        self.log.info(f"Starting BACKTEST mode ({days} days)")

        api_key = os.getenv('ANTHROPIC_API_KEY')
        use_claude = api_key is not None

        if not use_claude:
            self.log.warning("No API key - running backtest with simple logic")

        engine = BacktestEngine(self.config._raw_config)
        results = engine.run_backtest(days=days, use_claude=use_claude, api_key=api_key)

        # Print summary
        self.log.info("=" * 60)
        self.log.info("BACKTEST RESULTS")
        self.log.info("=" * 60)
        self.log.info(f"Period: {results['backtest_period']}")
        self.log.info(f"Total Bars: {results['total_bars']}")
        self.log.info(f"Total Trades: {results['total_trades']}")
        self.log.info(f"Wins: {results['wins']} | Losses: {results['losses']} | Breakeven: {results['breakeven']}")
        self.log.info(f"Win Rate: {results['win_rate']:.1%}")
        self.log.info(f"Total P&L: {results['total_pnl']:+.2f} points")
        self.log.info(f"Average P&L: {results['avg_pnl']:+.2f} points")
        self.log.info(f"Max Win: {results['max_win']:+.2f} points")
        self.log.info(f"Max Loss: {results['max_loss']:+.2f} points")
        self.log.info("=" * 60)

        engine.export_results(results, output_file)

    def run_monitor_mode(self):
        """Run in monitoring/dashboard mode"""
        self.log.info("Starting MONITOR mode")

        print("\n" + "=" * 60)
        print("SYSTEM STATUS")
        print("=" * 60)

        # Health status
        self.health_monitor.run_all_checks()
        print(self.health_monitor.get_summary())

        # Risk status
        print(self.risk_manager.get_summary())

        # Performance summary
        print(self.performance.get_summary())

        # Recent signals
        recent_signals = self.signal_generator.get_recent_signals(10)
        if recent_signals:
            print("\nRECENT SIGNALS:")
            print("-" * 60)
            for signal in recent_signals:
                print(f"{signal['DateTime']} | {signal['Direction']:<5} | "
                      f"Entry: {signal['Entry_Price']:<8} | "
                      f"Stop: {signal['Stop_Loss']:<8} | "
                      f"Target: {signal['Target']}")

        print(f"\nSignals today: {self.signal_generator.count_signals_today()}")
        print("=" * 60)

    def _shutdown(self):
        """Graceful shutdown"""
        self.log.info("Shutting down...")

        # Save performance data
        try:
            self.performance._save_data()
        except Exception:
            pass

        # Log final stats
        self.log.info("Final Risk Status:")
        self.log.info(self.risk_manager.get_summary())

        self.log.info("Shutdown complete")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Claude NQ Trading Agent - Enterprise Edition'
    )
    parser.add_argument(
        '--mode',
        choices=['live', 'backtest', 'monitor'],
        default='monitor',
        help='Operating mode'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days for backtest (default: 30)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/agent_config.json',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='backtest_results.json',
        help='Output file for backtest results'
    )

    args = parser.parse_args()

    # Initialize orchestrator
    try:
        orchestrator = EnterpriseTradingOrchestrator(config_path=args.config)
    except Exception as e:
        print(f"Failed to initialize: {e}")
        sys.exit(1)

    # Run in selected mode
    if args.mode == 'live':
        orchestrator.run_live_mode()
    elif args.mode == 'backtest':
        orchestrator.run_backtest_mode(days=args.days, output_file=args.output)
    elif args.mode == 'monitor':
        orchestrator.run_monitor_mode()


if __name__ == "__main__":
    main()
