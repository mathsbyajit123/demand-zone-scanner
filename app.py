import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE SETUP ---
st.set_page_config(page_title="Multi-TF 50 EMA Scanner", layout="wide", page_icon="🌊")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #2196F3; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #546E7A; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🌊 Multi-Timeframe 50 EMA Pullback Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Ensures HTF trend is Above 50 EMA, then hunts for LTF pullback touches (15m, 30m, 75m, 1D).</p>', unsafe_allow_html=True)

# --- MARKET SYMBOLS ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "ind_nifty50list.csv",
        "NIFTY Bank": "ind_niftybanklist.csv",
        "NIFTY IT": "ind_niftyitlist.csv",
        "NIFTY Midcap 100": "ind_niftymidcap100list.csv",
        "NIFTY 500": "ind_nifty500list.csv"
    }
    base_url = "https://archives.nseindia.com/content/indices/"
    try:
        df = pd.read_csv(base_url + urls[category])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- DATA PIPELINE ---
@st.cache_data(show_spinner=False)
def fetch_market_data(tickers):
    # Fetch 60 days of 15m data (maximum allowed by Yahoo Finance) for LTF math
    df_15m_raw = yf.download(tickers, period='60d', interval='15m', group_by='ticker', threads=True, progress=False)
    # Fetch 5 years of daily data for HTF math
    df_daily_raw = yf.download(tickers, period='5y', interval='1d', group_by='ticker', threads=True, progress=False)
    return df_15m_raw, df_daily_raw

# --- CUSTOM TIMEFRAME RESAMPLER ---
def resample_data(df, timeframe):
    if df.empty: return df
    
    if timeframe == '30m':
        return df.resample('30min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    elif timeframe == '75m':
        return df.resample('75min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    elif timeframe == '1W':
        return df.resample('1W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    elif timeframe == '1M':
        return df.resample('1ME').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    return df

def check_ema_touch(df, proximity_pct):
    if len(df) < 50: return "N/A"
    
    # Calculate 50 EMA
    ema_50 = df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    
    latest_low = df['Low'].iloc[-1]
    latest_high = df['High'].iloc[-1]
    latest_close = df['Close'].iloc[-1]
    
    # Logic: Is the current candle touching the EMA, or extremely close to it?
    upper_band = ema_50 * (1 + (proximity_pct / 100))
    lower_band = ema_50 * (1 - (proximity_pct / 100))
    
    if latest_low <= upper_band and latest_high >= lower_band:
        return "✅ Yes"
    else:
        return "❌ No"

# --- CORE LOGIC ENGINE ---
def evaluate_ema_matrix(df_15m_base, df_daily_base, htf_choice, prox_pct):
    # 1. Build the required DataFrames
    df_15m = df_15m_base.copy()
    df_30m = resample_data(df_15m_base, '30m')
    df_75m = resample_data(df_15m_base, '75m')
    df_1D = df_daily_base.copy()
    
    if htf_choice == '1 Week':
        df_htf = resample_data(df_daily_base, '1W')
    elif htf_choice == '1 Month':
        df_htf = resample_data(df_daily_base, '1M')
    else:
        df_htf = df_1D

    if len(df_htf) < 50 or len(df_1D) < 50: return None

    # 2. Check Higher Timeframe (Must be cleanly ABOVE 50 EMA)
    htf_ema = df_htf['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    htf_close = df_htf['Close'].iloc[-1]
    
    if htf_close <= htf_ema:
        return None # Stock is not in a macro uptrend, skip it.

    # 3. Check Lower Timeframe Pullbacks (Touches)
    touch_15m = check_ema_touch(df_15m, prox_pct)
    touch_30m = check_ema_touch(df_30m, prox_pct)
    touch_75m = check_ema_touch(df_75m, prox_pct)
    touch_1d = check_ema_touch(df_1D, prox_pct)

    # Only return the stock if it is touching AT LEAST ONE lower timeframe EMA
    if "✅" in [touch_15m, touch_30m, touch_75m, touch_1d]:
        return {
            "HTF Status": f"Above {htf_choice} 50 EMA",
            "15m Touch": touch_15m,
            "30m Touch": touch_30m,
            "75m Touch": touch_75m,
            "1D Touch": touch_1d,
            "Live Price": round(df_15m['Close'].iloc[-1], 2)
        }
        
    return None

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Macro Trend Filter (HTF)")
    htf_selection = st.selectbox("Stock Must Be ABOVE 50 EMA On:", ["1 Day", "1 Week", "1 Month"])
    
    st.divider()
    st.header("3. Pullback Tolerance")
    proximity = st.slider("EMA Touch Buffer (%)", 0.1, 1.5, 0.5, help="How close the price needs to be to the LTF 50 EMA to trigger a 'Yes'. 0.5% is standard.")
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE MTF SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:10] if "Test" in selected_sector else load_symbols(selected_sector)

# --- PROCESSING SYSTEM ---
if run_scan:
    scanned_opportunities = []
    
    with st.spinner("Downloading Intraday and Daily Data..."):
        raw_15m, raw_1d = fetch_market_data(target_symbols)
        
    execution_progress = st.progress(0, text="Calculating multi-timeframe EMAs...")
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        execution_progress.progress((idx + 1) / total_symbols, text=f"Checking EMA matrix for {ticker}...")
        
        try:
            if total_symbols > 1:
                df_15 = raw_15m[ticker].dropna()
                df_d = raw_1d[ticker].dropna()
            else:
                df_15 = raw_15m.dropna()
                df_d = raw_1d.dropna()
                
            outcome = evaluate_ema_matrix(df_15, df_d, htf_selection, proximity)
            
            if outcome:
                scanned_opportunities.append({
                    "Ticker Symbol": ticker.replace('.NS', ''),
                    "HTF Trend Validation": outcome["HTF Status"],
                    "Approach 1D 50 EMA": outcome["1D Touch"],
                    "Approach 75m 50 EMA": outcome["75m Touch"],
                    "Approach 30m 50 EMA": outcome["30m Touch"],
                    "Approach 15m 50 EMA": outcome["15m Touch"],
                    "Live Price": outcome["Live Price"]
                })
        except Exception:
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(display_dataframe)}** stocks pulling back to dynamic support.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No assets in {selected_sector} are currently in an HTF uptrend while simultaneously pulling back to a LTF 50 EMA.")
