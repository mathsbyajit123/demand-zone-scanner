import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Pure Demand Zone Scanner", layout="wide", page_icon="🟢")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #10B981; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🟢 Institutional Demand Zone Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for live price re-testing historically proven Demand Bases (1-6 Boring Candles followed by a strong rally).</p>', unsafe_allow_html=True)

# --- DATA UNIVERSE LOADER ---
@st.cache_data(ttl=86400)
def get_sector_symbols(sector_name):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY MIDCAP 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY SMALLCAP 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv"
    }
    
    try:
        df = pd.read_csv(urls.get(sector_name))
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        # Fallback just in case of NSE server timeout
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- PURE DEMAND ZONE ALGORITHM ---
def analyze_demand_zone(ticker, period, interval, min_base, max_base, tolerance_pct):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 50: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low'])
        latest_close = df['Close'].iloc[-1]
        
        # Calculate Boring Candle Metrics
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = (df['High'] - df['Low']).replace(0, 0.00001)
        df['Body_Ratio'] = df['Body'] / df['Range']
        df['Is_Green'] = df['Close'] > df['Open']
        
        BORING_THRESHOLD = 0.50
        LEG_OUT_THRESHOLD = 0.60  # The "good move" requirement
        
        # Look back through history (skip the most recent candles to allow a pullback to occur)
        for i in range(len(df) - 2, 10, -1):
            hero_idx = i
            
            # 1. Did a strong Leg Out happen here? (Good upward move originating from the zone)
            if df['Body_Ratio'].iloc[hero_idx] < LEG_OUT_THRESHOLD or not df['Is_Green'].iloc[hero_idx]: 
                continue
                
            # 2. Find the Base (Boring Candles)
            base_count = 0
            base_indices = []
            for j in range(hero_idx - 1, max(0, hero_idx - 10), -1):
                if df['Body_Ratio'].iloc[j] <= BORING_THRESHOLD:
                    base_count += 1
                    base_indices.append(j)
                else:
                    break
                    
            if not (min_base <= base_count <= max_base): 
                continue
                
            base_candles = df.iloc[base_indices]
            
            # 3. Define the Demand Zone
            sd_upper = base_candles['High'].max() # Proximal Line (Top of Base)
            sd_lower = base_candles['Low'].min()  # Distal Line (Bottom of Base)
            
            # 4. Validation: Check if the zone was already destroyed by a candle closing below it
            post_zone_df = df.iloc[hero_idx + 1: -1] # Everything after leg out, up to the live candle
            if not post_zone_df.empty:
                if post_zone_df['Close'].min() < sd_lower:
                    continue # Zone is dead/invalidated
            
            # 5. Live Price Proximity (Market is at that zone now)
            deviation = sd_upper * (tolerance_pct / 100.0)
            
            # Is live price touching the zone (or within the tolerance buffer above it) and above the distal line?
            if sd_lower <= latest_close <= (sd_upper + deviation):
                return {
                    "Ticker": ticker.replace('.NS', ''),
                    "Status": "🟢 IN DEMAND ZONE",
                    "Live Price": f"₹{round(latest_close, 2)}",
                    "Base Formed": f"{base_count} Boring Candles",
                    "Demand Zone (Proximal - Distal)": f"₹{round(sd_upper, 2)} - ₹{round(sd_lower, 2)}",
                    "Distance to Zone Top": f"{round(((latest_close - sd_upper)/sd_upper)*100, 2)}%"
                }
                
        return None
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Index", ["NIFTY 50", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 250"])
    
    st.divider()
    st.header("2. Execution Timeframe")
    tf_input = st.selectbox("Select Chart Horizon:", ["15 Minutes", "1 Hour", "1D", "1W", "1M"], index=2)
    
    st.divider()
    st.header("3. Boring Candle Parameters")
    col1, col2 = st.columns(2)
    with col1:
        min_base_input = st.number_input("Min Base Candles", 1, 6, 1)
    with col2:
        max_base_input = st.number_input("Max Base Candles", 1, 6, 5)
        
    st.divider()
    st.header("4. Zone Proximity")
    proximity_pct = st.slider("Entry Buffer (+%)", 0.0, 3.0, 1.0, step=0.1, help="How far above the top of the Demand Zone can the live price be to still trigger the scanner?")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE DEMAND SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = get_sector_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for Demand Zone Pullbacks on the **{tf_input}** chart...")
    
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
                analyze_demand_zone, ticker, active_cfg["period"], active_cfg["interval"],
                min_base_input, max_base_input, proximity_pct
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
            progress_ui.progress(percent_complete, text=f"Scanning Liquidity Zones: {completed_count}/{len(symbols_list)}")
            
            # Gentle throttle
            if completed_count % 30 == 0:
                time.sleep(0.3)
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks resting inside historical Demand Zones.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks are currently testing a valid Demand Zone. Try increasing your Entry Buffer (+%) or expanding the Base Candle limits.")
