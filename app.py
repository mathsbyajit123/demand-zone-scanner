import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="MTF Weekly + Daily EMA Accumulation Scanner", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #10B981; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ Multi-Timeframe (Weekly + Daily) Accumulation Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Weekly Alignment: Price > 21 WEMA > 44 WEMA | Daily Trigger: Low-Volume Retracement into 21/44 EMA Band</p>', unsafe_allow_html=True)

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

# --- MULTI-TIMEFRAME ANALYSIS ALGORITHM ---
def analyze_mtf_accumulation(ticker):
    try:
        stock = yf.Ticker(ticker)
        # Fetch 2 years of daily data to generate both daily and weekly EMAs
        df = stock.history(period="2y", interval="1d")
        
        if df.empty or len(df) < 150: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        
        # ==========================================
        # 1. WEEKLY TIMEFRAME CONFLUENCE (MACRO FILTER)
        # ==========================================
        df_weekly = df.resample('W-FRI').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        
        df_weekly['W_EMA_21'] = df_weekly['Close'].ewm(span=21, adjust=False).mean()
        df_weekly['W_EMA_44'] = df_weekly['Close'].ewm(span=44, adjust=False).mean()
        
        latest_w_close = df_weekly['Close'].iloc[-1]
        latest_w_ema21 = df_weekly['W_EMA_21'].iloc[-1]
        latest_w_ema44 = df_weekly['W_EMA_44'].iloc[-1]
        
        # Rule W1: Weekly Price > 21 WEMA
        if latest_w_close <= latest_w_ema21:
            return None
            
        # Rule W2: 21 WEMA > 44 WEMA (Macro Bullish Structure)
        if latest_w_ema21 <= latest_w_ema44:
            return None

        # ==========================================
        # 2. DAILY TIMEFRAME RETRACEMENT (TRIGGER)
        # ==========================================
        df['D_EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['D_EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
        df['Vol_Avg_20'] = df['Volume'].rolling(20).mean()
        
        d_close = df['Close'].iloc[-1]
        d_low = df['Low'].iloc[-1]
        d_ema21 = df['D_EMA_21'].iloc[-1]
        d_ema44 = df['D_EMA_44'].iloc[-1]
        d_vol_avg = df['Vol_Avg_20'].iloc[-1]
        
        # Rule D1: Daily 21 EMA > 44 EMA
        if d_ema21 <= d_ema44:
            return None
            
        # Rule D2: Prior Move / Rally (Price reached at least 2.5% above 21 Daily EMA in last 15 days)
        recent_high_15 = df['High'].iloc[-15:].max()
        if recent_high_15 < (d_ema21 * 1.025):
            return None
            
        # Rule D3: Retracement to Daily EMA zone
        # Daily Low is touching/below 21 EMA, but Close holds above/near 44 EMA
        is_in_ema_zone = (d_low <= (d_ema21 * 1.005)) and (d_close >= (d_ema44 * 0.99))
        if not is_in_ema_zone:
            return None
            
        # Rule D4: DRY VOLUME (Average volume over last 3 pullback days < 75% of 20-day Average)
        pullback_vol_3d = df['Volume'].iloc[-3:].mean()
        if pullback_vol_3d >= (d_vol_avg * 0.75):
            return None
            
        vol_dryness_pct = round((pullback_vol_3d / d_vol_avg) * 100, 1)
        
        return {
            "Ticker": ticker.replace('.NS', ''),
            "Live Price": f"₹{round(d_close, 2)}",
            "Weekly Macro": "✅ W-Close > 21 WEMA > 44 WEMA",
            "Daily Setup": "🎯 Testing Daily 21/44 EMA Band",
            "Retracement Volume": f"🔇 {vol_dryness_pct}% of Avg Vol (Dry)",
            "Action": "🔥 High-Probability Reversal Zone"
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
    st.success("✅ **MTF Confluence Rules**\n\n1. **Weekly:** Close > 21 WEMA > 44 WEMA\n2. **Daily:** 21 EMA > 44 EMA\n3. **Daily:** Retracement to 21/44 EMA\n4. **Volume:** < 75% of 20-day Average")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE MTF SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for Multi-Timeframe Accumulation Setups...")
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(analyze_mtf_accumulation, ticker): ticker 
            for ticker in symbols_list
        }
        
        completed_count = 0
        for future in as_completed(futures_map):
            completed_count += 1
            result = future.result()
            if result:
                confirmed_setups.append(result)
            
            percent_complete = completed_count / len(symbols_list)
            progress_ui.progress(percent_complete, text=f"Analyzing MTF Alignment: {completed_count}/{len(symbols_list)}")
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        # Sort by driest volume first
        results_df['Raw_Vol'] = results_df['Retracement Volume'].str.extract(r'(\d+\.\d+)%').astype(float)
        results_df = results_df.sort_values(by='Raw_Vol', ascending=True).drop(columns=['Raw_Vol'])
        
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks aligned on Weekly macro trend & Daily low-volume pullback.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks currently match all conditions. This means no Weekly uptrending stocks are undergoing a dry-volume Daily pullback right now.")
