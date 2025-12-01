#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using System.IO;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

//This namespace holds Strategies in this folder and is required. Do not change it.
namespace NinjaTrader.NinjaScript.Strategies
{
	public class ClaudeTrader : Strategy
	{
		#region Variables

		// Signal file monitoring
		private string signalsFilePath = @"C:\Users\Joshua\Documents\Projects\Claude Trader\data\trade_signals.csv";
		private string tradesLogFilePath = @"C:\Users\Joshua\Documents\Projects\Claude Trader\data\trades_taken.csv";
		private DateTime lastFileCheckTime = DateTime.MinValue;
		private HashSet<string> processedSignals = new HashSet<string>();
		private DateTime lastFileModified = DateTime.MinValue;

		// Current signal being processed
		private string currentSignalId = "";
		private double signalEntryPrice = 0;
		private double signalStopLoss = 0;
		private double signalTakeProfit = 0;
		private string signalDirection = "";
		private DateTime signalDateTime = DateTime.MinValue;

		// Position tracking
		private bool inPosition = false;
		private bool hasLimitOrder = false;
		private DateTime entryTime = DateTime.MinValue;
		private double actualEntryPrice = 0;

		// File check interval (seconds)
		private int fileCheckInterval = 2;

		// Position sizing
		private int contractQuantity = 12;  // Total contracts to trade

		#endregion

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description = @"ClaudeTrader - Receives signals from trade_signals.csv";
				Name = "ClaudeTrader";
				Calculate = Calculate.OnEachTick;
				EntriesPerDirection = 1;
				EntryHandling = EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy = true;
				ExitOnSessionCloseSeconds = 30;
				IsFillLimitOnTouch = false;
				MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution = OrderFillResolution.Standard;
				Slippage = 0;
				StartBehavior = StartBehavior.WaitUntilFlat;
				TimeInForce = TimeInForce.Gtc;
				TraceOrders = false;
				RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling = StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade = 1;
				IsInstantiatedOnEachOptimizationIteration = true;

				// Parameters
				SignalsFilePath = @"C:\Users\Joshua\Documents\Projects\Claude Trader\data\trade_signals.csv";
				TradesLogFilePath = @"C:\Users\Joshua\Documents\Projects\Claude Trader\data\trades_taken.csv";
				FileCheckInterval = 2;
				ContractQuantity = 2;
			}
			else if (State == State.Configure)
			{
				// Nothing to configure
			}
			else if (State == State.DataLoaded)
			{
				// FORCE CORRECT FILE PATHS (override any cached config)
				signalsFilePath = @"C:\Users\Joshua\Documents\Projects\Claude Trader\data\trade_signals.csv";
				tradesLogFilePath = @"C:\Users\Joshua\Documents\Projects\Claude Trader\data\trades_taken.csv";

				// Initialize processed signals tracking
				processedSignals = new HashSet<string>();

				// Force immediate file check by setting lastFileCheckTime to far past
				lastFileCheckTime = DateTime.MinValue;

				Print($"ClaudeTrader Initialized - Monitoring signals every {FileCheckInterval} seconds");
				Print($"Signals File: {signalsFilePath}");
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBar < BarsRequiredToTrade)
				return;

			// Check for new signals periodically
			if ((DateTime.Now - lastFileCheckTime).TotalSeconds >= FileCheckInterval)
			{
				CheckForNewSignals();
				lastFileCheckTime = DateTime.Now;
			}

			// Manage existing position
			ManagePosition();
		}

		private void CheckForNewSignals()
		{
			if (!File.Exists(signalsFilePath))
			{
				Print($"Signal file not found: {signalsFilePath}");
				return;
			}

			try
			{
				// Check if file has been modified
				DateTime currentModTime = File.GetLastWriteTime(signalsFilePath);

				if (currentModTime <= lastFileModified)
					return; // File hasn't changed

				lastFileModified = currentModTime;

				// Read all lines from the CSV file
				string[] lines = File.ReadAllLines(signalsFilePath);

				// Skip header row
				if (lines.Length <= 1)
					return;

				// Process the last (most recent) signal
				string lastLine = lines[lines.Length - 1];

				// Skip empty lines
				if (string.IsNullOrWhiteSpace(lastLine))
					return;

				ProcessSignalLine(lastLine);

				// Clear the signal file after processing (keep only header)
				ClearSignalsFile();
			}
			catch (Exception ex)
			{
				Print($"ERROR reading signals file: {ex.Message}");
			}
		}

		private void ClearSignalsFile()
		{
			try
			{
				// Rewrite file with only header row
				using (StreamWriter sw = new StreamWriter(signalsFilePath, false))
				{
					sw.WriteLine("DateTime,Direction,Entry_Price,Stop_Loss,Take_Profit");
				}
			}
			catch (Exception ex)
			{
				Print($"ERROR clearing signals file: {ex.Message}");
			}
		}

		private void ProcessSignalLine(string line)
		{
			try
			{
				// Parse CSV line: DateTime,Direction,Entry_Price,Stop_Loss,Take_Profit
				string[] parts = line.Split(',');

				if (parts.Length < 5)
				{
					Print($"ERROR: Invalid signal format (expected 5 fields, got {parts.Length})");
					Print($"Expected: DateTime,Direction,Entry_Price,Stop_Loss,Take_Profit");
					return;
				}

				// Create unique signal ID based on datetime and direction
				string signalId = $"{parts[0]}_{parts[1]}";

				// Skip if already processed
				if (processedSignals.Contains(signalId))
				{
					Print($"Signal already processed: {signalId}");
					return;
				}

				// Skip if already in position or has pending limit order
				if (Position.MarketPosition != MarketPosition.Flat || hasLimitOrder)
				{
					Print($"Already in position or has pending order, skipping signal: {signalId}");
					return;
				}

				// Parse signal data
				DateTime.TryParse(parts[0].Trim(), out signalDateTime);
				signalDirection = parts[1].Trim();  // LONG or SHORT
				double.TryParse(parts[2].Trim(), out signalEntryPrice);
				double.TryParse(parts[3].Trim(), out signalStopLoss);
				double.TryParse(parts[4].Trim(), out signalTakeProfit);

				// Store signal information
				currentSignalId = signalId;

				// Execute trade based on direction
				if (signalDirection.ToUpper() == "LONG")
				{
					ExecuteLongEntry();
				}
				else if (signalDirection.ToUpper() == "SHORT")
				{
					ExecuteShortEntry();
				}
				else
				{
					Print($"ERROR: Unknown direction '{signalDirection}' in signal");
					return;
				}

				// Mark signal as processed
				processedSignals.Add(signalId);
			}
			catch (Exception ex)
			{
				Print($"ERROR processing signal: {ex.Message}");
			}
		}

		private void ExecuteLongEntry()
		{
			// Place MARKET order for immediate entry
			EnterLong(0, contractQuantity, "CT_Long");
			hasLimitOrder = false;  // Using market order, not limit
			Print($"[SIGNAL] LONG MARKET ORDER ({contractQuantity} contracts)");
			Print($"  Reference Entry: {signalEntryPrice:F2}");
			Print($"  Target SL: {signalStopLoss:F2} | Target TP: {signalTakeProfit:F2}");
		}

		private void ExecuteShortEntry()
		{
			// Place MARKET order for immediate entry
			EnterShort(0, contractQuantity, "CT_Short");
			hasLimitOrder = false;  // Using market order, not limit
			Print($"[SIGNAL] SHORT MARKET ORDER ({contractQuantity} contracts)");
			Print($"  Reference Entry: {signalEntryPrice:F2}");
			Print($"  Target SL: {signalStopLoss:F2} | Target TP: {signalTakeProfit:F2}");
		}

		private void ManagePosition()
		{
			if (Position.MarketPosition == MarketPosition.Flat && inPosition)
			{
				inPosition = false;
				hasLimitOrder = false;
				currentSignalId = "";
			}
		}

		protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
		{
			if (execution.Order != null && execution.Order.OrderState == OrderState.Filled)
			{
				// Check if this is an entry order
				if (execution.Order.Name == "CT_Long" || execution.Order.Name == "CT_Short")
				{
					actualEntryPrice = execution.Price;
					entryTime = execution.Time;
					inPosition = true;
					hasLimitOrder = false;

					Print($"[FILLED] {signalDirection} {quantity} contracts @ {actualEntryPrice:F2}");
					Print($"  Position Size: {Position.Quantity} | Target: {contractQuantity}");

					// Only set SL/TP when position is fully filled
					Print($"[DEBUG] Checking position: Qty={Position.Quantity}, Target={contractQuantity}, Match={Position.Quantity == contractQuantity}");

					if (Position.Quantity == contractQuantity)
					{
						Print($"[SUBMITTING] Placing SL and TP orders now...");

						// Set profit targets and stop loss based on CSV signal prices
						if (Position.MarketPosition == MarketPosition.Long)
						{
							Print($"[LONG EXIT] Submitting SL @ {signalStopLoss:F2} and TP @ {signalTakeProfit:F2} for {Position.Quantity} contracts");

							// Submit stop loss FIRST as a stop market order (highest priority)
							ExitLongStopMarket(0, true, Position.Quantity, signalStopLoss, "SL", "CT_Long");
							// Then place limit order for profit target
							ExitLongLimit(0, true, Position.Quantity, signalTakeProfit, "TP", "CT_Long");

							Print($"[ORDERS SUBMITTED] Long exit orders sent to broker");
						}
						else if (Position.MarketPosition == MarketPosition.Short)
						{
							Print($"[SHORT EXIT] Submitting SL @ {signalStopLoss:F2} and TP @ {signalTakeProfit:F2} for {Position.Quantity} contracts");

							// Submit stop loss FIRST as a stop market order (highest priority)
							ExitShortStopMarket(0, true, Position.Quantity, signalStopLoss, "SL", "CT_Short");
							// Then place limit order for profit target
							ExitShortLimit(0, true, Position.Quantity, signalTakeProfit, "TP", "CT_Short");

							Print($"[ORDERS SUBMITTED] Short exit orders sent to broker");
						}

						// Log trade to CSV
						LogTradeToFile(signalDirection, actualEntryPrice);
					}
					else
					{
						Print($"[WAITING] Position partially filled ({Position.Quantity}/{contractQuantity}) - waiting for full fill before placing SL/TP");
					}
				}

				// Check if this is an exit order (TP or SL)
				else if (execution.Order.Name == "TP" || execution.Order.Name == "SL")
				{
					double exitPrice = execution.Price;
					double pnl = 0;

					if (execution.Order.Name == "TP")
					{
						if (signalDirection.ToUpper() == "LONG")
							pnl = (exitPrice - actualEntryPrice) * quantity;
						else
							pnl = (actualEntryPrice - exitPrice) * quantity;

						Print($"[EXIT TP] {quantity} contracts @ {exitPrice:F2} | P/L: ${pnl:F2}");
					}
					else if (execution.Order.Name == "SL")
					{
						if (signalDirection.ToUpper() == "LONG")
							pnl = (exitPrice - actualEntryPrice) * quantity;
						else
							pnl = (actualEntryPrice - exitPrice) * quantity;

						Print($"[EXIT SL] STOP LOSS @ {exitPrice:F2} | {quantity} contracts | P/L: ${pnl:F2}");
					}
				}
			}
		}

		protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity, int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string comment)
		{
			// Log all order state changes for debugging
			Print($"[ORDER UPDATE] {order.Name} | State: {orderState} | Price: Limit={limitPrice}, Stop={stopPrice} | Qty: {quantity}/{filled}");

			if (orderState == OrderState.Rejected)
			{
				Print($"[ERROR] Order rejected: {order.Name} - {comment} | Error: {error}");

				// If entry limit order was rejected or cancelled, reset flag
				if (order.Name == "CT_Long" || order.Name == "CT_Short")
				{
					hasLimitOrder = false;
				}
			}
			else if (orderState == OrderState.Cancelled)
			{
				// If entry limit order was cancelled, reset flag
				if (order.Name == "CT_Long" || order.Name == "CT_Short")
				{
					hasLimitOrder = false;
					Print($"[INFO] Entry limit order cancelled: {order.Name}");
				}
			}
			else if (orderState == OrderState.Working)
			{
				Print($"[ORDER WORKING] {order.Name} is now active");
			}
		}

		protected override void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition)
		{
			if (marketPosition == MarketPosition.Flat)
			{
				inPosition = false;
				hasLimitOrder = false;
			}
		}

		private void LogTradeToFile(string direction, double entryPrice)
		{
			try
			{
				bool fileExists = File.Exists(tradesLogFilePath);

				using (StreamWriter sw = new StreamWriter(tradesLogFilePath, true))
				{
					// Write header if file doesn't exist
					if (!fileExists)
					{
						sw.WriteLine("DateTime,Direction,Entry_Price");
					}

					// Write trade data
					string timestamp = DateTime.Now.ToString("MM/dd/yyyy HH:mm:ss");
					sw.WriteLine($"{timestamp},{direction},{entryPrice:F2}");
				}

				Print($"Trade logged to file: {direction} @ {entryPrice:F2}");
			}
			catch (Exception ex)
			{
				Print($"ERROR logging trade to file: {ex.Message}");
			}
		}

		#region Properties

		[NinjaScriptProperty]
		[Display(Name="Signals File Path", Description="Path to trade_signals.csv file", Order=1, GroupName="ClaudeTrader Parameters")]
		public string SignalsFilePath
		{
			get { return signalsFilePath; }
			set { signalsFilePath = value; }
		}

		[NinjaScriptProperty]
		[Display(Name="Trades Log File Path", Description="Path to trades_taken.csv file", Order=2, GroupName="ClaudeTrader Parameters")]
		public string TradesLogFilePath
		{
			get { return tradesLogFilePath; }
			set { tradesLogFilePath = value; }
		}

		[NinjaScriptProperty]
		[Range(1, 60)]
		[Display(Name="File Check Interval", Description="Interval in seconds to check for new signals", Order=3, GroupName="ClaudeTrader Parameters")]
		public int FileCheckInterval
		{
			get { return fileCheckInterval; }
			set { fileCheckInterval = value; }
		}

		[NinjaScriptProperty]
		[Range(1, 100)]
		[Display(Name="Contract Quantity", Description="Number of contracts to trade", Order=4, GroupName="ClaudeTrader Parameters")]
		public int ContractQuantity
		{
			get { return contractQuantity; }
			set { contractQuantity = Math.Max(1, value); }
		}

		#endregion
	}
}
