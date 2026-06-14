import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

# --- PAGE SETUP ---
st.set_page_config(page_title="Pure Extreme Divergence", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #E91E63; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #607D8B; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ Pure Extreme RSI Divergence Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Zero Support/Resistance noise. Scans strictly for targeted, deep RSI divergences (Regular & Hidden).</p>', unsafe_allow_html=True)

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

def calculate_rsi(price_series, period=14):
    delta = price_series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- PURE DIVERGENCE CORE ENGINE ---
def analyze_pure_divergence(df, hunt_mode, rsi_t1, rsi_t2, lookback_order=5):
    if len(df) < 35: 
        return None

    df['RSI'] = calculate_rsi(df['Close'])
    df = df.dropna()
    if df.empty: 
        return None

    # 1. Isolate Structural High/Low Turning Points
    peak_points = argrelextrema(df['High'].values, np.greater_equal, order=lookback_order)[0]
    valley_points = argrelextrema(df['Low'].values, np.less_equal, order=lookback_order)[0]

    # =========================================================================
    # BULLISH DIVERGENCES (Using Valleys)
    # =========================================================================
    if "Bullish" in hunt_mode:
        if len(valley_points) < 2: return None
        v1, v2 = valley_points[-2], valley_points[-1]
        
        # Prevent matching levels that are too close or radically disconnected
        if v2 - v1 < 4 or v2 - v1 > 60: return None
            
        price_v1, price_v2 = df['Low'].iloc[v1], df['Low'].iloc[v2]
        rsi_v1, rsi_v2 = df['RSI'].iloc[v1], df['RSI'].iloc[v2]
        
        # Enforce the strict depth values you requested (e.g., T1 <= 25, T2 <= 35)
        if rsi_v1 <= rsi_t1 and rsi_v2 <= rsi_t2:
            
            if hunt_mode == "Regular Bullish":
                # Price Lower Low, RSI Higher Low
                if price_v2 < price_v1 and rsi_v2 > rsi_v1:
                    return {"signal": "Regular Bullish 🟢", "price": price_v2, "rsi1": rsi_v1, "rsi2": rsi_v2}
                    
            elif hunt_mode == "Hidden Bullish":
                # Price Higher Low, RSI Lower Low
                if price_v2 > price_v1 and rsi_v2 < rsi_v1:
                    return {"signal": "Hidden Bullish 🚀", "price": price_v2, "rsi1": rsi_v1, "rsi2": rsi_v2}

    # =========================================================================
    # BEARISH DIVERGENCES (Using Peaks)
    # =========================================================================
    elif "Bearish" in hunt_mode:
        if len(peak_points) < 2: return None
        p1, p2 = peak_points[-2], peak_points[-1]
        
        if p2 - p1 < 4 or p2 - p1 > 60: return None
            
        price_p1, price_p2 = df['High'].iloc[p1], df['High'].iloc[p2]
        rsi_p1, rsi_p2 = df['RSI'].iloc[p1], df['RSI'].iloc[p2]
        
        # Enforce the strict height values (e.g., T1 >= 75, T2 >= 65)
        if rsi_p1 >= rsi_t1 and rsi_p2 >= rsi_t2:
            
            if hunt_mode == "Regular Bearish":
                # Price Higher High, RSI Lower High
                if price_p2 > price_p1 and rsi_p2 < rsi_p1:
                    return {"signal": "Regular Bearish 🔴", "price": price_p2, "rsi1": rsi_p1, "rsi2": rsi_p2}
                    
            elif hunt_mode == "Hidden Bearish":
                # Price Lower High, RSI Higher High
                if price_p2 < price_p1 and rsi_p2 > rsi_p1:
                    return {"signal": "Hidden Bearish 🩸", "price": price_p2, "rsi1": rsi_p1, "rsi2": rsi_p2}

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
    st.header("3. Divergence Type")
    execution_bias = st.selectbox("Hunt Objective:", [
        "Regular Bullish", "Hidden Bullish", 
        "Regular Bearish", "Hidden Bearish"
    ])
    
    st.divider()
    st.header("4. Strict RSI Thresholds")
    st.markdown("*Set how deep or high the RSI touches must be.*")
    
    if "Bullish" in execution_bias:
        st.info("Values must be LESS THAN OR EQUAL to these targets.")
        touch_1_limit = st.slider("1st Touch (Deep Limit) e.g., 25", 10.0, 45.0, 25.0)
        touch_2_limit = st.slider("2nd Touch (Shallow Limit) e.g., 35", 15.0, 50.0, 35.0)
    else:
        st.info("Values must be GREATER THAN OR EQUAL to these targets.")
        touch_1_limit = st.slider("1st Touch (High Limit) e.g., 75", 55.0, 90.0, 75.0)
        touch_2_limit = st.slider("2nd Touch (Shallow Limit) e.g., 65", 50.0, 85.0, 65.0)
        
    st.divider()
    trigger_processing = st.button("🚀 EXECUTE PURE DVG SCAN", type="primary", use_container_width=True)

target_symbols = load_market_symbols(selected_sector)

# --- COMPUTE PROCESSING SEQUENCE ---
if trigger_processing:
    scanned_opportunities = []
    
    with st.spinner(f"Downloading historical datasets for {selected_sector}..."):
        raw_market_candles = fetch_ticker_records(target_symbols, selected_tf)
        
    execution_progress = st.progress(0, text="Hunting for extreme targeted divergences...")
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing RSI depths for {ticker}...")
        
        try:
            if total_symbols > 1:
                df_ticker_block = raw_market_candles[ticker].copy()
            else:
                df_ticker_block = raw_market_candles.copy()
                
            analysis_outcome = analyze_pure_divergence(
                df_ticker_block, execution_bias, 
                touch_1_limit, touch_2_limit
            )
            
            if analysis_outcome:
                scanned_opportunities.append({
                    "Ticker Symbol": ticker.replace('.NS', ''),
                    "Signal Type": analysis_outcome["signal"],
                    "Trigger Price": round(analysis_outcome["price"], 2),
                    "Touch 1 (Extreme RSI)": round(analysis_outcome["rsi1"], 1),
                    "Touch 2 (Recent RSI)": round(analysis_outcome["rsi2"], 1)
                })
        except Exception:
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(display_dataframe)}** perfect depth divergences.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No assets meet your extreme RSI depth requirements today.")
