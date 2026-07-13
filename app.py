import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="EMA Dynamics Scanner", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #10B981; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📈 Advanced EMA Proximity & Channel Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans precise price locations relative to the 10, 20, and 50 EMAs.</p>', unsafe_allow_html=True)

# --- DYNAMIC F&O & SECTOR EXTRACTION ENGINE ---
@st.cache_data(ttl=43200) # Cache for 12 hours
def get_sector_symbols(sector_name):
    if sector_name == "Live F&O Active Stocks":
        try:
            # Spoof a real browser to bypass NSE's basic bot protection
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/csv'
            }
            url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                df.columns = df.columns.str.strip()
                symbols = df['SYMBOL'].str.strip().unique()
                
                # Filter out broad indices, keep only equities
                indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
                return [str(sym) + ".NS" for sym in symbols if sym not in indices]
        except Exception:
            st.error("Failed to fetch live F&O list from NSE. Ensure you have an active internet connection.")
            return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"]

    # Standard Sector Lists
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    
    try:
        df = pd.read_csv(urls.get(sector_name, urls["NIFTY 50"]))
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"]

# --- CORE EMA MATH ENGINE ---
def analyze_ema_structure(ticker, period, interval, strategy, tol_pct, min_dist, max_dist):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 50:
            return None
            
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        df = df.ffill().dropna(subset=['Close'])
        
        if len(df) < 50:
            return None
            
        # Calculate EMAs
        ema_10 = df['Close'].ewm(span=10, min_periods=1, adjust=False).mean().iloc[-1]
        ema_20 = df['Close'].ewm(span=20, min_periods=1, adjust=False).mean().iloc[-1]
        ema_50 = df['Close'].ewm(span=50, min_periods=1, adjust=False).mean().iloc[-1]
        latest_close = df['Close'].iloc[-1]
        
        # Determine exact percentage distance from 20 EMA for tracking
        dist_20_pct = ((latest_close - ema_20) / ema_20) * 100
        abs_dist_20 = abs(dist_20_pct)
        
        match_found = False
        strategy_note = ""
        
        # Evaluate User Strategy
        if strategy == "Trapped Between 10 & 20 EMA":
            upper_bound = max(ema_10, ema_20)
            lower_bound = min(ema_10, ema_20)
            if lower_bound <= latest_close <= upper_bound:
                match_found = True
                strategy_note = "Price floating inside 10-20 Zone"
                
        elif strategy == "Trapped Between 20 & 50 EMA":
            upper_bound = max(ema_20, ema_50)
            lower_bound = min(ema_20, ema_50)
            if lower_bound <= latest_close <= upper_bound:
                match_found = True
                strategy_note = "Price floating inside 20-50 Zone"
                
        elif strategy == "Just Touching 20 EMA":
            if abs_dist_20 <= tol_pct:
                match_found = True
                strategy_note = f"Touching 20 EMA ({round(dist_20_pct, 2)}%)"
                
        elif strategy == "Far Away from 20 EMA (Custom %)":
            if min_dist <= abs_dist_20 <= max_dist:
                match_found = True
                dir_icon = "🟢 Above" if dist_20_pct > 0 else "🔴 Below"
                strategy_note = f"{dir_icon} 20 EMA by {round(abs_dist_20, 2)}%"

        if match_found:
            return {
                "Ticker": ticker.replace('.NS', ''),
                "Live Price": f"₹{round(latest_close, 2)}",
                "Strategy Trigger": strategy_note,
                "10 EMA": f"₹{round(ema_10, 2)}",
                "20 EMA": f"₹{round(ema_20, 2)}",
                "50 EMA": f"₹{round(ema_50, 2)}"
            }
            
        return None
        
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Index", ["Live F&O Active Stocks", "NIFTY 50", "NIFTY 500"])
    
    st.divider()
    st.header("2. Horizon (Timeframe)")
    tf_input = st.selectbox("Execution Chart:", ["Daily", "Weekly", "Monthly"])
    
    st.divider()
    st.header("3. EMA Setup Logic")
    strategy_input = st.radio("Select Strategy:", [
        "Trapped Between 10 & 20 EMA",
        "Trapped Between 20 & 50 EMA",
        "Just Touching 20 EMA",
        "Far Away from 20 EMA (Custom %)"
    ])
    
    # Show specific sliders only when their strategy is selected
    if strategy_input == "Just Touching 20 EMA":
        touch_tolerance = st.slider("Tolerance (± %)", 0.1, 2.0, 0.5, step=0.1, help="Max distance price can be from the 20 EMA to count as a touch.")
    else:
        touch_tolerance = 0.5 # Default fallback
        
    if strategy_input == "Far Away from 20 EMA (Custom %)":
        col1, col2 = st.columns(2)
        with col1:
            min_distance = st.number_input("Min % Away", min_value=0.1, max_value=20.0, value=1.0, step=0.5)
        with col2:
            max_distance = st.number_input("Max % Away", min_value=1.0, max_value=50.0, value=2.0, step=0.5)
    else:
        min_distance = 1.0
        max_distance = 2.0
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE EMA SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = get_sector_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** on the **{tf_input}** chart...")
    
    # Configure Timeframes
    tf_configs = {
        "Daily": {"period": "2y", "interval": "1d"},
        "Weekly": {"period": "5y", "interval": "1wk"},
        "Monthly": {"period": "10y", "interval": "1mo"}
    }
    active_cfg = tf_configs[tf_input]
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    # Threading for speed
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures_map = {
            executor.submit(
                analyze_ema_structure, ticker, 
                active_cfg["period"], active_cfg["interval"], 
                strategy_input, touch_tolerance, min_distance, max_distance
            ): ticker 
            for ticker in symbols_list
        }
        
        completed_count = 0
        for future in as_completed(futures_map):
            completed_count += 1
            result = future.result()
            if result:
                confirmed_setups.append(result)
            
            percent_complete = completed_count / len(symbols_list)
            progress_ui.progress(percent_complete, text=f"Evaluating EMA Proximity: {completed_count}/{len(symbols_list)}")
            
            # Anti-ban throttle
            if completed_count % 30 == 0:
                time.sleep(0.3)
            
    progress_ui.empty()
    
    # --- DISPLAY ANALYTICAL MATRIX SHEET ---
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks matching your exact EMA criteria.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks currently match this specific EMA logic on the {tf_input} timeframe. Try adjusting your tolerances.")
