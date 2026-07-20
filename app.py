import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from scipy.signal import argrelextrema
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Pure Price Action S/R Scanner", layout="wide", page_icon="🏛️")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #3B82F6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🏛️ Precision Price Action S/R Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Maps tight, multi-touch Swing Pivot zones and hunts for live price retests.</p>', unsafe_allow_html=True)

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
def get_tight_clusters(pivots, max_width_pct, min_touches):
    if len(pivots) == 0:
        return []
    
    pivots = np.sort(pivots)
    clusters = []
    current_cluster = [pivots[0]]
    
    for i in range(1, len(pivots)):
        # Calculate width of the current cluster if we add this pivot
        cluster_bottom = current_cluster[0]
        proposed_top = pivots[i]
        width_pct = ((proposed_top - cluster_bottom) / cluster_bottom) * 100
        
        if width_pct <= max_width_pct:
            current_cluster.append(pivots[i])
        else:
            if len(current_cluster) >= min_touches:
                clusters.append({
                    'bottom': min(current_cluster),
                    'top': max(current_cluster),
                    'touches': len(current_cluster)
                })
            current_cluster = [pivots[i]]
            
    if len(current_cluster) >= min_touches:
        clusters.append({
            'bottom': min(current_cluster),
            'top': max(current_cluster),
            'touches': len(current_cluster)
        })
        
    return clusters

# --- PRICE ACTION ENGINE ---
def analyze_price_action(ticker, period, interval, pivot_len, max_width, min_touches, entry_buffer, scan_type):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 100: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        
        df = df.ffill().dropna(subset=['Close', 'High', 'Low'])
        latest_close = df['Close'].iloc[-1]
        
        # 1. Identify Raw Swing Highs and Lows
        highs = df['High'].values
        lows = df['Low'].values
        
        peak_idx = argrelextrema(highs, np.greater, order=pivot_len)[0]
        valley_idx = argrelextrema(lows, np.less, order=pivot_len)[0]
        
        raw_resistances = highs[peak_idx]
        raw_supports = lows[valley_idx]
        
        # 2. Cluster Pivots into Tight Zones
        resistance_zones = get_tight_clusters(raw_resistances, max_width, min_touches)
        support_zones = get_tight_clusters(raw_supports, max_width, min_touches)
        
        active_setup = None
        
        # 3. Check Live Proximity to Support Floors
        if scan_type in ["Both", "Support (Demand)"]:
            for sz in support_zones:
                buffer_val = sz['top'] * (entry_buffer / 100.0)
                # Is price inside the support zone or sitting right on top of it?
                if sz['bottom'] <= latest_close <= (sz['top'] + buffer_val):
                    dist_pct = ((latest_close - sz['top']) / sz['top']) * 100
                    active_setup = {
                        "Ticker": ticker.replace('.NS', ''),
                        "Zone Type": "🟢 SUPPORT FLOOR",
                        "Live Price": f"₹{round(latest_close, 2)}",
                        "Zone Bounds": f"₹{round(sz['bottom'], 2)} - ₹{round(sz['top'], 2)}",
                        "Structural Strength": f"⭐ {sz['touches']} Pivot Touches",
                        "Distance from Zone": f"+{round(dist_pct, 2)}%"
                    }
                    break # Prioritize the tightest active setup
                    
        # 4. Check Live Proximity to Resistance Ceilings
        if not active_setup and scan_type in ["Both", "Resistance (Supply)"]:
            for rz in resistance_zones:
                buffer_val = rz['bottom'] * (entry_buffer / 100.0)
                # Is price inside the resistance zone or sitting just below it?
                if (rz['bottom'] - buffer_val) <= latest_close <= rz['top']:
                    dist_pct = ((latest_close - rz['bottom']) / rz['bottom']) * 100
                    active_setup = {
                        "Ticker": ticker.replace('.NS', ''),
                        "Zone Type": "🔴 RESISTANCE CEILING",
                        "Live Price": f"₹{round(latest_close, 2)}",
                        "Zone Bounds": f"₹{round(rz['bottom'], 2)} - ₹{round(rz['top'], 2)}",
                        "Structural Strength": f"⭐ {rz['touches']} Pivot Touches",
                        "Distance from Zone": f"{round(dist_pct, 2)}%"
                    }
                    break

        return active_setup
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Universe", ["NIFTY 500", "NIFTY 50", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 250"])
    
    st.divider()
    st.header("2. Execution Horizon")
    tf_input = st.selectbox("Select Timeframe:", ["15 Minutes", "1 Hour", "1D", "1W", "1M"], index=2)
    
    st.divider()
    st.header("3. Setup Direction")
    direction_input = st.selectbox("Scan For:", ["Both", "Support (Demand)", "Resistance (Supply)"])
    
    st.divider()
    st.header("4. Structural Requirements")
    pivot_length = st.number_input("Pivot Lookback (Left/Right Bars)", 3, 30, 8, help="Higher number = More significant macro swings. Lower number = Micro swings.")
    min_touches = st.number_input("Min Zone Touches", 2, 10, 3, help="How many times must the market have bounced here in the past?")
    
    st.divider()
    st.header("5. Tight Zone Logic")
    max_zone_width = st.slider("Max Zone Width (%)", 0.1, 5.0, 1.5, step=0.1, help="Keeps the zone extremely tight. Prevents sloppy, massive blocks from passing the scan.")
    entry_buffer = st.slider("Entry Buffer Tolerance (%)", 0.0, 3.0, 0.5, step=0.1, help="How close the live price needs to be to the outer edge of the zone to trigger an alert.")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE PRICE ACTION SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for Precision S/R Zones on the **{tf_input}** chart...")
    
    tf_configs = {
        "15 Minutes": {"period": "60d", "interval": "15m"},
        "1 Hour": {"period": "730d", "interval": "1h"},
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
                analyze_price_action, ticker, active_cfg["period"], active_cfg["interval"],
                pivot_length, max_zone_width, min_touches, entry_buffer, direction_input
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
            progress_ui.progress(percent_complete, text=f"Analyzing Price Action Floors/Ceilings: {completed_count}/{len(symbols_list)}")
            
            if completed_count % 40 == 0:
                time.sleep(0.3)
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks resting at a historically verified Price Action zone.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks are currently testing a perfectly tight S/R zone. Try slightly expanding the 'Max Zone Width (%)' or lowering the 'Min Zone Touches'.")
