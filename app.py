import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time
from scipy.signal import argrelextrema
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="S/R & S/D Confluence Scanner", layout="wide", page_icon="🏛️")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #8B5CF6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🏛️ S/R & S/D Confluence Engine (Live Market Edition)</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Includes X-Ray Mode to verify live data flow and relax strict confluence rules.</p>', unsafe_allow_html=True)

# --- LIVE F&O & SECTOR EXTRACTION ---
@st.cache_data(ttl=43200)
def get_sector_symbols(sector_name):
    if sector_name == "Live F&O Active Stocks":
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/csv'
            }
            url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                df.columns = df.columns.str.strip()
                symbols = df['SYMBOL'].str.strip().unique()
                indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
                return [str(sym) + ".NS" for sym in symbols if sym not in indices]
        except Exception:
            return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"]

    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    
    try:
        df = pd.read_csv(urls.get(sector_name, urls["NIFTY 50"]))
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"]

# --- PINE SCRIPT S/R CHANNEL ALGORITHM ---
def map_sr_channels(df, pivot_len, max_width_pct, min_touches):
    try:
        highs = df['High'].values
        lows = df['Low'].values
        
        peak_idx = argrelextrema(highs, np.greater, order=pivot_len)[0]
        valley_idx = argrelextrema(lows, np.less, order=pivot_len)[0]
        
        pivots = np.concatenate((highs[peak_idx], lows[valley_idx]))
        pivots = np.sort(pivots)
        
        if len(pivots) == 0:
            return []
            
        channels = []
        current_cluster = [pivots[0]]
        
        for i in range(1, len(pivots)):
            if (pivots[i] - current_cluster[0]) / current_cluster[0] <= (max_width_pct / 100.0):
                current_cluster.append(pivots[i])
            else:
                if len(current_cluster) >= min_touches:
                    channels.append({
                        'floor': min(current_cluster),
                        'ceiling': max(current_cluster),
                        'strength': len(current_cluster)
                    })
                current_cluster = [pivots[i]]
                
        if len(current_cluster) >= min_touches:
            channels.append({'floor': min(current_cluster), 'ceiling': max(current_cluster), 'strength': len(current_cluster)})
            
        return channels
    except Exception:
        return []

# --- BORING CANDLE CONFLUENCE ALGORITHM ---
def analyze_confluence(ticker, period, interval, pivot_len, sr_width, min_touches, min_base, max_base, mode_choice, strict_mode):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 100:
            return None
            
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        
        # Bulletproof live market gap handling
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low'])
        
        latest_close = df['Close'].iloc[-1]
        
        sr_zones = map_sr_channels(df, pivot_len, sr_width, min_touches)
        
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = (df['High'] - df['Low']).replace(0, 0.00001)
        df['Body_Ratio'] = df['Body'] / df['Range']
        df['Is_Green'] = df['Close'] > df['Open']
        
        BORING_THRESHOLD = 0.50
        LEG_OUT_THRESHOLD = 0.60 
        
        # Look back over the last 20 candles
        for i in range(len(df) - 1, len(df) - 20, -1):
            hero_idx = i
            
            if df['Body_Ratio'].iloc[hero_idx] < LEG_OUT_THRESHOLD:
                continue
                
            is_hero_up = df['Is_Green'].iloc[hero_idx]
            
            base_count = 0
            base_indices = []
            for j in range(hero_idx - 1, hero_idx - 10, -1):
                if df['Body_Ratio'].iloc[j] <= BORING_THRESHOLD:
                    base_count += 1
                    base_indices.append(j)
                else:
                    break
                    
            if not (min_base <= base_count <= max_base):
                continue
                
            base_candles = df.iloc[base_indices]
            zone_type = "Demand" if is_hero_up else "Supply"
            
            if mode_choice != "Both" and mode_choice != zone_type:
                continue
                
            sd_upper = base_candles['High'].max()
            sd_lower = base_candles['Low'].min()
            
            overlapping_sr = None
            for sr in sr_zones:
                if max(sd_lower, sr['floor']) <= min(sd_upper, sr['ceiling']):
                    overlapping_sr = sr
                    break
                    
            if strict_mode and not overlapping_sr:
                continue 
                
            deviation = sd_upper * 0.015 
            
            is_testing = False
            if zone_type == "Demand" and (sd_upper + deviation) >= latest_close >= sd_lower:
                is_testing = True
            elif zone_type == "Supply" and (sd_lower - deviation) <= latest_close <= sd_upper:
                is_testing = True
                
            if not strict_mode or is_testing:
                return {
                    "Ticker": ticker.replace('.NS', ''),
                    "S/D Zone": f"{'🟢' if zone_type == 'Demand' else '🔴'} {zone_type}",
                    "Live Price": f"₹{round(latest_close, 2)}",
                    "Base": f"{base_count} Candles",
                    "Zone Bounds": f"₹{round(sd_lower, 2)} - ₹{round(sd_upper, 2)}",
                    "S/R Channel": f"₹{round(overlapping_sr['floor'], 2)} - ₹{round(overlapping_sr['ceiling'], 2)}" if overlapping_sr else "❌ No S/R Overlap",
                    "S/R Strength": f"⭐ {overlapping_sr['strength']} Touches" if overlapping_sr else "N/A"
                }
                
        return None
        
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Index", ["Live F&O Active Stocks", "NIFTY 50", "NIFTY 500"])
    
    st.divider()
    st.header("2. Execution Timeframe")
    tf_input = st.selectbox("Select Chart Horizon:", ["15 Min", "1 Hour", "Daily", "Weekly"])
    
    st.divider()
    st.header("3. S/R Channel Logic")
    pivot_length = st.number_input("Pivot Lookback", 5, 30, 10)
    sr_width_pct = st.slider("Max Channel Width (%)", 1.0, 10.0, 5.0, step=0.5)
    min_touches = st.number_input("Min S/R Touches", 2, 10, 3)
    
    st.divider()
    st.header("4. Boring Candle Logic")
    mode_filter = st.selectbox("Zone Direction:", ["Both", "Demand", "Supply"])
    col1, col2 = st.columns(2)
    with col1:
        min_base_input = st.number_input("Min Base", 1, 3, 1)
    with col2:
        max_base_input = st.number_input("Max Base", 2, 6, 4)
        
    st.divider()
    st.header("5. Engine Mode")
    strict_toggle = st.checkbox("Strict Confluence Mode", value=False, help="Uncheck to show ALL Boring Candle setups, even if they don't overlap with S/R.")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE CONFLUENCE SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = get_sector_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for S/D Zones on the **{tf_input}** chart...")
    
    tf_configs = {
        "15 Min": {"period": "60d", "interval": "15m"},
        "1 Hour": {"period": "730d", "interval": "1h"},
        "Daily": {"period": "3y", "interval": "1d"},
        "Weekly": {"period": "10y", "interval": "1wk"}
    }
    active_cfg = tf_configs[tf_input]
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures_map = {
            executor.submit(
                analyze_confluence, ticker, active_cfg["period"], active_cfg["interval"],
                pivot_length, sr_width_pct, min_touches, min_base_input, max_base_input, mode_filter, strict_toggle
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
            progress_ui.progress(percent_complete, text=f"Mapping Matrix: {completed_count}/{len(symbols_list)}")
            
            if completed_count % 25 == 0:
                time.sleep(0.5)
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        mode_text = "Strict Confluence" if strict_toggle else "X-Ray Mode"
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks in {mode_text}.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No active setups found. Try unchecking 'Strict Confluence Mode' to verify the data is flowing.")
