import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import io
from scipy.signal import argrelextrema
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Simple Support & EMA Scanner", layout="wide", page_icon="🟢")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #10B981; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🟢 Clean S/R & EMA Boring Candle Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for uptrends (20 EMA > 50 EMA) hitting a 2nd/3rd touch Support with a live Boring Candle.</p>', unsafe_allow_html=True)

# --- ROBUST DATA UNIVERSE LOADER (Bypasses NSE Blocks) ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY MIDCAP 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY SMALLCAP 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    url = urls.get(category)
    
    try:
        # Using headers to pretend we are a real browser so NSE doesn't block the download
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        # Massive built-in failsafe just in case NSE servers go down
        st.sidebar.warning("⚠️ NSE Server blocked full list. Using top 50 highly liquid failsafe stocks.")
        return ['ADANIENT.NS', 'ADANIPORTS.NS', 'APOLLOHOSP.NS', 'ASIANPAINT.NS', 'AXISBANK.NS', 'BAJAJ-AUTO.NS', 'BAJFINANCE.NS', 'BAJAJFINSV.NS', 'BPCL.NS', 'BHARTIARTL.NS', 'BRITANNIA.NS', 'CIPLA.NS', 'COALINDIA.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'EICHERMOT.NS', 'GRASIM.NS', 'HCLTECH.NS', 'HDFCBANK.NS', 'HDFCLIFE.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS', 'HINDUNILVR.NS', 'ICICIBANK.NS', 'ITC.NS', 'INDUSINDBK.NS', 'INFY.NS', 'JSWSTEEL.NS', 'KOTAKBANK.NS', 'LTIM.NS', 'LT.NS', 'M&M.NS', 'MARUTI.NS', 'NTPC.NS', 'NESTLEIND.NS', 'ONGC.NS', 'POWERGRID.NS', 'RELIANCE.NS', 'SBILIFE.NS', 'SBIN.NS', 'SUNPHARMA.NS', 'TCS.NS', 'TATACONSUM.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS', 'TECHM.NS', 'TITAN.NS', 'UPL.NS', 'ULTRACEMCO.NS', 'WIPRO.NS']

# --- SIMPLE, HUMAN-LIKE ALGORITHM ---
def analyze_simple_setup(ticker, period, interval):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 100: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low'])
        
        # 1. EMA Rule: 20 EMA must be above 50 EMA
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        if df['EMA_20'].iloc[-1] <= df['EMA_50'].iloc[-1]:
            return None # Skip if not in a solid uptrend
            
        # 2. Boring Candle Rule: Current or previous candle must be tight (Body < 50%)
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = (df['High'] - df['Low']).replace(0, 0.00001)
        df['Body_Ratio'] = df['Body'] / df['Range']
        
        # Check the last two candles. If neither is boring, skip.
        if df['Body_Ratio'].iloc[-1] > 0.50 and df['Body_Ratio'].iloc[-2] > 0.50:
            return None
            
        # 3. Support Touches Rule (Find historical swing lows)
        lows = df['Low'].values
        # Find major swing troughs (lowest low of 5 candles left and right)
        valley_idx = argrelextrema(lows, np.less, order=5)[0]
        
        # Filter out swings that just happened in the last 5 days
        historical_lows = [lows[i] for i in valley_idx if i < len(df) - 5]
        
        current_low = min(df['Low'].iloc[-1], df['Low'].iloc[-2])
        latest_close = df['Close'].iloc[-1]
        
        # We allow a 1.5% buffer zone to consider it the "same" support level
        buffer_zone = current_low * 0.015 
        
        touch_count = 1 # The current price action counts as Touch #1
        
        for h_low in historical_lows:
            if abs(h_low - current_low) <= buffer_zone:
                touch_count += 1
                
        # If it has hit this zone before (making this the 2nd, 3rd, or 4th touch)
        if 2 <= touch_count <= 4:
            return {
                "Ticker": ticker.replace('.NS', ''),
                "Live Price": f"₹{round(latest_close, 2)}",
                "Trend (EMA)": "✅ 20 > 50 (Uptrend)",
                "Support Strength": f"⭐ {touch_count} Touches (Validated)",
                "Current Action": "🟢 Boring Candle Forming",
                "Support Level": f"~₹{round(current_low, 2)}"
            }
            
        return None
    except Exception:
        return None

# --- SUPER CLEAN SIDEBAR ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Universe", ["NIFTY 500", "NIFTY 50", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 250"])
    
    st.divider()
    st.header("2. Execution Timeframe")
    tf_input = st.selectbox("Select Chart Horizon:", ["15 Minutes", "1 Hour", "1D", "1W", "1M"], index=2)
    
    st.divider()
    st.success("✅ **Automated Logic Active**\n\n1. 20 EMA > 50 EMA\n2. 2 to 4 Support Touches\n3. Live Boring Candle Base")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for Boring Candles at Multi-Touch Support on the **{tf_input}** chart...")
    
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
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(
                analyze_simple_setup, ticker, active_cfg["period"], active_cfg["interval"]
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
        st.success(f"🎯 Complete: Found **{len(results_df)}** perfectly aligned swing setups.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks match right now. This means no uptrending stocks are currently resting on a historical support with a boring candle.")
