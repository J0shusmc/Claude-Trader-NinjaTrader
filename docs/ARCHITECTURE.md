# Claude NQ Trading Agent - System Architecture

## System Overview

**Autonomous trading system that uses Claude's reasoning capabilities to make NQ futures trading decisions based on Fair Value Gaps and psychological levels.**

---

## Design Principles

1. **Reasoning Over Training**: Claude analyzes context, not pattern matching
2. **Explainability**: Every decision has transparent logic
3. **Adaptability**: Learning through memory, not gradient descent
4. **Safety First**: Stop losses mandatory, risk limits enforced
5. **Production Ready**: Direct integration with NinjaTrader

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    DATA SOURCES                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Historical   │  │  LiveFeed    │  │ FairValueGaps│ │
│  │ Data (OHLC)  │  │  (Real-time) │  │  (FVG Zones) │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                ANALYSIS LAYER                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ FVG Analyzer │  │ Level        │  │ Market       │ │
│  │ (Parse FVGs) │  │ Detector     │  │ Context      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│             INTELLIGENCE LAYER (CLAUDE)                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Claude Trading Agent                    │   │
│  │  - Analyzes FVG confluence with levels          │   │
│  │  - Reviews past trade outcomes from memory      │   │
│  │  - Reasons about setup quality                  │   │
│  │  - Calculates risk/reward                       │   │
│  │  - Makes trade decision with explanation        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│               MEMORY & LEARNING LAYER (MCP)             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Trade        │  │ Performance  │  │ Pattern      │ │
│  │ History      │  │ Metrics      │  │ Recognition  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                  EXECUTION LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Signal       │  │ trade_signals│  │ NinjaTrader  │ │
│  │ Generator    │  │ .csv (output)│  │ (execution)  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. FVG Analyzer (`src/fvg_analyzer.py`)

**Purpose**: Parse FVG data and prepare for Claude analysis

**Responsibilities**:
- Read active FVGs from FairValueGaps.py output/state
- Calculate distance from current price to each FVG
- Identify nearest bullish and bearish gaps
- Determine if price is inside any zones
- Format data for Claude consumption

**Input**:
- FVG zones (from FairValueGaps.py)
- Current price (from LiveFeed.csv)

**Output**:
```python
{
    "current_price": 14685.50,
    "nearest_bullish_fvg": {
        "top": 14715.00,
        "bottom": 14710.00,
        "size": 5.0,
        "distance": 24.50,  # pts to entry (top)
        "age_bars": 12
    },
    "nearest_bearish_fvg": {
        "top": 14655.00,
        "bottom": 14650.00,
        "size": 5.0,
        "distance": 30.50,  # pts to entry (bottom)
        "age_bars": 45
    },
    "price_in_zone": None  # or FVG object if inside
}
```

---

### 2. Level Detector (`src/level_detector.py`)

**Purpose**: Identify psychological levels and confluences

**Responsibilities**:
- Detect round number levels (100pt intervals: 14600, 14700, 14800)
- Calculate distance to nearest levels above/below
- Identify FVG + Level confluences
- Track historical strength of levels

**Input**:
- Current price
- Price history

**Output**:
```python
{
    "nearest_level_above": 14700,
    "distance_above": 14.50,
    "nearest_level_below": 14600,
    "distance_below": 85.50,
    "confluences": [
        {
            "level": 14700,
            "fvg": {bullish FVG object},
            "type": "resistance",
            "strength": "high"
        }
    ]
}
```

---

### 3. Claude Trading Agent (`src/trading_agent.py`)

**Purpose**: Main reasoning engine for trade decisions

**Responsibilities**:
- Receive market context (FVGs, levels, price)
- Query memory for similar past setups
- Reason about trade quality
- Calculate risk/reward
- Make GO/NO-GO decision
- Generate detailed reasoning explanation
- Output trade signal if criteria met

**Decision Framework**:
```python
def analyze_setup(context):
    """
    1. Assess confluence (FVG + Level?)
    2. Check gap quality (size, age, filled status)
    3. Query memory for similar setups
    4. Calculate risk/reward
    5. Evaluate against thresholds
    6. Generate reasoning chain
    7. Return decision + explanation
    """
```

**Claude Prompt Structure**:
```
You are an expert NQ futures trader analyzing a potential setup.

CURRENT MARKET:
- Price: {current_price}
- Nearest Bullish FVG: {fvg_data}
- Nearest Bearish FVG: {fvg_data}
- Psychological Levels: {level_data}
- Confluences: {confluence_data}

PAST PERFORMANCE:
- Similar bullish FVG trades: {memory_stats}
- Similar bearish FVG trades: {memory_stats}
- Confluence trades: {memory_stats}

ANALYZE:
1. Is there a high-quality setup forming?
2. What is the trade direction (LONG/SHORT/NONE)?
3. What is the entry price?
4. What is the stop loss (15-50pt range)?
5. What is the target?
6. What is the risk/reward ratio?
7. Should we take this trade? Why or why not?

Respond with structured JSON decision.
```

**Output**:
```python
{
    "decision": "SHORT",  # or "LONG" or "NONE"
    "entry": 14712.00,
    "stop": 14730.00,  # 18pt stop
    "target": 14650.00,
    "risk_reward": 3.44,
    "confidence": 0.78,
    "reasoning": "Bullish FVG at 14710-14715 aligns with 14700 psychological level creating strong resistance confluence. Historical data shows 72% win rate on similar setups. Current uptrend momentum suggests price will test this zone. 18pt stop provides buffer above FVG. Target is unfilled bearish FVG at 14650 with 62pt profit potential. R/R of 3.44:1 exceeds minimum threshold.",
    "setup_type": "confluence",  # or "fvg_only" or "level_only"
    "timestamp": "2025-11-25T14:30:00Z"
}
```

---

### 4. Memory Manager (`src/memory_manager.py`)

**Purpose**: Interface with MCP for trade history and learning

**Responsibilities**:
- Store completed trade outcomes
- Query past trades by setup type
- Calculate performance metrics
- Provide historical context to Claude
- Trigger adaptive learning

**MCP Integration**:
```python
# Store trade outcome
mcp__claude-flow__memory_usage(
    operation="store",
    key=f"trade_{timestamp}",
    data={trade_outcome}
)

# Query similar trades
mcp__claude-flow__memory_usage(
    operation="retrieve",
    filter={"setup_type": "confluence", "direction": "SHORT"}
)

# Adapt agent based on performance
mcp__claude-flow__daa_agent_adapt(
    agent_id="nq_trader",
    feedback="Last 10 confluence trades: 80% win rate",
    performance_score=0.80
)
```

**Trade History Schema**:
```python
{
    "trade_id": "2025-11-25_14:30:00",
    "setup": {
        "type": "confluence",
        "direction": "SHORT",
        "fvg": {fvg_data},
        "level": 14700,
        "entry": 14712,
        "stop": 14730,
        "target": 14650
    },
    "outcome": {
        "result": "WIN",  # or "LOSS" or "BREAKEVEN"
        "exit_price": 14651.00,
        "profit_loss": 61.00,
        "risk_reward_achieved": 3.39,
        "bars_held": 8,
        "exit_reason": "target_hit"
    },
    "reasoning": "...",
    "timestamp": "2025-11-25T14:30:00Z"
}
```

---

### 5. Signal Generator (`src/signal_generator.py`)

**Purpose**: Output trade signals to NinjaTrader format

**Responsibilities**:
- Format Claude decision as CSV row
- Append to trade_signals.csv
- Validate data format
- Handle file I/O errors
- Log signal generation

**Output Format** (trade_signals.csv):
```csv
DateTime,Direction,Entry_Price,Stop_Loss,Target
2025-11-25 14:30:00,SHORT,14712.00,14730.00,14650.00
2025-11-25 16:15:00,LONG,14603.00,14585.00,14665.00
```

**Code Structure**:
```python
def generate_signal(decision):
    """
    1. Validate decision object
    2. Format as CSV row
    3. Append to trade_signals.csv
    4. Log signal details
    5. Return confirmation
    """
```

---

### 6. Backtest Engine (`src/backtest_engine.py`)

**Purpose**: Test strategy on historical data

**Responsibilities**:
- Load historical OHLC data
- Simulate FVG detection on past bars
- Generate Claude decisions for each setup
- Calculate trade outcomes
- Compute performance metrics
- Generate detailed report

**Metrics Calculated**:
- Total trades
- Win rate (%)
- Average R/R achieved
- Sharpe ratio
- Maximum drawdown
- Profit factor
- Average bars held
- Setup type breakdown

**Output**:
```python
{
    "summary": {
        "total_trades": 127,
        "wins": 89,
        "losses": 38,
        "win_rate": 0.7008,
        "avg_rr_achieved": 2.84,
        "sharpe_ratio": 1.82,
        "max_drawdown": -185.50,
        "profit_factor": 2.41
    },
    "by_setup_type": {
        "confluence": {"trades": 42, "win_rate": 0.81, ...},
        "fvg_only": {"trades": 58, "win_rate": 0.67, ...},
        "level_only": {"trades": 27, "win_rate": 0.63, ...}
    },
    "trade_log": [detailed_trade_list]
}
```

---

### 7. Main Orchestrator (`main.py`)

**Purpose**: Coordinate all system components

**Modes**:

#### Backtest Mode
```bash
python main.py --mode backtest --days 30 --output results.json
```
- Load historical data
- Run backtest engine
- Generate performance report

#### Live Mode
```bash
python main.py --mode live
```
- Monitor FairValueGaps.py for new FVGs
- Poll LiveFeed.csv for price updates
- Trigger Claude analysis when setup forms
- Output signals to trade_signals.csv
- Log decisions and outcomes

#### Monitor Mode
```bash
python main.py --mode monitor
```
- Display current FVGs
- Show active positions (if any)
- Track performance metrics
- Real-time dashboard

---

## Data Flow: Live Trading

```
1. FairValueGaps.py detects new FVG
        ↓
2. Main.py detects new zone
        ↓
3. FVGAnalyzer parses FVG data
        ↓
4. LevelDetector checks for confluences
        ↓
5. TradingAgent queries memory for context
        ↓
6. Claude analyzes setup and decides
        ↓
7. IF trade criteria met:
   → SignalGenerator writes to trade_signals.csv
   → MemoryManager logs decision
        ↓
8. NinjaTrader reads trade_signals.csv
        ↓
9. Trade executed
        ↓
10. Outcome tracked and fed back to memory
```

---

## Learning Loop

**How the system improves over time:**

```
Trade Decision Made
        ↓
Execute Trade
        ↓
Outcome Recorded (WIN/LOSS/BREAKEVEN)
        ↓
Memory Updated with Outcome
        ↓
Next Decision:
  - Claude queries memory
  - Reviews similar past setups
  - Adjusts reasoning based on what worked
  - Higher confidence on proven patterns
  - Lower confidence on failed patterns
        ↓
Improved Decision Quality
```

**Key Insight**: Not gradient descent, but **contextual reasoning improvement**

---

## Risk Management

### Position Sizing
- Default: 1 contract
- Configurable based on account size
- No pyramiding (one trade at a time)

### Stop Loss Rules
- **Minimum**: 15 points (NQ volatility floor)
- **Default**: 20 points
- **Maximum**: 50 points
- **Placement**: Beyond FVG zone + buffer (5-10pts)

### Daily Limits
- Max trades per day: 5
- Max daily loss: 100 points
- Max consecutive losses before pause: 3

### Setup Quality Thresholds
- Minimum gap size: 5 points
- Maximum gap age: 100 bars
- Minimum R/R ratio: 3.0:1
- Minimum confidence: 0.65

---

## Configuration Files

### `config/agent_config.json`
```json
{
  "trading_params": {
    "min_gap_size": 5.0,
    "max_gap_age_bars": 100,
    "min_risk_reward": 3.0,
    "confidence_threshold": 0.65,
    "position_size": 1
  },
  "risk_management": {
    "stop_loss_min": 15,
    "stop_loss_default": 20,
    "stop_loss_max": 50,
    "stop_buffer": 5,
    "max_daily_trades": 5,
    "max_daily_loss": 100,
    "max_consecutive_losses": 3
  },
  "levels": {
    "psychological_intervals": [100],
    "track_historical_strength": true
  },
  "memory": {
    "max_trades_stored": 1000,
    "query_similar_count": 20
  }
}
```

### `config/risk_rules.json`
```json
{
  "mandatory_rules": [
    "Every trade must have a stop loss",
    "Stop loss must be 15-50 points",
    "Minimum R/R must be 3:1",
    "No trading after 3 consecutive losses",
    "No trading after daily loss limit hit"
  ],
  "validation": {
    "check_before_signal": true,
    "log_violations": true,
    "halt_on_violation": true
  }
}
```

---

## Error Handling

### Data Issues
- Missing FVG data → Skip analysis, log warning
- Missing price feed → Use last known price, log warning
- Corrupt CSV → Alert operator, halt trading

### API Issues
- Claude API timeout → Retry 3x, then skip decision
- Claude API error → Log error, continue monitoring
- Rate limit hit → Queue decision, process when available

### Execution Issues
- Cannot write to trade_signals.csv → Alert operator, log trade
- NinjaTrader offline → Store signals, replay when online

---

## Testing Strategy

### Unit Tests
- FVGAnalyzer parsing accuracy
- LevelDetector calculation correctness
- SignalGenerator CSV formatting
- MemoryManager MCP integration

### Integration Tests
- End-to-end decision flow
- Memory query → Claude → Signal output
- Error handling scenarios

### Backtest Validation
- Run on known historical periods
- Verify trade execution logic
- Compare manual vs automated decisions

---

## Performance Monitoring

### Real-Time Metrics
- Current P&L
- Win rate (rolling 20 trades)
- Average R/R achieved
- Trades today / this week
- Current drawdown

### System Health
- Claude API response time
- Memory query latency
- FVG detection lag
- Signal generation time

### Alerts
- Daily loss limit approaching (80%)
- 3 consecutive losses
- API errors
- Data feed disruption

---

## Deployment Checklist

- [ ] Backtest on full 1000-day dataset
- [ ] Validate win rate >60%
- [ ] Validate Sharpe ratio >1.5
- [ ] Test all error handling paths
- [ ] Configure stop loss rules appropriately
- [ ] Set daily loss limits
- [ ] Verify NinjaTrader integration
- [ ] Test signal CSV format
- [ ] Enable performance logging
- [ ] Set up monitoring dashboard
- [ ] Paper trade for 2 weeks
- [ ] Review and adjust parameters
- [ ] Go live with 1 contract

---

## Maintenance

### Daily
- Review trade decisions and reasoning
- Check system logs for errors
- Verify data feeds operational

### Weekly
- Analyze performance metrics
- Review memory-based adaptations
- Adjust parameters if needed

### Monthly
- Full system backtest on recent data
- Compare live vs backtest performance
- Review and update trading rules

---

**Version**: 1.0.0
**Last Updated**: 2025-11-25
**Status**: Implementation Phase
