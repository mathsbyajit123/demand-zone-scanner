import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- PAGE SETUP ---
st.set_page_config(page_title="Bull/Bear Matrix Engine", layout="wide", page_icon="⚖️")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #E65100; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #455A64; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚖️ Quantitative Bull/Bear Matrix Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Bulletproof Live-Market Edition: Forward-filling gaps and capturing live-candle EMAs.</p>', unsafe_allow_html=True)

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
def resample_data(df, timeframe):
    if df is None or df.empty: return None
    try:
        mapping = {
            '30m': '30min', '1h': '60min', '75m': '75min', 
            '1W': '1W', '1M': '1ME'
        }
        if timeframe in mapping:
            # Crucial Fix: Use ffill() to patch live-market liquidity gaps before dropping
            resampled = df.resample(mapping[timeframe]).agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
            }).ffill().dropna()
            return resampled
    except Exception:
        pass
    return df

# --- DYNAMIC EMA MATH ---
def calculate_ema_distance(df):
    if df is None or len(df) < 5: return None 
    # Crucial Fix: min_periods=1 ensures EMA calculates even for newer stocks without 50 full candles
    ema_50 = df['Close'].ewm(span=50, min_periods=1, adjust=False).mean().iloc[-1]
    latest_close = df['Close'].iloc[-1]
    distance_pct = ((latest_close - ema_50) / ema_50) * 100
    return round(distance_pct, 2)

def format_distance(dist, tolerance):
    if dist is None: return "N/A"
    if abs(dist) <= tolerance:
        return f"🎯 {dist}% (Touch)"
    elif dist > 0:
        return f"🟢 +{dist}%"
    else:
        return f"🔴 {dist}%"

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (5 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Trend Direction")
    trend_mode = st.radio("Select Hunt Objective:", ["Bullish (Uptrend Pullback)", "Bearish (Downtrend Pullback)"])
    
    st.divider()
    st.header("3. Macro Trend Zone (HTF)")
    htf_selection = st.selectbox("Select Master Trend TF:", ["1 Day", "1 Week", "1 Month"])
    htf_min_pct = st.number_input("Minimum % Distance", min_value=0.0, max_value=20.0, value=1.0, step=0.5)
    htf_max_pct = st.number_input("Maximum % Distance", min_value=1.0, max_value=80.0, value=30.0, step=0.5)
    
    st.divider()
    st.header("4. Micro Pullback Zone (LTF)")
    ltf_options = st.multiselect(
        "Select LTF Pullback Targets to Scan:",
        ["15m", "30m", "1h", "75m", "1D", "1W"],
        default=["15m", "30m", "75m", "1D"]
    )
    pullback_tolerance = st.slider("Approach Tolerance (± %)", 0.1, 5.0, 1.0, step=0.1)
    
    st.divider()
    st.header("5. Engine Mode")
    strict_mode = st.checkbox("Strict Mode: ONLY show stocks touching a LTF Pullback", value=False)
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE BULLETPROOF SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:5] if "Test" in selected_sector else load_symbols(selected_sector)

# --- LIVE PROCESSING ENGINE ---
if run_scan:
    if not ltf_options:
        st.error("⚠️ Please select at least one LTF Pullback Target from the sidebar.")
    else:
        scanned_opportunities = []
        st.info(f"🔄 Initiating Bulletproof {trend_mode} Engine...")
        execution_progress = st.progress(0, text="Igniting engine...")
        
        total_symbols = len(target_symbols)
        
        for idx, ticker in enumerate(target_symbols):
            clean_ticker = ticker.replace('.NS', '')
            execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing {clean_ticker}...")
            
            try:
                time.sleep(0.3) # Faster throttle
                
                # Fetch data
                df_15m_base = yf.download(ticker, period='60d', interval='15m', progress=False, show_errors=False)
                df_daily_base = yf.download(ticker, period='10y', interval='1d', progress=False, show_errors=False)
                
                if df_15m_base.empty or df_daily_base.empty:
                    continue
                
                # Crucial Fix: Forward-fill data before dropping to save live-market partial candles
                df_15m_base = df_15m_base.ffill().dropna(subset=['Close'])
                df_daily_base = df_daily_base.ffill().dropna(subset=['Close'])
                
                if len(df_15m_base) < 10 or len(df_daily_base) < 20:
                    continue
                    
                # Dynamically build requested timeframes
                df_map = {}
                if "15m" in ltf_options: df_map["15m"] = df_15m_base
                if "30m" in ltf_options: df_map["30m"] = resample_data(df_15m_base, '30m')
                if "1h" in ltf_options: df_map["1h"] = resample_data(df_15m_base, '1h')
                if "75m" in ltf_options: df_map["75m"] = resample_data(df_15m_base, '75m')
                if "1D" in ltf_options: df_map["1D"] = df_daily_base
                if "1W" in ltf_options: df_map["1W"] = resample_data(df_daily_base, '1W')
                
                # Master Trend TF
                if htf_selection == '1 Week': df_htf = resample_data(df_daily_base, '1W')
                elif htf_selection == '1 Month': df_htf = resample_data(df_daily_base, '1M')
                else: df_htf = df_daily_base
                    
                # 1. Evaluate Macro Trend
                htf_dist = calculate_ema_distance(df_htf)
                if htf_dist is None: continue 
                
                if "Bullish" in trend_mode:
                    if not (htf_min_pct <= htf_dist <= htf_max_pct): continue
                    trend_icon = "🟢"
                else: 
                    if not (-htf_max_pct <= htf_dist <= -htf_min_pct): continue
                    trend_icon = "🔴"
                    
                # 2. Evaluate Micro Pullbacks
                ltf_distances = {}
                for tf in ltf_options:
                    df_target = df_map.get(tf)
                    ltf_distances[tf] = calculate_ema_distance(df_target) if df_target is not None else None
                
                # 3. Apply Strict Mode Logic
                is_pulling_back = any((d is not None and abs(d) <= pullback_tolerance) for d in ltf_distances.values())
                
                if strict_mode and not is_pulling_back:
                    continue 
                    
                # 4. Build Table Row
                row_data = {
                    "Ticker": clean_ticker,
                    f"Macro Trend ({htf_selection})": f"{trend_icon} {htf_dist}%"
                }
                for tf in ltf_options:
                    row_data[f"Dist to {tf} 50-EMA"] = format_distance(ltf_distances[tf], pullback_tolerance)
                    
                row_data["Live Price"] = round(df_15m_base['Close'].iloc[-1], 2)
                scanned_opportunities.append(row_data)
                
            except Exception:
                pass
                
        execution_progress.empty()
        
        if scanned_opportunities:
            display_dataframe = pd.DataFrame(scanned_opportunities)
            if strict_mode:
                st.success(f"🎯 Strict Mode: Found **{len(display_dataframe)}** {trend_mode} setups pulling back perfectly.")
            else:
                st.success(f"📊 X-Ray Mode: Found **{len(display_dataframe)}** stocks in your {trend_mode} Macro Trend.")
            st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
        else:
            st.warning(f"No stocks matched. Tip: Uncheck 'Strict Mode' to see all stocks in the Macro Trend and verify the data is flowing.")
