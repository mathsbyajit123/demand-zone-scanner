import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from scipy.signal import argrelextrema
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Role Reversal Scanner", layout="wide", page_icon="🔄")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #10B981; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🔄 Institutional Role Reversal Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Hunts for old Resistance ceilings (3-5 touches) that broke and are now being retested as Demand floors.</p>', unsafe_allow_html=True)

# --- DATA UNIVERSE LOADER ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY MIDCAP 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY SMALLCAP 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls.get(category))
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS"]

# --- PIVOT CLUSTERING ALGORITHM ---
def get_tight_clusters(pivots, max_width_pct, min_touches, max_touches):
    if len(pivots) == 0: return []
    pivots = np.sort(pivots)
    clusters = []
    current_cluster = [pivots[0]]
    
    for i in range(1, len(pivots)):
        cluster_bottom = current_cluster[0]
        width_pct = ((pivots[i] - cluster_bottom) / cluster_bottom) * 100
        
        if width_pct <= max_width_pct:
            current_cluster.append(pivots[i])
        else:
            if min_touches <= len(current_cluster) <= max_touches:
                clusters.append({'bottom': min(current_cluster), 'top': max(current_cluster), 'touches': len(current_cluster)})
            current_cluster = [pivots[i]]
            
    if min_touches <= len(current_cluster) <= max_touches:
        clusters.append({'bottom': min(current_cluster), 'top': max(current_cluster), 'touches': len(current_cluster)})
    return clusters

# --- ROLE REVERSAL ENGINE ---
def analyze_role_reversal(ticker, period, interval, pivot_len, max_width, min_touches, max_touches, entry_buffer):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 100: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        
        df = df.ffill().dropna(subset=['Close', 'High', 'Low'])
        latest_close = df['Close'].iloc[-1]
        
        # 1. Identify Raw Swing Highs (Historical Resistance)
        highs = df['High'].values
        peak_idx = argrelextrema(highs, np.greater, order=pivot_len)[0]
        raw_resistances = highs[peak_idx]
        
        # 2. Cluster Pivots into Tight Resistance Zones (Requiring exactly 3 to 5 touches)
        resistance_zones = get_tight_clusters(raw_resistances, max_width, min_touches, max_touches)
        
        for rz in resistance_zones:
            # 3. Check Breakout Condition: Did the price eventually break significantly above this resistance?
            highest_close = df['Close'].max()
            breakout_margin = rz['top'] * 1.05 # Price must have gone at least 5% above the zone to prove a true breakout
            
            if highest_close > breakout_margin:
                
                # 4. Check Retest Condition: Is live price currently falling back into this old resistance?
                buffer_val = rz['top'] * (entry_buffer / 100.0)
                
                # The live price must be dropping into the top of the zone, or sitting inside it.
                if rz['bottom'] <= latest_close <= (rz['top'] + buffer_val):
                    
                    # Ensure it is currently a pullback (price is down from recent highs)
                    recent_high = df['High'].iloc[-15:].max()
                    if recent_high > (rz['top'] + buffer_val):
                        
                        dist_pct = ((latest_close - rz['top']) / rz['top']) * 100
                        return {
                            "Ticker": ticker.replace('.NS', ''),
                            "Status": "🔄 VALID ROLE REVERSAL",
                            "Live Price": f"₹{round(latest_close, 2)}",
                            "Zone (Old Ceiling -> New Floor)": f"₹{round(rz['bottom'], 2)} - ₹{round(rz['top'], 2)}",
                            "Historical Touches": f"⭐ {rz['touches']} Resistance Rejections",
                            "Distance to Zone Top": f"+{round(dist_pct, 2)}%"
                        }
        return None
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Universe", ["NIFTY 500", "NIFTY 50", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 250"])
    
    st.divider()
    st.header("2. Execution Horizon")
    # Restricted to the Higher Timeframes requested
    tf_input = st.selectbox("Select Timeframe:", ["1D", "1W", "1M"], index=0)
    
    st.divider()
    st.header("3. Resistance Structure")
    col1, col2 = st.columns(2)
    with col1:
        min_touches = st.number_input("Min Touches", 2, 10, 3)
    with col2:
        max_touches = st.number_input("Max Touches", 3, 15, 5)
        
    pivot_length = st.number_input("Pivot Lookback (Bars)", 3, 30, 8, help="How many bars left and right define a swing high.")
    
    st.divider()
    st.header("4. Retest Entry Parameters")
    max_zone_width = st.slider("Max Zone Width (%)", 0.1, 5.0, 2.0, step=0.1, help="Keeps the historical resistance ceiling tight.")
    entry_buffer = st.slider("Entry Buffer Tolerance (%)", 0.0, 5.0, 1.5, step=0.1, help="How far above the top of the zone can the live price be to trigger an alert.")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE RETEST SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for Break & Retest Setups on the **{tf_input}** chart...")
    
    tf_configs = {
        "1D": {"period": "3y", "interval": "1d"},
        "1W": {"period": "10y", "interval": "1wk"},
        "1M": {"period": "20y", "interval": "1mo"}
    }
    active_cfg = tf_configs[tf_input]
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures_map = {
            executor.submit(
                analyze_role_reversal, ticker, active_cfg["period"], active_cfg["interval"],
                pivot_length, max_zone_width, min_touches, max_touches, entry_buffer
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
            progress_ui.progress(percent_complete, text=f"Analyzing Role Reversals: {completed_count}/{len(symbols_list)}")
            
            if completed_count % 40 == 0:
                time.sleep(0.3)
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks actively testing an old Resistance as a new Support.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks are currently pulling back perfectly into a 3-5 touch resistance floor. Try expanding the Entry Buffer or lowering the Pivot Lookback.")
