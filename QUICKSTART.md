# Claude NQ Trading Agent - Quick Start

## Setup (5 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API key
# ANTHROPIC_API_KEY=your_key_here
```

### 3. Verify Data Files
Ensure these files exist:
- `data/HistoricalData.csv` - Historical OHLC data ✓
- `data/LiveFeed.csv` - Real-time price feed ✓
- `data/trade_signals.csv` - Trade output (auto-created)

---

## Usage

### Backtest (Recommended First)
Test strategy on historical data:
```bash
# Test last 30 days
python main.py --mode backtest --days 30

# Test last 100 days
python main.py --mode backtest --days 100

# Results saved to data/backtest_results.json
```

### Monitor Performance
View current performance and signals:
```bash
python main.py --mode monitor
```

### Live Trading
**⚠️ Only after successful backtest validation:**
```bash
# Ensure FairValueGaps.py is running in another terminal
python python fvg_bot.py

# Then start trading agent
python main.py --mode live
```

---

## Configuration

Edit `config/agent_config.json` to adjust:
- **Stop loss range**: 15-50 points (default: 20)
- **Min risk/reward**: Default 3:1
- **Confidence threshold**: Default 65%
- **Daily trade limits**: Default 5 trades/day
- **Max daily loss**: Default 100 points

---

## Important Notes

### Stop Loss Sizing
✅ Default: **20 points** (NQ appropriate)
- Minimum: 15 points (volatility floor)
- Maximum: 50 points (risk control)
- **Your feedback noted**: 8 points is too small ✓

### Risk Management
System enforces:
- Maximum 5 trades per day
- Maximum 100 point daily loss
- No trading after 3 consecutive losses
- Mandatory stops on every trade

### Trade Flow
```
FairValueGaps.py → Claude Analysis → trade_signals.csv → NinjaTrader
  (detects gaps)    (makes decision)      (CSV output)     (execution)
```

---

## Testing Without API Key

Run backtest with simple logic (no Claude):
```bash
# Unset API key temporarily
unset ANTHROPIC_API_KEY

# Run backtest - uses confluence detection only
python main.py --mode backtest --days 30
```

---

## File Structure

```
Claude Trader/
├── main.py                    # ← Start here
├── FairValueGaps.py           # Existing FVG detector (keep running)
├── src/                       # Trading agent modules
├── config/                    # Configuration files
├── data/
│   ├── HistoricalData.csv     # Your historical data
│   ├── LiveFeed.csv           # Your live feed
│   ├── trade_signals.csv      # Output to NinjaTrader
│   └── trade_history.json     # Performance tracking
├── docs/
│   ├── AGENT_README.md        # Full documentation
│   └── ARCHITECTURE.md        # System design
└── logs/                      # System logs (auto-created)
```

---

## Troubleshooting

### "No API key found"
Add to `.env` file:
```
ANTHROPIC_API_KEY=your_key_here
```

### "Cannot import module"
Install dependencies:
```bash
pip install -r requirements.txt
```

### "File not found: HistoricalData.csv"
Check that data files are in the `data/` directory

### "Trading blocked: Daily limit reached"
Risk management kicked in. Reset happens automatically at midnight or edit config.

---

## Next Steps

1. ✅ Run backtest on 30 days
2. ✅ Review results in `data/backtest_results.json`
3. ✅ Adjust stop loss if needed (config/agent_config.json)
4. ✅ Run monitor mode to see current state
5. ✅ Start FairValueGaps.py in one terminal
6. ✅ Start live trading in another terminal
7. ✅ Watch trade_signals.csv for signals
8. ✅ NinjaTrader executes trades

---

## Performance Tracking

System automatically tracks:
- Win rate by setup type (confluence vs FVG-only)
- Average risk/reward achieved
- Trade history with reasoning
- Performance metrics

View anytime:
```bash
python main.py --mode monitor
```

---

## Support

- **Full docs**: See `docs/AGENT_README.md`
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Trading philosophy**: See `docs/PRICE_ACTION_PHILOSOPHY.md`
- **Logs**: Check `logs/trading_agent.log`

---

**🚀 You're ready to trade with Claude!**

Remember: Start with backtesting, validate performance, then go live.
