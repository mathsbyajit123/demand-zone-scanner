import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

# --- PAGE SETUP ---
st.set_page_config(page_title="Pure Price Action Matrix", layout="wide", page_icon="🏛️")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #673AB7; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #607D8B; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🏛️ Pure Price Action S&R Matrix</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Zero Indicators. 100% Naked Chart Structural Zones mapped from HTF to LTF.</p>', unsafe_allow_html=True)

# --- LOAD SYMBOLS ---
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

# --- DATA FETCHING ---
@st.cache_data(show_spinner=False)
def fetch_data(tickers, matrix_mode):
    if matrix_mode == "1 Day -> 15 Min":
        period, interval = '60d', '15m'
    elif matrix_mode == "1 Week -> 1 Hour":
        period, interval = '730d', '1h'
    elif matrix_mode == "1 Month -> 1 Day":
        period, interval = '5y', '1d'
    else:  # 3 Month -> 1 Week
        period, interval = '10y', '1wk'
        
    return yf.download(tickers, period=period, interval=interval, group_by='ticker', threads=True, progress=False)

def build_htf(df, matrix_mode):
    if df.empty: return df
    
    if matrix_mode == "1 Day -> 15 Min":
        return df.resample('1D').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif matrix_mode == "1 Week -> 1 Hour":
        return df.resample('1W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif matrix_mode == "1 Month -> 1 Day":
        return df.resample('1ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif matrix_mode == "3 Month -> 1 Week":
        return df.resample('3ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    return df

# --- PURE PRICE ACTION ALGORITHM ---
def process_pure_structure(df_htf, df_ltf, target_type, width_pct):
    if len(df_htf) < 15: return None
        
    latest_close = df_ltf.iloc[-1]['Close']
    latest_high = df_ltf.iloc[-1]['High']
    latest_low = df_ltf.iloc[-1]['Low']
    
    # 1. Isolate Pure Swings (No Indicators, Just Raw Highs/Lows)
    peaks = df_htf.iloc[argrelextrema(df_htf['High'].values, np.greater_equal, order=5)[0]]['High'].values
    valleys = df_htf.iloc[argrelextrema(df_htf['Low'].values, np.less_equal, order=5)[0]]['Low'].values
    
    all_pivots = np.sort(np.concatenate((peaks, valleys)))
    if len(all_pivots) == 0: return None
        
    # 2. Cluster Swings into Thick Zones
    zones = []
    current_zone = [all_pivots[0]]
    
    for i in range(1, len(all_pivots)):
        if (all_pivots[i] - current_zone[0]) / current_zone[0] <= (width_pct / 100.0):
            current_zone.append(all_pivots[i])
        else:
            if len(current_zone) >= 3: # Demand at least 3 touches to prove it's a real structural zone
                zones.append({
                    'floor': min(current_zone),
                    'ceiling': max(current_zone),
                    'center': sum(current_zone) / len(current_zone)
                })
            current_zone = [all_pivots[i]]
            
    if len(current_zone) >= 3:
        zones.append({'floor': min(current_zone), 'ceiling': max(current_zone), 'center': sum(current_zone) / len(current_zone)})

    # 3. Evaluate LTF Entry Context
    for zone in zones:
        f, c = zone['floor'], zone['ceiling']
        
        if target_type == "Support / Demand (Buy)":
            # Is LTF price currently dipping into the HTF Support?
            if f * 0.99 <= latest_low <= c * 1.01:
                return f"LTF Entry: Inside HTF Support (₹{round(f,1)} - ₹{round(c,1)}) 🟢"
            # Did it break resistance and is now pulling back to test it as support?
            elif latest_close > c and latest_low <= c * 1.015:
                return f"Role Reversal: Testing New Support (₹{round(zone['center'],1)}) 🔄"
                
        elif target_type == "Resistance / Supply (Sell)":
            # Is LTF price currently rallying into the HTF Resistance?
            if f * 0.99 <= latest_high <= c * 1.01:
                return f"LTF Entry: Inside HTF Resistance (₹{round(f,1)} - ₹{round(c,1)}) 🔴"
            # Did it break support and is now pulling back up to test it as resistance?
            elif latest_close < f and latest_high >= f * 0.985:
                return f"Role Reversal: Testing New Resistance (₹{round(zone['center'],1)}) 🔄"
                
    return None

# --- UI CONTROL PANEL ---
with st.sidebar:
    st.header("1. Market Selection")
    index_choice = st.selectbox("Index Target", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY Midcap 100", "NIFTY Smallcap 250", "NIFTY 500"])
    
    st.divider()
    st.header("2. Structural Matrix")
    matrix_selection = st.selectbox("HTF Map -> LTF Entry", [
        "1 Day -> 15 Min",
        "1 Week -> 1 Hour",
        "1 Month -> 1 Day",
        "3 Month -> 1 Week"
    ])
    
    # Auto-adjust zone thickness based on timeframe size
    if "1 Day" in matrix_selection: default_width = 2.0
    elif "1 Week" in matrix_selection: default_width = 4.0
    elif "1 Month" in matrix_selection: default_width = 6.0
    else: default_width = 8.5 
        
    zone_width = st.slider("Zone Thickness Limit (%)", 0.5, 12.0, default_width)
    
    st.divider()
    st.header("3. Setup Direction")
    bias_direction = st.radio("Hunt For:", ["Support / Demand (Buy)", "Resistance / Supply (Sell)"])
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE NAKED SCAN", type="primary", use_container_width=True)

symbols_to_scan = load_symbols("NIFTY 50")[:10] if "Test" in index_choice else load_symbols(index_choice)

# --- EXECUTION SYSTEM ---
if run_scan:
    results = []
    
    with st.spinner(f"Pulling raw historical price action..."):
        raw_data = fetch_data(symbols_to_scan, matrix_selection)
        
    bar = st.progress(0, text="Calculating pure structural pivots...")
    total = len(symbols_to_scan)
    
    for idx, ticker in enumerate(symbols_to_scan):
        bar.progress((idx + 1) / total, text=f"Analyzing {ticker}...")
        
        try:
            if total > 1: df_base = raw_data[ticker].dropna()
            else: df_base = raw_data.dropna()
                
            if df_base.empty: continue
                
            df_ltf = df_base.copy()
            df_htf = build_htf(df_base, matrix_selection)
            
            status = process_pure_structure(df_htf, df_ltf, bias_direction, zone_width)
            
            if status:
                results.append({
                    "Ticker": ticker.replace('.NS', ''),
                    "Setup Found": status,
                    "LTF Current Price": round(df_ltf.iloc[-1]['Close'], 2)
                })
        except Exception:
            pass
            
    bar.empty()
    
    if results:
        df_display = pd.DataFrame(results)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(df_display)}** pure structural setups.")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No naked chart setups found matching this exact matrix right now.")
