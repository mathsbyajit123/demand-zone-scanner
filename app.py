import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Institutional S/D & S/R Matrix Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #0284c7; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 TradingView Style Boring Candle & S/R Core Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Asynchronous Multithreaded Engine. Scans F&O and traditional sectors for Multi-Touch S/R and Order Block Imbalances.</p>', unsafe_allow_html=True)

# --- REAL-TIME MULTI-SECTOR & F&O LOADER ---
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
    
    # Dynamic F&O Engine Extraction Route fallback to known core liquidity derivatives
    if sector_name == "F&O Active Stocks":
        try:
            # Cross-reference full index records to identify top derivative tickers
            df = pd.read_csv(urls["NIFTY 500 (All Sectors)"])
            all_symbols = df['Symbol'].tolist()
            # Backup static map representing core F&O liquidity space for stability
            fno_backups = [
                "RELIANCE", "HDFCBANK", "ICICIBANK", "TCS", "INFY", "SBIN", "BHARTIARTL", 
                "ITC", "LTIM", "MARUTI", "KOTAKBANK", "AXISBANK", "LT", "BAJFINANCE", 
                "HINDUNILVR", "TATASTEEL", "M&M", "SUNPHARMA", "NTPC", "POWERGRID", 
                "TATAMOTORS", "ADANIENT", "ADANIPORTS", "COALINDIA", "JIOFIN", "BPCL",
                "HCLTECH", "ONGC", "TITAN", "ULTRACEMCO", "ASIANPAINT", "GRASIM", "BAJAJFINSV",
                "WIPRO", "HINDALCO", "JSWSTEEL", "NESTLEIND", "TECHM", "EICHERMOT", "DIVISLAB",
                "CIPLA", "APOLLOHOSP", "DRREDDY", "BRITANNIA", "BPCL", "INDUSINDBK", "BAJAJ-AUTO"
            ]
            # Form list of matching active tokens
            return [str(symbol).strip() + ".NS" for symbol in all_symbols if symbol in fno_backups or symbol in fno_backups]
        except Exception:
            return [str(symbol) + ".NS" for symbol in ["RELIANCE", "HDFCBANK", "ICICIBANK", "TCS", "INFY"]]

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

# --- MATHEMATICAL TRADINGVIEW S/D + MULTI-TOUCH S/R ENGINE ---
def analyze_tv_structure(ticker, config, tf_choice, min_base, max_base, mode_choice, tolerance_pct):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=config["period"], interval=config["interval"])
        
        if df.empty or len(df) < 30:
            return None
            
        if tf_choice == "75 Min":
            df = convert_to_75m(df)
            
        if df is None or len(df) < 25:
            return None
            
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        latest_close = df['Close'].iloc[-1]
        
        # Structure Scanning Metrics
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = df['High'] - df['Low']
        df['Range'] = df['Range'].replace(0, 0.00001)
        df['Body_Ratio'] = df['Body'] / df['Range']
        df['Is_Green'] = df['Close'] > df['Open']
        
        BORING_THRESHOLD = 0.50  # TradingView default baseline body calculation
        
        # Walk back through historical pricing vectors
        for i in range(len(df) - 6, 15, -1):
            hero_idx = i
            
            # Identify explosive 'Leg Out / Hero' Marubozu expansion candles
            if df['Body_Ratio'].iloc[hero_idx] <= BORING_THRESHOLD:
                continue
                
            is_hero_up = df['Is_Green'].iloc[hero_idx]
            
            # Process back-to-back boring base clusters
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
                
            leg_in_idx = hero_idx - base_count - 1
            is_leg_in_up = df['Is_Green'].iloc[leg_in_idx]
            
            # Categorize the Imbalance Zone Pattern
            zone_type = None
            structural_pattern = ""
            
            if is_hero_up:
                zone_type = "Demand"
                structural_pattern = "Rally-Base-Rally (RBR)" if is_leg_in_up else "Drop-Base-Rally (DBR)"
            else:
                zone_type = "Supply"
                structural_pattern = "Drop-Base-Drop (DBD)" if not is_leg_in_up else "Rally-Base-Drop (RBD)"
                
            if mode_choice != "All" and mode_choice != zone_type:
                continue
                
            base_candles_df = df.iloc[base_indices]
            zone_proximal = base_candles_df['High'].max() if zone_type == "Demand" else base_candles_df['Low'].min()
            zone_distal = base_candles_df['Low'].min() if zone_type == "Demand" else base_candles_df['High'].max()
            
            # --- EVALUATE MULTI-TOUCH TRADINGVIEW S/R ALIGNMENT ---
            # Evaluate how many historical candles have touched this S/R line
            historical_data = df.iloc[:leg_in_idx]
            touch_count = 0
            
            deviation_limit = zone_proximal * (tolerance_pct / 100)
            
            for k in range(len(historical_data)):
                h_high = historical_data['High'].iloc[k]
                h_low = historical_data['Low'].iloc[k]
                # If the price level falls within the high/low range of a historical candle
                if abs(h_high - zone_proximal) <= deviation_limit or abs(h_low - zone_proximal) <= deviation_limit:
                    touch_count += 1
            
            # Filter out weak or completely unconfirmed retail price zones
            if touch_count < 2: 
                continue
                
            # Check Zone Mitigations / Freshness Status
            post_zone_df = df.iloc[hero_idx + 1:]
            is_fresh = True
            
            if zone_type == "Demand":
                if not post_zone_df.empty and post_zone_df['Low'].iloc[:-1].min() <= zone_proximal:
                    is_fresh = False
                is_currently_in_zone = latest_close <= zone_proximal and latest_close >= zone_distal
            else:
                if not post_zone_df.empty and post_zone_df['High'].iloc[:-1].max() >= zone_proximal:
                    is_fresh = False
                is_currently_in_zone = latest_close >= zone_proximal and latest_close <= zone_distal
                
            if is_fresh or is_currently_in_zone:
                proximity_pct = abs((latest_close - zone_proximal) / zone_proximal) * 100
                
                return {
                    "Ticker": ticker.replace('.NS', ''),
                    "Zone Type": "🟢 DEMAND" if zone_type == "Demand" else "🔴 SUPPLY",
                    "Pattern Structure": structural_pattern,
                    "Live Price": round(latest_close, 2),
                    "S/R Proximal Key": round(zone_proximal, 2),
                    "Distal Boundary": round(zone_distal, 2),
                    "Base Candles": int(base_count),
                    "S/R Strength (Touches)": f"⭐ {touch_count} Verified Touches",
                    "Proximity to Zone": f"{round(proximity_pct, 2)}%",
                    "Freshness Status": "✨ FRESH TOUCH" if is_currently_in_zone else "UNMITIGATED ZONE"
                }
        return None
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Market Universe")
    sector_input = st.selectbox("Select Target Segment:", [
        "F&O Active Stocks", "NIFTY 50 (Large Cap)", "NIFTY Next 50", 
        "NIFTY Bank", "NIFTY IT", "NIFTY Midcap 100", "NIFTY 500 (All Sectors)"
    ])
    
    st.divider()
    st.header("2. Fractal Frame Horizon")
    timeframe_input = st.selectbox("Select Horizon Line:", [
        "15 Min", "75 Min", "Daily", "Weekly", "Monthly"
    ], index=2)
    
    st.divider()
    st.header("3. TradingView Ind. Settings")
    mode_filter = st.selectbox("Target Structural Track:", ["All", "Demand", "Supply"])
    
    col1, col2 = st.columns(2)
    with col1:
        min_base_input = st.number_input("Min Base", min_value=1, max_value=3, value=1)
    with col2:
        max_base_input = st.number_input("Max Base", min_value=2, max_value=6, value=4)
        
    sr_tolerance = st.slider("S/R Touch Sensitivity (%)", 0.1, 2.0, 0.5, step=0.1, help="Max percentage deviation allowed to count a candle level as an S/R touch.")
    threads_count = st.slider("Parallel Workers", 10, 30, 20, step=5)
    
    st.divider()
    execute_button = st.button("🚀 LAUNCH TV MATRIX SCAN", type="primary", use_container_width=True)

# --- EXECUTION CONTROL CONTROLLER ---
if execute_button:
    symbols_list = get_sector_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** inside **{sector_input}** using high-confluence parameters...")
    
    tf_mapping = {
        "15 Min": {"period": "30d", "interval": "15m"},
        "75 Min": {"period": "30d", "interval": "15m"},
        "Daily": {"period": "1y", "interval": "1d"},
        "Weekly": {"period": "2y", "interval": "1wk"},
        "Monthly": {"period": "5y", "interval": "1mo"}
    }
    
    active_cfg = tf_mapping[timeframe_input]
    confirmed_setups = []
    
    progress_ui = st.progress(0, text="Spawning multithreaded pipelines...")
    
    with ThreadPoolExecutor(max_workers=threads_count) as executor:
        futures_map = {
            executor.submit(
                analyze_tv_structure, ticker, active_cfg, timeframe_input, 
                min_base_input, max_base_input, mode_filter, sr_tolerance
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
            progress_ui.progress(percent_complete, text=f"Scanning Matrix: {completed_count}/{len(symbols_list)} Extracted")
            
    progress_ui.empty()
    
    # --- DISPLAY ANALYTICAL MATRIX SHEET ---
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Verified Complete: Isolated **{len(results_df)}** multi-touch structural setups.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks in **{sector_input}** match these structural constraints right now. Try expanding your base boundaries or increasing your S/R sensitivity filter.")
