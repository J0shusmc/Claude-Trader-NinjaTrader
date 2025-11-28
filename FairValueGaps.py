import pandas as pd
import time
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FVGDisplay:
    def __init__(self, instrument='NQ', historical_path='data/HistoricalData.csv', live_feed_path='data/LiveFeed.csv'):
        self.instrument = instrument
        self.historical_path = historical_path
        self.live_feed_path = live_feed_path

        # FVG tracking
        self.active_fvgs = []
        self.last_processed_bar_time = None
        self.last_historical_mod_time = None

    def check_historical_updated(self):
        """Check if HistoricalData.csv has been updated (new hourly bar)"""
        try:
            if not os.path.exists(self.historical_path):
                return False

            current_mod_time = os.path.getmtime(self.historical_path)

            if self.last_historical_mod_time is None:
                self.last_historical_mod_time = current_mod_time
                return True

            if current_mod_time > self.last_historical_mod_time:
                self.last_historical_mod_time = current_mod_time
                return True

            return False
        except Exception as e:
            logger.error(f"Error checking historical file: {e}")
            return False
    
    def read_historical_data(self):
        """Read historical hourly data for FVG detection"""
        try:
            if not os.path.exists(self.historical_path):
                return None

            df = pd.read_csv(self.historical_path)
            if df.empty:
                return None

            df['DateTime'] = pd.to_datetime(df['DateTime'])
            df = df.sort_values('DateTime').reset_index(drop=True)
            return df
        except Exception as e:
            logger.error(f"Error reading historical data: {e}")
            return None

    def read_current_price(self):
        """Read current price from live feed (last line)"""
        try:
            if not os.path.exists(self.live_feed_path):
                return None

            df = pd.read_csv(self.live_feed_path)
            if df.empty:
                return None

            # Get the last line for current price
            last_row = df.iloc[-1]
            return float(last_row['Last'])
        except Exception as e:
            logger.error(f"Error reading current price: {e}")
            return None
        

    def find_fvgs_in_data(self, df, start_index=2):
        """Find FVGs in price data"""
        fvgs = []
        
        for i in range(start_index, len(df)):
            candle1 = df.iloc[i - 2]
            candle2 = df.iloc[i - 1]  
            candle3 = df.iloc[i]
            
            # Check for bullish FVG (gap up)
            if candle3['Low'] > candle1['High']:
                gap_size = candle3['Low'] - candle1['High']
                if gap_size >= 5.0:  # Minimum gap size
                    fvg = {
                        'type': 'bullish',
                        'top': candle3['Low'],
                        'bottom': candle1['High'],
                        'gap_size': gap_size,
                        'datetime': candle3['DateTime'],
                        'index': i,
                        'filled': False,
                        'trade_taken': False,
                        'trade_bar_timestamp': None,  # Track which bar the trade occurred in
                        'price_was_outside': True  # Track if price was outside zone
                    }
                    fvgs.append(fvg)

            # Check for bearish FVG (gap down)
            elif candle3['High'] < candle1['Low']:
                gap_size = candle1['Low'] - candle3['High']
                if gap_size >= 5.0:
                    fvg = {
                        'type': 'bearish',
                        'top': candle1['Low'],
                        'bottom': candle3['High'],
                        'gap_size': gap_size,
                        'datetime': candle3['DateTime'],
                        'index': i,
                        'filled': False,
                        'trade_taken': False,
                        'trade_bar_timestamp': None,  # Track which bar the trade occurred in
                        'price_was_outside': True  # Track if price was outside zone
                    }
                    fvgs.append(fvg)
        
        return fvgs
    
    def is_fvg_filled(self, fvg, df, start_index):
        """Check if FVG has been filled by subsequent price action"""
        for j in range(start_index + 1, len(df)):
            check_candle = df.iloc[j]

            # Bullish FVG fills when price touches/closes at or below the bottom
            if fvg['type'] == 'bullish' and check_candle['Low'] <= fvg['bottom']:
                return True
            # Bearish FVG fills when price touches/closes at or above the top
            elif fvg['type'] == 'bearish' and check_candle['High'] >= fvg['top']:
                return True

        return False
    
    def process_historical_bars(self):
        """Process historical data for new FVG detection"""
        df = self.read_historical_data()

        if df is None or df.empty or len(df) < 3:
            return

        # Get the latest bar time
        latest_bar_time = df.iloc[-1]['DateTime']
        current_index = len(df) - 1

        # Check if this is a new bar
        is_new_bar = self.last_processed_bar_time != latest_bar_time

        if is_new_bar:
            logger.info(f"New hourly bar detected at {latest_bar_time}")

            # Look for new FVGs
            self.find_new_fvgs(df, current_index)

            # Check if any FVGs got filled
            self.check_fvg_fill_status(df, current_index)

            self.last_processed_bar_time = latest_bar_time

    def clear_screen(self):
        """Clear screen - optimized for Windows"""
        if os.name == 'nt':
            # Windows: use standard os.system for proper clearing
            os.system('cls')
        else:
            # Unix: use ANSI codes
            os.system('clear')

    def zones_overlap(self, zone1_bottom, zone1_top, zone2_bottom, zone2_top):
        """Check if two zones overlap"""
        if zone1_bottom >= zone2_top or zone2_bottom >= zone1_top:
            return False
        return True

    def is_duplicate_zone(self, new_fvg):
        """Check if a new FVG overlaps with existing zones - keep smaller zone (silent)"""
        zones_to_remove = []

        for i, existing_fvg in enumerate(self.active_fvgs):
            if existing_fvg['type'] != new_fvg['type']:
                continue
            if existing_fvg['filled']:
                continue

            if self.zones_overlap(existing_fvg['bottom'], existing_fvg['top'],
                                 new_fvg['bottom'], new_fvg['top']):
                existing_size = existing_fvg['gap_size']
                new_size = new_fvg['gap_size']

                if new_size < existing_size:
                    zones_to_remove.append(i)
                else:
                    return True

        for i in reversed(zones_to_remove):
            self.active_fvgs.pop(i)

        return False

    def find_new_fvgs(self, df, current_index):
        """Find new FVGs in the latest price data"""
        if current_index < 2:
            return

        candle1 = df.iloc[current_index - 2]
        candle2 = df.iloc[current_index - 1]
        candle3 = df.iloc[current_index]

        # Check for bullish FVG
        if candle3['Low'] > candle1['High']:
            gap_size = candle3['Low'] - candle1['High']
            if gap_size >= 5.0:
                fvg = {
                    'type': 'bullish',
                    'top': candle3['Low'],
                    'bottom': candle1['High'],
                    'gap_size': gap_size,
                    'datetime': candle3['DateTime'],
                    'index': current_index,
                    'filled': False
                }

                logger.info(f"NEW BULLISH FVG: Gap {gap_size:.2f}pts ({candle1['High']:.2f} to {candle3['Low']:.2f})")

                if not self.is_duplicate_zone(fvg):
                    self.active_fvgs.append(fvg)

        # Check for bearish FVG
        elif candle3['High'] < candle1['Low']:
            gap_size = candle1['Low'] - candle3['High']
            if gap_size >= 5.0:
                fvg = {
                    'type': 'bearish',
                    'top': candle1['Low'],
                    'bottom': candle3['High'],
                    'gap_size': gap_size,
                    'datetime': candle3['DateTime'],
                    'index': current_index,
                    'filled': False
                }

                logger.info(f"NEW BEARISH FVG: Gap {gap_size:.2f}pts ({candle3['High']:.2f} to {candle1['Low']:.2f})")

                if not self.is_duplicate_zone(fvg):
                    self.active_fvgs.append(fvg)

        # Clean up old FVGs
        self.clean_old_fvgs(current_index)
    
    
    def check_fvg_fill_status(self, df, current_index):
        """Check if any FVGs have been filled by completed bars"""
        current_bar = df.iloc[current_index]

        for fvg in self.active_fvgs:
            if fvg['filled']:
                continue

            # Bullish FVG fills when price touches/closes at or below the bottom
            if fvg['type'] == 'bullish' and current_bar['Low'] <= fvg['bottom']:
                fvg['filled'] = True
                logger.info(f"BULLISH FVG FILLED: Low {current_bar['Low']:.2f} touched bottom {fvg['bottom']:.2f}")
            # Bearish FVG fills when price touches/closes at or above the top
            elif fvg['type'] == 'bearish' and current_bar['High'] >= fvg['top']:
                fvg['filled'] = True
                logger.info(f"BEARISH FVG FILLED: High {current_bar['High']:.2f} touched top {fvg['top']:.2f}")

    def check_live_fvg_fills(self, current_price):
        """Check if any FVGs have been filled by current live price"""
        for fvg in self.active_fvgs:
            if fvg['filled']:
                continue

            # Bearish FVG fills when current price reaches or exceeds the TOP
            if fvg['type'] == 'bearish' and current_price >= fvg['top']:
                fvg['filled'] = True
                logger.info(f"*** BEARISH FVG FILLED (LIVE) ***")
                logger.info(f"  Zone: {fvg['bottom']:.2f} - {fvg['top']:.2f}")
                logger.info(f"  Fill Price: {current_price:.2f}")
                logger.info(f"  Zone removed from active list")

            # Bullish FVG fills when current price reaches or goes below the BOTTOM
            elif fvg['type'] == 'bullish' and current_price <= fvg['bottom']:
                fvg['filled'] = True
                logger.info(f"*** BULLISH FVG FILLED (LIVE) ***")
                logger.info(f"  Zone: {fvg['bottom']:.2f} - {fvg['top']:.2f}")
                logger.info(f"  Fill Price: {current_price:.2f}")
                logger.info(f"  Zone removed from active list")
    
    def load_historical_fvgs(self):
        """Load FVGs from historical hourly data on startup"""
        logger.info("Scanning historical hourly data for existing FVGs...")

        df = self.read_historical_data()
        if df is None or len(df) < 3:
            logger.info("Not enough historical data to scan for FVGs")
            return

        # Find all FVGs in historical data
        historical_fvgs = self.find_fvgs_in_data(df)

        # Filter out filled FVGs and duplicates, then add to active list
        for fvg in historical_fvgs:
            if not self.is_fvg_filled(fvg, df, fvg['index']):
                if not self.is_duplicate_zone(fvg):
                    self.active_fvgs.append(fvg)

        logger.info(f"Loaded {len(self.active_fvgs)} active FVGs from historical data")
        bullish_count = len([f for f in self.active_fvgs if f['type'] == 'bullish'])
        bearish_count = len([f for f in self.active_fvgs if f['type'] == 'bearish'])
        logger.info(f"  - {bullish_count} bullish FVGs")
        logger.info(f"  - {bearish_count} bearish FVGs")
        logger.info(f"  - Displaying nearest 5 of each type")

    def clean_old_fvgs(self, current_index, current_price=None):
        """Remove only filled FVGs - keep all unfilled zones"""
        cleaned_fvgs = []
        for fvg in self.active_fvgs:
            # Only remove filled FVGs, keep all unfilled zones regardless of distance
            if not fvg['filled']:
                cleaned_fvgs.append(fvg)

        removed_count = len(self.active_fvgs) - len(cleaned_fvgs)
        self.active_fvgs = cleaned_fvgs

        if removed_count > 0:
            logger.info(f"Cleaned {removed_count} filled FVGs")
    
    def display_status(self, current_price):
        """Display current bot status with real-time updates"""
        if current_price is None:
            return

        # Build the entire display as a string buffer first
        lines = []
        lines.append("            NQ FAIR VALUE GAPS")
        lines.append("="*60)
        lines.append("")

        # Get all active FVGs and calculate distances
        active_fvgs = [fvg for fvg in self.active_fvgs if not fvg['filled']]

        if active_fvgs:
            # Add distance to each FVG and sort by distance
            fvgs_with_distance = []
            for fvg in active_fvgs:
                # Calculate distance to entry point
                # Positive = price must go UP, Negative = price must go DOWN
                if fvg['type'] == 'bearish':
                    # For LONG zones: entry at BOTTOM
                    # Positive if price needs to rise to reach bottom
                    distance = fvg['bottom'] - current_price
                else:  # bullish
                    # For SHORT zones: entry at TOP
                    # Negative if price needs to drop to reach top
                    distance = fvg['top'] - current_price

                fvgs_with_distance.append({
                    'fvg': fvg,
                    'distance': distance
                })

            # Sort by absolute distance (closest first)
            fvgs_with_distance.sort(key=lambda x: abs(x['distance']))

            # Separate by type but keep distance ordering
            bullish_sorted = [item for item in fvgs_with_distance if item['fvg']['type'] == 'bullish']
            bearish_sorted = [item for item in fvgs_with_distance if item['fvg']['type'] == 'bearish']

            # Display BEARISH gaps (reversed - furthest first, closest to center last)
            # Show only nearest 5
            lines.append("   BEARISH GAPS (LONG)     Gap Size     Distance       ")
            lines.append("-"*60)
            if bearish_sorted:
                # Take only the 5 nearest bearish zones
                nearest_5_bearish = bearish_sorted[:5]
                # Reverse the order so furthest of the 5 is at top, closest to center at bottom
                for item in reversed(nearest_5_bearish):
                    fvg = item['fvg']
                    distance = item['distance']
                    # Show BOTTOM first for bearish zones (price approaches from below)
                    zone_range = f"{fvg['bottom']:.2f} - {fvg['top']:.2f}"
                    gap_size = f"{fvg['gap_size']:.2f}pts"
                    # Show signed distance with arrows (↑ = price needs to go up, ↓ = price needs to go down)
                    if distance > 0:
                        distance_str = f"↑ {distance:.2f}pts"
                    else:
                        distance_str = f"↓ {abs(distance):.2f}pts"

                    # Check if price is currently in this zone
                    price_in_zone = (current_price >= fvg['bottom'] and current_price <= fvg['top'])
                    zone_annotation = "In Zone" if price_in_zone else ""

                    lines.append(f"    {zone_range:<22} {gap_size:<12} {distance_str:<12}{zone_annotation}")
            else:
                lines.append("    No bearish gaps")

            # Center line with time, instrument, and price
            lines.append("")
            time_str = datetime.now().strftime('%H:%M:%S')
            center_line = f" {time_str} | Instrument: {self.instrument} | Current Price: {current_price:.2f}"
            lines.append(center_line)
            lines.append("")

            # Display BULLISH gaps (top first - closest to price when looking for shorts)
            # Show only nearest 5
            if bullish_sorted:
                # Take only the 5 nearest bullish zones
                nearest_5_bullish = bullish_sorted[:5]
                for item in nearest_5_bullish:
                    fvg = item['fvg']
                    distance = item['distance']
                    # Show TOP first for bullish zones (price approaches from above)
                    zone_range = f"{fvg['top']:.2f} - {fvg['bottom']:.2f}"
                    gap_size = f"{fvg['gap_size']:.2f}pts"
                    # Show signed distance with arrows (↑ = price needs to go up, ↓ = price needs to go down)
                    if distance > 0:
                        distance_str = f"↑ {distance:.2f}pts"
                    else:
                        distance_str = f"↓ {abs(distance):.2f}pts"

                    # Check if price is currently in this zone
                    price_in_zone = (current_price >= fvg['bottom'] and current_price <= fvg['top'])
                    zone_annotation = "In Zone" if price_in_zone else ""

                    lines.append(f"    {zone_range:<22} {gap_size:<12} {distance_str:<12}{zone_annotation}")
            else:
                lines.append("    No bullish gaps")

            lines.append("-"*60)
            lines.append("  BULLISH GAPS (SHORT)     Gap Size     Distance       ")
        else:
            lines.append("\nNo active FVGs")

        lines.append("="*60)

        # Print all lines at once with proper flushing
        output = '\n'.join(lines)
        print(output, end='', flush=True)
    
    def run(self):
        """Main display loop"""
        logger.info("Starting NQ Fair Value Gaps Display...")
        logger.info("Monitoring Fair Value Gaps in real-time")
        logger.info("="*50)

        # Load historical FVGs on startup
        self.load_historical_fvgs()
        logger.info("="*50)

        logger.info(f"Displaying FVGs for {self.instrument}")
        logger.info("Monitoring HistoricalData.csv for new hourly bars and FVGs...")
        logger.info("Monitoring LiveFeed.csv for real-time price updates...")
        logger.info("Display updates every second with live price data...")

        # Enable ANSI escape codes for Windows 10+
        if os.name == 'nt':
            os.system('color')

        # Hide cursor for cleaner display
        if os.name == 'nt':
            # Windows cursor control
            os.system('echo off')
        else:
            print('\033[?25l', end='', flush=True)

        # Clear screen once at startup
        os.system('cls' if os.name == 'nt' else 'clear')

        try:
            while True:
                # Check for new hourly bars (new FVGs)
                if self.check_historical_updated():
                    self.process_historical_bars()

                # Get current price from LiveFeed
                current_price = self.read_current_price()

                if current_price is not None:
                    # Check if any zones have been filled (real-time)
                    self.check_live_fvg_fills(current_price)

                    # Clean FVGs based on distance from current price
                    df = self.read_historical_data()
                    if df is not None and len(df) > 0:
                        current_index = len(df) - 1
                        self.clean_old_fvgs(current_index, current_price)

                    # Display status with current price
                    self.clear_screen()
                    self.display_status(current_price)

                # Sleep for 1 second - updates every second
                time.sleep(1)

        except KeyboardInterrupt:
            # Show cursor again before exiting
            if os.name == 'nt':
                os.system('echo on')
            else:
                print('\033[?25h', end='', flush=True)
            logger.info("\nStopping NQ Fair Value Gaps Display...")
            logger.info(f"Final active FVGs: {len(self.active_fvgs)}")
        except Exception as e:
            # Show cursor again on error
            if os.name == 'nt':
                os.system('echo on')
            else:
                print('\033[?25h', end='', flush=True)
            logger.error(f"Error in main loop: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            # Ensure cursor is visible
            if os.name == 'nt':
                os.system('echo on')
            else:
                print('\033[?25h', end='', flush=True)
            logger.info("FVG Display stopped")

if __name__ == "__main__":
    # Configure for NQ futures
    display = FVGDisplay(instrument='NQ')
    display.run()