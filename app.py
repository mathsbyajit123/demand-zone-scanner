import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

# --- PAGE SETUP ---
st.set_page_config(page_title="Pro Divergence & Sector Scanner", layout="wide", page_icon="📡")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #651FFF; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #607D8B; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📡 Master Divergence & Sector Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Multi-Timeframe scans for Regular & Hidden RSI Divergences across NIFTY Sectors.</p>', unsafe_allow_html=True)

# --- SECTOR & SYMBOL MAPPING ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    # Mapping NSE Sectoral indices URLs
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
        # Robust Fallback if NSE servers block the request
        fallbacks = {
            "NIFTY Bank": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"],
            "NIFTY IT": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS"],
            "NIFTY Auto": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS"]
        }
        return fallbacks.get(category, ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "SBIN.NS"])

# --- DATA FETCHING & MATH ---
@st.cache_data(show_spinner=False)
def fetch_data(tickers, timeframe):
    if timeframe == '15m': period, interval = '60d', '15m'
    elif timeframe == '1h': period, interval = '730d', '1h'
    elif timeframe in ['1d', '1wk']: period, interval = '5y', timeframe
    else: period, interval = '10y', '1mo'
        
    return yf.download(tickers, period=period, interval=interval, group_by='ticker', threads=True, progress=False)

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- THE DIVERGENCE ENGINE ---
def detect_divergence(df, div_type, lookback=5):
    if len(df) < 30: return None

    df['RSI'] = calc_rsi(df['Close'])
    df = df.dropna()
    if df.empty: return None

    # Find structural pivots
    peak_idx = argrelextrema(df['High'].values, np.greater_equal, order=lookback)[0]
    valley_idx = argrelextrema(df['Low'].values, np.less_equal, order=lookback)[0]

    # Evaluate Bullish Divergences (Uses Valleys)
    if "Bullish" in div_type:
        if len(valley_idx) < 2: return None
        v1, v2 = valley_idx[-2], valley_idx[-1]
        
        # Ensure the pivots aren't too far apart or too close
        if v2 - v1 < 3 or v2 - v1 > 50: return None
        
        p1, p2 = df['Low'].iloc[v1], df['Low'].iloc[v2]
        rsi1, rsi2 = df['RSI'].iloc[v1], df['RSI'].iloc[v2]
        
        if div_type == "Regular Bullish (Reversal)":
            # Price Lower Low, RSI Higher Low
            if p2 < p1 and rsi2 > rsi1:
                return {"type": "Regular Bullish 🟢", "price": p2, "rsi": rsi2}
                
        elif div_type == "Hidden Bullish (Continuation)":
            # Price Higher Low, RSI Lower Low
            if p2 > p1 and rsi2 < rsi1:
                return {"type": "Hidden Bullish 🚀", "price": p2, "rsi": rsi2}

    # Evaluate Bearish Divergences (Uses Peaks)
    elif "Bearish" in div_type:
        if len(peak_idx) < 2: return None
        p1_idx, p2_idx = peak_idx[-2], peak_idx[-1]
        
        if p2_idx - p1_idx < 3 or p2_idx - p1_idx > 50: return None
        
        price1, price2 = df['High'].iloc[p1_idx], df['High'].iloc[p2_idx]
        rsi1, rsi2 = df['RSI'].iloc[p1_idx], df['RSI'].iloc[p2_idx]
        
        if div_type == "Regular Bearish (Reversal)":
            # Price Higher High, RSI Lower High
            if price2 > price1 and rsi2 < rsi1:
                return {"type": "Regular Bearish 🔴", "price": price2, "rsi": rsi2}
                
        elif div_type == "Hidden Bearish (Continuation)":
            # Price Lower High, RSI Higher High
            if price2 < price1 and rsi2 > rsi1:
                return {"type": "Hidden Bearish 🩸", "price": price2, "rsi": rsi2}

    return None

# --- UI CONTROL PANEL ---
with st.sidebar:
    st.header("1. Market / Sector")
    sector_choice = st.selectbox("Select Universe", [
        "NIFTY 50", "NIFTY Bank", "NIFTY IT", "NIFTY Auto", 
        "NIFTY Metal", "NIFTY Pharma", "NIFTY FMCG", "NIFTY Realty", 
        "NIFTY Energy", "NIFTY 500"
    ])
    
    st.divider()
    st.header("2. Timeframe")
    timeframe = st.selectbox("Execution Scale", ["15m", "1h", "1d", "1wk", "1mo"])
    
    st.divider()
    st.header("3. Divergence Type")
    divergence_target = st.selectbox("Hunt For:", [
        "Regular Bullish (Reversal)",
        "Hidden Bullish (Continuation)",
        "Regular Bearish (Reversal)",
        "Hidden Bearish (Continuation)"
    ])
    
    st.divider()
    st.info("**What this means:**\n- **Regular:** Trend is exhausted. Look for Reversal.\n- **Hidden:** Trend is taking a breather. Look for Continuation.")
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE SECTOR SCAN", type="primary", use_container_width=True)

symbols_to_scan = load_symbols(sector_choice)

# --- EXECUTION SYSTEM ---
if run_scan:
    results = []
    
    with st.spinner(f"Downloading {timeframe} data for {sector_choice}..."):
        raw_data = fetch_data(symbols_to_scan, timeframe)
        
    bar = st.progress(0, text=f"Hunting for {divergence_target}...")
    total = len(symbols_to_scan)
    
    for idx, ticker in enumerate(symbols_to_scan):
        bar.progress((idx + 1) / total, text=f"Analyzing {ticker}...")
        
        try:
            if total > 1: df = raw_data[ticker].copy()
            else: df = raw_data.copy()
                
            status = detect_divergence(df, divergence_target)
            
            if status:
                results.append({
                    "Ticker": ticker.replace('.NS', ''),
                    "Sector": sector_choice,
                    "Signal Detected": status["type"],
                    "Trigger Price": round(status["price"], 2),
                    "RSI Value": round(status["rsi"], 1)
                })
        except Exception:
            pass
            
    bar.empty()
    
    if results:
        df_display = pd.DataFrame(results)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(df_display)}** setups in the {sector_choice} sector.")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No valid {divergence_target} setups found in {sector_choice} on the {timeframe} chart right now.")
