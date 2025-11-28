# FVG Trading AI - Level & Gap-Based Trading System

## Project Vision

Build an AI-driven trading system that mimics human trading behavior based on **price levels** and **Fair Value Gaps (FVGs)**. The core philosophy: **Price is always moving toward something - either a psychological level or a gap that needs to be filled.**

---

## Trading Philosophy

### Core Principles

1. **Price Magnetism to Round Numbers**
   - Price gravitates toward psychological levels: 6,700 | 6,800 | 6,900
   - These act as magnets and decision points
   - Markets respect these levels as support/resistance

2. **Fair Value Gaps (FVGs) as Price Targets**
   - Price seeks to fill imbalances (gaps) in the market
   - FVGs represent unfilled orders and inefficient price discovery
   - When a gap exists, price will eventually return to fill it

3. **Directional Bias**
   - Price is always heading TOWARD something
   - Either toward a psychological level (100-point intervals)
   - Or toward an unfilled FVG zone
   - The AI should predict which target is most likely

### How I Trade

- **Identify active FVG zones** (bullish/bearish gaps in price)
- **Monitor psychological levels** (6,700, 6,800, 6,900, etc.)
- **Watch price behavior** as it approaches these zones/levels
- **Enter trades** when price enters an FVG zone or bounces off a level
- **Exit when the gap is filled** or the next level is reached

---

## Project Goals

### Phase 1: Foundation (Current)
- [x] FVG zone identification from historical data
- [x] Detection of bullish/bearish gaps
- [x] Zone filtering (active vs filled)
- [ ] Psychological level detection (round number identification)
- [ ] Feature engineering for ML model

### Phase 2: AI Model Development
- [ ] Build dataset with labeled features:
  - Current price position
  - Distance to nearest FVG (bullish/bearish)
  - Distance to nearest psychological level
  - Gap size and age
  - Market direction/momentum
- [ ] Train neural network to predict:
  - Which target price is heading toward (FVG vs level)
  - Probability of reaching target
  - Optimal entry/exit points
- [ ] Backtest model on historical data

### Phase 3: Advanced Intelligence
- [ ] Pattern recognition (how price behaves near levels/gaps)
- [ ] Multi-timeframe analysis
- [ ] Volume/momentum integration
- [ ] Reinforcement learning for trade timing
- [ ] Risk management and position sizing

### Phase 4: Deployment
- [ ] Real-time trading signals
- [ ] Integration with trading platform
- [ ] Performance monitoring and model retraining
- [ ] Dashboard for visualization

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER                              │
│  - Historical OHLC data (1hr bars)                          │
│  - FVG zones (bullish/bearish)                              │
│  - Psychological levels (100-point intervals)               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 FEATURE ENGINEERING                         │
│  - Distance to nearest FVG (up/down)                        │
│  - Distance to nearest level (up/down)                      │
│  - Price momentum and direction                             │
│  - Gap characteristics (size, age, type)                    │
│  - Level proximity (how close to 00 level)                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    AI MODEL LAYER                           │
│  Option A: Neural Network (TensorFlow/PyTorch)             │
│  Option B: Reinforcement Learning (Q-Learning/PPO)         │
│  Option C: Ensemble (Multiple models voting)               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   DECISION ENGINE                           │
│  - Target prediction (FVG vs Level)                         │
│  - Entry signal generation                                   │
│  - Exit signal generation                                    │
│  - Risk management                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTION LAYER                          │
│  - Signal output (CSV/API)                                  │
│  - Performance tracking                                      │
│  - Model feedback loop                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Current Project Structure

```
Neural Network/
├── data/
│   ├── HistoricalData.csv          # Raw OHLC price data
│   ├── fvg_zones.csv                # Identified FVG zones (output)
│   └── [future: levels.csv]         # Psychological level data
├── src/
│   └── [future: AI models]
├── docs/
│   └── README.md                     # This file
├── fvg.py                            # FVG zone identifier (current tool)
└── fvgbot.py                         # Original trading bot (archived)
```

---

## Data Features (Planned)

### Input Features for AI Model

| Feature | Description | Example |
|---------|-------------|---------|
| `current_price` | Current market price | 6758.25 |
| `nearest_fvg_bull_dist` | Distance to nearest bullish FVG | -11.25 pts |
| `nearest_fvg_bear_dist` | Distance to nearest bearish FVG | +51.00 pts |
| `nearest_level_up` | Distance to level above | +41.75 (→ 6800) |
| `nearest_level_down` | Distance to level below | -58.25 (→ 6700) |
| `fvg_bull_size` | Size of nearest bullish gap | 20.25 pts |
| `fvg_bear_size` | Size of nearest bearish gap | 7.50 pts |
| `fvg_bull_age` | Age of bullish gap | 4 bars |
| `fvg_bear_age` | Age of bearish gap | 27 bars |
| `price_momentum` | Rate of price change | +2.5 pts/bar |
| `bars_since_level` | Bars since touching a level | 15 bars |

### Target Labels

- **Target Type:** `FVG_BULL` | `FVG_BEAR` | `LEVEL_UP` | `LEVEL_DOWN`
- **Confidence:** 0.0 - 1.0 (probability of reaching target)
- **Action:** `LONG` | `SHORT` | `HOLD`

---

## Next Steps (Immediate)

### 1. Add Psychological Level Detection
Create a module to identify 100-point levels:
- Detect levels like 6,700, 6,800, 6,900
- Track price behavior near these levels
- Calculate distance to nearest level (up/down)

### 2. Feature Engineering Pipeline
Build a data preparation script:
- Combine FVG data + level data + price data
- Calculate all features in table above
- Label historical data with outcomes (did price reach FVG or level first?)

### 3. Exploratory Data Analysis (EDA)
Analyze patterns:
- Correlation between gap size and fill probability
- How often price respects levels vs gaps
- Optimal entry/exit timing patterns

### 4. Initial Model Prototype
Start simple:
- Binary classifier: "Will price fill this FVG?" (Yes/No)
- Train on historical data with known outcomes
- Evaluate accuracy and iterate

---

## Technologies & Tools

### Current Stack
- **Python 3.x**
- **pandas** - Data manipulation
- **numpy** - Numerical computing
- **CSV** - Data storage

### Planned Additions
- **TensorFlow/Keras** or **PyTorch** - Neural network framework
- **scikit-learn** - Feature engineering, preprocessing
- **matplotlib/seaborn** - Visualization
- **TA-Lib** - Technical indicators (if needed)
- **Gymnasium** - Reinforcement learning environment (optional)

---

## Success Metrics

### Model Performance
- **Accuracy:** >65% on predicting correct target (FVG vs level)
- **Precision:** >70% on trade signals (reduce false positives)
- **Sharpe Ratio:** >1.5 in backtesting
- **Win Rate:** >55% of trades profitable

### Business Goals
- Automate trading decisions based on levels + gaps
- Reduce emotional trading errors
- Consistent profitability over time
- Scalable to multiple instruments (ES, NQ, etc.)

### Final Performance Visualization
**The ultimate test:** Side-by-side equity curve comparison
- **Strategy P&L** - AI-driven FVG/Level trading system
- **Buy & Hold Baseline** - Simple long position from start to end
- **Visual proof** that the strategy outperforms passive holding
- Charts showing cumulative returns, drawdowns, and win rate over time

---

## Key Questions to Answer with AI

1. **Which target is price heading toward?**
   - Nearest FVG vs nearest psychological level
   - Confidence level for each target

2. **When to enter a trade?**
   - Price enters FVG zone
   - Price bounces off a level
   - Combination of both signals

3. **When to exit a trade?**
   - Gap is filled
   - Level is reached
   - Stop loss hit (risk management)

4. **What is the probability of success?**
   - Based on gap size, age, distance
   - Based on level strength (historical bounces)
   - Based on momentum and volume

---

## Development Roadmap

### Milestone 1: Data Foundation (Week 1-2)
- [x] FVG identification complete
- [ ] Psychological level detection
- [ ] Feature engineering pipeline
- [ ] Labeled dataset creation

### Milestone 2: Model Prototype (Week 3-4)
- [ ] Simple binary classifier (FVG fill prediction)
- [ ] Baseline model evaluation
- [ ] Feature importance analysis
- [ ] Initial backtesting framework

### Milestone 3: Advanced Model (Week 5-6)
- [ ] Multi-class prediction (target selection)
- [ ] Deep neural network architecture
- [ ] Hyperparameter tuning
- [ ] Cross-validation and robustness testing

### Milestone 4: Production Ready (Week 7-8)
- [ ] Real-time prediction pipeline
- [ ] Integration with trading platform
- [ ] Monitoring and alerting
- [ ] Performance dashboard

---

## Research & Learning Resources

### Trading Concepts
- Fair Value Gaps (FVG) / Liquidity Voids
- Institutional Order Flow
- Market Structure (higher highs, higher lows)
- Support/Resistance levels

### AI/ML Techniques
- Time series prediction
- Reinforcement learning for trading
- LSTM/GRU for sequential data
- Feature engineering for financial data

---

## Notes & Observations

### What Makes This Different?
- **Not indicator-based** (no RSI, MACD, etc.)
- **Level-focused** (psychological price points)
- **Gap-focused** (price inefficiencies)
- **Simple and explainable** (not a black box)

### Trading Psychology
- Price doesn't move randomly
- It seeks balance and fills gaps
- Round numbers matter psychologically
- Patterns repeat over time

---

## Contributing & Collaboration

This is a personal trading system development project. As we build this:
- Document all assumptions and observations
- Test every hypothesis with data
- Keep the system simple and explainable
- Iterate based on results

---

## License & Disclaimer

**This is an experimental trading system for educational purposes.**

Trading involves risk. Past performance does not guarantee future results.
This AI model should not be used with real money without extensive testing and validation.

---

## Contact & Questions

For questions about this project or trading methodology:
- Review code in [fvg.py](../fvg.py)
- Check data outputs in [data/fvg_zones.csv](../data/fvg_zones.csv)
- Analyze patterns in historical data

---

**Last Updated:** November 16, 2025
**Version:** 0.1.0 - Foundation Phase
**Status:** Active Development
