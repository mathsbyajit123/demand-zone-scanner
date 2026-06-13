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

st.markdown('<p class="main-title">🏛️ Break & Retest PA Matrix</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Strict HTF-to-LTF structural zones with True Role Reversal detection.</p>', unsafe_allow_html=True)

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
def process_pure_structure(df_htf, df_ltf, target_type, min_width, max_width):
    if len(df_htf) < 15: return None
        
    latest_close = df_ltf.iloc[-1]['Close']
    latest_high = df_ltf.iloc[-1]['High']
    latest_low = df_ltf.iloc[-1]['Low']
    
    # 1. Isolate Pure Swings 
    peaks = df_htf.iloc[argrelextrema(df_htf['High'].values, np.greater_equal, order=5)[0]]['High'].values
    valleys = df_htf.iloc[argrelextrema(df_htf['Low'].values, np.less_equal, order=5)[0]]['Low'].values
    
    all_pivots = np.sort(np.concatenate((peaks, valleys)))
    if len(all_pivots) == 0: return None
        
    # 2. Cluster Swings into Thick Zones (Using Max Width as tolerance)
    zones = []
    current_zone = [all_pivots[0]]
    
    for i in range(1, len(all_pivots)):
        if (all_pivots[i] - current_zone[0]) / current_zone[0] <= (max_width / 100.0):
            current_zone.append(all_pivots[i])
        else:
            if len(current_zone) >= 3:
                zones.append({
                    'floor': min(current_zone),
                    'ceiling': max(current_zone),
                    'center': sum(current_zone) / len(current_zone)
                })
            current_zone = [all_pivots[i]]
            
    if len(current_zone) >= 3:
        zones.append({'floor': min(current_zone), 'ceiling': max(current_zone), 'center': sum(current_zone) / len(current_zone)})

    # 3. Evaluate LTF Entry Context & Filter by Width
    for zone in zones:
        f, c = zone['floor'], zone['ceiling']
        
        # Ensure the final zone size fits your strict Min/Max % rule
        actual_width_pct = ((c - f) / f) * 100
        # If zone is perfectly flat (0%), give it a tiny buffer to pass min check
        if actual_width_pct == 0: actual_width_pct = 0.1 
        if not (min_width <= actual_width_pct <= max_width): continue
        
        # Count structural history for Role Reversal checks
        zone_peaks = len([p for p in peaks if f * 0.99 <= p <= c * 1.01])
        zone_valleys = len([v for v in valleys if f * 0.99 <= v <= c * 1.01])
        
        if target_type == "Support / Demand (Buy)":
            # ROLE REVERSAL: Was it heavy resistance in the past? Did it break? Is it pulling back now?
            if zone_peaks >= 2 and latest_close > c and f * 0.98 <= latest_low <= c * 1.02:
                return f"Break & Retest: Old Resistance is now Support 🔄 (Zone: ₹{round(f,1)}-₹{round(c,1)})"
                
            # STANDARD SUPPORT: Price dipping into a floor
            elif zone_valleys >= 2 and f * 0.99 <= latest_low <= c * 1.01:
                return f"LTF Entry: Bouncing off HTF Support 🟢 (Zone: ₹{round(f,1)}-₹{round(c,1)})"
                
        elif target_type == "Resistance / Supply (Sell)":
            # ROLE REVERSAL: Was it heavy support in the past? Did it break down? Is it rallying back now?
            if zone_valleys >= 2 and latest_close < f and f * 0.98 <= latest_high <= c * 1.02:
                return f"Break & Retest: Old Support is now Resistance 🔄 (Zone: ₹{round(f,1)}-₹{round(c,1)})"
                
            # STANDARD RESISTANCE: Price rallying into a ceiling
            elif zone_peaks >= 2 and f * 0.99 <= latest_high <= c * 1.01:
                return f"LTF Entry: Rejecting at HTF Resistance 🔴 (Zone: ₹{round(f,1)}-₹{round(c,1)})"
                
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
    
    # Auto-adjust zone thickness defaults based on timeframe scale
    if "1 Day" in matrix_selection: def_min, def_max = 1.0, 3.0
    elif "1 Week" in matrix_selection: def_min, def_max = 3.0, 5.0
    elif "1 Month" in matrix_selection: def_min, def_max = 5.0, 7.0
    else: def_min, def_max = 7.0, 10.0
        
    st.markdown("**Zone Size Limits (%)**")
    zone_limits = st.slider("Min & Max Width", 0.1, 15.0, (def_min, def_max))
    min_w, max_w = zone_limits
    
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
            
            status = process_pure_structure(df_htf, df_ltf, bias_direction, min_w, max_w)
            
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
