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
st.set_page_config(page_title="200 EMA Liquidity Sweep Scanner", layout="wide", page_icon="🐋")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #0EA5E9; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🐋 200 EMA "W" Liquidity Sweep Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Hunts for institutional stop-hunts: W-patterns that sweep below the 200 EMA on low volume, close above it, and break out with massive volume.</p>', unsafe_allow_html=True)

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

# --- INSTITUTIONAL "W" SWEEP ALGORITHM ---
def analyze_liquidity_sweep(ticker, period, interval):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        # We need at least 200 bars to accurately calculate the 200 EMA
        if df.empty or len(df) < 250: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        
        # Calculate the 200 EMA and 20-period Average Volume
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        
        # Focus on the recent price action (last 45 bars) to find the W pattern
        recent = df.iloc[-45:].copy()
        recent.reset_index(inplace=True)
        
        # 1. Find all local swing lows in this recent period
        lows_idx = argrelextrema(recent['Low'].values, np.less, order=3)[0]
        
        # 2. Filter for sweeps: Low must wick below/touch 200 EMA, but Close MUST be above it
        valid_sweeps = []
        for idx in lows_idx:
            row = recent.iloc[idx]
            # Price sweeps near/below 200 EMA but closes above it (no strong closes below)
            if row['Low'] <= (row['EMA_200'] * 1.01) and row['Close'] >= (row['EMA_200'] * 0.99):
                valid_sweeps.append(idx)
                
        # We need a "W" pattern, so we need at least 2 touches/sweeps
        if len(valid_sweeps) >= 2:
            leg1_idx = valid_sweeps[-2] # First bottom of the W
            leg2_idx = valid_sweeps[-1] # Second bottom of the W
            
            # Must be separated by a few bars to form a proper W
            if leg2_idx - leg1_idx >= 4:
                
                # 3. Find the Neckline (the swing high between the two bottoms)
                neckline = recent['High'].iloc[leg1_idx:leg2_idx].max()
                
                # 4. Check Liquidity Grab: Second leg should dip as low or lower than the first to grab stops
                # Or at least be a clear double bottom
                if recent['Low'].iloc[leg2_idx] <= (recent['Low'].iloc[leg1_idx] * 1.02):
                    
                    # 5. Volume Check: Volume on the downward sweep candles must be low/average (sellers exhausted)
                    vol_leg1 = recent['Volume'].iloc[leg1_idx]
                    avg_vol1 = recent['Vol_Avg'].iloc[leg1_idx]
                    vol_leg2 = recent['Volume'].iloc[leg2_idx]
                    avg_vol2 = recent['Vol_Avg'].iloc[leg2_idx]
                    
                    if vol_leg1 <= (avg_vol1 * 1.2) and vol_leg2 <= (avg_vol2 * 1.2):
                        
                        # 6. The Breakout Check: Current price breaking the Neckline with MASSIVE volume
                        latest = recent.iloc[-1]
                        is_green = latest['Close'] > latest['Open']
                        
                        # Price is breaking the W neckline OR recently broke it
                        if latest['Close'] > neckline:
                            # Breakout volume must be massive (> 1.5x average)
                            if latest['Volume'] >= (latest['Vol_Avg'] * 1.5) and is_green:
                                
                                vol_multiplier = latest['Volume'] / latest['Vol_Avg']
                                
                                return {
                                    "Ticker": ticker.replace('.NS', ''),
                                    "Live Price": f"₹{round(latest['Close'], 2)}",
                                    "200 EMA Sweep": "✅ W-Pattern Liquidity Grab",
                                    "Base Volume": "🔇 Low (Sellers Exhausted)",
                                    "Breakout Volume": f"🚀 Massive ({round(vol_multiplier, 1)}x Avg)",
                                    "Action": "🔥 Neckline Broken (Bullish)"
                                }
                                
        return None
    except Exception:
        return None

# --- CLEAN SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Sector")
    sector_input = st.selectbox("Market Universe:", [
        "NIFTY 500", 
        "NIFTY 50", 
        "NIFTY NEXT 50", 
        "NIFTY MIDCAP 100", 
        "NIFTY SMALLCAP 250"
    ])
    
    st.divider()
    st.header("2. Execution Timeframe")
    tf_input = st.selectbox("Select Chart Horizon:", ["1D", "1W", "1 Hour", "15 Minutes", "1M"], index=0)
    
    st.divider()
    st.success("✅ **Active Setup**\n\n1. Double Sweep of 200 EMA (W Pattern)\n2. Closes Above 200 EMA\n3. Low Volume on the Drop\n4. Massive Volume on Green Breakout")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE LIQUIDITY SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for 200 EMA Liquidity Sweeps on the **{tf_input}** chart...")
    
    # We require long periods to ensure the 200 EMA calculates correctly
    tf_configs = {
        "15 Minutes": {"period": "60d", "interval": "15m"},
        "1 Hour": {"period": "730d", "interval": "1h"},
        "1D": {"period": "3y", "interval": "1d"},
        "1W": {"period": "10y", "interval": "1wk"},
        "1M": {"period": "25y", "interval": "1mo"}
    }
    active_cfg = tf_configs[tf_input]
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(
                analyze_liquidity_sweep, ticker, active_cfg["period"], active_cfg["interval"]
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
            progress_ui.progress(percent_complete, text=f"Analyzing Institutional Sweeps: {completed_count}/{len(symbols_list)}")
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        # Sort by the most massive volume multipliers first
        results_df['Raw_Vol'] = results_df['Breakout Volume'].str.extract(r'(\d+\.\d+)x').astype(float)
        results_df = results_df.sort_values(by='Raw_Vol', ascending=False).drop(columns=['Raw_Vol'])
        
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks executing a 200 EMA Liquidity Sweep with massive breakout volume.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks matched. This setup is rare and highly explosive. It means no stocks are currently breaking the neckline of a 200 EMA W-pattern on massive volume in the {tf_input} timeframe today.")
