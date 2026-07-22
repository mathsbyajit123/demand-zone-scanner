import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Expanded Wick-Capture Engine", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #3B82F6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 Expanded Wick-Capture & Pullback Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for trend-intact pullbacks. Catches wicks entering the 21/44 zone on dry volume without being overly strict on prior minor touches.</p>', unsafe_allow_html=True)

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

# --- EXPANDED WICK-CAPTURE ALGORITHM ---
def analyze_expanded_pullback(ticker, period, interval, fast_ema_val, slow_ema_val, min_rally_pct, max_rally_pct, max_vol_pct, zone_buffer):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 120: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        
        # 1. Calculate EMAs & Volume Average
        df['EMA_Fast'] = df['Close'].ewm(span=fast_ema_val, adjust=False).mean()
        df['EMA_Slow'] = df['Close'].ewm(span=slow_ema_val, adjust=False).mean()
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        
        latest_close = df['Close'].iloc[-1]
        latest_low = df['Low'].iloc[-1]
        ema_fast_live = df['EMA_Fast'].iloc[-1]
        ema_slow_live = df['EMA_Slow'].iloc[-1]
        vol_avg_live = df['Vol_Avg'].iloc[-1]
        
        # Must currently be in an uptrend
        if ema_fast_live <= ema_slow_live:
            return None
            
        # 2. Locate the Crossover
        df['Bull_Cross'] = (df['EMA_Fast'] > df['EMA_Slow']) & (df['EMA_Fast'].shift(1) <= df['EMA_Slow'].shift(1))
        recent_crosses = df[df['Bull_Cross']]
        
        if recent_crosses.empty:
            return None
            
        last_cross_idx = recent_crosses.index[-1]
        cross_pos = df.index.get_loc(last_cross_idx)
        curr_pos = len(df) - 1
        
        bars_since_cross = curr_pos - cross_pos
        
        # Expanded to 90 bars to catch slower, high-quality setups
        if bars_since_cross > 90 or bars_since_cross < 3:
            return None
            
        post_cross_df = df.iloc[cross_pos : curr_pos + 1]
        cross_price = df.iloc[cross_pos]['Close']
        max_high = post_cross_df['High'].max()
        
        # 3. RALLY FILTER
        rally_pct = ((max_high - cross_price) / cross_price) * 100.0
        if rally_pct < min_rally_pct or rally_pct > max_rally_pct:
            return None
            
        # 4. TREND INTACT SHIELD (Replaces the hyper-strict Zero-Touch rule)
        # We only reject the stock if it CLOSED below the 44 EMA during the run-up
        middle_df = df.iloc[cross_pos + 1 : curr_pos - 1]
        if not middle_df.empty:
            trend_broken = (middle_df['Close'] < (middle_df['EMA_Slow'] * 0.99)).any()
            if trend_broken:
                return None # The uptrend failed previously
                
        # 5. CURRENT ENTRY TEST (Wick + Body Logic)
        buffer_multiplier = 1 + (zone_buffer / 100.0)
        
        # Wick must dip into or get very close to the Fast EMA (based on your buffer slider)
        reached_fast_ema = latest_low <= (ema_fast_live * buffer_multiplier)
        
        # Body (Close) must hold at or above the Slow EMA (with a tiny 1% allowance for closing right on the line)
        held_slow_ema = latest_close >= (ema_slow_live * 0.99)
        
        # Ensure it's actually a pullback (Close isn't flying 5% above the 21 EMA right now)
        is_pullback = latest_close <= (ema_fast_live * 1.03)

        if not (reached_fast_ema and held_slow_ema and is_pullback):
            return None
            
        # 6. VOLUME DRY-UP FILTER
        recent_pullback_vol = df['Volume'].iloc[-3:].mean()
        vol_ratio = (recent_pullback_vol / vol_avg_live) * 100.0
        
        if vol_ratio >= max_vol_pct:
            return None
            
        return {
            "Ticker": ticker.replace('.NS', ''),
            "Live Price": f"₹{round(latest_close, 2)}",
            "Initial Move": f"📈 +{round(rally_pct, 1)}% Rally",
            "Zone Entry": "🎯 Valid Wick in EMA Zone",
            "Retracement Volume": f"🔇 {round(vol_ratio, 1)}% (Dry)",
            "Action": "🔥 Ready for Reversal"
        }
                
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Universe:", [
        "NIFTY 500", "NIFTY 50", "NIFTY NEXT 50", 
        "NIFTY BANK", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 250"
    ], index=0)
    
    st.divider()
    st.header("2. Execution Timeframe")
    tf_input = st.selectbox("Scanning Timeframe:", ["1 Day", "1 Week", "1 Hour", "15 Minutes"], index=0)
    
    st.divider()
    st.header("3. Momentum Parameters")
    col1, col2 = st.columns(2)
    with col1:
        fast_ema = st.number_input("Fast EMA", value=21)
    with col2:
        slow_ema = st.number_input("Slow EMA", value=44)
        
    min_rally = st.slider("Min 1st-Leg Rally (%)", 2.0, 20.0, 5.0, step=1.0)
    max_rally = st.slider("Max 1st-Leg Rally (%)", 15.0, 70.0, 40.0, step=1.0)
    
    st.divider()
    st.header("4. Entry Parameters")
    zone_buffer = st.slider("Wick Proximity Buffer (%)", 0.0, 3.0, 1.5, step=0.5, 
                            help="How close the wick needs to get to the 21 EMA to trigger. Higher % catches more stocks.")
    max_volume = st.slider("Max Retracement Volume (%)", 30.0, 120.0, 85.0, step=5.0)
    
    st.divider()
    execute_button = st.button("🚀 EXECUTE EXPANDED SCAN", type="primary", use_container_width=True)

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
    st.info(f"Scanning **{len(symbols_list)} stocks** for valid wick entries on the **{tf_input}** chart...")
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(
                analyze_expanded_pullback, 
                ticker, 
                active_cfg["period"], 
                active_cfg["interval"],
                fast_ema,
                slow_ema,
                min_rally,
                max_rally,
                max_volume,
                zone_buffer
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
            progress_ui.progress(percent_complete, text=f"Hunting setups: {completed_count}/{len(symbols_list)}")
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        results_df['Raw_Vol'] = results_df['Retracement Volume'].str.extract(r'🔇 (\d+\.\d+)%').astype(float)
        results_df = results_df.sort_values(by='Raw_Vol', ascending=True).drop(columns=['Raw_Vol'])
        
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks actively pulling back into your EMA zone.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks matched. Try increasing the 'Wick Proximity Buffer' or 'Max Retracement Volume' to widen the net further.")
