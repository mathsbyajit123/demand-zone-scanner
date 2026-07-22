import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Fresh First-Touch EMA Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #10B981; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 Fresh First-Touch Crossover Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Strictly filters for the VERY FIRST retest after a 21/44 EMA cross & rally. Rejects 2nd, 3rd, or 4th touches.</p>', unsafe_allow_html=True)

# --- ROBUST DATA UNIVERSE LOADER ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY NEXT 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "NIFTY BANK": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY MIDCAP 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY SMALLCAP 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    url = urls.get(category)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        st.sidebar.warning("⚠️ NSE Server blocked full list. Using liquid failsafe stocks.")
        return ['RELIANCE.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'TCS.NS', 'ITC.NS', 'LT.NS', 'SBIN.NS', 'BHARTIARTL.NS']

# --- FRESH FIRST-TOUCH ALGORITHM ---
def analyze_fresh_first_touch(ticker, period, interval, fast_ema_val, slow_ema_val, min_rally_pct, max_vol_pct):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 120: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        
        # 1. Calculate EMAs and Volume Base
        df['EMA_Fast'] = df['Close'].ewm(span=fast_ema_val, adjust=False).mean()
        df['EMA_Slow'] = df['Close'].ewm(span=slow_ema_val, adjust=False).mean()
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        
        latest_close = df['Close'].iloc[-1]
        latest_low = df['Low'].iloc[-1]
        ema_fast_live = df['EMA_Fast'].iloc[-1]
        ema_slow_live = df['EMA_Slow'].iloc[-1]
        vol_avg_live = df['Vol_Avg'].iloc[-1]
        
        # Current trend check: Fast EMA must be above Slow EMA
        if ema_fast_live <= ema_slow_live:
            return None
            
        # 2. Find the most recent Crossover
        df['Bull_Cross'] = (df['EMA_Fast'] > df['EMA_Slow']) & (df['EMA_Fast'].shift(1) <= df['EMA_Slow'].shift(1))
        
        recent_crosses = df[df['Bull_Cross']]
        if recent_crosses.empty:
            return None 
            
        last_cross_idx = recent_crosses.index[-1]
        cross_pos = df.index.get_loc(last_cross_idx)
        
        # Ensure crossover happened within recent history (last 80 bars max)
        if (len(df) - cross_pos) > 80:
            return None
            
        post_cross_df = df.iloc[cross_pos:]
        
        # 3. Check Rally Strength (Must move at least min_rally_pct post-cross)
        cross_price = df.iloc[cross_pos]['Close']
        max_high = post_cross_df['High'].max()
        rally_pct = ((max_high - cross_price) / cross_price) * 100.0
        
        if rally_pct < min_rally_pct:
            return None
            
        # Locate exact position of the rally peak
        peak_pos_in_post = post_cross_df['High'].values.argmax()
        peak_pos = cross_pos + peak_pos_in_post
        
        curr_pos = len(df) - 1
        
        # 4. STRICT FIRST-TOUCH FILTER (Eliminates 2nd, 3rd, 4th touches)
        # Check every single bar between the rally PEAK and 3 bars ago
        if peak_pos < (curr_pos - 3):
            intermediate_df = df.iloc[peak_pos : curr_pos - 3]
            
            # If the price touched or dipped into the Fast EMA during this middle period, REJECT IT!
            prior_touch = (intermediate_df['Low'] <= (intermediate_df['EMA_Fast'] * 1.005)).any()
            if prior_touch:
                return None  # This was already retested before today. Not a fresh first touch!
                
        # 5. Verify the price is currently at the EMA zone (The First Touch happening NOW)
        is_in_ema_zone = (latest_low <= (ema_fast_live * 1.015)) and (latest_close >= (ema_slow_live * 0.985))
        if not is_in_ema_zone:
            return None
            
        # Ensure it has pulled back from the high
        if latest_close >= (max_high * 0.96):
            return None
            
        # 6. Volume Dry-Up Verification
        recent_pullback_vol = df['Volume'].iloc[-3:].mean()
        vol_ratio = (recent_pullback_vol / vol_avg_live) * 100.0
        
        if vol_ratio >= max_vol_pct:
            return None 
            
        return {
            "Ticker": ticker.replace('.NS', ''),
            "Live Price": f"₹{round(latest_close, 2)}",
            "Initial Rally": f"📈 +{round(rally_pct, 1)}% Post-Cross",
            "Touch Status": "🌟 FRESH 1ST RETEST (0 Prior Touches)",
            "Retracement Volume": f"🔇 {round(vol_ratio, 1)}% of Avg Vol",
            "Action": "🔥 Fresh Institutional Entry"
        }
                
    except Exception:
        return None

# --- INTERACTIVE SIDEBAR ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Universe:", [
        "NIFTY 500", "NIFTY 50", "NIFTY NEXT 50", 
        "NIFTY BANK", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 250"
    ])
    
    st.divider()
    st.header("2. Execution Timeframe")
    tf_input = st.selectbox(
        "Scanning Timeframe:", 
        ["1 Day", "1 Week", "1 Hour", "15 Minutes"], 
        index=0,
        help="Select chart horizon."
    )
    
    st.divider()
    st.header("3. Momentum Parameters")
    col1, col2 = st.columns(2)
    with col1:
        fast_ema = st.number_input("Fast EMA", min_value=5, max_value=100, value=21)
    with col2:
        slow_ema = st.number_input("Slow EMA", min_value=10, max_value=200, value=44)
        
    min_rally = st.slider(
        "Minimum Post-Cross Rally (%)", 
        min_value=5.0, 
        max_value=30.0, 
        value=10.0, 
        step=1.0, 
        help="Filters out weak crosses. Forces stock to rally at least this much before pulling back."
    )
    
    st.divider()
    st.header("4. Accumulation Parameters")
    max_volume = st.slider(
        "Max Retracement Volume (%)", 
        min_value=10.0, 
        max_value=120.0, 
        value=75.0, 
        step=5.0, 
        help="Limits pullback volume to ensure sellers are exhausted."
    )
    
    st.divider()
    execute_button = st.button("🚀 SCAN FOR FRESH FIRST-TOUCH", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    tf_configs = {
        "1 Week": {"period": "5y", "interval": "1wk"},
        "1 Day": {"period": "2y", "interval": "1d"},
        "1 Hour": {"period": "729d", "interval": "1h"},
        "15 Minutes": {"period": "59d", "interval": "15m"}
    }
    active_cfg = tf_configs[tf_input]

    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for **Fresh 1st Retests** on the **{tf_input}** chart...")
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(
                analyze_fresh_first_touch, 
                ticker, 
                active_cfg["period"], 
                active_cfg["interval"],
                fast_ema,
                slow_ema,
                min_rally,
                max_volume
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
            progress_ui.progress(percent_complete, text=f"Filtering Out Old Touches: {completed_count}/{len(symbols_list)}")
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        # Sort by largest rally first
        results_df['Raw_Rally'] = results_df['Initial Rally'].str.extract(r'\+(\d+\.\d+)%').astype(float)
        results_df = results_df.sort_values(by='Raw_Rally', ascending=False).drop(columns=['Raw_Rally'])
        
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks making their VERY FIRST retest after a crossover & rally.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks currently match. Requiring a fresh 1st touch after a >{min_rally}% rally is an extremely strict institutional filter. If results are zero, try lowering 'Minimum Post-Cross Rally (%)' to 7.0% or 8.0%.")
