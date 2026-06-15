import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- PAGE SETUP ---
st.set_page_config(page_title="Quantitative EMA Matrix", layout="wide", page_icon="🧮")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #00C853; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #455A64; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🧮 Quantitative Distance Matrix Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Upgraded Data Pipeline: 10-Year Depth for Monthly EMAs & Non-Strict Mode for Trend X-Ray.</p>', unsafe_allow_html=True)

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
        elif timeframe == '1h':
            return df.resample('60min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '75m':
            return df.resample('75min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '1W':
            return df.resample('1W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
        elif timeframe == '1M':
            return df.resample('1ME').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    except Exception:
        pass
    return df

def calculate_ema_distance(df):
    # Lowered minimum length to 20 to allow newer stocks to bypass the 50-candle requirement gracefully
    if len(df) < 20: return None 
    ema_50 = df['Close'].ewm(span=50, min_periods=20, adjust=False).mean().iloc[-1]
    latest_close = df['Close'].iloc[-1]
    distance_pct = ((latest_close - ema_50) / ema_50) * 100
    return round(distance_pct, 2)

def format_distance(dist, tolerance):
    if dist is None: return "N/A"
    if abs(dist) <= tolerance:
        return f"🎯 {dist}% (Touch)"
    elif dist > 0:
        return f"🔼 +{dist}%"
    else:
        return f"🔽 {dist}%"

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (5 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Macro Trend Zone (HTF)")
    htf_selection = st.selectbox("Select Master Trend TF:", ["1 Day", "1 Week", "1 Month"])
    
    htf_min_pct = st.number_input("Minimum % Above", min_value=0.1, max_value=20.0, value=2.0, step=0.5)
    htf_max_pct = st.number_input("Maximum % Above", min_value=1.0, max_value=80.0, value=30.0, step=0.5)
    
    st.divider()
    st.header("3. Micro Pullback Zone (LTF)")
    pullback_tolerance = st.slider("Approach Tolerance (± %)", 0.1, 5.0, 1.0, step=0.1)
    
    st.divider()
    st.header("4. Engine Mode")
    strict_mode = st.checkbox("Strict Mode: ONLY show stocks touching a LTF Pullback", value=False, help="Uncheck this to see all stocks in the Macro Trend, even if they aren't pulling back yet.")
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE DISTANCE SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:5] if "Test" in selected_sector else load_symbols(selected_sector)

# --- LIVE PROCESSING ENGINE ---
if run_scan:
    scanned_opportunities = []
    
    st.info("🔄 Initiating Deep-History Pipeline...")
    execution_progress = st.progress(0, text="Igniting engine...")
    
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        clean_ticker = ticker.replace('.NS', '')
        execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing {clean_ticker}...")
        
        try:
            # INCREASED PERIOD TO 10 YEARS for Monthly EMA calculations
            df_15m_base = yf.download(ticker, period='60d', interval='15m', progress=False, show_errors=False)
            df_daily_base = yf.download(ticker, period='10y', interval='1d', progress=False, show_errors=False)
            
            df_15m_base = df_15m_base.dropna(subset=['Close'])
            df_daily_base = df_daily_base.dropna(subset=['Close'])
            
            if len(df_15m_base) < 20 or len(df_daily_base) < 50:
                continue
                
            # Build timeframe structures
            df_15m = df_15m_base.copy()
            df_30m = resample_data(df_15m_base, '30m')
            df_1h = resample_data(df_15m_base, '1h')
            df_75m = resample_data(df_15m_base, '75m')
            df_1D = df_daily_base.copy()
            
            if htf_selection == '1 Week': df_htf = resample_data(df_daily_base, '1W')
            elif htf_selection == '1 Month': df_htf = resample_data(df_daily_base, '1M')
            else: df_htf = df_1D
                
            # 1. Evaluate Macro Trend Filter
            htf_dist = calculate_ema_distance(df_htf)
            if htf_dist is None or not (htf_min_pct <= htf_dist <= htf_max_pct):
                continue 
                
            # 2. Evaluate Micro Pullbacks
            dist_1d = calculate_ema_distance(df_1D)
            dist_75m = calculate_ema_distance(df_75m)
            dist_1h = calculate_ema_distance(df_1h)
            dist_30m = calculate_ema_distance(df_30m)
            dist_15m = calculate_ema_distance(df_15m)
            
            # 3. Apply Strict Mode Logic
            distances = [dist_1d, dist_75m, dist_1h, dist_30m, dist_15m]
            is_pulling_back = any((d is not None and abs(d) <= pullback_tolerance) for d in distances)
            
            if strict_mode and not is_pulling_back:
                continue # Skip if strict mode is ON and no pullbacks exist
                
            scanned_opportunities.append({
                "Ticker": clean_ticker,
                f"Macro Trend ({htf_selection})": f"✅ +{htf_dist}%",
                "1D 50-EMA": format_distance(dist_1d, pullback_tolerance),
                "75m 50-EMA": format_distance(dist_75m, pullback_tolerance),
                "1H 50-EMA": format_distance(dist_1h, pullback_tolerance),
                "30m 50-EMA": format_distance(dist_30m, pullback_tolerance),
                "15m 50-EMA": format_distance(dist_15m, pullback_tolerance),
                "Live Price": round(df_15m['Close'].iloc[-1], 2)
            })
            
            # Sleep tiny bit to avoid API rate bans on 500 stocks
            if total_symbols > 100: time.sleep(0.1)
            
        except Exception:
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        if strict_mode:
            st.success(f"🎯 Strict Mode: Found **{len(display_dataframe)}** setups pulling back exactly into your execution zones.")
        else:
            st.success(f"📊 X-Ray Mode: Found **{len(display_dataframe)}** stocks in your Macro Trend. Showing all LTF distances.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks matched your criteria. Either the API rate-limited the connection, or no stocks are currently in that exact percentage band.")
