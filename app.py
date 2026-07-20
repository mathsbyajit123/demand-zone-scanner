import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Doji Origin S/D Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #8B5CF6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 Doji Origin (Base-to-Leg) Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for tight Doji bases that launched a massive move, where price has now returned to the origin zone.</p>', unsafe_allow_html=True)

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

# --- DOJI & EXPLOSION ALGORITHM ---
def analyze_doji_origin(ticker, period, interval):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 60: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low'])
        
        # Calculate candle metrics
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = (df['High'] - df['Low']).replace(0, 0.00001)
        df['Body_Ratio'] = df['Body'] / df['Range']
        df['Is_Green'] = df['Close'] > df['Open']
        
        # Calculate average volatility to ensure the Doji isn't massive and the Leg-Out IS massive
        df['Avg_Range'] = df['Range'].rolling(14).mean().shift(1)
        df['Avg_Body'] = df['Body'].rolling(14).mean().shift(1)
        
        latest_close = df['Close'].iloc[-1]
        
        # Loop backward to find the setup (skip the most recent candles so we have room for the retracement)
        for i in range(len(df) - 5, 15, -1):
            
            # 1. Identify the Base (Small to Medium Doji / Boring Candle)
            # Body must be less than 50% of the wick range, and the overall range shouldn't be unusually huge
            is_doji = df['Body_Ratio'].iloc[i] <= 0.50 and df['Range'].iloc[i] <= (df['Avg_Range'].iloc[i] * 1.5)
            if not is_doji: continue
                
            doji_high = df['High'].iloc[i]
            doji_low = df['Low'].iloc[i]
            
            # 2. Identify the Great Move (Leg-Out)
            c1 = df.iloc[i + 1]
            c2 = df.iloc[i + 2]
            
            # Condition A: One single massive leg-out candle (Body > 60% of range, and much larger than average body)
            one_strong_leg = c1['Body_Ratio'] >= 0.60 and c1['Body'] >= (c1['Avg_Body'] * 1.5)
            
            # Condition B: Two consecutive healthy leg-out candles in the same direction
            two_healthy_legs = (c1['Body_Ratio'] >= 0.50 and c2['Body_Ratio'] >= 0.50) and (c1['Is_Green'] == c2['Is_Green'])
            
            if not (one_strong_leg or two_healthy_legs): continue
                
            is_bullish = c1['Is_Green']
            zone_type = "🟢 DEMAND" if is_bullish else "🔴 SUPPLY"
            
            # 3. Verify it actually left the zone (The Rally or Drop)
            path_df = df.iloc[i + 2 : -1]
            if path_df.empty: continue
                
            if is_bullish:
                max_away = path_df['High'].max()
                if max_away < (doji_high * 1.02): continue # Didn't rally far enough before returning
            else:
                min_away = path_df['Low'].min()
                if min_away > (doji_low * 0.98): continue # Didn't drop far enough before returning
                    
            # 4. Check Live Retracement (Is price inside the Doji zone right now?)
            # Adding a tiny 0.5% buffer so you don't miss trades sitting right on the edge of the zone
            buffer = doji_high * 0.005
            is_testing = (doji_low - buffer) <= latest_close <= (doji_high + buffer)
            
            if is_testing:
                move_desc = "🚀 1 Massive Leg-Out" if one_strong_leg else "📈 2-3 Healthy Leg-Outs"
                
                return {
                    "Ticker": ticker.replace('.NS', ''),
                    "Zone Type": zone_type,
                    "Live Price": f"₹{round(latest_close, 2)}",
                    "Doji Zone Range": f"₹{round(doji_low, 2)} - ₹{round(doji_high, 2)}",
                    "Explosive Move": move_desc,
                    "Status": "✅ Pulled back to Origin"
                }
                
        return None
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
    st.success("✅ **Active Strategy**\n\n1. Identify tight Doji base\n2. Verify explosive Leg-Out\n3. Wait for price to pull back exactly to Doji boundaries.")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE DOJI SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for Doji Origin zones on the **{tf_input}** chart...")
    
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
                analyze_doji_origin, ticker, active_cfg["period"], active_cfg["interval"]
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
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks resting perfectly at the Doji origin zone.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks matched. This means no Nifty stocks are currently pulling back perfectly into a historical Doji base on the {tf_input} timeframe right now.")
