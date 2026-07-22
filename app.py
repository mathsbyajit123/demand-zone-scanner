import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="21/44 EMA Trend Scanner", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #3B82F6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📈 21/44 EMA Momentum Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for pure uptrends: Price > 21 EMA, 21 EMA > 44 EMA, with both moving averages sloping upward.</p>', unsafe_allow_html=True)

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
        st.sidebar.warning("⚠️ NSE Server blocked full list. Using top liquid failsafe stocks.")
        return ['RELIANCE.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'TCS.NS', 'ITC.NS', 'LT.NS', 'SBIN.NS', 'BHARTIARTL.NS']

# --- EMA TREND ALGORITHM ---
def analyze_ema_trend(ticker, period, interval):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 60: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close'])
        
        # Calculate 21 and 44 EMAs
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
        
        latest_close = df['Close'].iloc[-1]
        ema21_live = df['EMA_21'].iloc[-1]
        ema44_live = df['EMA_44'].iloc[-1]
        
        # Get EMA values from 5 candles ago to check the slope (momentum)
        ema21_past = df['EMA_21'].iloc[-5]
        ema44_past = df['EMA_44'].iloc[-5]
        
        # Rule 1: Live Price must be ABOVE the 21 EMA
        if latest_close <= ema21_live:
            return None
            
        # Rule 2: 21 EMA must be ABOVE the 44 EMA
        if ema21_live <= ema44_live:
            return None
            
        # Rule 3: Both EMAs must be sloping UPWARD (Current value > Past value)
        if ema21_live <= ema21_past or ema44_live <= ema44_past:
            return None
            
        # Calculate the 21 EMA slope percentage for display
        slope_pct = ((ema21_live - ema21_past) / ema21_past) * 100.0
        
        return {
            "Ticker": ticker.replace('.NS', ''),
            "Live Price": f"₹{round(latest_close, 2)}",
            "Trend Status": "🟢 Price > 21 EMA",
            "EMA Alignment": "✅ 21 EMA > 44 EMA",
            "Momentum (Slope)": f"📈 Upward (+{round(slope_pct, 2)}%)",
            "Action": "🚀 Confirmed Uptrend"
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
    st.success("✅ **Active Strategy**\n\n1. Price is Above 21 EMA\n2. 21 EMA is Above 44 EMA\n3. EMAs are Sloping Upward")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE TREND SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for 21/44 EMA momentum on the **{tf_input}** chart...")
    
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
                analyze_ema_trend, ticker, active_cfg["period"], active_cfg["interval"]
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
            progress_ui.progress(percent_complete, text=f"Analyzing {completed_count}/{len(symbols_list)}")
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        # Sort by slope percentage (extracted from string) to show the strongest momentum at the top
        results_df['Raw_Slope'] = results_df['Momentum (Slope)'].str.extract(r'\(\+(.*)%\)').astype(float)
        results_df = results_df.sort_values(by='Raw_Slope', ascending=False).drop(columns=['Raw_Slope'])
        
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks in a confirmed uptrend.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks matched. This means no Nifty stocks are currently meeting the strict 21/44 EMA upward slope conditions on the {tf_input} timeframe right now.")
