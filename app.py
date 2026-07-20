import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Fast Retest S/D Engine", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #EAB308; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ Double Leg-Out & Fast Retest Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for zones with 2+ consecutive explosive leg-out candles and a quick, fresh retracement.</p>', unsafe_allow_html=True)

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

# --- DOUBLE LEG-OUT & FAST RETEST ALGORITHM ---
def analyze_fast_retest(ticker, period, interval, min_base, max_base, vol_multiplier, scan_direction, max_return_bars):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 80: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        latest_close = df['Close'].iloc[-1]
        
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = (df['High'] - df['Low']).replace(0, 0.00001)
        df['Body_Ratio'] = df['Body'] / df['Range']
        df['Is_Green'] = df['Close'] > df['Open']
        df['Avg_Volume'] = df['Volume'].rolling(window=20).mean().shift(1)
        
        BORING_THRESHOLD = 0.50
        LEG_OUT_THRESHOLD = 0.60  
        
        # Loop to find the setup (stopping early enough to allow for the Double Leg-Out)
        for i in range(len(df) - 3, 25, -1):
            hero_1_idx = i
            hero_2_idx = i + 1
            
            # 1. Require at least TWO consecutive explosive leg-out candles
            if df['Body_Ratio'].iloc[hero_1_idx] < LEG_OUT_THRESHOLD or df['Body_Ratio'].iloc[hero_2_idx] < LEG_OUT_THRESHOLD: 
                continue
                
            is_hero_up = df['Is_Green'].iloc[hero_1_idx]
            if df['Is_Green'].iloc[hero_2_idx] != is_hero_up: 
                continue # Both candles must be pushing in the exact same direction
                
            zone_type = "Demand" if is_hero_up else "Supply"
            if scan_direction != "Both" and scan_direction != zone_type: 
                continue
                
            # 2. Volume Check on the initial breakout candle
            if df['Volume'].iloc[hero_1_idx] < (vol_multiplier * df['Avg_Volume'].iloc[hero_1_idx]): 
                continue
                
            # 3. Find the Base (Boring Candles)
            base_count = 0
            base_indices = []
            for j in range(hero_1_idx - 1, max(5, hero_1_idx - 10), -1):
                if df['Body_Ratio'].iloc[j] <= BORING_THRESHOLD:
                    base_count += 1
                    base_indices.append(j)
                else: break
                    
            if not (min_base <= base_count <= max_base): 
                continue
                
            # 4. Fast Retracement Filter (Lower time spent away = more reliable)
            bars_since_breakout = (len(df) - 1) - hero_2_idx
            if bars_since_breakout > max_return_bars or bars_since_breakout < 2: 
                continue # Discard if it took too long to return, or hasn't actually retraced yet
                
            # 5. Define Boundaries & Pattern
            base_candles = df.iloc[base_indices]
            proximal = base_candles['High'].max() if zone_type == "Demand" else base_candles['Low'].min()
            distal = base_candles['Low'].min() if zone_type == "Demand" else base_candles['High'].max()
            
            leg_in_idx = hero_1_idx - base_count - 1
            is_leg_in_up = df['Is_Green'].iloc[leg_in_idx]
            
            if zone_type == "Demand":
                pattern = "RBR" if is_leg_in_up else "DBR"
            else:
                pattern = "DBD" if not is_leg_in_up else "RBD"
            
            # 6. Verify Zone Freshness
            post_zone_df = df.iloc[hero_2_idx + 1: -1]
            if post_zone_df.empty: continue
            
            if zone_type == "Demand" and post_zone_df['Close'].min() < distal: continue
            if zone_type == "Supply" and post_zone_df['Close'].max() > distal: continue
                
            # 7. Verify live price is testing the zone RIGHT NOW
            deviation = proximal * 0.015 
            is_testing = False
            
            if zone_type == "Demand" and distal <= latest_close <= (proximal + deviation): is_testing = True
            elif zone_type == "Supply" and (proximal - deviation) <= latest_close <= distal: is_testing = True
                
            if not is_testing: continue
                
            # Output Data
            return {
                "Ticker": ticker.replace('.NS', ''),
                "Bias": "🟢 BULL" if zone_type == "Demand" else "🔴 BEAR",
                "Pattern": pattern,
                "Live Price": f"₹{round(latest_close, 2)}",
                "Breakout Strength": "🚀 Double Leg-Out",
                "Zone Width (Prox-Dist)": f"₹{round(proximal, 2)} - ₹{round(distal, 2)}",
                "Time Spent Away": f"⏱️ {bars_since_breakout} Candles",
                "Volume Surge": f"🔥 {vol_multiplier}X+"
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
    direction_input = st.selectbox("Swing Bias:", ["Both", "Demand", "Supply"])
    
    st.divider()
    st.header("4. Structural Requirements")
    col1, col2 = st.columns(2)
    with col1:
        min_base_input = st.number_input("Min Base", 1, 6, 1)
    with col2:
        max_base_input = st.number_input("Max Base", 1, 6, 4)
        
    vol_input = st.slider("Min Volume Multiplier", 1.0, 4.0, 2.0, step=0.5)
    
    st.divider()
    st.header("5. Retracement Speed")
    max_return_bars = st.slider("Max Time Spent Away (Candles)", 5, 80, 30, step=5, help="Maximum number of candles allowed between the explosive breakout and the current pullback. Lower is more reliable.")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE FAST RETEST SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for Double Leg-Out Fast Retests on the **{tf_input}** chart...")
    
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
                analyze_fast_retest, ticker, active_cfg["period"], active_cfg["interval"],
                min_base_input, max_base_input, vol_input, direction_input, max_return_bars
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
            progress_ui.progress(percent_complete, text=f"Analyzing Momentum Traps: {completed_count}/{len(symbols_list)}")
            
            if completed_count % 40 == 0:
                time.sleep(0.3)
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Complete: Found **{len(results_df)}** premium setups with a Double Leg-Out and Quick Pullback.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks matched. Demanding 2 consecutive explosive candles + 2X volume + quick retracement is a very strict filter. Try expanding 'Max Time Spent Away' or dropping volume to 1.5x.")
