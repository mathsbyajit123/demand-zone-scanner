import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from nselib import capital_market
import time
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ SCANNER CONFIGURATION
# ==========================================
TICKERS = ["REDINGTON", "TATASTEEL", "RELIANCE", "INFY", "HDFCBANK", "ZOMATO"]
DAYS_TO_SCAN = 10
EXCHANGE = "NSE"

# 🔄 SORTING OPTIONS
# Choose one: "Deliv Multiplier", "% Change", "Latest Deliv", "10D Avg Deliv", "Deliv Change"
SORT_BY = "Deliv Multiplier"  
ASCENDING = False  # False = Highest to Lowest (Descending), True = Lowest to Highest
# ==========================================

def get_market_cap_category(mcap_cr):
    """Categorizes the market cap into the requested brackets."""
    if mcap_cr == 0: return "Unknown"
    elif mcap_cr < 100: return "Under 100 Cr"
    elif 100 <= mcap_cr < 500: return "100 Cr - 500 Cr"
    elif 500 <= mcap_cr < 1000: return "500 Cr - 1000 Cr"
    elif 1000 <= mcap_cr < 10000: return "1000 Cr - 10000 Cr"
    elif 10000 <= mcap_cr < 100000: return "10000 Cr - 1 Lakh Cr"
    else: return "Over 1 Lakh Cr"

def fetch_historical_delivery(days):
    """Fetches NSE Bhavcopy for the last 'N' trading days."""
    print(f"📥 Fetching NSE Delivery Data for the last {days} trading days...")
    
    valid_dataframes = []
    current_date = datetime.now()
    days_collected = 0
    
    while days_collected < days:
        if current_date.weekday() < 5: # Skip weekends
            date_str = current_date.strftime("%d-%m-%Y")
            try:
                df = capital_market.bhav_copy_with_delivery(date_str)
                df.columns = df.columns.str.strip()
                df = df[df['SERIES'].str.strip() == 'EQ']
                df['DATE'] = current_date
                
                valid_dataframes.append(df)
                days_collected += 1
                print(f"   ✅ Data loaded for {date_str}")
                time.sleep(1.5) # Prevent server block
            except Exception:
                pass # Holiday or data not out yet
                
        current_date -= timedelta(days=1)
        
    if not valid_dataframes:
        return pd.DataFrame()
        
    return pd.concat(valid_dataframes, ignore_index=True)

def main():
    print(f"\n🚀 Starting Sorted Market Cap & Delivery Scanner ({EXCHANGE})")
    
    hist_df = fetch_historical_delivery(DAYS_TO_SCAN)
    if hist_df.empty:
        print("❌ Failed to fetch historical data from NSE.")
        return

    hist_df['DELIV_QTY'] = pd.to_numeric(hist_df['DELIV_QTY'].astype(str).str.replace(',', ''), errors='coerce')
    
    results = []

    print("\n🔍 Analyzing Tickers and Fetching Metadata from Yahoo Finance...")
    for ticker in TICKERS:
        ticker_data = hist_df[hist_df['SYMBOL'] == ticker].sort_values(by='DATE')
        
        if ticker_data.empty or len(ticker_data) < 2:
            continue
            
        # --- Core Calculations ---
        avg_delivery = ticker_data['DELIV_QTY'].mean()
        latest_delivery = ticker_data.iloc[-1]['DELIV_QTY']
        prev_delivery = ticker_data.iloc[-2]['DELIV_QTY']
        
        change_in_delivery = latest_delivery - prev_delivery
        pct_change_delivery = (change_in_delivery / prev_delivery) * 100 if prev_delivery > 0 else 0
        
        # New Calculation: Delivery Times (Multiplier)
        delivery_times = (latest_delivery / avg_delivery) if avg_delivery > 0 else 0

        # --- Fetch Sector & Market Cap ---
        try:
            yf_ticker = yf.Ticker(f"{ticker}.NS")
            info = yf_ticker.info
            mcap_cr = info.get('marketCap', 0) / 10_000_000
            sector = info.get('sector', 'N/A')
            mcap_category = get_market_cap_category(mcap_cr)
        except Exception:
            sector = "N/A"
            mcap_category = "Unknown"

        # Store RAW numbers for accurate sorting later
        results.append({
            "Ticker": ticker,
            "Exchange": EXCHANGE,
            "Sector": sector,
            "Market Cap": mcap_category,
            "10D Avg Deliv": avg_delivery,
            "Latest Deliv": latest_delivery,
            "Deliv Change": change_in_delivery,
            "% Change": pct_change_delivery,
            "Deliv Multiplier": delivery_times
        })

    if results:
        # 1. Convert to DataFrame
        final_df = pd.DataFrame(results)
        
        # 2. Apply Sorting based on Configuration
        if SORT_BY in final_df.columns:
            final_df = final_df.sort_values(by=SORT_BY, ascending=ASCENDING)
        
        # 3. Format the numbers for clean reading AFTER sorting
        final_df['10D Avg Deliv'] = final_df['10D Avg Deliv'].apply(lambda x: f"{int(x):,}")
        final_df['Latest Deliv'] = final_df['Latest Deliv'].apply(lambda x: f"{int(x):,}")
        final_df['Deliv Change'] = final_df['Deliv Change'].apply(lambda x: f"{int(x):,}")
        final_df['% Change'] = final_df['% Change'].apply(lambda x: f"{x:.2f}%")
        final_df['Deliv Multiplier'] = final_df['Deliv Multiplier'].apply(lambda x: f"{x:.2f}x")
        
        # 4. Display
        print("\n" + "="*130)
        print(final_df.to_string(index=False))
        print("="*130 + "\nScan Complete.\n")
    else:
        print("No valid data found for the provided tickers.")

if __name__ == "__main__":
    main()
