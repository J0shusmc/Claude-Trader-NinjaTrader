# Claude Trader - Enterprise AI Trading System

An enterprise-grade automated trading system for NQ futures that combines Claude AI analysis with NinjaTrader execution. Features multi-layer validation, intelligent risk management, and professional exit strategies.

## Architecture Overview

```
                         Claude AI
                            |
                    Enhanced Analysis
                            |
    +-----------------------------------------------+
    |           Enterprise Orchestrator             |
    +-----------------------------------------------+
            |           |           |           |
        AI Validator  Edge Filters  Risk Manager  Exit Manager
            |           |           |           |
    +-----------------------------------------------+
    |              Signal Generator                 |
    +-----------------------------------------------+
                            |
                     trade_signals.csv
                            |
    +-----------------------------------------------+
    |        NinjaTrader (ClaudeTrader.cs)          |
    +-----------------------------------------------+
                            |
                      Broker Orders
```

## Key Features

### AI-Powered Analysis
- **Enhanced Trading Agent**: Structured prompts with examples for consistent JSON output
- **Multi-Perspective Analysis**: Consensus from trend, zone, and risk perspectives
- **Self-Verification Loop**: AI critiques its own decisions before execution
- **Performance-Aware Context**: AI knows its recent track record

### Multi-Layer Validation (Don't Blindly Trust AI)
1. **AI Decision Validator**: Mathematical and sanity checks on every AI decision
   - Stop/target price validation
   - Risk/reward verification
   - Trend alignment warnings
   - Consistency checks for flip-flopping
2. **Edge Filters**: Setup quality scoring (A/B/C/D/F grades)
   - Session timing (morning best, lunch worst)
   - Market regime detection
   - Entry confirmation patterns
   - Dynamic position sizing based on grade

### Intelligent Exit Management
- **Scaled Exits**: Take partial profits at 1R, 2R, let runner go to 3.5R
- **Breakeven Stop**: Move to breakeven at 1.5R
- **Trailing Stop**: Start trailing at 2R with 0.5R offset
- **Time-Based Exit**: Exit after max bars if trade isn't working
- **Reversal Detection**: Exit if market structure breaks

### Enterprise Risk Management
- Daily trade limits with automatic halt
- Daily loss limits with circuit breaker
- Consecutive loss tracking with cooldown periods
- Maximum drawdown protection
- Position size limits and dynamic adjustment
- Stop loss range validation (15-50 points)

### System Health Monitoring
- Real-time file and API health checks
- System resource monitoring (CPU, memory, disk)
- Heartbeat for external monitoring
- Alert callbacks for degraded/unhealthy states
- Uptime tracking

## Operating Modes

```bash
# Monitor mode - View system status
python main.py --mode monitor

# Live trading mode - Full automated trading
python main.py --mode live

# Backtest mode - Historical simulation
python main.py --mode backtest --days 30 --output results.json
```

## Project Structure

```
claude-trader-ninjatrader/
├── main.py                      # Enterprise orchestrator entry point
├── config/
│   ├── agent_config.json        # Main configuration
│   └── risk_rules.json          # Risk management rules
├── src/
│   ├── core/
│   │   ├── config_manager.py    # Centralized configuration
│   │   ├── logging_setup.py     # Enterprise logging with correlation IDs
│   │   ├── retry.py             # Retry logic and circuit breaker
│   │   ├── file_lock.py         # Safe file operations
│   │   └── exceptions.py        # Custom exceptions
│   ├── enhanced_ai_agent.py     # Claude AI integration
│   ├── ai_validator.py          # AI decision validation
│   ├── edge_filters.py          # Setup quality scoring
│   ├── exit_strategies.py       # Exit management
│   ├── risk_manager.py          # Enterprise risk management
│   ├── health_monitor.py        # System health monitoring
│   ├── performance_analytics.py # Performance tracking
│   ├── fvg_analyzer.py          # Fair Value Gap analysis
│   ├── level_detector.py        # Support/resistance detection
│   ├── signal_generator.py      # CSV signal generation
│   ├── trading_agent.py         # Legacy trading agent
│   ├── memory_manager.py        # Context memory
│   ├── market_analysis_manager.py # Analysis persistence
│   └── backtest_engine.py       # Backtesting engine
├── ninjascripts/
│   └── claudetrader.cs          # NinjaTrader strategy
├── data/
│   ├── trade_signals.csv        # Input: signals for NinjaTrader
│   └── trades_taken.csv         # Output: executed trades log
└── FairValueGaps.py             # FVG detection and display
```

## Signal Flow

### 1. Market Data Ingestion
```
NinjaTrader → SecondHistoricalData.cs → historical_data.csv → Python
            → SecondLifeFeed.cs → live_feed.csv → Python
```

### 2. AI Analysis Pipeline
```
FVG Detection → Market Context → Claude AI → Multi-Perspective Consensus
     ↓                                              ↓
Active FVGs     EMA/Stochastic           Trend + Zone + Risk Analysis
```

### 3. Validation Pipeline
```
AI Decision → AI Validator → Edge Filters → Risk Manager → Signal Generator
     ↓             ↓              ↓              ↓              ↓
  Decision    Math Check    Quality Grade   Pre-trade OK   CSV Written
```

### 4. Execution Pipeline
```
trade_signals.csv → ClaudeTrader.cs → Limit Order → Fill → SL/TP Orders
                                           ↓
                                    trades_taken.csv
```

## Configuration

### Environment Variables
```bash
ANTHROPIC_API_KEY=your_api_key_here
```

### Key Configuration (config/agent_config.json)
```json
{
  "trading_params": {
    "min_gap_size": 5.0,
    "min_risk_reward": 3.0,
    "confidence_threshold": 0.65,
    "position_size": 2
  },
  "risk": {
    "max_daily_trades": 5,
    "max_daily_loss": 100,
    "max_consecutive_losses": 3,
    "max_position_size": 3,
    "stop_loss_min": 15,
    "stop_loss_max": 50,
    "cool_down_after_loss_minutes": 15
  }
}
```

## NinjaTrader Integration

### CSV Signal Format
```csv
DateTime,Direction,Entry_Price,Stop_Loss,Take_Profit
11/30/2025 14:30:00,LONG,21000.00,20970.00,21090.00
```

### Installation
1. Copy `ninjascripts/claudetrader.cs` to `Documents\NinjaTrader 8\bin\Custom\Strategies\`
2. Compile in NinjaTrader (Tools → Edit NinjaScript → Strategy → Compile)
3. Apply to NQ chart with desired parameters

### Strategy Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| Signals File Path | Configurable | Path to trade_signals.csv |
| Contract Quantity | 2 | Contracts per trade |
| File Check Interval | 2 seconds | Signal polling frequency |

## Setup Quality Grades

The edge filter system scores setups from 0-100:

| Grade | Score | Recommendation | Position Size |
|-------|-------|----------------|---------------|
| A | 85-100 | TAKE | 1.5x normal |
| B | 70-84 | TAKE | 1.0x normal |
| C | 55-69 | WAIT | 0.5x normal |
| D | 40-54 | SKIP | 0x |
| F | 0-39 | SKIP | 0x |

### Scoring Factors
- **Session Timing** (0-25 pts): Morning=25, Afternoon=20, Lunch=7
- **Market Regime** (0-25 pts): Trend aligned=25, Ranging=10, Counter-trend=5
- **Entry Confirmation** (0-25 pts): Pattern confirmed=25, No confirmation=8
- **Risk/Reward** (0-25 pts): 4R+=25, 3R=20, 2R=12, <2R=5

## Risk Management States

| State | Description | Action |
|-------|-------------|--------|
| NORMAL | All systems operational | Trading allowed |
| WARNING | Approaching limits | Reduced position size |
| COOLDOWN | After loss | Wait for cooldown timer |
| HALTED | Limit breached | No trading until reset |

## Safety Features

### AI Validation Errors (Trade Blocked)
- Stop above entry for LONG / below entry for SHORT
- Target below entry for LONG / above entry for SHORT
- Entry too far from current price (>2%)
- Stop too tight (<10 pts) or too wide (>100 pts)
- R/R below minimum (3.0)

### AI Validation Warnings (Proceed with Caution)
- Trade against strong trend
- Entry far from FVG zone (>50 pts)
- Direction changed within 1 hour

## Development

### Running Tests
```bash
pytest tests/
```

### Dependencies
```
anthropic
pandas
python-dotenv
psutil (optional, for system monitoring)
```

## Version History

- **v1.0** - Initial market order implementation
- **v1.1** - Changed to limit orders with CSV-based SL/TP
- **v1.2** - Added partial fill handling
- **v1.3** - Enhanced logging and error handling
- **v2.0** - Enterprise rewrite with AI validation, edge filters, exit strategies, risk management, and health monitoring

## License

Proprietary - For personal trading use only.

---

**Last Updated**: November 30, 2025
**Status**: Production Ready
**Version**: 2.0 Enterprise Edition
**Tested On**: NinjaTrader 8, NQ Futures
