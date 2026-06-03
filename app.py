import streamlit as st
import yfinance as yf
import pandas as pd
import time

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Fractal EMA Screener", layout="wide")
st.title("📈 Advanced Multi-Timeframe EMA Screener")
st.write("Dynamic timeframe auto-selection for precise pullbacks (Monthly -> Weekly -> Daily -> 15m).")

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

# 1. Index Selection
selected_index = st.sidebar.selectbox("1. Select Index", ["Nifty 50", "Nifty 500", "Nifty Midcap 100", "Nifty Smallcap 250"])

# 2. Market Phase
market_phase = st.sidebar.radio("2. Market Phase", ["Bullish (Uptrend)", "Bearish (Downtrend)"])
is_bull = "Bullish" in market_phase

# 3. Primary Trend Selection
st.sidebar.markdown("### 3. Primary Trend")
if is_bull:
    primary_trend = st.sidebar.radio("Select Anchor Trend", [
        "Price > 50 Monthly EMA",
        "Price > 50 Weekly EMA",
        "Price > 50 Daily EMA"
    ])
else:
    primary_trend = st.sidebar.radio("Select Anchor Trend", [
        "Price < 50 Monthly EMA",
        "Price < 50 Weekly EMA",
        "Price < 50 Daily EMA"
    ])

# 4. Dynamic Pullback Sub-Menu
st.sidebar.markdown("### 4. Pullback Setup (Auto-Selected TF)")

if "Monthly" in primary_trend:
    tf_primary = "Monthly"
    tf_pullback = "Weekly"
    st.sidebar.info("📉 Pullback TF: **Weekly**")
    setup_choice = st.sidebar.radio("Select Setup:", [
        "a). Price touches 50 EMA in Weekly timeframe",
        "b). Price within 20 EMA and 50 EMA zone in Weekly timeframe"
    ])
elif "Weekly" in primary_trend:
    tf_primary = "Weekly"
    tf_pullback = "Daily"
    st.sidebar.info("📉 Pullback TF: **Daily**")
    setup_choice = st.sidebar.radio("Select Setup:", [
        "a). Price touches 50 EMA in Daily timeframe",
        "b). Price within 20 EMA and 50 EMA zone in Daily timeframe"
    ])
else:
    tf_primary = "Daily"
    tf_pullback = "15m"
    st.sidebar.info("📉 Pullback TF: **15 Minute**")
    setup_choice = st.sidebar.radio("Select Setup:", [
        "a). Price touches 50 EMA in 15 Min timeframe",
        "b). Price within 20 EMA and 50 EMA zone in 15 Min timeframe"
    ])

is_touch_setup = "touches" in setup_choice

# --- MAIN SCANNER LOGIC ---
if st.sidebar.button("Run Fast Scanner"):
    tickers = get_nifty_tickers(selected_index)
    if not tickers:
        st.stop()
        
    st.info(f"Scanning {len(tickers)} stocks for {tf_primary} Trend + {tf_pullback} Pullback...")
    
    results = []
    my_bar = st.progress(0, text="Starting scan...")
    
    chunk_size = 100 
    total_chunks = (len(tickers) // chunk_size) + 1
    
    # Determine how much daily data we need based on Primary Trend
    if tf_primary == "Monthly": period_1d = "5y"
    elif tf_primary == "Weekly": period_1d = "2y"
    else: period_1d = "1y"
    
    for chunk_idx in range(total_chunks):
        start_idx = chunk_idx * chunk_size
        end_idx = min(start_idx + chunk_size, len(tickers))
        current_batch = tickers[start_idx:end_idx]
        
        if not current_batch: break
            
        my_bar.progress(chunk_idx / total_chunks, text=f"Downloading batch {chunk_idx + 1} of {total_chunks}...")
        
        # Download Daily Data (needed for all setups to establish anchor trends)
        data_1d = yf.download(current_batch, period=period_1d, interval="1d", group_by="ticker", threads=True, progress=False)
        
        # Download 15m Data ONLY if needed (saves memory and prevents timeouts)
        data_15m = None
        if tf_pullback == "15m":
            data_15m = yf.download(current_batch, period="60d", interval="15m", group_by="ticker", threads=True, progress=False)
        
        for ticker in current_batch:
            try:
                df_1d = extract_data(data_1d, ticker)
                if len(df_1d) < 50: continue
                
                is_match = False
                trend_match = False
                
                # --- CALCULATE REQUIRED TIMEFRAMES ---
                
                if tf_primary == "Monthly":
                    # Monthly Trend
                    df_m = df_1d.resample('ME').last().dropna()
                    if len(df_m) < 50: continue
                    m_c = df_m['Close'].iloc[-1]
                    m_50 = df_m['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                    
                    if is_bull and m_c > m_50: trend_match = True
                    elif not is_bull and m_c < m_50: trend_match = True
                        
                    # Weekly Pullback
                    if trend_match:
                        df_w = df_1d.resample('W-FRI').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
                        w_c, w_l, w_h = df_w['Close'].iloc[-1], df_w['Low'].iloc[-1], df_w['High'].iloc[-1]
                        w_50 = df_w['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                        w_20 = df_w['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                        
                        if is_bull:
                            if is_touch_setup and w_l <= w_50 and w_c > w_50: is_match = True
                            elif not is_touch_setup and w_50 < w_c < w_20: is_match = True
                        else:
                            if is_touch_setup and w_h >= w_50 and w_c < w_50: is_match = True
                            elif not is_touch_setup and w_50 > w_c > w_20: is_match = True

                elif tf_primary == "Weekly":
                    # Weekly Trend
                    df_w = df_1d.resample('W-FRI').last().dropna()
                    if len(df_w) < 50: continue
                    w_c = df_w['Close'].iloc[-1]
                    w_50 = df_w['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                    
                    if is_bull and w_c > w_50: trend_match = True
                    elif not is_bull and w_c < w_50: trend_match = True
                        
                    # Daily Pullback
                    if trend_match:
                        d_c, d_l, d_h = df_1d['Close'].iloc[-1], df_1d['Low'].iloc[-1], df_1d['High'].iloc[-1]
                        d_50 = df_1d['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                        d_20 = df_1d['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                        
                        if is_bull:
                            if is_touch_setup and d_l <= d_50 and d_c > d_50: is_match = True
                            elif not is_touch_setup and d_50 < d_c < d_20: is_match = True
                        else:
                            if is_touch_setup and d_h >= d_50 and d_c < d_50: is_match = True
                            elif not is_touch_setup and d_50 > d_c > d_20: is_match = True

                elif tf_primary == "Daily":
                    # Daily Trend
                    d_c = df_1d['Close'].iloc[-1]
                    d_50 = df_1d['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                    
                    if is_bull and d_c > d_50: trend_match = True
                    elif not is_bull and d_c < d_50: trend_match = True
                        
                    # 15m Pullback
                    if trend_match and data_15m is not None:
                        df_15 = extract_data(data_15m, ticker)
                        if len(df_15) < 50: continue
                        
                        c_15, l_15, h_15 = df_15['Close'].iloc[-1], df_15['Low'].iloc[-1], df_15['High'].iloc[-1]
                        ema50_15 = df_15['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                        ema20_15 = df_15['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                        
                        if is_bull:
                            if is_touch_setup and l_15 <= ema50_15 and c_15 > ema50_15: is_match = True
                            elif not is_touch_setup and ema50_15 < c_15 < ema20_15: is_match = True
                        else:
                            if is_touch_setup and h_15 >= ema50_15 and c_15 < ema50_15: is_match = True
                            elif not is_touch_setup and ema50_15 > c_15 > ema20_15: is_match = True

                # --- RECORD MATCH ---
                if is_match:
                    results.append({
                        "Ticker": ticker.replace(".NS", ""),
                        "Primary Trend": f"Matched ({tf_primary})",
                        "Pullback Setup": f"Matched ({tf_pullback})",
                        "Current Price": round(df_1d['Close'].iloc[-1], 2)
                    })
            except Exception:
                continue
                
        time.sleep(0.5) # Protect server RAM
                
    my_bar.empty()
    
    if results:
        st.success(f"Found {len(results)} perfect setups!")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("No stocks met this exact fractal criteria right now.")
