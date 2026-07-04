import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Institutional S/D Matrix Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #0284c7; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 Institutional Supply & Demand Zone Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Asynchronous Order-Block Engine. Locates fresh structural imbalances, base clusters, and breakout extensions.</p>', unsafe_allow_html=True)

# --- REAL-TIME MULTI-SECTOR LOADER ---
@st.cache_data(ttl=86400)
def get_sector_symbols(sector_name):
    urls = {
        "NIFTY 50 (Large Cap)": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY Smallcap 100": "https://archives.nseindia.com/content/indices/ind_niftysmallcap100list.csv",
        "NIFTY 500 (All Sectors)": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[sector_name])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        st.error("NSE Server Timeout. Loading backup core liquidity tickers...")
        return ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- INTERNAL 75m AGGREGATOR ---
def convert_to_75m(df_15m):
    if df_15m is None or df_15m.empty:
        return None
    df_15m['Date_Str'] = df_15m.index.strftime('%Y-%m-%d')
    df_15m['Bar_Chunk'] = df_15m.groupby('Date_Str').cumcount() // 5
    resampled = df_15m.groupby(['Date_Str', 'Bar_Chunk']).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).reset_index(drop=True)
    timestamps = df_15m.groupby(['Date_Str', 'Bar_Chunk']).index.last().reset_index(drop=True)
    resampled.index = timestamps
    return resampled

# --- ORDER BLOCK SUPPLY/DEMAND CORING ENGINE ---
def analyze_supply_demand(ticker, config, tf_choice, min_base, max_base, mode_choice):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=config["period"], interval=config["interval"])
        
        if df.empty:
            return None
            
        if tf_choice == "75 Min":
            df = convert_to_75m(df)
            
        if df is None or len(df) < 25:
            return None
            
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        latest_close = df['Close'].iloc[-1]
        
        # Calculate structural characteristics per candle
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = df['High'] - df['Low']
        df['Range'] = df['Range'].replace(0, 0.00001) # Avoid division by zero
        df['Body_Ratio'] = df['Body'] / df['Range']
        df['Is_Green'] = df['Close'] > df['Open']
        
        # Threshold constants
        BORING_THRESHOLD = 0.50
        
        # Scan backward from the end of the historical sequence to find structural zones
        for i in range(len(df) - 10, 10, -1):
            # Check the "Hero" candle (The leg-out expansion bar)
            hero_idx = i
            if df['Body_Ratio'].iloc[hero_idx] <= BORING_THRESHOLD:
                continue
            
            is_hero_up = df['Is_Green'].iloc[hero_idx]
            
            # Count the preceding base (boring) candles
            base_count = 0
            base_indices = []
            for j in range(hero_idx - 1, 0, -1):
                if df['Body_Ratio'].iloc[j] <= BORING_THRESHOLD:
                    base_count += 1
                    base_indices.append(j)
                else:
                    break
                    
            if not (min_base <= base_count <= max_base):
                continue
                
            # Identify the Leg-In Candle (Pre-base structure)
            leg_in_idx = hero_idx - base_count - 1
            is_leg_in_up = df['Is_Green'].iloc[leg_in_idx]
            
            # Determine Pattern Structural Classification
            zone_type = None
            structural_pattern = ""
            
            if is_hero_up: # DEMAND FORMATION
                zone_type = "Demand"
                if is_leg_in_up:
                    structural_pattern = "Rally-Base-Rally (RBR)"
                else:
                    structural_pattern = "Drop-Base-Rally (DBR)"
            else: # SUPPLY FORMATION
                zone_type = "Supply"
                if not is_leg_in_up:
                    structural_pattern = "Drop-Base-Drop (DBD)"
                else:
                    structural_pattern = "Rally-Base-Drop (RBD)"
                    
            # Filter layout configuration by interface selection
            if mode_choice != "All" and mode_choice != zone_type:
                continue
                
            # Define exact parameters of the base zone
            base_candles_df = df.iloc[base_indices]
            zone_proximal = base_candles_df['High'].max() if zone_type == "Demand" else base_candles_df['Low'].min()
            zone_distal = base_candles_df['Low'].min() if zone_type == "Demand" else base_candles_df['High'].max()
            
            # Freshness / Mitigated Analysis Verification Pipeline
            post_zone_df = df.iloc[hero_idx + 1:]
            is_fresh = True
            
            if zone_type == "Demand":
                # If any subsequent low dropped below the proximal boundary before right now
                if not post_zone_df.empty and post_zone_df['Low'].iloc[:-1].min() <= zone_proximal:
                    is_fresh = False
                is_currently_in_zone = latest_close <= zone_proximal and latest_close >= zone_distal
            else:
                # If any subsequent high breached above the proximal boundary before right now
                if not post_zone_df.empty and post_zone_df['High'].iloc[:-1].max() >= zone_proximal:
                    is_fresh = False
                is_currently_in_zone = latest_close >= zone_proximal and latest_close <= zone_distal
                
            # Retain only fresh configurations or active current-touch footprints
            if is_fresh or is_currently_in_zone:
                proximity_pct = abs((latest_close - zone_proximal) / zone_proximal) * 100
                
                # Check institutional volume strength
                avg_volume = df['Volume'].iloc[leg_in_idx:hero_idx+1].mean()
                volume_strength = "🔥 ULTRA LIQUID" if df['Volume'].iloc[hero_idx] > (avg_volume * 1.5) else "STANDARD"
                
                return {
                    "Ticker": ticker.replace('.NS', ''),
                    "Zone Type": "🟢 DEMAND" if zone_type == "Demand" else "🔴 SUPPLY",
                    "Pattern Structure": structural_pattern,
                    "Live Price": round(latest_close, 2),
                    "Proximal Level": round(zone_proximal, 2),
                    "Distal Boundary": round(zone_distal, 2),
                    "Base Count": int(base_count),
                    "Proximity to Zone": f"{round(proximity_pct, 2)}%",
                    "Status": "✨ FRESH TOUCH ZONE" if is_currently_in_zone else "UNMITIGATED RUNWAY",
                    "Institutional Vol": volume_strength
                }
                
        return None
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Market Sector")
    sector_input = st.selectbox("Select NSE Sector Universe:", [
        "NIFTY 50 (Large Cap)", "NIFTY Next 50", "NIFTY Bank", "NIFTY IT", 
        "NIFTY Midcap 100", "NIFTY Smallcap 100", "NIFTY 500 (All Sectors)"
    ])
    
    st.divider()
    st.header("2. Fractal Frame Scale")
    timeframe_input = st.selectbox("Select Core Horizon:", [
        "15 Min", "75 Min", "Daily", "Weekly", "Monthly"
    ], index=2)
    
    st.divider()
    st.header("3. Matrix Boundaries")
    mode_filter = st.selectbox("Target Matrix Track:", ["All", "Demand", "Supply"])
    
    col1, col2 = st.columns(2)
    with col1:
        min_base_input = st.number_input("Min Base Bars", min_value=1, max_value=5, value=1)
    with col2:
        max_base_input = st.number_input("Max Base Bars", min_value=2, max_value=6, value=4)
        
    threads_count = st.slider("Parallel Server Workers", 10, 30, 20, step=5)
    
    st.divider()
    execute_button = st.button("🚀 LAUNCH ORDER BLOCK SCAN", type="primary", use_container_width=True)

# --- EXECUTION CONTROL CONTROLLER ---
if execute_button:
    symbols_list = get_sector_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** inside **{sector_input}** for fresh tracking vectors...")
    
    tf_mapping = {
        "15 Min": {"period": "30d", "interval": "15m"},
        "75 Min": {"period": "30d", "interval": "15m"},
        "Daily": {"period": "1y", "interval": "1d"},
        "Weekly": {"period": "2y", "interval": "1wk"},
        "Monthly": {"period": "5y", "interval": "1mo"}
    }
    
    active_cfg = tf_mapping[timeframe_input]
    confirmed_setups = []
    
    # --- ASYNCHRONOUS MULTITHREADING PIPELINE ---
    progress_ui = st.progress(0, text="Spawning institutional order pathways...")
    
    with ThreadPoolExecutor(max_workers=threads_count) as executor:
        futures_map = {
            executor.submit(
                analyze_supply_demand, ticker, active_cfg, timeframe_input, 
                min_base_input, max_base_input, mode_filter
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
            progress_ui.progress(percent_complete, text=f"Scanning System Tracker: {completed_count}/{len(symbols_list)} Extracted")
            
    progress_ui.empty()
    
    # --- DISPLAY ANALYTICAL MATRIX SHEET ---
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Order Block Discovery Finished: Isolated **{len(results_df)}** verified imbalances.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks in **{sector_input}** match the required base-candle structure or structural constraints on the current setup.")
