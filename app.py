import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from nselib import capital_market
import time
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ STREAMLIT PAGE SETUP
# ==========================================
st.set_page_config(page_title="NSE Delivery Scanner", layout="wide")
st.title("🚀 Advanced Market Cap & Delivery Scanner")

# ==========================================
# 🎛️ SIDEBAR CONFIGURATION
# ==========================================
st.sidebar.header("Scanner Settings")

default_tickers = "REDINGTON, TATASTEEL, RELIANCE, INFY, HDFCBANK, ZOMATO"
tickers_input = st.sidebar.text_area("Tickers (Comma separated)", default_tickers)

days_to_scan = st.sidebar.slider("Historical Days to Scan", min_value=3, max_value=20, value=10)

sort_by = st.sidebar.selectbox(
    "Sort Results By", 
    ["Deliv Multiplier", "% Change", "Latest Deliv", f"{days_to_scan}D Avg Deliv", "Deliv Change"]
)

ascending = st.sidebar.checkbox("Lowest to Highest (Ascending)", value=False)
run_scan = st.sidebar.button("Run Scanner", type="primary")

# ==========================================
# 🧠 CORE FUNCTIONS
# ==========================================
def get_market_cap_category(mcap_cr):
    if mcap_cr == 0: return "Unknown"
    elif mcap_cr < 100: return "Under 100 Cr"
    elif 100 <= mcap_cr < 500: return "100 Cr - 500 Cr"
    elif 500 <= mcap_cr < 1000: return "500 Cr - 1000 Cr"
    elif 1000 <= mcap_cr < 10000: return "1000 Cr - 10000 Cr"
    elif 10000 <= mcap_cr < 100000: return "10000 Cr - 1 Lakh Cr"
    else: return "Over 1 Lakh Cr"

def fetch_historical_delivery(days):
    valid_dataframes = []
    current_date = datetime.now()
    days_collected = 0
    
    # UI Progress indicators
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while days_collected < days:
        if current_date.weekday() < 5:  # Skip weekends
            date_str = current_date.strftime("%d-%m-%Y")
            status_text.text(f"Fetching official NSE Bhavcopy for {date_str}...")
            
            try:
                df = capital_market.bhav_copy_with_delivery(date_str)
                df.columns = df.columns.str.strip()
                df = df[df['SERIES'].str.strip() == 'EQ']
                df['DATE'] = current_date
                
                valid_dataframes.append(df)
                days_collected += 1
                progress_bar.progress(days_collected / days)
                time.sleep(1.5)  # Pause to prevent NSE from blocking the IP
            except Exception:
                pass  # Skip if it's a holiday or data isn't published yet
                
        current_date -= timedelta(days=1)
        
    # Clear progress UI once done
    status_text.empty()
    progress_bar.empty()
    
    if not valid_dataframes:
        return pd.DataFrame()
        
    return pd.concat(valid_dataframes, ignore_index=True)

# ==========================================
# 🚀 EXECUTION BLOCK
# ==========================================
if run_scan:
    ticker_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    
    if not ticker_list:
        st.warning("⚠️ Please enter at least one ticker symbol.")
    else:
        with st.spinner("Downloading historical delivery data from NSE..."):
            hist_df = fetch_historical_delivery(days_to_scan)
            
        if hist_df.empty:
            st.error("❌ Failed to fetch historical data. The NSE servers might be down, or it is a holiday.")
        else:
            hist_df['DELIV_QTY'] = pd.to_numeric(hist_df['DELIV_QTY'].astype(str).str.replace(',', ''), errors='coerce')
            results = []
            
            status_text = st.empty()
            
            for i, ticker in enumerate(ticker_list):
                status_text.text(f"Analyzing {ticker} & fetching Yahoo Finance metadata ({i+1}/{len(ticker_list)})...")
                ticker_data = hist_df[hist_df['SYMBOL'] == ticker].sort_values(by='DATE')
                
                if ticker_data.empty or len(ticker_data) < 2:
                    continue
                    
                # Calculations
                avg_delivery = ticker_data['DELIV_QTY'].mean()
                latest_delivery = ticker_data.iloc[-1]['DELIV_QTY']
                prev_delivery = ticker_data.iloc[-2]['DELIV_QTY']
                
                change_in_delivery = latest_delivery - prev_delivery
                pct_change_delivery = (change_in_delivery / prev_delivery) * 100 if prev_delivery > 0 else 0
                delivery_times = (latest_delivery / avg_delivery) if avg_delivery > 0 else 0

                # Fetch Sector & Market Cap
                try:
                    yf_ticker = yf.Ticker(f"{ticker}.NS")
                    info = yf_ticker.info
                    mcap_cr = info.get('marketCap', 0) / 10_000_000
                    sector = info.get('sector', 'N/A')
                    mcap_category = get_market_cap_category(mcap_cr)
                except Exception:
                    sector = "N/A"
                    mcap_category = "Unknown"

                results.append({
                    "Ticker": ticker,
                    "Sector": sector,
                    "Market Cap": mcap_category,
                    f"{days_to_scan}D Avg Deliv": avg_delivery,
                    "Latest Deliv": latest_delivery,
                    "Deliv Change": change_in_delivery,
                    "% Change": pct_change_delivery,
                    "Deliv Multiplier": delivery_times
                })
                
            status_text.empty()
            
            if results:
                # Convert to Pandas DataFrame
                final_df = pd.DataFrame(results)
                
                # Apply Sorting
                if sort_by in final_df.columns:
                    final_df = final_df.sort_values(by=sort_by, ascending=ascending)
                
                # Format numbers for clean UI rendering
                display_df = final_df.copy()
                display_df[f'{days_to_scan}D Avg Deliv'] = display_df[f'{days_to_scan}D Avg Deliv'].apply(lambda x: f"{int(x):,}")
                display_df['Latest Deliv'] = display_df['Latest Deliv'].apply(lambda x: f"{int(x):,}")
                display_df['Deliv Change'] = display_df['Deliv Change'].apply(lambda x: f"{int(x):,}")
                display_df['% Change'] = display_df['% Change'].apply(lambda x: f"{x:.2f}%")
                display_df['Deliv Multiplier'] = display_df['Deliv Multiplier'].apply(lambda x: f"{x:.2f}x")
                
                st.success("✅ Scan Complete!")
                
                # Render the interactive Streamlit table
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.warning("No valid data found for the provided tickers. Check your ticker spellings.")
