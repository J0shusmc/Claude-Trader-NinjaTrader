#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class SecondHistoricalData : Strategy
    {
        private string filePath;
        private bool isFileInitialized = false;

        // EMA Indicators
        private EMA ema21;
        private EMA ema75;
        private EMA ema150;

        // Stochastic Indicator
        private Stochastics stochastic;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Historical hourly data feed with EMAs and Stochastic D";
                Name = "SecondHistoricalData";
                Calculate = Calculate.OnBarClose;  // Only write completed bars
                EntriesPerDirection = 1;
                BarsRequiredToTrade = 150;  // Ensure enough bars for all indicators
                IsOverlay = true;  // Overlay EMAs on price chart
            }
            else if (State == State.Configure)
            {
                filePath = @"C:\Users\Joshua\Documents\Projects\Claude Trader\data\HistoricalData.csv";
            }
            else if (State == State.DataLoaded)
            {
                // Initialize EMA indicators
                ema21 = EMA(21);
                ema75 = EMA(75);
                ema150 = EMA(150);

                // Initialize Stochastic indicator (periodD: 7, periodK: 24, smooth: 3)
                stochastic = Stochastics(7, 24, 3);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            // Safety check to ensure bar data is valid
            if (Bars == null || CurrentBar < 0)
                return;

            // Ensure all indicators are ready
            if (ema21 == null || ema75 == null || ema150 == null || stochastic == null)
                return;

            if (!isFileInitialized)
            {
                InitializeFile();
                isFileInitialized = true;
            }

            AppendDataToFile();
        }

        private void InitializeFile()
        {
            try
            {
                // Create file with header
                using (StreamWriter writer = new StreamWriter(filePath, false))
                {
                    writer.WriteLine("DateTime,Open,High,Low,Close,EMA21,EMA75,EMA150,StochD");
                }
            }
            catch (Exception ex)
            {
                Print($"SecondHistoricalData Error initializing file: {ex.Message}");
            }
        }

        private void AppendDataToFile()
        {
            try
            {
                // Safety checks before accessing bar data
                if (Time.Count == 0 || Open.Count == 0 || High.Count == 0 || Low.Count == 0 || Close.Count == 0)
                    return;

                // Get Stochastic D value (index 0 is the D line)
                double stochDValue = stochastic.D[0];

                // Write completed bar to file with EMA and Stochastic D values
                using (StreamWriter writer = new StreamWriter(filePath, true))
                {
                    writer.WriteLine(
                        $"{Time[0]:MM/dd/yyyy HH:mm:ss},{Open[0]:F2},{High[0]:F2},{Low[0]:F2},{Close[0]:F2},{ema21[0]:F2},{ema75[0]:F2},{ema150[0]:F2},{stochDValue:F2}"
                    );
                }
            }
            catch (Exception ex)
            {
                Print($"SecondHistoricalData Error writing to file: {ex.Message}");
            }
        }
    }
}
