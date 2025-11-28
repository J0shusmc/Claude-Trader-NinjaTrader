# Claude NQ Trading Agent

## What It Does

**Autonomous AI trading system that reasons about Fair Value Gaps and psychological levels to make NQ futures trading decisions.**

No neural networks. No indicators. Pure price action reasoning powered by Claude.

---

## Core Concept

```
Price → FVG Detection → Claude Reasoning → Trade Decision → NinjaTrader
         (existing)      (AI analysis)      (signals.csv)    (execution)
```

**The System:**
1. Monitors FVG zones from `FairValueGaps.py`
2. Claude analyzes price context + gap confluence
3. Reviews past trade outcomes from memory
4. Makes trade decisions based on reasoning
5. Outputs signals to `trade_signals.csv`
6. Learns from outcomes through feedback loop

---

## Architecture

### Data Layer
- **FairValueGaps.py** - Real-time FVG detection (existing)
- **HistoricalData.csv** - 1000 days OHLC + EMAs
- **LiveFeed.csv** - Real-time price updates

### Intelligence Layer
- **trading_agent.py** - Claude reasoning engine
- **fvg_analyzer.py** - Parses FVG data + calculates distances
- **level_detector.py** - Identifies psychological levels (100pt intervals)
- **memory_manager.py** - MCP integration for trade history

### Execution Layer
- **signal_generator.py** - Outputs to trade_signals.csv
- **NinjaTrader** - Executes actual orders

### Learning Layer
- **MCP Memory** - Stores trade outcomes
- **Feedback Loop** - Claude reviews past performance
- **Adaptive Reasoning** - Improves decisions over time

---

## How Learning Works

**Not Machine Learning. Context Learning.**

```
Traditional ML:                Claude Approach:
─────────────────             ─────────────────
Train on dataset    →         Analyze current setup
Gradient descent    →         Query similar past trades
Weight updates      →         Reason about outcomes
Model inference     →         Adapt decision logic

✓ Explainable                 ✓ Fast adaptation
✓ No retraining needed        ✓ Works with small samples
✓ Transparent logic           ✓ Immediate rule updates
```

---

## Trading Logic

### Entry Criteria (Claude Evaluates)
- **Gap Confluence**: FVG aligns with psychological level
- **Distance**: Price proximity to entry zone
- **Gap Quality**: Size (>5pts), age (<100 bars), unfilled
- **Memory**: Historical win rate for similar setups
- **Risk/Reward**: Minimum 3:1 ratio (configurable)

### Example Decision
```
SETUP:
Price: 14,685
Bullish FVG: 14,710-14,715 (resistance)
Psych Level: 14,700 (confluence!)
Memory: 72% win rate on level+FVG shorts

CLAUDE DECIDES:
Entry: 14,712 (SHORT)
Stop: 14,730 (20pt stop - NQ appropriate)
Target: 14,650 (bearish FVG fill)
R/R: 20pts / 62pts = 3.1:1 ✓

OUTPUT:
2025-11-25 14:30:00,SHORT,14712,14730,14650
```

### Stop Loss Rules
- **Minimum**: 15 points (NQ volatility appropriate)
- **Default**: 20 points
- **Maximum**: 50 points
- **Placement**: Beyond FVG zone + buffer (5-10pts)

---

## Project Structure

```
Claude Trader/
├── src/
│   ├── trading_agent.py          # Main Claude reasoning engine
│   ├── fvg_analyzer.py            # FVG data parser
│   ├── level_detector.py          # Psychological level finder
│   ├── signal_generator.py        # trade_signals.csv writer
│   ├── memory_manager.py          # MCP integration
│   └── backtest_engine.py         # Historical testing
├── config/
│   ├── agent_config.json          # Trading parameters
│   └── risk_rules.json            # Risk management
├── data/
│   ├── trade_history.json         # Past trade outcomes
│   └── performance_log.json       # System metrics
├── tests/
│   └── test_*.py                  # Test suite
├── docs/
│   ├── AGENT_README.md            # This file
│   └── ARCHITECTURE.md            # Detailed design
├── FairValueGaps.py               # (existing - unchanged)
└── main.py                        # System orchestrator
```

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API
```bash
# .env file
ANTHROPIC_API_KEY=your_key_here
```

### 3. Run Backtest (Recommended First)
```bash
python main.py --mode backtest --days 30
```

### 4. Run Live Trading
```bash
python main.py --mode live
```

### 5. Monitor Performance
```bash
python main.py --mode monitor
```

---

## Configuration

### agent_config.json
```json
{
  "min_gap_size": 5.0,
  "max_gap_age_bars": 100,
  "min_risk_reward": 3.0,
  "stop_loss_min": 15,
  "stop_loss_default": 20,
  "stop_loss_max": 50,
  "position_size": 1,
  "psychological_levels": [100],
  "confidence_threshold": 0.65
}
```

---

## Performance Tracking

System automatically tracks:
- **Win Rate**: Percentage of profitable trades
- **Average R/R**: Risk/reward ratio achieved
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest equity drop
- **Setup Quality**: FVG vs Level vs Confluence trades

### Memory-Based Improvement
- Claude reviews outcomes before each decision
- Identifies which setup types work best
- Adjusts confidence levels based on history
- No retraining required - instant adaptation

---

## Key Features

### ✓ Reasoning Over Training
Claude analyzes each setup contextually - not pattern matching

### ✓ Explainable Decisions
Every trade has a clear reasoning chain you can audit

### ✓ Adaptive Without Retraining
Learns from outcomes through memory - no model updates needed

### ✓ Risk-Aware
Stop losses sized appropriately for NQ volatility (15-50pts)

### ✓ Backtestable
Test strategies on 1000 days of historical data

### ✓ Production Ready
Outputs directly to NinjaTrader via CSV

---

## MCP Integration

Uses Claude Flow MCP tools for:
- **Memory Management**: `memory_usage` - Store/retrieve trade history
- **Agent Adaptation**: `daa_agent_adapt` - Learn from feedback
- **Performance Tracking**: `agent_metrics` - Monitor system health

---

## Backtesting Results (Coming Soon)

Will compare:
- **Claude Agent P&L** vs **Buy & Hold**
- **Trade-by-trade analysis** with reasoning logs
- **Setup quality breakdown** (confluence vs single-factor trades)
- **Parameter sensitivity testing**

---

## Safety Features

- **No live trading until backtest validated**
- **Stop losses mandatory on every trade**
- **Position sizing limits enforced**
- **Maximum daily loss threshold**
- **Manual override capability**

---

## Roadmap

**Phase 1: Foundation** (Week 1) ✓
- FVG detection working
- Claude agent architecture designed
- MCP integration planned

**Phase 2: Core Implementation** (Week 2)
- Trading agent built
- Backtesting framework complete
- Memory system operational

**Phase 3: Validation** (Week 3)
- 1000-day backtest analysis
- Parameter optimization
- Risk validation

**Phase 4: Production** (Week 4)
- Live paper trading
- Performance monitoring
- Iterative improvement

---

## Why This Works

**Markets seek efficiency. Gaps are inefficiency. Price fills gaps.**

The edge:
1. FVGs are measurable inefficiencies
2. Psychological levels are proven S/R zones
3. Confluence = double confirmation
4. Claude reasons about context (not just patterns)
5. Memory creates adaptive intelligence

This isn't speculation. It's systematic gap-fill trading with AI reasoning.

---

## Support

- **Architecture Details**: See `docs/ARCHITECTURE.md`
- **Trading Philosophy**: See `docs/PRICE_ACTION_PHILOSOPHY.md`
- **FVG Detection**: See `FairValueGaps.py`
- **Issues**: Review logs in `data/performance_log.json`

---

**Last Updated**: 2025-11-25
**Version**: 1.0.0 - Production Architecture
**Status**: Implementation Phase
