# Claude Trader - NinjaTrader Strategy

## Current Status: ✅ WORKING

An automated trading strategy for NinjaTrader 8 that receives trade signals from CSV files and executes limit orders with stop loss and take profit levels.

---

## How It Works

### Signal Flow
```
Python/Agent → trade_signals.csv → ClaudeTrader.cs → NinjaTrader Execution
  (generates)      (CSV file)         (NinjaScript)      (broker orders)
```

### Trade Execution Process

1. **Signal Detection**: ClaudeTrader monitors `trade_signals.csv` every 2 seconds
2. **Limit Order Entry**: Places limit order at specified entry price
3. **Position Management**: Once filled, automatically sets:
   - Stop Loss (as stop market order)
   - Take Profit (as limit order)
4. **Trade Logging**: Logs executed trades to `trades_taken.csv`

---

## CSV File Format

### Input: `trade_signals.csv`
Located at: `C:\Users\Joshua\Documents\Projects\Claude Trader\data\trade_signals.csv`

```csv
DateTime,Direction,Entry_Price,Stop_Loss,Take_Profit
11/25/2025 14:30:00,LONG,6700.00,6690.00,6710.00
11/25/2025 15:45:00,SHORT,6720.00,6730.00,6705.00
```

**Fields:**
- `DateTime`: Signal timestamp
- `Direction`: LONG or SHORT
- `Entry_Price`: Limit order price
- `Stop_Loss`: Stop loss price (absolute price level)
- `Take_Profit`: Take profit price (absolute price level)

### Output: `trades_taken.csv`
Located at: `C:\Users\Joshua\Documents\Projects\Claude Trader\data\trades_taken.csv`

```csv
DateTime,Direction,Entry_Price
11/25/2025 14:32:15,LONG,6700.50
11/25/2025 15:47:22,SHORT,6719.75
```

---

## Features

### Current Working Features ✅
- **CSV Signal Monitoring**: Checks for new signals every 2 seconds
- **Limit Order Entry**: Places limit orders at specified price levels
- **Automatic Stop Loss**: Sets stop market orders at CSV-specified prices
- **Automatic Take Profit**: Sets limit orders at CSV-specified prices
- **Duplicate Prevention**: Tracks processed signals to avoid re-entry
- **Position Tracking**: Won't take new signals while in position
- **Order State Management**: Handles rejected/cancelled orders gracefully
- **Trade Logging**: Records all executed trades with timestamps
- **Detailed Logging**: Comprehensive output for debugging

### Configurable Parameters
- **Contract Quantity**: Number of contracts per trade (default: 2)
- **File Check Interval**: How often to check for signals (default: 2 seconds)
- **File Paths**: Customizable signal and log file locations

---

## Installation

### 1. Copy Strategy to NinjaTrader
```
Copy: src/claudetrader.cs
To: Documents\NinjaTrader 8\bin\Custom\Strategies\
```

### 2. Compile in NinjaTrader
1. Open NinjaTrader 8
2. Tools → Edit NinjaScript → Strategy
3. Find "ClaudeTrader"
4. Click Compile (F5)

### 3. Create Data Directories
```
C:\Users\Joshua\Documents\Projects\Claude Trader\data\
  ├── trade_signals.csv    (input - agent writes here)
  └── trades_taken.csv     (output - strategy writes here)
```

### 4. Initialize Signal File
Create `trade_signals.csv` with header:
```csv
DateTime,Direction,Entry_Price,Stop_Loss,Take_Profit

```

---

## Usage

### 1. Apply Strategy to Chart
1. Open NinjaTrader chart (e.g., NQ 12-25)
2. Strategies → ClaudeTrader
3. Configure parameters:
   - **Contract Quantity**: 2 (or desired size)
   - **Signals File Path**: Verify correct path
   - **File Check Interval**: 2 seconds
4. Click OK

### 2. Send Trade Signals
Add a line to `trade_signals.csv`:
```csv
DateTime,Direction,Entry_Price,Stop_Loss,Take_Profit
11/25/2025 14:30:00,LONG,25100.00,25090.00,25120.00
```

### 3. Strategy Execution
- Strategy detects new signal within 2 seconds
- Places LONG limit order at 25100.00
- Once filled:
  - Stop Loss at 25090.00
  - Take Profit at 25120.00
- Clears signal file (keeps header)
- Logs trade to `trades_taken.csv`

---

## Output Log Example

```
ClaudeTrader Initialized - Monitoring signals every 2 seconds
Signals File: C:\Users\Joshua\Documents\Projects\Claude Trader\data\trade_signals.csv
[SIGNAL] LONG LIMIT @ 25100.00 (2 contracts)
  Target SL: 25090.00 | Target TP: 25120.00
[ORDER UPDATE] CT_Long | State: Submitted | Price: Limit=25100.00, Stop=0 | Qty: 2/0
[ORDER WORKING] CT_Long is now active
[FILLED] LONG 1 contracts @ 25100.00
  Position Size: 1 | Target: 2
[DEBUG] Checking position: Qty=1, Target=2, Match=False
[WAITING] Position partially filled (1/2) - waiting for full fill before placing SL/TP
[FILLED] LONG 1 contracts @ 25100.00
  Position Size: 2 | Target: 2
[DEBUG] Checking position: Qty=2, Target=2, Match=True
[SUBMITTING] Placing SL and TP orders now...
[LONG EXIT] Submitting SL @ 25090.00 and TP @ 25120.00 for 2 contracts
[ORDERS SUBMITTED] Long exit orders sent to broker
[ORDER UPDATE] SL | State: Working | Price: Limit=0, Stop=25090.00 | Qty: 2/0
[ORDER UPDATE] TP | State: Working | Price: Limit=25120.00, Stop=0 | Qty: 2/0
Trade logged to file: LONG @ 25100.00
[EXIT TP] 2 contracts @ 25120.00 | P/L: $40.00
```

---

## Configuration

### Strategy Parameters (NinjaTrader UI)

| Parameter | Default | Description |
|-----------|---------|-------------|
| Signals File Path | `C:\Users\Joshua\Documents\Projects\Claude Trader\data\trade_signals.csv` | Input signal file |
| Trades Log File Path | `C:\Users\Joshua\Documents\Projects\Claude Trader\data\trades_taken.csv` | Trade log output |
| File Check Interval | 2 seconds | How often to check for signals |
| Contract Quantity | 2 | Number of contracts per trade |

### Built-in Settings (in code)
- **Calculate**: OnEachTick (real-time monitoring)
- **Order Fill Resolution**: Standard
- **Stop Target Handling**: PerEntryExecution
- **Entry Handling**: AllEntries
- **Entries Per Direction**: 1

---

## Project Structure

```
Claude Trader/
├── src/
│   └── claudetrader.cs          # NinjaScript strategy
├── data/
│   ├── trade_signals.csv        # Input: trade signals
│   └── trades_taken.csv         # Output: executed trades
├── README.md                    # This file
└── QUICKSTART.md               # Agent setup guide
```

---

## Safety Features

### Duplicate Prevention
- Tracks processed signals by unique ID (DateTime + Direction)
- Won't process same signal twice
- Clears signal file after processing

### Position Management
- Only one position at a time
- Won't accept new signals while in position
- Won't accept new signals while limit order pending

### Order Error Handling
- Detects rejected orders
- Detects cancelled orders
- Resets state on order failures
- Detailed error logging

### Risk Management
- Stop loss submitted FIRST (highest priority)
- Take profit submitted after stop loss
- Uses actual position quantity for exit orders
- Waits for full position fill before placing exits

---

## Troubleshooting

### Signal Not Detected
- Check file path is correct
- Verify CSV format matches exactly
- Ensure file has been modified (timestamp check)
- Look for "ERROR reading signals file" in output

### Orders Not Placed
- Check output for "[ORDERS SUBMITTED]" message
- Look for "[ORDER UPDATE]" messages
- Check for "[ERROR] Order rejected" messages
- Verify SL/TP prices are valid for direction:
  - LONG: SL < Entry < TP
  - SHORT: TP < Entry < SL

### Partial Fills
- Strategy waits for full position before placing SL/TP
- Look for "[WAITING] Position partially filled" message
- SL/TP placed only when `Position.Quantity == ContractQuantity`

### File Permission Errors
- Ensure data directory exists
- Check Windows file permissions
- Close CSV files in Excel before strategy runs

---

## Things To Do

### 1. Live Market Context Persistence - Market Ideas File
**Problem**: Agent makes fresh assessments on every bar without maintaining market context. It forgets what it just analyzed (goldfish memory).

**What's Needed**:
Save a file with **what the agent currently sees in the market** - its live market assessment of long and short trade ideas.

**Implementation**:
- Create `data/market_ideas.json` file that stores:
  - **Current LONG trade ideas** the agent sees right now
  - **Current SHORT trade ideas** the agent sees right now
  - Key support/resistance levels identified
  - Market bias (bullish/bearish/neutral)
  - Recent confluence zones

**Workflow on Each New Bar**:
1. **Load** existing `market_ideas.json`
2. **Send to agent**: "Here's what you saw last bar: [market_ideas]. New bar just closed: [OHLC data]. Update your assessment."
3. **Agent updates/refines** existing ideas instead of starting from scratch
4. **Save** updated market_ideas.json back to file

**Key Point**: Instead of making new assessments every time, we give the agent a good starting point - what it already knows about the market.

**Benefits**:
- Agent maintains continuity across bars
- Faster analysis (updates existing ideas vs. full analysis)
- More consistent trade ideas
- Tracks evolving market structure
- Reduces API calls

---

### 2. Patience in Entry Execution - "It's Okay to Wait and See"
**Problem**: Current system enters immediately when price is near a zone, even when the chart is screaming the opposite direction.

**Example Scenario**:
```
Price near long zone above
BUT chart is screaming SHORT
❌ Current: Takes long entry anyway
✅ Desired: WAIT and see what develops
```

**Philosophy**:
**It's okay to wait and see.** If price is near a zone but the chart structure/momentum disagrees, don't force the trade. Wait for alignment.

**Implementation Ideas**:
- Add "signal_status" field to trade_signals.csv:
  - `WATCHING`: Zone identified but waiting for confirmation
  - `READY`: All conditions aligned, safe to enter
  - `ACTIVE`: Order placed/filled

- Agent workflow:
  1. Identifies potential zone/setup → Status: `WATCHING`
  2. Monitors price action and momentum
  3. **Only** when everything aligns → Status: `READY`
  4. ClaudeTrader.cs **only acts on `READY` signals**

**Wait For**:
- Price action confirmation (rejection wicks, engulfing candles, etc.)
- Momentum alignment (not fighting the trend)
- Structure agreement (higher highs for longs, lower lows for shorts)
- No conflicting signals

**Benefits**:
- Better entry timing
- Fewer false signals
- Trade WITH the flow, not against it
- Higher win rate through patience
- Avoid "forcing" trades that don't set up properly

### 3. Future Enhancements
- [ ] Multi-timeframe context integration
- [ ] Dynamic position sizing based on setup quality
- [ ] Partial exit capabilities (scale out)
- [ ] Time-based filters (avoid news events)
- [ ] Session-based trading rules
- [ ] Advanced order types (trailing stops)
- [ ] Performance analytics dashboard
- [ ] Integration with backtesting framework

---

## Development Notes

### Version History
- **v1.0** - Initial market order implementation
- **v1.1** - Changed to limit orders with CSV-based SL/TP
- **v1.2** - Added partial fill handling
- **v1.3** - Enhanced logging and error handling (current)

### Known Issues
- None currently

### Testing Recommendations
1. Test with 1 contract first
2. Verify SL/TP prices are correct for direction
3. Monitor output window for detailed logs
4. Check both CSV files after each trade
5. Use Strategy Analyzer for backtesting

---

## Support & Documentation

- **Strategy Code**: [src/claudetrader.cs](src/claudetrader.cs)
- **Agent Setup**: [QUICKSTART.md](QUICKSTART.md)
- **NinjaTrader Docs**: https://ninjatrader.com/support/helpGuides/nt8/

---

## License

Proprietary - For personal trading use only.

---

**Last Updated**: November 25, 2025
**Status**: Production Ready ✅
**Tested On**: NinjaTrader 8, NQ Futures
