import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from scipy.stats import linregress

# --- PAGE ARCHITECTURE & UI STYLING ---
st.set_page_config(page_title="Institutional Trap Matrix Engine", layout="wide", page_icon="🪤")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #0288D1; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #546E7A; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🪤 Dual-Structure Liquidity Sweep Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Tracks institutional traps across matching Horizontal Zones and Diagonal Trendlines simultaneously.</p>', unsafe_allow_html=True)

# --- SECURITIES DIRECTORY RETRIEVAL ---
@st.cache_data(ttl=86400)
def load_market_symbols(index_name):
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
        return ["BHARTIARTL.NS", "BIOCON.NS", "TATASTEEL.NS", "RELIANCE.NS", "SBIN.NS"]

# --- MULTI-TIMEFRAME DATA PIPELINE ---
@st.cache_data(show_spinner=False)
def fetch_framework_datasets(tickers, structural_matrix):
    if structural_matrix == "Weekly HTF -> Daily LTF":
        df_htf = yf.download(tickers, period='5y', interval='1wk', group_by='ticker', threads=True, progress=False)
        df_ltf = yf.download(tickers, period='1y', interval='1d', group_by='ticker', threads=True, progress=False)
    else: # Monthly HTF -> Daily/Weekly LTF Framework
        df_htf = yf.download(tickers, period='10y', interval='1mo', group_by='ticker', threads=True, progress=False)
        df_ltf = yf.download(tickers, period='3y', interval='1d', group_by='ticker', threads=True, progress=False)
    return df_htf, df_ltf

# --- COMPREHENSIVE SWEEP ANALYSIS ENGINE ---
def execute_sweep_analysis(df_htf, df_ltf, system_bias, min_zone_w, max_zone_w):
    if len(df_htf) < 25 or len(df_ltf) < 5:
        return None
        
    latest_ltf_close = df_ltf.iloc[-1]['Close']
    latest_ltf_high = df_ltf.iloc[-1]['High']
    latest_ltf_low = df_ltf.iloc[-1]['Low']
    
    current_htf_idx = len(df_htf) - 1
    
    # 1. Map Out Major Swing Points (Pivots) on HTF
    peak_points = argrelextrema(df_htf['High'].values, np.greater_equal, order=5)[0]
    valley_points = argrelextrema(df_htf['Low'].values, np.less_equal, order=5)[0]
    
    # =========================================================================
    # CONDITION A: DIAGONAL TRENDLINE GEOMETRY
    # =========================================================================
    if system_bias == "Bullish Sweeps (Support)" and len(valley_points) >= 2:
        v_idx = valley_points[-2:]
        v_vals = df_htf.iloc[v_idx]['Low'].values
        slope, intercept, _, _, _ = linregress(v_idx, v_vals)
        
        if slope > 0: # Ascending Support Trendline
            projected_diagonal = (slope * current_htf_idx) + intercept
            # Validate Sweep: LTF Low went below the line, but LTF Close recovered above it
            if latest_ltf_low < projected_diagonal and latest_ltf_close > projected_diagonal:
                return f"Diagonal Sweep: Pierced Ascending Trendline (Value: ₹{round(projected_diagonal,1)}) 📈"
                
    elif system_bias == "Bearish Sweeps (Resistance)" and len(peak_points) >= 2:
        p_idx = peak_points[-2:]
        p_vals = df_htf.iloc[p_idx]['High'].values
        slope, intercept, _, _, _ = linregress(p_idx, p_vals)
        
        if slope < 0: # Descending Resistance Trendline
            projected_diagonal = (slope * current_htf_idx) + intercept
            # Validate Sweep: LTF High went above the line, but LTF Close accepted below it
            if latest_ltf_high > projected_diagonal and latest_ltf_close < projected_diagonal:
                return f"Diagonal Sweep: Pierced Descending Trendline (Value: ₹{round(projected_diagonal,1)}) 📉"

    # =========================================================================
    # CONDITION B: HORIZONTAL ZONE GEOMETRY
    # =========================================================================
    all_htf_swings = np.sort(np.concatenate((df_htf.iloc[peak_points]['High'].values, df_htf.iloc[valley_points]['Low'].values)))
    if len(all_htf_swings) == 0:
        return None
        
    horizontal_zones = []
    active_cluster = [all_htf_swings[0]]
    
    for i in range(1, len(all_htf_swings)):
        if (all_htf_swings[i] - active_cluster[0]) / active_cluster[0] <= (max_zone_w / 100.0):
            active_cluster.append(all_htf_swings[i])
        else:
            if len(active_cluster) >= 2:
                horizontal_zones.append({'floor': min(active_cluster), 'ceiling': max(active_cluster)})
            active_cluster = [all_htf_swings[i]]
    if len(active_cluster) >= 2:
        horizontal_zones.append({'floor': min(active_cluster), 'ceiling': max(active_cluster)})

    for zone in horizontal_zones:
        f, c = zone['floor'], zone['ceiling']
        zone_span_pct = ((c - f) / f) * 100
        if zone_span_pct == 0: 
            zone_span_pct = 0.1
            
        if not (min_zone_w <= zone_span_pct <= max_zone_w):
            continue
            
        if system_bias == "Bullish Sweeps (Support)":
            # Count historical floor validations to confirm stability
            floor_touches = len([v for v in df_htf.iloc[valley_points]['Low'].values if f * 0.99 <= v <= c * 1.01])
            if floor_touches >= 2:
                # Sweep check: LTF Low breaches the zone floor, but LTF Close recovers safely inside/above
                if latest_ltf_low < f and latest_ltf_close > f:
                    return f"Horizontal Sweep: Cleared Support Base Floor (₹{round(f,1)} - ₹{round(c,1)}) 🟢"
                    
        elif system_bias == "Bearish Sweeps (Resistance)":
            # Count historical ceiling validations to confirm stability
            ceiling_touches = len([p for p in df_htf.iloc[peak_points]['High'].values if f * 0.99 <= p <= c * 1.01])
            if ceiling_touches >= 2:
                # Sweep check: LTF High punches past the ceiling, but LTF Close pulls back below
                if latest_ltf_high > c and latest_ltf_close < c:
                    return f"Horizontal Sweep: Cleared Resistance Base Ceiling (₹{round(f,1)} - ₹{round(c,1)}) 🔴"

    return None

# --- GRAPHICAL INTERFACE WORKSPACE ---
with st.sidebar:
    st.header("1. Framework Settings")
    market_universe = st.selectbox("Select Index", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY Midcap 100", "NIFTY Smallcap 250", "NIFTY 500"])
    
    st.divider()
    st.header("2. Structural Horizon Matrix")
    horizon_matrix = st.selectbox("Framework Mapping", [
        "Weekly HTF -> Daily LTF",
        "Monthly HTF -> Daily LTF"
    ])
    
    # Pre-configure responsive defaults matching structural scaling laws
    if "Weekly" in horizon_matrix:
        initial_min, initial_max = 2.0, 4.0
    else:
        initial_min, initial_max = 5.0, 8.0
        
    st.markdown("**HTF Cluster Window Constraints (%)**")
    adaptive_bounds = st.slider("Min & Max Structural Bounds", 0.1, 15.0, (initial_min, initial_max))
    min_pct_w, max_pct_w = adaptive_bounds
    
    st.divider()
    st.header("3. Targeted Liquidity Flow")
    execution_bias = st.radio("Hunt Objective Type", ["Bullish Sweeps (Support)", "Bearish Sweeps (Resistance)"])
    
    st.divider()
    trigger_processing = st.button("🚀 EXECUTE SCAN ENGINE", type="primary", use_container_width=True)

# Define processing queue depth
target_symbols = load_market_symbols("NIFTY 50")[:10] if "Test" in market_universe else load_market_symbols(market_universe)

# --- EXECUTION SYSTEM ---
if trigger_processing:
    identified_setups = []
    
    with st.spinner("Extracting multi-dimensional baseline chart data modules..."):
        htf_bulk_dataset, ltf_bulk_dataset = fetch_framework_datasets(target_symbols, horizon_matrix)
        
    execution_progress = st.progress(0, text="Analyzing trend lines and structural clusters...")
    total_processing_queue = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        execution_progress.progress((idx + 1) / total_processing_queue, text=f"Processing multi-timeframe mapping maps for {ticker}...")
        
        try:
            if total_processing_queue > 1:
                df_htf_module = htf_bulk_dataset[ticker].dropna()
                df_ltf_module = ltf_bulk_dataset[ticker].dropna()
            else:
                df_htf_module = htf_bulk_dataset.dropna()
                df_ltf_module = ltf_bulk_dataset.dropna()
                
            if df_htf_module.empty or df_ltf_module.empty:
                continue
                
            structural_status = execute_sweep_analysis(df_htf_module, df_ltf_module, execution_bias, min_pct_w, max_pct_w)
            
            if structural_status:
                identified_setups.append({
                    "Ticker Symbol": ticker.replace('.NS', ''),
                    "Institutional Footprint": structural_status,
                    "Live Execution Price": round(df_ltf_module.iloc[-1]['Close'], 2)
                })
        except Exception:
            pass
            
    execution_progress.empty()
    
    # Present computational analytical outputs
    if identified_setups:
        output_table = pd.DataFrame(identified_setups)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(output_table)}** clear multi-timeframe traps matching your requirements.")
        st.dataframe(output_table, use_container_width=True, hide_index=True)
    else:
        st.warning("No assets are exhibiting lower-timeframe liquidity grabs at higher-timeframe boundaries right now.")
