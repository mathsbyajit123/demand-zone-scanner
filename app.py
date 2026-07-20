import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from scipy.signal import argrelextrema
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="S/R & S/D Confluence Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #8B5CF6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 S/R & S/D Confluence Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Combines tight Price Action Pivot Clusters (S/R) with Institutional Boring Candle Bases (S/D).</p>', unsafe_allow_html=True)

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

# --- PIVOT CLUSTERING ALGORITHM (S/R) ---
def get_tight_clusters(pivots, max_width_pct, min_touches):
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
            if len(current_cluster) >= min_touches:
                clusters.append({'bottom': min(current_cluster), 'top': max(current_cluster), 'touches': len(current_cluster)})
            current_cluster = [pivots[i]]
            
    if len(current_cluster) >= min_touches:
        clusters.append({'bottom': min(current_cluster), 'top': max(current_cluster), 'touches': len(current_cluster)})
    return clusters

# --- MERGED ENGINE: S/D + S/R ---
def analyze_confluence(ticker, period, interval, min_base, max_base, pivot_len, sr_width, min_touches, entry_buffer, direction):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 100: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low'])
        latest_close = df['Close'].iloc[-1]
        
        # 1. MAP TIGHT S/R PIVOT ZONES
        highs = df['High'].values
        lows = df['Low'].values
        peak_idx = argrelextrema(highs, np.greater, order=pivot_len)[0]
        valley_idx = argrelextrema(lows, np.less, order=pivot_len)[0]
        
        res_zones = get_tight_clusters(highs[peak_idx], sr_width, min_touches)
        sup_zones = get_tight_clusters(lows[valley_idx], sr_width, min_touches)
        all_sr_zones = res_zones + sup_zones

        # 2. FIND INSTITUTIONAL S/D ZONES (Boring Candles + Leg-Out)
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = (df['High'] - df['Low']).replace(0, 0.00001)
        df['Body_Ratio'] = df['Body'] / df['Range']
        df['Is_Green'] = df['Close'] > df['Open']
        
        BORING_THRESHOLD = 0.50
        LEG_OUT_THRESHOLD = 0.60
        
        for i in range(len(df) - 2, 20, -1):
            hero_idx = i
            if df['Body_Ratio'].iloc[hero_idx] < LEG_OUT_THRESHOLD: continue
                
            is_hero_up = df['Is_Green'].iloc[hero_idx]
            zone_type = "Demand" if is_hero_up else "Supply"
            if direction != "Both" and direction != zone_type: continue
                
            # Base (Boring Candles)
            base_count = 0
            base_indices = []
            for j in range(hero_idx - 1, max(0, hero_idx - 10), -1):
                if df['Body_Ratio'].iloc[j] <= BORING_THRESHOLD:
                    base_count += 1
                    base_indices.append(j)
                else: break
                    
            if not (min_base <= base_count <= max_base): continue
            
            # Pattern Identification
            leg_in_idx = hero_idx - base_count - 1
            is_leg_in_up = df['Is_Green'].iloc[leg_in_idx]
            if zone_type == "Demand": pattern = "RBR" if is_leg_in_up else "DBR"
            else: pattern = "DBD" if not is_leg_in_up else "RBD"
                
            # Boundaries
            base_candles = df.iloc[base_indices]
            proximal = base_candles['High'].max() if zone_type == "Demand" else base_candles['Low'].min()
            distal = base_candles['Low'].min() if zone_type == "Demand" else base_candles['High'].max()
            
            # Freshness Check
            post_zone_df = df.iloc[hero_idx + 1: -1]
            if not post_zone_df.empty:
                if zone_type == "Demand" and post_zone_df['Close'].min() < distal: continue
                if zone_type == "Supply" and post_zone_df['Close'].max() > distal: continue
            
            # 3. PROXIMITY CHECK (Is live price testing this S/D zone?)
            deviation = proximal * (entry_buffer / 100.0)
            is_testing = False
            
            if zone_type == "Demand" and distal <= latest_close <= (proximal + deviation): is_testing = True
            elif zone_type == "Supply" and (proximal - deviation) <= latest_close <= distal: is_testing = True
                
            if not is_testing: continue

            # 4. CONFLUENCE CHECK (Does this S/D Zone overlap with a tight S/R Pivot Zone?)
            sr_overlap_text = "❌ No S/R Overlap"
            for sr in all_sr_zones:
                # Overlap logic: max(start1, start2) <= min(end1, end2)
                if max(min(proximal, distal), sr['bottom']) <= min(max(proximal, distal), sr['top']):
                    sr_overlap_text = f"⭐ Yes ({sr['touches']} S/R Touches)"
                    break

            return {
                "Ticker": ticker.replace('.NS', ''),
                "Setup Type": f"{'🟢 DEMAND' if zone_type == 'Demand' else '🔴 SUPPLY'}",
                "Pattern": pattern,
                "Live Price": f"₹{round(latest_close, 2)}",
                "Base Strength": f"{base_count} Boring Candles",
                "S/D Zone Bounds": f"₹{round(min(proximal, distal), 2)} - ₹{round(max(proximal, distal), 2)}",
                "S/R Confluence?": sr_overlap_text
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
    tf_input = st.selectbox("Select Timeframe:", ["15 Minutes", "1 Hour", "1D", "1W", "1M"], index=2)
    
    st.divider()
    st.header("3. Setup Direction")
    direction_input = st.selectbox("Scan For:", ["Both", "Demand", "Supply"])
    
    st.divider()
    st.header("4. Boring Candle S/D Logic")
    col1, col2 = st.columns(2)
    with col1: min_base = st.number_input("Min Base", 1, 6, 1)
    with col2: max_base = st.number_input("Max Base", 1, 6, 4)
    entry_buffer = st.slider("Zone Entry Buffer (%)", 0.0, 3.0, 1.0, step=0.1)
    
    st.divider()
    st.header("5. Tight S/R Pivot Logic")
    pivot_length = st.number_input("Pivot Lookback (Bars)", 3, 30, 8)
    max_zone_width = st.slider("Max S/R Zone Width (%)", 0.1, 5.0, 1.5, step=0.1)
    min_touches = st.number_input("Min S/R Touches", 2, 10, 3)
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE CONFLUENCE SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for S/D & S/R Confluence on the **{tf_input}** chart...")
    
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
                analyze_confluence, ticker, active_cfg["period"], active_cfg["interval"],
                min_base, max_base, pivot_length, max_zone_width, min_touches, entry_buffer, direction_input
            ): ticker for ticker in symbols_list
        }
        
        completed_count = 0
        for future in as_completed(futures_map):
            completed_count += 1
            result = future.result()
            if result:
                confirmed_setups.append(result)
            
            percent_complete = completed_count / len(symbols_list)
            progress_ui.progress(percent_complete, text=f"Analyzing Structural Confluence: {completed_count}/{len(symbols_list)}")
            if completed_count % 40 == 0: time.sleep(0.3)
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks resting at Institutional Supply/Demand Zones.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks matched perfectly. Try increasing the 'Zone Entry Buffer' or 'Max S/R Zone Width'.")
