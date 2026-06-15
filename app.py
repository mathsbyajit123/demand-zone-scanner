import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- PAGE SETUP ---
st.set_page_config(page_title="Quantitative EMA Matrix", layout="wide", page_icon="🧮")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #00C853; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #455A64; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🧮 Quantitative Distance Matrix Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Fully Customizable LTF Selection with Anti-Ban Throttling.</p>', unsafe_allow_html=True)

# --- MARKET SYMBOLS ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[category])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- CUSTOM TIMEFRAME RESAMPLER ---
def resample_data(df, timeframe):
    if df.empty: return df
    try:
        if timeframe == '30m':
            return df.resample('30min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '1h':
            return df.resample('60min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '75m':
            return df.resample('75min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '1W':
            return df.resample('1W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '1M':
            return df.resample('1ME').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    except Exception:
        pass
    return df

def calculate_ema_distance(df):
    if df is None or len(df) < 20: return None 
    ema_50 = df['Close'].ewm(span=50, min_periods=20, adjust=False).mean().iloc[-1]
    latest_close = df['Close'].iloc[-1]
    distance_pct = ((latest_close - ema_50) / ema_50) * 100
    return round(distance_pct, 2)

def format_distance(dist, tolerance):
    if dist is None: return "N/A"
    if abs(dist) <= tolerance:
        return f"🎯 {dist}% (Touch)"
    elif dist > 0:
        return f"🔼 +{dist}%"
    else:
        return f"🔽 {dist}%"

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (5 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Macro Trend Zone (HTF)")
    htf_selection = st.selectbox("Select Master Trend TF:", ["1 Day", "1 Week", "1 Month"])
    htf_min_pct = st.number_input("Minimum % Above", min_value=0.1, max_value=20.0, value=2.0, step=0.5)
    htf_max_pct = st.number_input("Maximum % Above", min_value=1.0, max_value=80.0, value=30.0, step=0.5)
    
    st.divider()
    st.header("3. Micro Pullback Zone (LTF)")
    
    # --- NEW: USER SELECTABLE LTF OPTIONS ---
    ltf_options = st.multiselect(
        "Select LTF Pullback Targets to Scan:",
        ["15m", "30m", "1h", "75m", "1D", "1W"],
        default=["15m", "30m", "75m", "1D"]
    )
    
    pullback_tolerance = st.slider("Approach Tolerance (± %)", 0.1, 5.0, 1.0, step=0.1)
    
    st.divider()
    st.header("4. Engine Mode")
    strict_mode = st.checkbox("Strict Mode: ONLY show stocks touching a LTF Pullback", value=False)
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE DISTANCE SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:5] if "Test" in selected_sector else load_symbols(selected_sector)

# --- LIVE PROCESSING ENGINE ---
if run_scan:
    if not ltf_options:
        st.error("Please select at least one LTF Pullback Target from the sidebar.")
    else:
        scanned_opportunities = []
        
        st.info("🔄 Initiating Anti-Ban Engine with Custom LTFs...")
        execution_progress = st.progress(0, text="Igniting engine...")
        
        total_symbols = len(target_symbols)
        
        for idx, ticker in enumerate(target_symbols):
            clean_ticker = ticker.replace('.NS', '')
            execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing {clean_ticker}...")
            
            try:
                time.sleep(0.5) # Anti-ban throttle
                
                df_15m_base = yf.download(ticker, period='60d', interval='15m', progress=False, show_errors=False)
                df_daily_base = yf.download(ticker, period='10y', interval='1d', progress=False, show_errors=False)
                
                if df_15m_base.empty or df_daily_base.empty:
                    execution_progress.progress((idx + 1) / total_symbols, text=f"⚠️ API Limit! Cooling down 10s...")
                    time.sleep(10)
                    continue
                
                df_15m_base = df_15m_base.dropna(subset=['Close'])
                df_daily_base = df_daily_base.dropna(subset=['Close'])
                
                if len(df_15m_base) < 20 or len(
