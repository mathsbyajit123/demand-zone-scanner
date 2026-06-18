import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Production Fractal Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #059669; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ Production-Grade Institutional Fractal Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Asynchronous Multithreaded Engine. Sweeps entire sectors across parallel data pathways simultaneously.</p>', unsafe_allow_html=True)

# --- REAL-TIME MULTI-SECTOR LOADER ---
@st.cache_data(ttl=86400)
def get_sector_symbols(sector_name):
    urls = {
        "NIFTY 50 (Large Cap)": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY Smallcap 100": "https://archives.nseindia.com/content/indices/ind_niftysmallcap100list.csv",
        "NIFTY 500 (All Sectors)": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[sector_name])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        st.error("NSE Server Timeout. Loading backup core liquidity tickers...")
        return ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- INTERNAL 75m AGGREGATOR ---
def convert_to_75m(df_15m):
    if df_15m is None or df_15m.empty:
        return None
    df_15m['Date_Str'] = df_15m.index.strftime('%Y-%m-%d')
    df_15m['Bar_Chunk'] = df_15m.groupby('Date_Str').cumcount() // 5
    resampled = df_15m.groupby(['Date_Str', 'Bar_Chunk']).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).reset_index(drop=True)
    timestamps = df_15m.groupby(['Date_Str', 'Bar_Chunk']).index.last().reset_index(drop=True)
    resampled.index = timestamps
    return resampled

# --- MATHEMATICAL S/R FLIP CORING ENGINE ---
def analyze_stock_structure(ticker, config, tf_choice, tolerance):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=config["period"], interval=config["interval"])
        
        if df.empty:
            return None
            
        if tf_choice == "75 Min":
            df = convert_to_75m(df)
            
        if df is None or len(df) < 20:
            return None
            
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        latest_close = df['Close'].iloc[-1]
        
        # Structure Scanning Math: Define historical vs immediate boundaries
        historical_canvas = df.iloc[:-5]
        recent_canvas = df.iloc[-5:]
        
        historical_ceiling = historical_canvas['High'].max()
        recent_peak = recent_canvas['High'].max()
        
        is_breakout = recent_peak > historical_ceiling
        distance_to_floor = ((latest_close - historical_ceiling) / historical_ceiling) * 100
        
        if is_breakout and (abs(distance_to_floor) <= tolerance) and (latest_close >= historical_ceiling * 0.99):
            return {
                "Ticker": ticker.replace('.NS', ''),
                "Live Price": round(latest_close, 2),
                "Institutional Floor": round(historical_ceiling, 2),
                "Proximity": f"{round(distance_to_floor, 2)}%",
                "Signal Strength": "🔥 HIGH CONFLUENCE" if recent_canvas['Volume'].max() > (historical_canvas['Volume'].mean() * 2) else "STANDARD"
            }
    except Exception:
        return None
    return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Market Sector")
    sector_input = st.selectbox("Select NSE Sector Universe:", [
        "NIFTY 50 (Large Cap)", "NIFTY Next 50", "NIFTY Bank", "NIFTY IT", 
        "NIFTY Midcap 100", "NIFTY Smallcap 100", "NIFTY 500 (All Sectors)"
    ])
    
    st.divider()
    st.header("2. Fractal Frame Scale")
    timeframe_input = st.selectbox("Select Core Horizon:", [
        "15 Min", "75 Min", "Daily", "Weekly", "Monthly"
    ], index=2)
    
    st.divider()
    st.header("3. Mathematical Bounds")
    proximity_slider = st.slider("Max Distance From S/R Floor (%)", 0.5, 4.0, 1.5, step=0.1)
    threads_count = st.slider("Parallel Server Workers", 10, 30, 20, step=5, help="Higher values speed up execution but require more bandwidth.")
    
    st.divider()
    execute_button = st.button("🚀 LAUNCH REAL-TIME PARALLEL SCAN", type="primary", use_container_width=True)

# --- EXECUTION CONTROL CONTROLLER ---
if execute_button:
    symbols_list = get_sector_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** inside **{sector_input}** on a **{timeframe_input}** structural matrix...")
    
    tf_mapping = {
        "15 Min": {"period": "30d", "interval": "15m"},
        "75 Min": {"period": "30d", "interval": "15m"},
        "Daily": {"period": "1y", "interval": "1d"},
        "Weekly": {"period": "2y", "interval": "1wk"},
        "Monthly": {"period": "5y", "interval": "1mo"}
    }
    
    active_cfg = tf_mapping[timeframe_input]
    confirmed_setups = []
    
    # --- ASYNCHRONOUS MULTITHREADING PIPELINE ---
    progress_ui = st.progress(0, text="Spawning parallel matrix tracks...")
    
    with ThreadPoolExecutor(max_workers=threads_count) as executor:
        futures_map = {
            executor.submit(analyze_stock_structure, ticker, active_cfg, timeframe_input, proximity_slider): ticker 
            for ticker in symbols_list
        }
        
        completed_count = 0
        for future in as_completed(futures_map):
            completed_count += 1
            result = future.result()
            if result:
                confirmed_setups.append(result)
            
            # Update the progress bar dynamically as parallel threads return data
            percent_complete = completed_count / len(symbols_list)
            progress_ui.progress(percent_complete, text=f"Parallel Execution Stream: {completed_count}/{len(symbols_list)} Processed")
            
    progress_ui.empty()
    
    # --- DISPLAY ANALYTICAL MATRIX SHEET ---
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Verified Real Scan Complete: Isolated **{len(results_df)}** valid structural setups.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks in **{sector_input}** are currently pulling back to valid structure on the **{timeframe_input}** framework. Try increasing the proximity slider.")
