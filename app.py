import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

# --- PAGE SETUP ---
st.set_page_config(page_title="Institutional Cost-Floor Engine", layout="wide", page_icon="🛡️")

st.markdown("""
    <style>
    .main-title { font-size: 36px; font-weight: 800; color: #1E3A8A; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🛡️ Institutional Accumulation & Cost-Floor Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Unbiased End-of-Day Swing Scanner. Tracks FII/DII footprints via Event-Based Anchored VWAP.</p>', unsafe_allow_html=True)

# --- BULLETPROOF INDEX SYMBOL LOADER ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[category])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "LT.NS"]

# --- DYNAMIC ANCHORED VWAP MATH ENGINE ---
def process_institutional_floor(df, lookback_days, volume_multiplier):
    if df is None or len(df) < 40:
        return None
    
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    
    total_bars = len(df)
    start_idx = max(20, total_bars - lookback_days)
    lookback_df = df.iloc[start_idx:]
    
    spike_condition = lookback_df['Volume'] > (volume_multiplier * lookback_df['Vol_SMA20'])
    event_days = lookback_df[spike_condition]
    
    if event_days.empty:
        return None 
    
    anchor_date = event_days['Volume'].idxmax()
    df_anchored = df.loc[anchor_date:].copy()
    
    if len(df_anchored) < 1:
        return None
        
    df_anchored['Typical_Price'] = (df_anchored['High'] + df_anchored['Low'] + df_anchored['Close']) / 3
    
    df_anchored['PV'] = df_anchored['Typical_Price'] * df_anchored['Volume']
    df_anchored['Cum_PV'] = df_anchored['PV'].cumsum()
    df_anchored['Cum_Vol'] = df_anchored['Volume'].cumsum()
    df_anchored['AVWAP'] = df_anchored['Cum_PV'] / df_anchored['Cum_Vol']
    
    latest_close = df['Close'].iloc[-1]
    latest_avwap = df_anchored['AVWAP'].iloc[-1]
    proximity_pct = ((latest_close - latest_avwap) / latest_avwap) * 100
    
    event_vol_multiplier = event_days.loc[anchor_date, 'Volume'] / event_days.loc[anchor_date, 'Vol_SMA20']
    
    return {
        "anchor_date": anchor_date.strftime('%Y-%m-%d'),
        "latest_close": round(latest_close, 2),
        "avwap_value": round(latest_avwap, 2),
        "proximity": round(proximity_pct, 2),
        "vol_mult": round(event_vol_multiplier, 1)
    }

# --- SIDEBAR INTERFACE CONTROL ---
with st.sidebar:
    st.header("1. Liquidity Pool")
    selected_sector = st.selectbox("Market Index Universe", ["Test Large-Caps", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Footprint Detection")
    lookback_window = st.slider("Event Lookback Window (Days)", 10, 60, 30, step=5)
    vol_threshold = st.slider("Institutional Vol Multiplier", 2.0, 5.0, 3.0, step=0.5)
    
    st.divider()
    st.header("3. Accumulation Zone")
    max_proximity = st.slider("Max Proximity Tolerance (%)", 0.5, 3.0, 2.0, step=0.1)
    
    st.divider()
    run_scan = st.button("🚀 RUN INSTITUTIONAL SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50") if "Test" in selected_sector else load_symbols(selected_sector)

# --- CODE EXECUTION CORE ENGINE ---
if run_scan:
    scanned_opportunities = []
    st.info("📊 Fetching delivery-grade historical data sheets...")
    execution_progress = st.progress(0, text="Initializing database access...")
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        clean_ticker = ticker.replace('.NS', '')
        execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing {clean_ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            df_daily = stock.history(period='1y', interval='1d')
            
            if df_daily.empty or len(df_daily) < 40:
                continue
                
            if df_daily.index.tz is not None: 
                df_daily.index = df_daily.index.tz_localize(None)
                
            df_daily = df_daily.ffill().dropna(subset=['Close'])
            metrics = process_institutional_floor(df_daily, lookback_window, vol_threshold)
            
            if metrics is None:
                continue
            
            # Pure Unbiased Entry Filtering
            if -0.5 <= metrics["proximity"] <= max_proximity:
                scanned_opportunities.append({
                    "Stock Symbol": clean_ticker,
                    "Live Price (₹)": metrics["latest_close"],
                    "Institutional Cost Basis (₹)": metrics["avwap_value"],
                    "Proximity to Floor (%)": f"🎯 {metrics['proximity']}%" if metrics['proximity'] >= 0 else f"⚠️ {metrics['proximity']}%",
                    "Anchor Event Date": metrics["anchor_date"],
                    "Volume Spike Size": f"{metrics['vol_mult']}x Avg"
                })
                
        except Exception:
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_df = pd.DataFrame(scanned_opportunities)
        st.success(f"🛡️ Found **{len(display_df)}** institutional accumulation setups matching your rules.")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks are currently defending historical cost lines inside your tolerance settings.")
