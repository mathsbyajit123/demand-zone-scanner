import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="HTF Matrix S&R Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 36px; font-weight: 800; color: #009688; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #78909C; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 Multi-Timeframe Matrix Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Tracks institutional Higher Timeframe (HTF) horizontal zones matching specific entry execution parameters.</p>', unsafe_allow_html=True)

# --- INDEX SYMBOL DOWNLOAD ---
@st.cache_data(ttl=86400)
def load_symbols(index_name):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY Smallcap 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[index_name])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "TCS.NS", "CIPLA.NS", "INFY.NS", "SBIN.NS"]

# --- DYNAMIC DATA RETRIEVAL ---
@st.cache_data(show_spinner=False)
def fetch_matrix_data(tickers, htf_selection):
    # Select optimized intervals based on yfinance performance limitations
    if htf_selection == "1 Day -> 15 Min":
        period, interval = '60d', '15m'
    elif htf_selection == "1 Week -> 1 Hour":
        period, interval = '730d', '1h'
    elif htf_selection == "1 Month -> 1 Day":
        period, interval = '5y', '1d'
    else:  # 3 Month -> 1 Week
        period, interval = '10y', '1wk'
        
    data = yf.download(tickers, period=period, interval=interval, group_by='ticker', threads=True, progress=False)
    return data

def build_htf_dataframe(df_source, htf_selection):
    """Derives the primary Higher Timeframe structure from incoming marketplace streams."""
    if df_source.empty:
        return pd.DataFrame()
        
    if htf_selection == "1 Day -> 15 Min":
        # Group intraday 15-minute intervals to complete Day structures
        return df_source.resample('1D').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif htf_selection == "1 Week -> 1 Hour":
        return df_source.resample('1W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif htf_selection == "1 Month -> 1 Day":
        return df_source.resample('1ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif htf_selection == "3 Month -> 1 Week":
        return df_source.resample('3ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    return df_source

# --- MATRICES LOGIC ENGINE ---
def process_structural_zones(df_htf, df_ltf, matrix_type, width_pct, lookback=5):
    if len(df_htf) < 15: 
        return None
        
    latest_close = df_ltf.iloc[-1]['Close']
    latest_high = df_ltf.iloc[-1]['High']
    latest_low = df_ltf.iloc[-1]['Low']
    
    # Isolate key market turns (structural highs and lows)
    high_pivots = df_htf.iloc[argrelextrema(df_htf['High'].values, np.greater_equal, order=lookback)[0]]['High'].values
    low_pivots = df_htf.iloc[argrelextrema(df_htf['Low'].values, np.less_equal, order=lookback)[0]]['Low'].values
    
    all_pivots = np.sort(np.concatenate((high_pivots, low_pivots)))
    if len(all_pivots) == 0: 
        return None
        
    # Group neighboring turn keys into unified horizontal zones
    zones = []
    active_cluster = [all_pivots[0]]
    
    for i in range(1, len(all_pivots)):
        if (all_pivots[i] - active_cluster[0]) / active_cluster[0] <= (width_pct / 100.0):
            active_cluster.append(all_pivots[i])
        else:
            if len(active_cluster) >= 3:
                zones.append({
                    'floor': min(active_cluster),
                    'ceiling': max(active_cluster),
                    'center': sum(active_cluster) / len(active_cluster),
                    'touches': len(active_cluster)
                })
            active_cluster = [all_pivots[i]]
            
    if len(active_cluster) >= 3:
        zones.append({
            'floor': min(active_cluster), 
            'ceiling': max(active_cluster), 
            'center': sum(active_cluster) / len(active_cluster),
            'touches': len(active_cluster)
        })

    # Validate structural setups against the selected mode
    for zone in zones:
        f, c = zone['floor'], zone['ceiling']
        
        if matrix_type == "Bullish Setups (Support)":
            # Verification: Price hovering just inside or interacting directly with the base floor
            if f * 0.99 <= latest_low <= c * 1.01:
                return f"Testing HTF Support Zone (₹{round(f,1)} - ₹{round(c,1)})"
            elif latest_close > c and latest_low <= c * 1.015:
                return f"Role Reversal / Confirmed Support Bounce (Zone Center: ₹{round(zone['center'],1)})"
                
        elif matrix_type == "Bearish Setups (Resistance)":
            # Verification: Price encountering ceiling friction or showing breakout rejection signs
            if f * 0.99 <= latest_high <= c * 1.01:
                return f"Testing HTF Resistance Zone (₹{round(f,1)} - ₹{round(c,1)})"
            elif latest_close < f and latest_high >= f * 0.985:
                return f"Confirmed Resistance Rejection (Zone Center: ₹{round(zone['center'],1)})"
                
    return None

# --- CONTROL PANEL ---
with st.sidebar:
    st.header("1. Universe Selection")
    index_choice = st.selectbox("Market Target", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY Midcap 100", "NIFTY Smallcap 250", "NIFTY 500"])
    
    st.divider()
    st.header("2. Timeframe Matrix Configuration")
    matrix_selection = st.selectbox("Select HTF -> LTF Framework", [
        "1 Day -> 15 Min",
        "1 Week -> 1 Hour",
        "1 Month -> 1 Day",
        "3 Month -> 1 Week"
    ])
    
    # Assign specific adaptive zone boundaries based on your parameters
    if "1 Day" in matrix_selection:
        default_width = 2.0  # 1% to 3% spectrum
    elif "1 Week" in matrix_selection:
        default_width = 4.0  # 3% to 5% spectrum
    elif "1 Month" in matrix_selection:
        default_width = 6.0  # 5% to 7% spectrum
    else:
        default_width = 8.5  # Macro 7% to 10% spectrum
        
    zone_width = st.slider("Target HTF Zone Width (%)", 0.5, 12.0, default_width, help="Matches structure width parameters to the chosen scale.")
    
    st.divider()
    st.header("3. Market Direction")
    bias_direction = st.radio("Scan Target Direction", ["Bullish Setups (Support)", "Bearish Setups (Resistance)"])
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE MATRIX SCAN", type="primary", use_container_width=True)

# Process symbols
symbols_to_scan = load_symbols("NIFTY 50")[:10] if "Test" in index_choice else load_symbols(index_choice)

# --- PROCESSING SYSTEM ---
if run_scan:
    scanned_results = []
    
    with st.spinner(f"Acquiring required background price charts for analysis..."):
        historical_dataset = fetch_matrix_data(symbols_to_scan, matrix_selection)
        
    progress_bar = st.progress(0, text="Deconstructing structural key levels...")
    total_assets = len(symbols_to_scan)
    
    for idx, ticker in enumerate(symbols_to_scan):
        progress_bar.progress((idx + 1) / total_assets, text=f"Processing multi-timeframe maps for {ticker}...")
        
        try:
            # Extract standard tracking parameters per symbol
            if total_assets > 1:
                df_base = historical_dataset[ticker].dropna()
            else:
                df_base = historical_dataset.dropna()
                
            if df_base.empty:
                continue
                
            # Isolate the high resolution execution dataframe (Lower Timeframe)
            df_ltf = df_base.copy()
            
            # Formulate the major structural trend baseline (Higher Timeframe)
            df_htf = build_htf_dataframe(df_base, matrix_selection)
            
            # Find matching criteria
            findings = process_structural_zones(df_htf, df_ltf, bias_direction, zone_width)
            
            if findings:
                scanned_results.append({
                    "Ticker Symbol": ticker.replace('.NS', ''),
                    "Identified Scenario": findings,
                    "LTF Entry Price": round(df_ltf.iloc[-1]['Close'], 2)
                })
        except Exception:
            pass
            
    progress_bar.empty()
    
    # Display performance outcomes
    if scanned_results:
        display_dataframe = pd.DataFrame(scanned_results)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(display_dataframe)}** clear institutional set-ups.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No assets matching the structural criteria were found on the {matrix_selection} scale right now.")
