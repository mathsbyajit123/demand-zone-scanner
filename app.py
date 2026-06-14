import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from scipy.stats import linregress

# --- PAGE SETUP ---
st.set_page_config(page_title="Advanced Confluence Scanner", layout="wide", page_icon="📐")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #E65100; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #607D8B; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📐 Trendline & Zonal Confluence Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Hunts for exact intersections where Diagonal Trendlines meet Horizontal Zones.</p>', unsafe_allow_html=True)

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
        return ["BIOCON.NS", "RELIANCE.NS", "TCS.NS", "CIPLA.NS", "SBIN.NS"]

# --- DATA FETCHING ---
@st.cache_data(show_spinner=False)
def fetch_data(tickers, matrix_mode):
    if matrix_mode == "1 Day -> 15 Min": period, interval = '60d', '15m'
    elif matrix_mode == "1 Week -> 1 Hour": period, interval = '730d', '1h'
    elif matrix_mode == "1 Month -> 1 Day": period, interval = '5y', '1d'
    else: period, interval = '10y', '1wk'
        
    return yf.download(tickers, period=period, interval=interval, group_by='ticker', threads=True, progress=False)

def build_htf(df, matrix_mode):
    if df.empty: return df
    if matrix_mode == "1 Day -> 15 Min": return df.resample('1D').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif matrix_mode == "1 Week -> 1 Hour": return df.resample('1W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif matrix_mode == "1 Month -> 1 Day": return df.resample('1ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif matrix_mode == "3 Month -> 1 Week": return df.resample('3ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    return df

# --- PURE PRICE ACTION ALGORITHM ---
def process_confluence(df_htf, df_ltf, target_type, min_width, max_width):
    if len(df_htf) < 20: return None
        
    latest_close = df_ltf.iloc[-1]['Close']
    latest_high = df_ltf.iloc[-1]['High']
    latest_low = df_ltf.iloc[-1]['Low']
    current_idx = len(df_htf) - 1
    
    # 1. Isolate Pure Swings (Pivots)
    peak_indices = argrelextrema(df_htf['High'].values, np.greater_equal, order=5)[0]
    valley_indices = argrelextrema(df_htf['Low'].values, np.less_equal, order=5)[0]
    
    if len(peak_indices) < 3 or len(valley_indices) < 3: return None
    
    peaks = df_htf.iloc[peak_indices]['High'].values
    valleys = df_htf.iloc[valley_indices]['Low'].values
    
    # 2. HORIZONTAL ZONES (Clustering)
    all_pivots = np.sort(np.concatenate((peaks, valleys)))
    zones = []
    current_zone = [all_pivots[0]]
    
    for i in range(1, len(all_pivots)):
        if (all_pivots[i] - current_zone[0]) / current_zone[0] <= (max_width / 100.0):
            current_zone.append(all_pivots[i])
        else:
            if len(current_zone) >= 2:
                zones.append({'floor': min(current_zone), 'ceiling': max(current_zone)})
            current_zone = [all_pivots[i]]
    if len(current_zone) >= 2:
        zones.append({'floor': min(current_zone), 'ceiling': max(current_zone)})

    # 3. DIAGONAL TRENDLINES (Linear Regression on last 3-4 pivots)
    # Valleys for Support Trendline
    recent_valley_idx = valley_indices[-4:]
    recent_valleys = valleys[-4:]
    slope_sup, intercept_sup, r_val_sup, _, _ = linregress(recent_valley_idx, recent_valleys)
    projected_trend_support = (slope_sup * current_idx) + intercept_sup
    
    # Peaks for Resistance Trendline
    recent_peak_idx = peak_indices[-4:]
    recent_peaks = peaks[-4:]
    slope_res, intercept_res, r_val_res, _, _ = linregress(recent_peak_idx, recent_peaks)
    projected_trend_resistance = (slope_res * current_idx) + intercept_res

    # 4. EVALUATE SETUP (Confluence)
    for zone in zones:
        f, c = zone['floor'], zone['ceiling']
        actual_width_pct = ((c - f) / f) * 100
        if actual_width_pct == 0: actual_width_pct = 0.1 
        if not (min_width <= actual_width_pct <= max_width): continue
        
        if target_type == "Support / Demand (Buy)":
            # Is price near Horizontal Support?
            near_horiz_sup = f * 0.98 <= latest_low <= c * 1.02
            # Is price near Diagonal Trendline Support?
            near_trend_sup = projected_trend_support * 0.98 <= latest_low <= projected_trend_support * 1.02
            
            if near_horiz_sup and near_trend_sup and slope_sup > 0:
                return f"🔥 PERFECT CONFLUENCE: Horizontal Zone (₹{round(f,1)}) + Ascending Trendline"
            elif near_horiz_sup:
                return f"Horizontal Support Zone Bounce (₹{round(f,1)}-₹{round(c,1)})"
            elif near_trend_sup and slope_sup > 0:
                return f"Ascending Trendline Support Bounce (₹{round(projected_trend_support, 1)})"
                
        elif target_type == "Resistance / Supply (Sell)":
            # Is price near Horizontal Resistance?
            near_horiz_res = f * 0.98 <= latest_high <= c * 1.02
            # Is price near Diagonal Trendline Resistance?
            near_trend_res = projected_trend_resistance * 0.98 <= latest_high <= projected_trend_resistance * 1.02
            
            if near_horiz_res and near_trend_res and slope_res < 0:
                return f"🔥 PERFECT CONFLUENCE: Horizontal Zone (₹{round(c,1)}) + Descending Trendline"
            elif near_horiz_res:
                return f"Horizontal Resistance Zone Rejection (₹{round(f,1)}-₹{round(c,1)})"
            elif near_trend_res and slope_res < 0:
                return f"Descending Trendline Resistance Rejection (₹{round(projected_trend_resistance, 1)})"
                
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
    
    if "1 Day" in matrix_selection: def_min, def_max = 1.0, 3.0
    elif "1 Week" in matrix_selection: def_min, def_max = 3.0, 5.0
    elif "1 Month" in matrix_selection: def_min, def_max = 5.0, 7.0
    else: def_min, def_max = 7.0, 10.0
        
    st.markdown("**Horizontal Zone Limits (%)**")
    zone_limits = st.slider("Min & Max Width", 0.1, 15.0, (def_min, def_max))
    min_w, max_w = zone_limits
    
    st.divider()
    st.header("3. Setup Direction")
    bias_direction = st.radio("Hunt For:", ["Support / Demand (Buy)", "Resistance / Supply (Sell)"])
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE CONFLUENCE SCAN", type="primary", use_container_width=True)

symbols_to_scan = load_symbols("NIFTY 50")[:10] if "Test" in index_choice else load_symbols(index_choice)

# --- EXECUTION SYSTEM ---
if run_scan:
    results = []
    
    with st.spinner(f"Calculating diagonal slopes and horizontal grids..."):
        raw_data = fetch_data(symbols_to_scan, matrix_selection)
        
    bar = st.progress(0, text="Processing geometrical confluences...")
    total = len(symbols_to_scan)
    
    for idx, ticker in enumerate(symbols_to_scan):
        bar.progress((idx + 1) / total, text=f"Analyzing {ticker}...")
        
        try:
            if total > 1: df_base = raw_data[ticker].dropna()
            else: df_base = raw_data.dropna()
                
            if df_base.empty: continue
                
            df_ltf = df_base.copy()
            df_htf = build_htf(df_base, matrix_selection)
            
            status = process_confluence(df_htf, df_ltf, bias_direction, min_w, max_w)
            
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
        st.success(f"🎯 Analysis Complete! Uncovered **{len(df_display)}** structural setups.")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No naked chart setups found matching this exact matrix right now.")
