#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class SecondLiveFeed : Strategy
    {
        private string filePath;
        private bool isFileInitialized = false;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Live price feed - Real-time current price";
                Name = "SecondLiveFeed";
                Calculate = Calculate.OnEachTick;  // Real-time price updates
                EntriesPerDirection = 1;
                BarsRequiredToTrade = 20;
            }
            else if (State == State.Configure)
            {
                filePath = @"C:\Users\Joshua\Documents\Projects\Claude Trader\data\LiveFeed.csv";
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            // Safety check to ensure bar data is valid
            if (Bars == null || CurrentBar < 0)
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
                // Create file with header - open and close immediately
                using (StreamWriter writer = new StreamWriter(filePath, false))
                {
                    writer.WriteLine("DateTime,Last");
                }
            }
            catch (Exception ex)
            {
                Print($"Error initializing file: {ex.Message}");
            }
        }

        private void AppendDataToFile()
        {
            try
            {
                // Safety checks before accessing bar data
                if (Time.Count == 0 || Open.Count == 0 || High.Count == 0 || Low.Count == 0 || Close.Count == 0)
                    return;

                // Write current price tick to file
                using (StreamWriter writer = new StreamWriter(filePath, true))
                {
                    writer.WriteLine(
                        $"{DateTime.Now:MM/dd/yyyy HH:mm:ss},{Close[0]:F2}"
                    );
                }
            }
            catch (Exception ex)
            {
                Print($"Error writing to file: {ex.Message}");
            }
        }
    }
}
