import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- PAGE SETUP ---
st.set_page_config(page_title="Multi-TF Intersect Engine", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #00BCD4; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #455A64; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ Multi-TF Intersect & Touch Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Filters for HTF Macro Trend, then hunts for exact candle intersections on 15m, 30m, and 75m EMAs.</p>', unsafe_allow_html=True)

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

# --- BULLETPROOF RESAMPLER ---
def resample_ltf(df, timeframe):
    if df is None or df.empty: return None
    try:
        mapping = {'30m': '30min', '75m': '75min'}
        if timeframe in mapping:
            resampled = df.resample(mapping[timeframe]).agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
            }).ffill().dropna()
            return resampled
    except Exception:
        pass
    return df

# --- INTERSECT & TOUCH LOGIC ---
def evaluate_ltf_action(df, tolerance_pct):
    if df is None or len(df) < 20: return "N/A"
    
    ema_50 = df['Close'].ewm(span=50, min_periods=1, adjust=False).mean().iloc[-1]
    latest_high = df['High'].iloc[-1]
    latest_low = df['Low'].iloc[-1]
    latest_close = df['Close'].iloc[-1]
    
    # 1. Check for exact intersection (Candle is passing through the EMA)
    if latest_low <= ema_50 <= latest_high:
        return f"⚔️ Intersect (EMA: ₹{round(ema_50, 2)})"
        
    # 2. Check for close proximity touch
    dist_pct = ((latest_close - ema_50) / ema_50) * 100
    if abs(dist_pct) <= tolerance_pct:
        return f"🎯 Touch {round(dist_pct, 2)}% (EMA: ₹{round(ema_50, 2)})"
        
    return "❌ Away"

# --- HTF MACRO LOGIC ---
def evaluate_htf(df, target_tf, min_pct, max_pct):
    if df is None or len(df) < 20: return None
    
    if target_tf == '1 Week':
        df = df.resample('1W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).ffill().dropna()
    elif target_tf == '1 Month':
        df = df.resample('1ME').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).ffill().dropna()

    ema_50 = df['Close'].ewm(span=50, min_periods=1, adjust=False).mean().iloc[-1]
    latest_close = df['Close'].iloc[-1]
    
    dist_pct = ((latest_close - ema_50) / ema_50) * 100
    
    if min_pct <= dist_pct <= max_pct:
        return f"✅ +{round(dist_pct, 2)}%"
    return None

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (5 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Macro Trend Zone (HTF)")
    htf_selection = st.selectbox("Select Master Trend TF:", ["1 Day", "1 Week", "1 Month"])
    htf_min_pct = st.number_input("Minimum % Above 50 EMA", min_value=0.1, max_value=20.0, value=1.0, step=0.5)
    htf_max_pct = st.number_input("Maximum % Above 50 EMA", min_value=1.0, max_value=80.0, value=30.0, step=0.5)
    
    st.divider()
    st.header("3. Micro Pullback Zone (LTF)")
    pullback_tolerance = st.slider("Approach Tolerance (± %)", 0.1, 5.0, 0.5, step=0.1, help="If the candle isn't intersecting, how close does it need to be to trigger a 'Touch'?")
    
    st.divider()
    st.header("4. Engine Mode")
    strict_mode = st.checkbox("Strict Mode: ONLY show stocks Intersecting or Touching a LTF", value=False)
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE INTERSECT SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:5] if "Test" in selected_sector else load_symbols(selected_sector)

# --- LIVE PROCESSING ENGINE ---
if run_scan:
    scanned_opportunities = []
    st.info("🔄 Streaming Intraday and Daily Data...")
    execution_progress = st.progress(0, text="Igniting engine...")
    
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        clean_ticker = ticker.replace('.NS', '')
        execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing {clean_ticker}...")
        
        try:
            time.sleep(0.3) # Throttle to prevent API ban
            
            stock = yf.Ticker(ticker)
            
            # Fetch both Daily and Intraday safely
            df_daily = stock.history(period='5y', interval='1d')
            df_15m = stock.history(period='60d', interval='15m')
            
            if df_daily.empty or df_15m.empty:
                continue
                
            if df_daily.index.tz is not None: df_daily.index = df_daily.index.tz_localize(None)
            if df_15m.index.tz is not None: df_15m.index = df_15m.index.tz_localize(None)
            
            df_daily = df_daily.ffill().dropna(subset=['Close', 'High', 'Low'])
            df_15m = df_15m.ffill().dropna(subset=['Close', 'High', 'Low'])
            
            # 1. Check Macro Trend First (Save processing power)
            htf_status = evaluate_htf(df_daily, htf_selection, htf_min_pct, htf_max_pct)
            
            if htf_status is None:
                continue # Fails HTF macro trend, skip stock entirely
                
            # 2. Build LTF Dataframes
            df_30m = resample_ltf(df_15m, '30m')
            df_75m = resample_ltf(df_15m, '75m')
            
            # 3. Evaluate Intersections
            status_15m = evaluate_ltf_action(df_15m, pullback_tolerance)
            status_30m = evaluate_ltf_action(df_30m, pullback_tolerance)
            status_75m = evaluate_ltf_action(df_75m, pullback_tolerance)
            
            # 4. Strict Mode Logic
            has_action = any("⚔️" in s or "🎯" in s for s in [status_15m, status_30m, status_75m])
            
            if strict_mode and not has_action:
                continue
                
            scanned_opportunities.append({
                "Ticker": clean_ticker,
                "Live Price": f"₹{round(df_15m['Close'].iloc[-1], 2)}",
                f"Macro Trend ({htf_selection})": htf_status,
                "75m Action": status_75m,
                "30m Action": status_30m,
                "15m Action": status_15m
            })
            
        except Exception:
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        if strict_mode:
            st.success(f"🎯 Strict Mode: Found **{len(display_dataframe)}** stocks intersecting or touching an intraday 50 EMA.")
        else:
            st.success(f"📊 X-Ray Mode: Found **{len(display_dataframe)}** stocks in the Macro Trend.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks matched. Ensure the market is open or expand your Macro Trend limits.")
