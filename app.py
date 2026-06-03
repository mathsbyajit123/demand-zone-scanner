import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import datetime

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Indian Market 50 EMA Screener", layout="wide")
st.title("📈 50 EMA Swing Trading Screener")
st.write("Scan Indian indices for specific 50 EMA setups.")

# --- HELPER FUNCTIONS ---
@st.cache_data(ttl=86400) # Cache for 24 hours to speed up loads
def get_nifty_tickers(index_name):
    """Fetches official stock lists from NSE and formats for yfinance."""
    urls = {
        "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "Nifty Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "Nifty Smallcap 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv"
    }
    
    try:
        df = pd.read_csv(urls[index_name])
        # yfinance requires '.NS' suffix for Indian National Stock Exchange tickers
        tickers = df['Symbol'].astype(str) + ".NS"
        return tickers.tolist()
    except Exception as e:
        st.error(f"Failed to fetch ticker list from NSE: {e}")
        return []

def calculate_ema_conditions(ticker, period="1y", interval="1d", condition_type="Above"):
    """Fetches data and checks the 50 EMA conditions."""
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty or len(data) < 50:
            return None
            
        # Calculate 50 EMA
        data['EMA_50'] = ta.ema(data['Close'], length=50)
        data.dropna(inplace=True)
        
        if data.empty:
            return None
            
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        close = latest['Close']
        low = latest['Low']
        ema = latest['EMA_50']
        
        prev_close = prev['Close']
        prev_low = prev['Low']
        prev_ema = prev['EMA_50']

        # Determine if condition is met
        status = False
        
        if condition_type == "1. Just Approaching (Within 2%)":
            # Price is above EMA, but has dropped to within 2% of it
            proximity = ((close - ema) / ema) * 100
            if 0 < proximity <= 2.0:
                status = True
                
        elif condition_type == "2. Just Touched (Bounce off)":
            # Low went below/touched EMA, but closed above it
            if low <= ema and close > ema:
                status = True
                
        elif condition_type == "3. Touch and Away (Confirmed Bounce)":
            # Yesterday touched, today is green and moving up
            if (prev_low <= prev_ema and prev_close > prev_ema) and (close > prev_close):
                status = True
                
        elif condition_type == "4. Above 50 EMA":
            # Simple trend check
            if close > ema:
                status = True

        if status:
            return {"Ticker": ticker.replace(".NS", ""), "Close": round(close, 2), "EMA_50": round(ema, 2)}
        return None

    except Exception:
        return None

# --- SIDEBAR UI ---
st.sidebar.header("Filter Settings")

selected_index = st.sidebar.selectbox(
    "1. Select Index",
    ["Nifty 500", "Nifty Midcap 100", "Nifty Smallcap 250"]
)

selected_tf = st.sidebar.selectbox(
    "2. Select Timeframe",
    ["Daily", "Weekly", "Monthly"]
)

# Map UI selection to yfinance intervals
tf_mapping = {"Daily": "1d", "Weekly": "1wk", "Monthly": "1mo"}
period_mapping = {"Daily": "1y", "Weekly": "3y", "Monthly": "5y"}

selected_condition = st.sidebar.selectbox(
    "3. Select 50 EMA Condition",
    [
        "1. Just Approaching (Within 2%)", 
        "2. Just Touched (Bounce off)", 
        "3. Touch and Away (Confirmed Bounce)", 
        "4. Above 50 EMA"
    ]
)

# --- MAIN APP LOGIC ---
if st.sidebar.button("Run Scanner"):
    tickers = get_nifty_tickers(selected_index)
    
    if tickers:
        st.write(f"Scanning **{len(tickers)}** stocks in **{selected_index}** on **{selected_tf}** timeframe for: *{selected_condition}*")
        
        # Progress bar
        progress_text = "Scanning in progress. Please wait..."
        my_bar = st.progress(0, text=progress_text)
        
        results = []
        total_tickers = len(tickers)
        
        # We limit to first 100 for live app performance, yfinance rate limits can trigger on 500
        # Remove `[:100]` if you want to scan all 500, but it will take a few minutes.
        scan_list = tickers[:100] 
        
        for i, ticker in enumerate(scan_list):
            res = calculate_ema_conditions(
                ticker, 
                period=period_mapping[selected_tf], 
                interval=tf_mapping[selected_tf], 
                condition_type=selected_condition
            )
            if res:
                results.append(res)
                
            # Update progress
            my_bar.progress((i + 1) / len(scan_list), text=f"Scanning {ticker}...")
            
        my_bar.empty()
        
        if results:
            st.success(f"Found {len(results)} stocks matching your criteria!")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.warning("No stocks found matching this exact criteria right now.")

st.sidebar.markdown("---")
st.sidebar.info("Note: Scanning 500 stocks live via Yahoo Finance takes time. The code defaults to scanning the top 100 of the list to prevent timeouts. You can adjust this in the code.")
