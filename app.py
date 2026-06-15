import streamlit as st
import yfinance as yf
import pandas as pd
import time

# --- PAGE SETUP ---
st.set_page_config(page_title="Pure LTF Proximity Scanner", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #E91E63; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #455A64; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ Pure LTF Proximity Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Lightning-fast intraday scanner. Hunts for exact ±% touches on 15m, 30m, 1H, and 75m EMAs.</p>', unsafe_allow_html=True)

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
        mapping = {'30m': '30min', '1h': '60min', '75m': '75min'}
        if timeframe in mapping:
            resampled = df.resample(mapping[timeframe]).agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'
            }).ffill().dropna()
            return resampled
    except Exception:
        pass
    return df

# --- PROXIMITY MATH ---
def calculate_ema_data(df):
    if df is None or len(df) < 50: return None, None
    ema_50 = df['Close'].ewm(span=50, min_periods=1, adjust=False).mean().iloc[-1]
    latest_close = df['Close'].iloc[-1]
    
    distance_pct = ((latest_close - ema_50) / ema_50) * 100
    return round(distance_pct, 2), round(ema_50, 2)

def format_cell(dist, ema_val, tolerance):
    if dist is None: return "N/A"
    
    base_text = f"{dist}% (EMA: ₹{ema_val})"
    
    if abs(dist) <= tolerance:
        return f"🎯 {base_text}"
    elif dist > 0:
        return f"🟢 +{base_text}"
    else:
        return f"🔴 {base_text}"

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (5 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Setup Direction")
    trend_mode = st.radio("Select Trading Bias:", ["Bullish (Looking for Support)", "Bearish (Looking for Resistance)"])
    
    st.divider()
    st.header("3. Proximity Matrix")
    ltf_options = st.multiselect(
        "Select Timeframes to Scan:",
        ["15m", "30m", "1h", "75m"],
        default=["15m", "30m", "1h", "75m"]
    )
    
    pullback_tolerance = st.slider("± Approach Tolerance (%)", 0.1, 2.0, 0.5, step=0.1, help="Finds stocks sitting exactly within this + or - percentage of the 50 EMA.")
    
    st.divider()
    st.header("4. Engine Mode")
    strict_mode = st.checkbox("Strict Mode: ONLY show stocks within the ± tolerance on a selected timeframe", value=True)
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE INTRADAY SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:5] if "Test" in selected_sector else load_symbols(selected_sector)

# --- LIVE PROCESSING ENGINE ---
if run_scan:
    if not ltf_options:
        st.error("⚠️ Please select at least one Timeframe from the sidebar.")
    else:
        scanned_opportunities = []
        st.info("⚡ Streaming Pure Intraday Data...")
        execution_progress = st.progress(0, text="Igniting engine...")
        
        total_symbols = len(target_symbols)
        
        for idx, ticker in enumerate(target_symbols):
            clean_ticker = ticker.replace('.NS', '')
            execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing {clean_ticker}...")
            
            try:
                time.sleep(0.1) # Ultra-fast throttle since we only make 1 request per stock
                
                # Fetch 60 days of 15m data (maximum allowed for intraday)
                stock = yf.Ticker(ticker)
                df_15m_base = stock.history(period='60d', interval='15m')
                
                if df_15m_base.empty:
                    continue
                
                # Clean timezone data and forward-fill gaps
                if df_15m_base.index.tz is not None: 
                    df_15m_base.index = df_15m_base.index.tz_localize(None)
                    
                df_15m_base = df_15m_base.ffill().dropna(subset=['Close'])
                
                if len(df_15m_base) < 50:
                    continue
                    
                # Build Timeframes dynamically
                df_map = {}
                if "15m" in ltf_options: df_map["15m"] = df_15m_base
                if "30m" in ltf_options: df_map["30m"] = resample_ltf(df_15m_base, '30m')
                if "1h" in ltf_options: df_map["1h"] = resample_ltf(df_15m_base, '1h')
                if "75m" in ltf_options: df_map["75m"] = resample_ltf(df_15m_base, '75m')
                
                ltf_results = {}
                is_within_tolerance = False
                matches_bias = False
                
                for tf in ltf_options:
                    df_target = df_map.get(tf)
                    dist, ema_val = calculate_ema_data(df_target)
                    ltf_results[tf] = {"dist": dist, "ema": ema_val}
                    
                    if dist is not None:
                        # Check Absolute Proximity
                        if abs(dist) <= pullback_tolerance:
                            is_within_tolerance = True
                            
                        # Check Bias Alignment (Only keep if it matches Bull/Bear logic)
                        if "Bullish" in trend_mode and dist >= -0.5: # Allow slight dip below EMA
                            matches_bias = True
                        elif "Bearish" in trend_mode and dist <= 0.5: # Allow slight pop above EMA
                            matches_bias = True
                
                # Filter Logic
                if strict_mode and not is_within_tolerance:
                    continue
                    
                if not matches_bias:
                    continue
                    
                # Build Table Row
                row_data = {
                    "Ticker": clean_ticker,
                    "Live Price": f"₹{round(df_15m_base['Close'].iloc[-1], 2)}"
                }
                
                for tf in ltf_options:
                    res = ltf_results[tf]
                    row_data[f"{tf} 50-EMA"] = format_cell(res["dist"], res["ema"], pullback_tolerance)
                    
                scanned_opportunities.append(row_data)
                
            except Exception:
                pass
                
        execution_progress.empty()
        
        if scanned_opportunities:
            display_dataframe = pd.DataFrame(scanned_opportunities)
            if strict_mode:
                st.success(f"🎯 Strict Mode: Found **{len(display_dataframe)}** {trend_mode} setups sitting right on the intraday EMAs.")
            else:
                st.success(f"📊 Matrix Mode: Found **{len(display_dataframe)}** {trend_mode} setups.")
            st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
        else:
            st.warning(f"No stocks are within ±{pullback_tolerance}% of the selected EMAs right now. Try increasing the tolerance slider.")
