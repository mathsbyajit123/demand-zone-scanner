import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="21/44 EMA Low-Vol Pullback Scanner", layout="wide", page_icon="🪃")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #10B981; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🪃 21/44 EMA Low-Volume Accumulation Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for stocks in strong uptrends (21 > 44 EMA) pulling back to the 21/44 EMA zone on extremely low volume.</p>', unsafe_allow_html=True)

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

# --- LOW VOLUME RETRACEMENT ALGORITHM ---
def analyze_ema_pullback(ticker, period, interval):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 60: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        
        # Calculate 21 and 44 EMAs + 20-period Volume Average
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        
        latest_close = df['Close'].iloc[-1]
        latest_low = df['Low'].iloc[-1]
        ema21_live = df['EMA_21'].iloc[-1]
        ema44_live = df['EMA_44'].iloc[-1]
        vol_avg_live = df['Vol_Avg'].iloc[-1]
        
        # Rule 1: Uptrend Filter (21 EMA must be strictly above 44 EMA)
        if ema21_live <= ema44_live:
            return None
            
        # Rule 2: Prior Expansion Check (Must have had a move/rally above 21 EMA in the last 15 candles)
        recent_high_15 = df['High'].iloc[-15:].max()
        if recent_high_15 < (ema21_live * 1.025): # At least 2.5% move above the 21 EMA
            return None
            
        # Rule 3: Retracement Condition (Price pulled back to or inside the 21 EMA - 44 EMA band)
        # Low is touching/below 21 EMA, but Close is holding above or near 44 EMA
        is_pullback_zone = (latest_low <= (ema21_live * 1.005)) and (latest_close >= (ema44_live * 0.99))
        if not is_pullback_zone:
            return None
            
        # Rule 4: Volume Dry-Up (Average volume over the last 3 pullback bars is noticeably lower than 20-period Avg)
        pullback_vol_avg = df['Volume'].iloc[-3:].mean()
        
        # Pullback volume must be < 80% of the 20-period average volume
        if pullback_vol_avg >= (vol_avg_live * 0.80):
            return None
            
        vol_dryup_pct = round((pullback_vol_avg / vol_avg_live) * 100, 1)
        
        return {
            "Ticker": ticker.replace('.NS', ''),
            "Live Price": f"₹{round(latest_close, 2)}",
            "EMA Trend": "✅ 21 EMA > 44 EMA",
            "Zone Status": "🎯 Testing 21/44 EMA Band",
            "Retracement Volume": f"🔇 {vol_dryup_pct}% of Avg Vol (Dry)",
            "Action": "🟢 Watch for Reversal Candle"
        }
                
    except Exception:
        return None

# --- CLEAN SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Sector/Universe")
    sector_input = st.selectbox("Market Universe:", [
        "NIFTY 500", 
        "NIFTY 50", 
        "NIFTY NEXT 50", 
        "NIFTY BANK", 
        "NIFTY MIDCAP 100", 
        "NIFTY SMALLCAP 250"
    ])
    
    st.divider()
    st.header("2. Execution Timeframe")
    tf_input = st.selectbox("Select Chart Horizon:", ["15 Minutes", "1 Hour", "1D", "1W", "1M"], index=2)
    
    st.divider()
    st.success("✅ **Active Setup**\n\n1. 21 EMA > 44 EMA\n2. Prior Expansion/Rally\n3. Retracement into 21-44 EMA Band\n4. Volume < 80% of Average (Low Vol)")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for low-volume EMA pullbacks on the **{tf_input}** chart...")
    
    tf_configs = {
        "15 Minutes": {"period": "60d", "interval": "15m"},
        "1 Hour": {"period": "730d", "interval": "1h"},
        "1D": {"period": "2y", "interval": "1d"},
        "1W": {"period": "5y", "interval": "1wk"},
        "1M": {"period": "10y", "interval": "1mo"}
    }
    active_cfg = tf_configs[tf_input]
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(
                analyze_ema_pullback, ticker, active_cfg["period"], active_cfg["interval"]
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
            progress_ui.progress(percent_complete, text=f"Analyzing Low-Volume Retracements: {completed_count}/{len(symbols_list)}")
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        # Sort by the lowest volume percentage (driest volume at top)
        results_df['Raw_Vol'] = results_df['Retracement Volume'].str.extract(r'(\d+\.\d+)%').astype(float)
        results_df = results_df.sort_values(by='Raw_Vol', ascending=True).drop(columns=['Raw_Vol'])
        
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks in a low-volume EMA accumulation pullback.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks matched. This means no uptrending stocks are currently resting inside the 21/44 EMA band on low volume in the {tf_input} timeframe right now.")
