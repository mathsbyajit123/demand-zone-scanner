import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

# --- PAGE SETUP ---
st.set_page_config(page_title="Extreme Divergence Engine", layout="wide", page_icon="📡")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #D32F2F; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #455A64; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📡 Extreme Overbought/Oversold Divergence Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Exclusively flags structural RSI Divergences forming strictly within institutional boundaries at S/R zones.</p>', unsafe_allow_html=True)

# --- SECURITIES MAPPING ARCHIVE ---
@st.cache_data(ttl=86400)
def load_market_symbols(category):
    urls = {
        "NIFTY 50": "ind_nifty50list.csv",
        "NIFTY Bank": "ind_niftybanklist.csv",
        "NIFTY IT": "ind_niftyitlist.csv",
        "NIFTY Auto": "ind_niftyautolist.csv",
        "NIFTY Metal": "ind_niftymetallist.csv",
        "NIFTY Pharma": "ind_niftypharmalist.csv",
        "NIFTY FMCG": "ind_niftyfmcglist.csv",
        "NIFTY Realty": "ind_niftyrealtylist.csv",
        "NIFTY Energy": "ind_niftyenergylist.csv",
        "NIFTY 500": "ind_nifty500list.csv"
    }
    base_url = "https://archives.nseindia.com/content/indices/"
    try:
        df = pd.read_csv(base_url + urls[category])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        fallbacks = {
            "NIFTY Bank": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"],
            "NIFTY IT": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS"],
            "NIFTY Auto": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS"]
        }
        return fallbacks.get(category, ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "SBIN.NS"])

# --- MARKET DATA RETRIEVAL PIPELINE ---
@st.cache_data(show_spinner=False)
def fetch_ticker_records(tickers, timeframe):
    if timeframe == '15m': period, interval = '60d', '15m'
    elif timeframe == '1h': period, interval = '730d', '1h'
    elif timeframe in ['1d', '1wk']: period, interval = '5y', timeframe
    else: period, interval = '10y', '1mo'
    return yf.download(tickers, period=period, interval=interval, group_by='ticker', threads=True, progress=False)

def calculate_rsi_stream(price_series, period=14):
    price_delta = price_series.diff()
    positive_gain = (price_delta.where(price_delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    negative_loss = (-price_delta.where(price_delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    relative_strength = positive_gain / negative_loss
    return 100 - (100 / (1 + relative_strength))

# --- STRUCTURAL EXHAUSTION CORE ENGINE ---
def analyze_extreme_divergence(df, hunt_mode, max_zone_w, ob_level, os_level, lookback_order=5):
    if len(df) < 35: 
        return None

    df['RSI'] = calculate_rsi_stream(df['Close'])
    df = df.dropna()
    if df.empty: 
        return None

    latest_close = df.iloc[-1]['Close']
    latest_high = df.iloc[-1]['High']
    latest_low = df.iloc[-1]['Low']

    # 1. Isolate Structural High/Low Turning Points
    peak_points = argrelextrema(df['High'].values, np.greater_equal, order=lookback_order)[0]
    valley_points = argrelextrema(df['Low'].values, np.less_equal, order=lookback_order)[0]

    # 2. Extract Valid Horizontal S/R Clustered Zones
    all_swings = np.sort(np.concatenate((df['High'].iloc[peak_points].values, df['Low'].iloc[valley_points].values)))
    horizontal_zones = []
    
    if len(all_swings) > 0:
        active_cluster = [all_swings[0]]
        for i in range(1, len(all_swings)):
            if (all_swings[i] - active_cluster[0]) / active_cluster[0] <= (max_zone_w / 100.0):
                active_cluster.append(all_swings[i])
            else:
                if len(active_cluster) >= 2:
                    horizontal_zones.append({'floor': min(active_cluster), 'ceiling': max(active_cluster)})
                active_cluster = [all_swings[i]]
        if len(active_cluster) >= 2:
            horizontal_zones.append({'floor': min(active_cluster), 'ceiling': max(active_cluster)})

    # =========================================================================
    # CONFIGURATION A: BULLISH DIVERGENCE AT SUPPORT FLOOR
    # =========================================================================
    if hunt_mode == "Extreme Bullish Divergence (At Support Floor)":
        if len(valley_points) < 2: 
            return None
        v1, v2 = valley_points[-2], valley_points[-1]
        
        # Guard rail: Prevent matching levels that are too close or radically disconnected
        if v2 - v1 < 4 or v2 - v1 > 60: 
            return None
            
        price_v1, price_v2 = df['Low'].iloc[v1], df['Low'].iloc[v2]
        rsi_v1, rsi_v2 = df['RSI'].iloc[v1], df['RSI'].iloc[v2]
        
        # Verify Regular Bullish Divergence Signatures
        if price_v2 < price_v1 and rsi_v2 > rsi_v1:
            # CRITICAL FILTER: Both structural RSI points must reside in extreme institutional Oversold conditions
            if rsi_v1 <= os_level or rsi_v2 <= os_level:
                # Structure Validation: Confirm price action occurs directly at a verified support boundary
                for zone in horizontal_zones:
                    if zone['floor'] * 0.985 <= latest_low <= zone['ceiling'] * 1.015:
                        return {
                            "signal": "Platinum Bullish Divergence 🟢",
                            "context": f"Oversold Sweep at Support (₹{round(zone['floor'],1)} - ₹{round(zone['ceiling'],1)})",
                            "rsi_val": rsi_v2
                        }

    # =========================================================================
    # CONFIGURATION B: BEARISH DIVERGENCE AT RESISTANCE CEILING
    # =========================================================================
    elif hunt_mode == "Extreme Bearish Divergence (At Resistance Ceiling)":
        if len(peak_points) < 2: 
            return None
        p1, p2 = peak_points[-2], peak_points[-1]
        
        if p2 - p1 < 4 or p2 - p1 > 60: 
            return None
            
        price_p1, price_p2 = df['High'].iloc[p1], df['High'].iloc[p2]
        rsi_p1, rsi_p2 = df['RSI'].iloc[p1], df['RSI'].iloc[p2]
        
        # Verify Regular Bearish Divergence Signatures
        if price_p2 > price_p1 and rsi_p2 < rsi_p1:
            # CRITICAL FILTER: Both structural RSI points must reside in extreme institutional Overbought conditions
            if rsi_p1 >= ob_level or rsi_p2 >= ob_level:
                # Structure Validation: Confirm price action occurs directly at a verified resistance boundary
                for zone in horizontal_zones:
                    if zone['floor'] * 0.985 <= latest_high <= zone['ceiling'] * 1.015:
                        return {
                            "signal": "Platinum Bearish Divergence 🔴",
                            "context": f"Overbought Sweep at Resistance (₹{round(zone['floor'],1)} - ₹{round(zone['ceiling'],1)})",
                            "rsi_val": rsi_p2
                        }

    return None

# --- GRAPHICAL CONTROL DASHBOARD ---
with st.sidebar:
    st.header("1. Target Market Map")
    selected_sector = st.selectbox("Market Sector Index", [
        "NIFTY 50", "NIFTY Bank", "NIFTY IT", "NIFTY Auto", 
        "NIFTY Metal", "NIFTY Pharma", "NIFTY FMCG", "NIFTY Realty", 
        "NIFTY Energy", "NIFTY 500"
    ])
    
    st.divider()
    st.header("2. Execution Scale")
    selected_tf = st.selectbox("Timeframe Window", ["15m", "1h", "1d", "1wk", "1mo"])
    
    st.divider()
    st.header("3. Hunting Objective")
    execution_bias = st.radio("Select Strategy Alignment:", [
        "Extreme Bullish Divergence (At Support Floor)",
        "Extreme Bearish Divergence (At Resistance Ceiling)"
    ])
    
    st.divider()
    st.header("4. Threshold Strictness")
    max_w_pct = st.slider("Max Zone Tolerance Width (%)", 1.0, 8.0, 3.5)
    
    if "Bullish" in execution_bias:
        oversold_barrier = st.slider("Extreme Oversold Floor Barrier (≤)", 20, 40, 30)
        overbought_barrier = 70
    else:
        overbought_barrier = st.slider("Extreme Overbought Ceiling Barrier (≥)", 60, 80, 70)
        oversold_barrier = 30
        
    st.divider()
    trigger_processing = st.button("🚀 EXECUTE PLATINUM SCAN", type="primary", use_container_width=True)

# Select processing queue layout parameters
target_symbols = load_market_symbols(selected_sector)

# --- COMPUTE PROCESSING SEQUENCE ---
if trigger_processing:
    scanned_opportunities = []
    
    with st.spinner(f"Downloading historical datasets for {selected_sector} matrix networks..."):
        raw_market_candles = fetch_ticker_records(target_symbols, selected_tf)
        
    execution_progress = st.progress(0, text="Evaluating momentum matrix structures...")
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing structural exhaustion channels for {ticker}...")
        
        try:
            if total_symbols > 1:
                df_ticker_block = raw_market_candles[ticker].copy()
            else:
                df_ticker_block = raw_market_candles.copy()
                
            analysis_outcome = analyze_extreme_divergence(
                df_ticker_block, execution_bias, max_w_pct, 
                overbought_barrier, oversold_barrier
            )
            
            if analysis_outcome:
                scanned_opportunities.append({
                    "Ticker Symbol": ticker.replace('.NS', ''),
                    "Signal Profile": analysis_outcome["signal"],
                    "Structural Environment": analysis_outcome["context"],
                    "Live Exhaustion Price": round(df_ticker_block.iloc[-1]['Close'], 2),
                    "RSI Index": round(analysis_outcome["rsi_val"], 1)
                })
        except Exception:
            pass
            
    execution_progress.empty()
    
    # Render operational metrics and dashboard grids
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(display_dataframe)}** elite institutional setups.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No assets meet all conditions today. The scanner is maintaining perfect strictness.")
