import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE SETUP ---
st.set_page_config(page_title="Live Multi-TF 50 EMA Scanner", layout="wide", page_icon="🌊")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #2196F3; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #546E7A; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🌊 Live Multi-Timeframe 50 EMA Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Robust Live-Market Ingestion: Filters for HTF Uptrends & LTF Pullback Touches.</p>', unsafe_allow_html=True)

# --- MARKET SYMBOLS ---
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
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- CUSTOM TIMEFRAME RESAMPLER ---
def resample_data(df, timeframe):
    if df.empty: return df
    try:
        if timeframe == '30m':
            return df.resample('30min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '75m':
            return df.resample('75min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '1W':
            return df.resample('1W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '1M':
            return df.resample('1ME').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    except Exception:
        pass
    return df

def check_ema_touch(df, proximity_pct):
    if len(df) < 50: return "N/A"
    
    # Calculate 50 EMA safely
    ema_series = df['Close'].ewm(span=50, adjust=False).mean()
    ema_50 = ema_series.iloc[-1]
    
    latest_low = df['Low'].iloc[-1]
    latest_high = df['High'].iloc[-1]
    
    # Calculate boundaries based on user tolerance
    upper_band = ema_50 * (1 + (proximity_pct / 100))
    lower_band = ema_50 * (1 - (proximity_pct / 100))
    
    if latest_low <= upper_band and latest_high >= lower_band:
        return "✅ Yes"
    else:
        return "❌ No"

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (5 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY IT", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Macro Trend Filter (HTF)")
    htf_selection = st.selectbox("Stock Must Be ABOVE 50 EMA On:", ["1 Day", "1 Week", "1 Month"])
    
    st.divider()
    st.header("3. Pullback Tolerance")
    proximity = st.slider("EMA Touch Buffer (%)", 0.1, 3.0, 1.0, help="Increase this if you want a wider window to catch stocks approaching the EMA.")
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE LIVE SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:5] if "Test" in selected_sector else load_symbols(selected_sector)

# --- LIVE PROCESSING ENGINE ---
if run_scan:
    scanned_opportunities = []
    
    st.info("🔄 Initiating live stream processing pipeline...")
    execution_progress = st.progress(0, text="Preparing engine...")
    
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        clean_ticker = ticker.replace('.NS', '')
        execution_progress.progress((idx + 1) / total_symbols, text=f"Streaming live metrics for {clean_ticker}...")
        
        try:
            # Download individually to bypass live multi-index formatting issues
            df_15m_base = yf.download(ticker, period='60d', interval='15m', progress=False, show_errors=False)
            df_daily_base = yf.download(ticker, period='5y', interval='1d', progress=False, show_errors=False)
            
            # Clean only empty rows, preserving historical integrity
            df_15m_base = df_15m_base.dropna(subset=['Close', 'High', 'Low'])
            df_daily_base = df_daily_base.dropna(subset=['Close', 'High', 'Low'])
            
            if len(df_15m_base) < 50 or len(df_daily_base) < 50:
                continue
                
            # Generate timeframes
            df_15m = df_15m_base.copy()
            df_30m = resample_data(df_15m_base, '30m')
            df_75m = resample_data(df_15m_base, '75m')
            df_1D = df_daily_base.copy()
            
            if htf_selection == '1 Week':
                df_htf = resample_data(df_daily_base, '1W')
            elif htf_selection == '1 Month':
                df_htf = resample_data(df_daily_base, '1M')
            else:
                df_htf = df_1D
                
            if len(df_htf) < 50:
                continue
                
            # Verify Higher Timeframe Trend
            htf_ema = df_htf['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
            htf_close = df_htf['Close'].iloc[-1]
            
            # Match condition: Must be structurally above HTF 50 EMA
            if htf_close > htf_ema:
                touch_15m = check_ema_touch(df_15m, proximity)
                touch_30m = check_ema_touch(df_30m, proximity)
                touch_75m = check_ema_touch(df_75m, proximity)
                touch_1d = check_ema_touch(df_1D, proximity)
                
                scanned_opportunities.append({
                    "Ticker Symbol": clean_ticker,
                    "HTF Trend status": f"Above {htf_selection} 50 EMA",
                    "Approach 1D 50 EMA": touch_1d,
                    "Approach 75m 50 EMA": touch_75m,
                    "Approach 30m 50 EMA": touch_30m,
                    "Approach 15m 50 EMA": touch_15m,
                    "Current Price": round(df_15m['Close'].iloc[-1], 2)
                })
        except Exception:
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        st.success(f"🎯 Live Scan Complete! Found **{len(display_dataframe)}** stocks holding the macro trend line.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning("All stocks downloaded successfully, but none are currently pulling back close enough to their lower timeframe 50 EMAs. Try increasing the 'EMA Touch Buffer (%)' slider in the sidebar to catch near-misses.")
