import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Golden Cross Pullback Scanner", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #3B82F6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📈 Post-Cross 10%+ Expansion & Pullback Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for stocks that crossed 21 EMA > 44 EMA, rallied 10%+, and are now pulling back into the EMA band on dry volume.</p>', unsafe_allow_html=True)

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

# --- POST-CROSS PULLBACK ALGORITHM ---
def analyze_post_cross_pullback(ticker, period, interval):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 100: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        
        # Calculate EMAs and Volume Average
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        
        latest_close = df['Close'].iloc[-1]
        latest_low = df['Low'].iloc[-1]
        ema21_live = df['EMA_21'].iloc[-1]
        ema44_live = df['EMA_44'].iloc[-1]
        vol_avg_live = df['Vol_Avg'].iloc[-1]
        
        # 1. Current Trend Verification
        if ema21_live <= ema44_live:
            return None
            
        # 2. Find the most recent Bullish Cross (21 crossing above 44)
        df['Bull_Cross'] = (df['EMA_21'] > df['EMA_44']) & (df['EMA_21'].shift(1) <= df['EMA_44'].shift(1))
        cross_indices = df[df['Bull_Cross']].index
        
        if len(cross_indices) == 0:
            return None # No cross happened in the scanned period
            
        last_cross_date = cross_indices[-1]
        post_cross_df = df.loc[last_cross_date:]
        
        # 3. 10%+ Expansion Check
        cross_price = df.loc[last_cross_date, 'Close']
        max_high_since_cross = post_cross_df['High'].max()
        
        move_pct = ((max_high_since_cross - cross_price) / cross_price) * 100.0
        
        if move_pct < 10.0:
            return None # The move wasn't strong enough (less than 10%)
            
        # 4. Retracement into the EMA Zone
        # Low must be touching or dipping below the 21 EMA, while Close holds near/above the 44 EMA
        is_in_ema_zone = (latest_low <= (ema21_live * 1.015)) and (latest_close >= (ema44_live * 0.985))
        
        if not is_in_ema_zone:
            return None
            
        # Ensure we are currently down from the recent peak (a true pullback)
        if latest_close >= (max_high_since_cross * 0.95):
            return None
            
        # 5. Volume Dry-Up (Accumulation Phase)
        # Average volume of the last 3 days of the pullback must be < 75% of the 20-day average
        pullback_vol = df['Volume'].iloc[-3:].mean()
        
        if pullback_vol >= (vol_avg_live * 0.75):
            return None
            
        vol_dryness = round((pullback_vol / vol_avg_live) * 100, 1)
        
        return {
            "Ticker": ticker.replace('.NS', ''),
            "Live Price": f"₹{round(latest_close, 2)}",
            "Post-Cross Move": f"🚀 +{round(move_pct, 1)}% Rally",
            "EMA Zone Status": "🎯 Retesting 21/44 Band",
            "Pullback Volume": f"🔇 {vol_dryness}% of Avg (Dry)",
            "Action": "🔔 Ready for Reversal"
        }
                
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Sector")
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
        help="Select the chart horizon to hunt for the EMA Cross, Rally, and Pullback."
    )
    
    st.divider()
    st.success(f"**Engine Active**\n\n1. 21 crosses above 44 EMA\n2. Price rallies > 10%\n3. Pulls back into 21/44 band\n4. Volume < 75% of Average")
    execute_button = st.button("🚀 EXECUTE SCAN", type="primary", use_container_width=True)

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
    st.info(f"Scanning **{len(symbols_list)} stocks** for 10%+ Post-Cross Expansion and Dry Pullbacks on the **{tf_input}** chart...")
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(analyze_post_cross_pullback, ticker, active_cfg["period"], active_cfg["interval"]): ticker 
            for ticker in symbols_list
        }
        
        completed_count = 0
        for future in as_completed(futures_map):
            completed_count += 1
            result = future.result()
            if result:
                confirmed_setups.append(result)
            
            percent_complete = completed_count / len(symbols_list)
            progress_ui.progress(percent_complete, text=f"Analyzing Crosses & Pullbacks: {completed_count}/{len(symbols_list)}")
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        # Sort by the largest Post-Cross Move first
        results_df['Raw_Move'] = results_df['Post-Cross Move'].str.extract(r'\+(\d+\.\d+)%').astype(float)
        results_df = results_df.sort_values(by='Raw_Move', ascending=False).drop(columns=['Raw_Move'])
        
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks successfully executing the Post-Cross Accumulation strategy.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks currently match. This means no {tf_input} stocks have recently completed a 10%+ rally following a 21/44 EMA cross AND are currently pulling back on dry volume.")
