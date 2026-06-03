import streamlit as st
import yfinance as yf
import pandas as pd
import time

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Advanced EMA Screener", layout="wide")
st.title("📈 Multi-Timeframe EMA Screener")
st.write("Dynamic timeframe auto-selection for precise pullbacks.")

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

# --- SIDEBAR UI LOGIC ---
st.sidebar.header("Filter Settings")

# 1. Index Selection
selected_index = st.sidebar.selectbox("Select Index", ["Nifty 50", "Nifty 500", "Nifty Midcap 100", "Nifty Smallcap 250"])

# Market Phase
market_phase = st.sidebar.radio("Market Phase", ["Bullish (Support/Bounce)", "Bearish (Resistance/Rejection)"])

# 2. Primary Trend
st.sidebar.markdown("### 1. Primary Trend")
if "Bullish" in market_phase:
    primary_trend = st.sidebar.radio("Select Trend Condition", [
        "Price > 50 MEMA (Monthly)",
        "Price > 50 WEMA (Weekly)",
        "Price > 50 DEMA (Daily)"
    ])
else:
    primary_trend = st.sidebar.radio("Select Trend Condition", [
        "Price < 50 MEMA (Monthly)",
        "Price < 50 WEMA (Weekly)",
        "Price < 50 DEMA (Daily)"
    ])

# 3. Setup Strategy (Point 2 vs Point 3 logic)
st.sidebar.markdown("### 2. Pullback Strategy")
setup_type = st.sidebar.radio("Choose Setup Engine", [
    "Use Auto 50 EMA Pullback (Point 2)",
    "Use 20 EMA Pullback (Point 3)"
])

# Logic variables for the scanner
active_setup = ""

st.sidebar.markdown("### 3. Active Configuration")
if setup_type == "Use Auto 50 EMA Pullback (Point 2)":
    if "MEMA" in primary_trend:
        st.sidebar.success("Auto-Selected: Touch 50 WEMA")
        active_setup = "50_WEMA_TOUCH"
    elif "WEMA" in primary_trend:
        st.sidebar.success("Auto-Selected: Touch 50 DEMA")
        active_setup = "50_DEMA_TOUCH"
    else:
        st.sidebar.error("Daily trend selected. Please switch to 'Use 20 EMA Pullback' for lower timeframes.")
        active_setup = "NONE"
else:
    # Point 3 takes over
    active_setup = st.sidebar.radio("Select 20 EMA Touch Configuration:", [
        "Touch 20 WEMA",
        "Touch 20 DEMA"
    ])

# --- MAIN SCANNER LOGIC ---
if st.sidebar.button("Run Fast Scanner"):
    if active_setup == "NONE":
        st.warning("Invalid configuration. Please adjust your sidebar settings.")
        st.stop()

    tickers = get_nifty_tickers(selected_index)
    if not tickers:
        st.stop()
        
    st.info(f"Scanning {len(tickers)} stocks in {selected_index}...")
    
    results = []
    my_bar = st.progress(0, text="Starting scan...")
    
    chunk_size = 100 
    total_chunks = (len(tickers) // chunk_size) + 1
    
    for chunk_idx in range(total_chunks):
        start_idx = chunk_idx * chunk_size
        end_idx = min(start_idx + chunk_size, len(tickers))
        current_batch = tickers[start_idx:end_idx]
        
        if not current_batch:
            break
            
        my_bar.progress((chunk_idx) / total_chunks, text=f"Downloading batch {chunk_idx + 1} of {total_chunks}...")
        
        # Download chunk
        data = yf.download(current_batch, period="5y", interval="1d", group_by="ticker", threads=True, progress=False)
        
        for ticker in current_batch:
            try:
                if len(current_batch) == 1:
                    df = data.dropna()
                elif isinstance(data.columns, pd.MultiIndex):
                    if ticker not in data.columns.get_level_values(0):
                        continue
                    df = data[ticker].dropna()
                else:
                    df = data.dropna()
                    
                if len(df) < 250: 
                    continue
                    
                # --- CALCULATE TIMEFRAMES ---
                # Daily
                d_c = df['Close'].iloc[-1]
                d_low = df['Low'].iloc[-1]
                d_high = df['High'].iloc[-1]
                d_20 = df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                d_50 = df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                
                # Weekly (Need high/low for touch logic)
                weekly_df = df.resample('W-FRI').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
                if len(weekly_df) < 50: continue
                w_c = weekly_df['Close'].iloc[-1]
                w_low = weekly_df['Low'].iloc[-1]
                w_high = weekly_df['High'].iloc[-1]
                w_20 = weekly_df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                w_50 = weekly_df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                
                # Monthly
                monthly_df = df.resample('ME').last().dropna()
                if len(monthly_df) < 50: continue
                m_c = monthly_df['Close'].iloc[-1]
                m_50 = monthly_df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]

                is_match = False
                trend_match = False

                # --- 1. CHECK PRIMARY TREND ---
                if "Bullish" in market_phase:
                    if "MEMA" in primary_trend and m_c > m_50: trend_match = True
                    elif "WEMA" in primary_trend and w_c > w_50: trend_match = True
                    elif "DEMA" in primary_trend and d_c > d_50: trend_match = True
                else:
                    if "MEMA" in primary_trend and m_c < m_50: trend_match = True
                    elif "WEMA" in primary_trend and w_c < w_50: trend_match = True
                    elif "DEMA" in primary_trend and d_c < d_50: trend_match = True

                # --- 2. CHECK SETUP TOUCH CONDITION ---
                if trend_match:
                    if "Bullish" in market_phase:
                        # Bullish Touch: Low goes below EMA, but Close stays above EMA
                        if active_setup == "50_WEMA_TOUCH" and w_low <= w_50 and w_c > w_50: is_match = True
                        elif active_setup == "50_DEMA_TOUCH" and d_low <= d_50 and d_c > d_50: is_match = True
                        elif active_setup == "Touch 20 WEMA" and w_low <= w_20 and w_c > w_20: is_match = True
                        elif active_setup == "Touch 20 DEMA" and d_low <= d_20 and d_c > d_20: is_match = True
                    else:
                        # Bearish Touch: High goes above EMA, but Close stays below EMA
                        if active_setup == "50_WEMA_TOUCH" and w_high >= w_50 and w_c < w_50: is_match = True
                        elif active_setup == "50_DEMA_TOUCH" and d_high >= d_50 and d_c < d_50: is_match = True
                        elif active_setup == "Touch 20 WEMA" and w_high >= w_20 and w_c < w_20: is_match = True
                        elif active_setup == "Touch 20 DEMA" and d_high >= d_20 and d_c < d_20: is_match = True

                # --- RECORD MATCH ---
                if is_match:
                    results.append({
                        "Ticker": ticker.replace(".NS", ""),
                        "Close Price": round(d_c, 2),
                        "Daily 20/50 EMA": f"{round(d_20, 2)} / {round(d_50, 2)}",
                        "Weekly 20/50 EMA": f"{round(w_20, 2)} / {round(w_50, 2)}",
                        "Monthly 50 EMA": round(m_50, 2)
                    })
            except Exception:
                continue
                
        time.sleep(1) # Prevent memory overload
                
    my_bar.empty()
    
    if results:
        st.success(f"Found {len(results)} stocks matching your strategy!")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("No stocks met this specific technical criteria at today's close.")
