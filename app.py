import streamlit as st
import yfinance as yf
import pandas as pd
import time

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Pure Momentum EMA Screener", layout="wide")
st.title("📈 Pure Momentum EMA Screener")
st.write("Focused single-timeframe scanner for 50 EMA momentum and fresh pullbacks.")

# --- HELPER FUNCTIONS ---
@st.cache_data(ttl=86400)
def get_nifty_tickers(index_name):
    """Fetches exact official lists from NSE."""
    urls = {
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "Nifty Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "Nifty Smallcap 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv"
    }
    try:
        df = pd.read_csv(urls[index_name])
        return (df['Symbol'].astype(str) + ".NS").tolist()
    except Exception as e:
        st.error(f"Failed to fetch list from NSE: {e}")
        return []

def extract_data(data_batch, ticker):
    """Safely extracts a single ticker's dataframe from a yfinance batch download."""
    if isinstance(data_batch.columns, pd.MultiIndex):
        if ticker not in data_batch.columns.get_level_values(0):
            return pd.DataFrame()
        return data_batch[ticker].dropna()
    else:
        return data_batch.dropna()

# --- SIDEBAR UI LOGIC ---
st.sidebar.header("Filter Settings")

# 1. Sector Selection
selected_index = st.sidebar.selectbox("1. Select Sector / Index", ["Nifty 50", "Nifty 500", "Nifty Midcap 100", "Nifty Smallcap 250"])

# 2. Market Phase
market_phase = st.sidebar.radio("2. Market Phase", ["Bullish", "Bearish"])
is_bull = "Bullish" in market_phase

# 3. Time Frame Selection
tf_selection = st.sidebar.selectbox("3. Select Time Frame", ["1 Day", "1 Week", "1 Month", "3 Months"])

# Dynamic Default Percentage based on Time Frame
if tf_selection == "1 Day":
    default_gap = 3.0
elif tf_selection == "1 Week":
    default_gap = 7.5  # Right between 7 and 8
elif tf_selection == "1 Month":
    default_gap = 11.0 # Right between 10 and 12
else: # 3 Months
    default_gap = 15.0

# 4. Setup Condition & Momentum Gap
st.sidebar.markdown("### 4. Setup Condition")
trend_gap = st.sidebar.slider("Adjust % Distance from 50 EMA", min_value=1.0, max_value=25.0, value=default_gap, step=0.5)
gap_decimal = trend_gap / 100.0

if is_bull:
    setup_choice = st.sidebar.radio(f"Select setup for {tf_selection}:", [
        f"a) Price > {trend_gap}% above 50 EMA",
        f"b) Price just touches 50 EMA"
    ])
else:
    setup_choice = st.sidebar.radio(f"Select setup for {tf_selection}:", [
        f"a) Price > {trend_gap}% below 50 EMA",
        f"b) Price just touches 50 EMA"
    ])

is_gap = ">" in setup_choice
is_touch = "touches" in setup_choice

# --- MAIN SCANNER LOGIC ---
if st.sidebar.button("Run Fast Scanner"):
    tickers = get_nifty_tickers(selected_index)
    if not tickers:
        st.stop()
        
    st.info(f"Scanning {len(tickers)} stocks on the {tf_selection} timeframe...")
    
    results = []
    my_bar = st.progress(0, text="Starting scan...")
    
    chunk_size = 100 
    total_chunks = (len(tickers) // chunk_size) + 1
    
    # Determine data lookback needed to calculate a 50 EMA on the selected timeframe
    if tf_selection == "3 Months": period_1d = "15y" 
    elif tf_selection == "1 Month": period_1d = "5y" 
    elif tf_selection == "1 Week": period_1d = "2y"  
    else: period_1d = "1y"                           
    
    for chunk_idx in range(total_chunks):
        start_idx = chunk_idx * chunk_size
        end_idx = min(start_idx + chunk_size, len(tickers))
        current_batch = tickers[start_idx:end_idx]
        
        if not current_batch: break
            
        my_bar.progress(chunk_idx / total_chunks, text=f"Downloading batch {chunk_idx + 1} of {total_chunks}...")
        
        # Download Data
        data_1d = yf.download(current_batch, period=period_1d, interval="1d", group_by="ticker", threads=True, progress=False)
        
        for ticker in current_batch:
            try:
                df_1d = extract_data(data_1d, ticker)
                if len(df_1d) < 10: continue
                
                # --- RESAMPLE BASED ON SELECTED TIMEFRAME ---
                if tf_selection == "1 Day":
                    df_tf = df_1d.copy()
                elif tf_selection == "1 Week":
                    df_tf = df_1d.resample('W-FRI').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
                elif tf_selection == "1 Month":
                    df_tf = df_1d.resample('ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
                elif tf_selection == "3 Months":
                    df_tf = df_1d.resample('QE').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()

                # Ensure we have at least 50 periods on this timeframe to calculate the EMA
                if len(df_tf) < 50: 
                    continue
                
                # --- EXTRACT CURRENT & PREVIOUS CANDLES ---
                c = df_tf['Close'].iloc[-1]
                l = df_tf['Low'].iloc[-1]
                h = df_tf['High'].iloc[-1]
                
                prev_l = df_tf['Low'].iloc[-2]
                prev_h = df_tf['High'].iloc[-2]
                
                # --- CALCULATE EMA ---
                ema_series = df_tf['Close'].ewm(span=50, adjust=False).mean()
                ema = ema_series.iloc[-1]
                prev_ema = ema_series.iloc[-2]

                is_match = False

                # --- APPLY LOGIC ---
                if is_bull:
                    if is_gap:
                        # Price is at least X% above 50 EMA
                        if (c - ema) / ema >= gap_decimal: 
                            is_match = True
                    elif is_touch:
                        # Bullish Fresh Touch: Prev Low > Prev EMA, Current Low dips <= Current EMA, Close > EMA
                        if (prev_l > prev_ema) and (l <= ema) and (c > ema): 
                            is_match = True
                else:
                    if is_gap:
                        # Price is at least X% below 50 EMA
                        if (ema - c) / ema >= gap_decimal: 
                            is_match = True
                    elif is_touch:
                        # Bearish Fresh Touch: Prev High < Prev EMA, Current High spikes >= Current EMA, Close < EMA
                        if (prev_h < prev_ema) and (h >= ema) and (c < ema): 
                            is_match = True

                # --- RECORD MATCH ---
                if is_match:
                    results.append({
                        "Ticker": ticker.replace(".NS", ""),
                        "Time Frame": tf_selection,
                        "Condition Met": f"Gap > {trend_gap}%" if is_gap else "Fresh Touch",
                        "Current Price": round(c, 2),
                        "50 EMA": round(ema, 2)
                    })
            except Exception:
                continue
                
        time.sleep(0.5) 
                
    my_bar.empty()
    
    if results:
        st.success(f"Scan Complete! Found {len(results)} stocks matching your criteria.")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("Scan Complete. No stocks met this specific criteria.")
