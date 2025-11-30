#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
	/// <summary>
	/// ClaudeTrader - Enterprise-grade signal execution for Claude Trading System
	/// Monitors CSV signals and executes trades with proper risk management
	/// </summary>
	public class ClaudeTrader : Strategy
	{
		#region Variables

		// File paths (configurable via properties)
		private string signalsFilePath;
		private string tradesLogFilePath;

		// File monitoring
		private DateTime lastFileCheckTime = DateTime.MinValue;
		private HashSet<string> processedSignals = new HashSet<string>();
		private DateTime lastFileModified = DateTime.MinValue;

		// Current signal state
		private string currentSignalId = "";
		private double signalEntryPrice = 0;
		private double signalStopLoss = 0;
		private double signalTarget = 0;
		private string signalDirection = "";
		private DateTime signalDateTime = DateTime.MinValue;

		// Position tracking
		private bool inPosition = false;
		private bool hasLimitOrder = false;
		private DateTime entryTime = DateTime.MinValue;
		private double actualEntryPrice = 0;

		// Configuration
		private int fileCheckInterval = 2;
		private int contractQuantity = 1;

		// Statistics
		private int dailyTrades = 0;
		private double dailyPnL = 0;
		private int consecutiveLosses = 0;
		private DateTime lastTradeDate = DateTime.MinValue;

		#endregion

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description = @"ClaudeTrader Enterprise - Signal execution from Claude Trading System";
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
				TraceOrders = true;
				RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling = StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade = 1;
				IsInstantiatedOnEachOptimizationIteration = true;

				// Default file paths - MUST BE CONFIGURED BY USER
				SignalsFilePath = "";
				TradesLogFilePath = "";
				FileCheckInterval = 2;
				ContractQuantity = 1;

				// Risk limits
				MaxDailyTrades = 5;
				MaxDailyLoss = 100;
				MaxConsecutiveLosses = 3;
			}
			else if (State == State.Configure)
			{
				// Validate file paths
				if (string.IsNullOrEmpty(SignalsFilePath))
				{
					Print("ERROR: SignalsFilePath must be configured!");
					Print("Set the path to your trade_signals.csv file in the strategy properties.");
				}
			}
			else if (State == State.DataLoaded)
			{
				// Initialize
				processedSignals = new HashSet<string>();
				lastFileCheckTime = DateTime.MinValue;

				// Reset daily counters if new day
				if (lastTradeDate.Date != DateTime.Now.Date)
				{
					dailyTrades = 0;
					dailyPnL = 0;
					// Don't reset consecutive losses - they carry over
					lastTradeDate = DateTime.Now;
				}

				Print($"ClaudeTrader Initialized");
				Print($"  Signals File: {SignalsFilePath}");
				Print($"  Trades Log: {TradesLogFilePath}");
				Print($"  Check Interval: {FileCheckInterval}s");
				Print($"  Contract Quantity: {ContractQuantity}");
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBar < BarsRequiredToTrade)
				return;

			// Validate configuration
			if (string.IsNullOrEmpty(SignalsFilePath))
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

		private bool CheckRiskLimits()
		{
			// Check daily trade limit
			if (dailyTrades >= MaxDailyTrades)
			{
				Print($"Daily trade limit reached ({MaxDailyTrades})");
				return false;
			}

			// Check daily loss limit
			if (dailyPnL <= -MaxDailyLoss)
			{
				Print($"Daily loss limit reached ({MaxDailyLoss} points)");
				return false;
			}

			// Check consecutive losses
			if (consecutiveLosses >= MaxConsecutiveLosses)
			{
				Print($"Consecutive loss limit reached ({MaxConsecutiveLosses})");
				return false;
			}

			return true;
		}

		private void CheckForNewSignals()
		{
			if (!File.Exists(SignalsFilePath))
			{
				return; // File doesn't exist yet - this is OK during startup
			}

			try
			{
				// Check if file has been modified
				DateTime currentModTime = File.GetLastWriteTime(SignalsFilePath);

				if (currentModTime <= lastFileModified)
					return;

				lastFileModified = currentModTime;

				// Read file with retry for locked files
				string[] lines = null;
				int retries = 3;

				while (retries > 0)
				{
					try
					{
						lines = File.ReadAllLines(SignalsFilePath);
						break;
					}
					catch (IOException)
					{
						retries--;
						if (retries > 0)
							System.Threading.Thread.Sleep(100);
					}
				}

				if (lines == null || lines.Length <= 1)
					return;

				// Process the last (most recent) signal
				string lastLine = lines[lines.Length - 1];

				if (string.IsNullOrWhiteSpace(lastLine))
					return;

				ProcessSignalLine(lastLine);

				// Clear the signal file after processing
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
				int retries = 3;
				while (retries > 0)
				{
					try
					{
						// Use consistent header with Python: DateTime,Direction,Entry_Price,Stop_Loss,Target
						using (StreamWriter sw = new StreamWriter(SignalsFilePath, false))
						{
							sw.WriteLine("DateTime,Direction,Entry_Price,Stop_Loss,Target");
						}
						break;
					}
					catch (IOException)
					{
						retries--;
						if (retries > 0)
							System.Threading.Thread.Sleep(100);
					}
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
				// Parse CSV line: DateTime,Direction,Entry_Price,Stop_Loss,Target
				string[] parts = line.Split(',');

				if (parts.Length < 5)
				{
					Print($"ERROR: Invalid signal format (expected 5 fields, got {parts.Length})");
					Print($"Expected: DateTime,Direction,Entry_Price,Stop_Loss,Target");
					return;
				}

				// Create unique signal ID
				string signalId = $"{parts[0].Trim()}_{parts[1].Trim()}";

				// Skip if already processed
				if (processedSignals.Contains(signalId))
				{
					Print($"Signal already processed: {signalId}");
					return;
				}

				// Check risk limits
				if (!CheckRiskLimits())
				{
					Print($"Signal rejected due to risk limits: {signalId}");
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
				signalDirection = parts[1].Trim().ToUpper();
				double.TryParse(parts[2].Trim(), out signalEntryPrice);
				double.TryParse(parts[3].Trim(), out signalStopLoss);
				double.TryParse(parts[4].Trim(), out signalTarget);

				// Validate signal
				if (!ValidateSignal())
				{
					Print($"Signal validation failed: {signalId}");
					return;
				}

				currentSignalId = signalId;

				// Execute trade
				if (signalDirection == "LONG")
				{
					ExecuteLongEntry();
				}
				else if (signalDirection == "SHORT")
				{
					ExecuteShortEntry();
				}
				else
				{
					Print($"ERROR: Unknown direction '{signalDirection}'");
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

		private bool ValidateSignal()
		{
			// Validate stop loss direction
			if (signalDirection == "LONG")
			{
				if (signalStopLoss >= signalEntryPrice)
				{
					Print($"Invalid LONG signal: stop ({signalStopLoss}) must be below entry ({signalEntryPrice})");
					return false;
				}
				if (signalTarget <= signalEntryPrice)
				{
					Print($"Invalid LONG signal: target ({signalTarget}) must be above entry ({signalEntryPrice})");
					return false;
				}
			}
			else if (signalDirection == "SHORT")
			{
				if (signalStopLoss <= signalEntryPrice)
				{
					Print($"Invalid SHORT signal: stop ({signalStopLoss}) must be above entry ({signalEntryPrice})");
					return false;
				}
				if (signalTarget >= signalEntryPrice)
				{
					Print($"Invalid SHORT signal: target ({signalTarget}) must be below entry ({signalEntryPrice})");
					return false;
				}
			}

			// Validate stop distance
			double stopDistance = Math.Abs(signalEntryPrice - signalStopLoss);
			if (stopDistance < 15 || stopDistance > 50)
			{
				Print($"Invalid stop distance: {stopDistance} points (must be 15-50)");
				return false;
			}

			// Validate risk/reward
			double targetDistance = Math.Abs(signalTarget - signalEntryPrice);
			double riskReward = targetDistance / stopDistance;
			if (riskReward < 3.0)
			{
				Print($"Invalid R/R: {riskReward:F2} (minimum 3.0)");
				return false;
			}

			return true;
		}

		private void ExecuteLongEntry()
		{
			EnterLongLimit(0, true, ContractQuantity, signalEntryPrice, "CT_Long");
			hasLimitOrder = true;
			Print($"[SIGNAL] LONG LIMIT @ {signalEntryPrice:F2} ({ContractQuantity} contracts)");
			Print($"  Stop: {signalStopLoss:F2} | Target: {signalTarget:F2}");
			Print($"  R/R: {Math.Abs(signalTarget - signalEntryPrice) / Math.Abs(signalEntryPrice - signalStopLoss):F2}:1");
		}

		private void ExecuteShortEntry()
		{
			EnterShortLimit(0, true, ContractQuantity, signalEntryPrice, "CT_Short");
			hasLimitOrder = true;
			Print($"[SIGNAL] SHORT LIMIT @ {signalEntryPrice:F2} ({ContractQuantity} contracts)");
			Print($"  Stop: {signalStopLoss:F2} | Target: {signalTarget:F2}");
			Print($"  R/R: {Math.Abs(signalEntryPrice - signalTarget) / Math.Abs(signalStopLoss - signalEntryPrice):F2}:1");
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
				// Entry order filled
				if (execution.Order.Name == "CT_Long" || execution.Order.Name == "CT_Short")
				{
					actualEntryPrice = execution.Price;
					entryTime = execution.Time;
					inPosition = true;
					hasLimitOrder = false;
					dailyTrades++;

					Print($"[FILLED] {signalDirection} {quantity} contracts @ {actualEntryPrice:F2}");
					Print($"  Daily trades: {dailyTrades}/{MaxDailyTrades}");

					// Set stop loss and take profit when fully filled
					if (Position.Quantity == ContractQuantity)
					{
						Print($"[PLACING EXITS] SL @ {signalStopLoss:F2} | TP @ {signalTarget:F2}");

						if (Position.MarketPosition == MarketPosition.Long)
						{
							ExitLongStopMarket(0, true, Position.Quantity, signalStopLoss, "SL", "CT_Long");
							ExitLongLimit(0, true, Position.Quantity, signalTarget, "TP", "CT_Long");
						}
						else if (Position.MarketPosition == MarketPosition.Short)
						{
							ExitShortStopMarket(0, true, Position.Quantity, signalStopLoss, "SL", "CT_Short");
							ExitShortLimit(0, true, Position.Quantity, signalTarget, "TP", "CT_Short");
						}

						// Log trade entry
						LogTradeToFile(signalDirection, actualEntryPrice, "ENTRY");
					}
				}
				// Exit order filled
				else if (execution.Order.Name == "TP" || execution.Order.Name == "SL")
				{
					double exitPrice = execution.Price;
					double pnl = 0;

					if (signalDirection == "LONG")
						pnl = (exitPrice - actualEntryPrice) * quantity;
					else
						pnl = (actualEntryPrice - exitPrice) * quantity;

					dailyPnL += pnl;

					string result = execution.Order.Name == "TP" ? "WIN" : "LOSS";

					if (result == "WIN")
					{
						consecutiveLosses = 0;
						Print($"[EXIT TP] WIN @ {exitPrice:F2} | P/L: {pnl:+F2} points");
					}
					else
					{
						consecutiveLosses++;
						Print($"[EXIT SL] LOSS @ {exitPrice:F2} | P/L: {pnl:+F2} points");
						Print($"  Consecutive losses: {consecutiveLosses}/{MaxConsecutiveLosses}");
					}

					Print($"  Daily P/L: {dailyPnL:+F2} points");

					// Log trade exit
					LogTradeToFile(signalDirection, exitPrice, result);
				}
			}
		}

		protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity, int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string comment)
		{
			if (orderState == OrderState.Rejected)
			{
				Print($"[REJECTED] {order.Name} - {comment} | Error: {error}");

				if (order.Name == "CT_Long" || order.Name == "CT_Short")
				{
					hasLimitOrder = false;
				}
			}
			else if (orderState == OrderState.Cancelled)
			{
				if (order.Name == "CT_Long" || order.Name == "CT_Short")
				{
					hasLimitOrder = false;
					Print($"[CANCELLED] Entry order: {order.Name}");
				}
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

		private void LogTradeToFile(string direction, double price, string action)
		{
			if (string.IsNullOrEmpty(TradesLogFilePath))
				return;

			try
			{
				bool fileExists = File.Exists(TradesLogFilePath);

				using (StreamWriter sw = new StreamWriter(TradesLogFilePath, true))
				{
					if (!fileExists)
					{
						sw.WriteLine("DateTime,Direction,Price,Action,DailyPnL,ConsecutiveLosses");
					}

					string timestamp = DateTime.Now.ToString("MM/dd/yyyy HH:mm:ss");
					sw.WriteLine($"{timestamp},{direction},{price:F2},{action},{dailyPnL:F2},{consecutiveLosses}");
				}
			}
			catch (Exception ex)
			{
				Print($"ERROR logging trade: {ex.Message}");
			}
		}

		#region Properties

		[NinjaScriptProperty]
		[Display(Name="Signals File Path", Description="Full path to trade_signals.csv", Order=1, GroupName="File Paths")]
		public string SignalsFilePath
		{
			get { return signalsFilePath; }
			set { signalsFilePath = value; }
		}

		[NinjaScriptProperty]
		[Display(Name="Trades Log File Path", Description="Full path to trades_taken.csv", Order=2, GroupName="File Paths")]
		public string TradesLogFilePath
		{
			get { return tradesLogFilePath; }
			set { tradesLogFilePath = value; }
		}

		[NinjaScriptProperty]
		[Range(1, 60)]
		[Display(Name="File Check Interval", Description="Seconds between signal file checks", Order=3, GroupName="Settings")]
		public int FileCheckInterval
		{
			get { return fileCheckInterval; }
			set { fileCheckInterval = Math.Max(1, value); }
		}

		[NinjaScriptProperty]
		[Range(1, 100)]
		[Display(Name="Contract Quantity", Description="Number of contracts per trade", Order=4, GroupName="Settings")]
		public int ContractQuantity
		{
			get { return contractQuantity; }
			set { contractQuantity = Math.Max(1, value); }
		}

		[NinjaScriptProperty]
		[Range(1, 20)]
		[Display(Name="Max Daily Trades", Description="Maximum trades per day", Order=1, GroupName="Risk Management")]
		public int MaxDailyTrades { get; set; }

		[NinjaScriptProperty]
		[Range(10, 500)]
		[Display(Name="Max Daily Loss", Description="Maximum daily loss in points", Order=2, GroupName="Risk Management")]
		public int MaxDailyLoss { get; set; }

		[NinjaScriptProperty]
		[Range(1, 10)]
		[Display(Name="Max Consecutive Losses", Description="Maximum consecutive losses before stopping", Order=3, GroupName="Risk Management")]
		public int MaxConsecutiveLosses { get; set; }

		#endregion
	}
}
