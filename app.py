import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Multi-TF EMA Screener", layout="wide")
st.title("📈 Advanced Multi-Timeframe EMA Screener")
st.write("Scans all 500 Nifty stocks simultaneously using Batch Downloading (approx 10-15 seconds).")

# --- HELPER FUNCTIONS ---
@st.cache_data(ttl=86400)
def get_nifty_tickers(index_name):
    """Fetches exact official lists from NSE."""
    urls = {
        "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "Nifty Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "Nifty Smallcap 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv"
    }
    try:
        df = pd.read_csv(urls[index_name])
        # Add .NS suffix for Indian Stocks in Yahoo Finance
        return (df['Symbol'].astype(str) + ".NS").tolist()
    except Exception as e:
        st.error(f"Failed to fetch list from NSE: {e}")
        return []

# --- SIDEBAR UI ---
st.sidebar.header("Filter Settings")
selected_index = st.sidebar.selectbox("1. Select Index", ["Nifty 500", "Nifty Midcap 100", "Nifty Smallcap 250"])

market_phase = st.sidebar.radio("2. Multi-Timeframe Trend", [
    "Bull Market (Price > 50 EMA on Daily, Weekly, & Monthly)", 
    "Bear Market (Price < 50 EMA on Daily, Weekly, & Monthly)"
])

setup_condition = st.sidebar.radio("3. Daily Trade Setup", [
    "Pullback Zone (Between 20 EMA and 50 EMA)",
    "Just Touched 50 EMA (Bounce)",
    "Standard (Just follow Multi-TF Trend)"
])

# --- MAIN LOGIC ---
if st.sidebar.button("Run Fast Scanner"):
    tickers = get_nifty_tickers(selected_index)
    if not tickers:
        st.stop()
        
    st.info(f"Downloading 5 years of historical data for {len(tickers)} stocks at once. Please wait 10-15 seconds...")
    
    # --- BATCH DOWNLOAD (Solves the timeout issue) ---
    data = yf.download(tickers, period="5y", interval="1d", group_by="ticker", threads=True, progress=False)
    
    results = []
    
    # Progress bar for internal calculations
    my_bar = st.progress(0, text="Calculating EMAs across multiple timeframes...")
    
    for i, ticker in enumerate(tickers):
        my_bar.progress((i + 1) / len(tickers), text=f"Analyzing {ticker}...")
        
        try:
            # Safely extract ticker data from the batch download
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.get_level_values(0):
                    continue
                df = data[ticker].dropna()
            else:
                df = data.dropna()
                
            # Need at least ~250 days to calculate a proper Monthly 50 EMA
            if len(df) < 250: 
                continue
                
            # --- DAILY DATA ---
            daily_close = df['Close']
            d_20 = ta.ema(daily_close, length=20).iloc[-1]
            d_50 = ta.ema(daily_close, length=50).iloc[-1]
            d_c = daily_close.iloc[-1]
            
            # --- WEEKLY DATA (Resampled) ---
            weekly_close = daily_close.resample('W-FRI').last().dropna()
            if len(weekly_close) < 50: continue
            w_50 = ta.ema(weekly_close, length=50).iloc[-1]
            w_c = weekly_close.iloc[-1]
            
            # --- MONTHLY DATA (Resampled) ---
            monthly_close = daily_close.resample('ME').last().dropna()
            if len(monthly_close) < 50: continue
            m_50 = ta.ema(monthly_close, length=50).iloc[-1]
            m_c = monthly_close.iloc[-1]
            
            is_match = False
            
            # --- BULL MARKET LOGIC ---
            if market_phase == "Bull Market (Price > 50 EMA on Daily, Weekly, & Monthly)":
                if d_c > d_50 and w_c > w_50 and m_c > m_50: # Trend Alignment Check
                    
                    if setup_condition == "Pullback Zone (Between 20 EMA and 50 EMA)":
                        # Price is dropping below 20 EMA, but 50 EMA is supporting it
                        if d_50 < d_c < d_20:
                            is_match = True
                            
                    elif setup_condition == "Just Touched 50 EMA (Bounce)":
                        # Daily Low dipped below 50 EMA, but Daily Close bounced above it
                        d_l = df['Low'].iloc[-1]
                        if d_l <= d_50 and d_c > d_50:
                            is_match = True
                            
                    elif setup_condition == "Standard (Just follow Multi-TF Trend)":
                        is_match = True

            # --- BEAR MARKET LOGIC ---
            elif market_phase == "Bear Market (Price < 50 EMA on Daily, Weekly, & Monthly)":
                if d_c < d_50 and w_c < w_50 and m_c < m_50: # Trend Alignment Check
                    
                    if setup_condition == "Pullback Zone (Between 20 EMA and 50 EMA)":
                        # Price is rallying above 20 EMA, but 50 EMA is resisting it
                        if d_50 > d_c > d_20:
                            is_match = True
                            
                    elif setup_condition == "Just Touched 50 EMA (Bounce)":
                        # Daily High rallied into 50 EMA, but Daily Close was pushed below it
                        d_h = df['High'].iloc[-1]
                        if d_h >= d_50 and d_c < d_50:
                            is_match = True
                            
                    elif setup_condition == "Standard (Just follow Multi-TF Trend)":
                        is_match = True

            if is_match:
                results.append({
                    "Ticker": ticker.replace(".NS", ""),
                    "Close Price": round(d_c, 2),
                    "Daily 20 EMA": round(d_20, 2),
                    "Daily 50 EMA": round(d_50, 2),
                    "Weekly 50 EMA": round(w_50, 2),
                    "Monthly 50 EMA": round(m_50, 2)
                })
                
        except Exception:
            continue
            
    my_bar.empty()
    
    if results:
        st.success(f"Found {len(results)} stocks matching your exact criteria.")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("No stocks met this exact technical criteria at today's close.")
