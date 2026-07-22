import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Custom MTF Accumulation Scanner", layout="wide", page_icon="⚙️")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #8B5CF6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚙️ Fully Customizable MTF Accumulation Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">You control the timeframes. Scans for Macro Uptrends + Micro Low-Volume Retracements.</p>', unsafe_allow_html=True)

# --- ROBUST DATA UNIVERSE LOADER ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY NEXT 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "NIFTY BANK": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY MIDCAP 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY SMALLCAP 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    url = urls.get(category)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        st.sidebar.warning("⚠️ NSE Server blocked full list. Using liquid failsafe stocks.")
        return ['RELIANCE.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'TCS.NS', 'ITC.NS', 'LT.NS', 'SBIN.NS', 'BHARTIARTL.NS']

# --- CUSTOM MULTI-TIMEFRAME ALGORITHM ---
def analyze_custom_mtf(ticker, macro_cfg, trigger_cfg):
    try:
        stock = yf.Ticker(ticker)
        
        # --- 1. FETCH & ANALYZE MACRO TIMEFRAME ---
        df_macro = stock.history(period=macro_cfg["period"], interval=macro_cfg["interval"])
        if df_macro.empty or len(df_macro) < 50: return None
        if df_macro.index.tz is not None: df_macro.index = df_macro.index.tz_localize(None)
        df_macro = df_macro.ffill().dropna(subset=['Close'])
        
        df_macro['EMA_21'] = df_macro['Close'].ewm(span=21, adjust=False).mean()
        df_macro['EMA_44'] = df_macro['Close'].ewm(span=44, adjust=False).mean()
        
        macro_close = df_macro['Close'].iloc[-1]
        macro_ema21 = df_macro['EMA_21'].iloc[-1]
        macro_ema44 = df_macro['EMA_44'].iloc[-1]
        
        # MACRO RULES: Price > 21 EMA and 21 EMA > 44 EMA
        if macro_close <= macro_ema21 or macro_ema21 <= macro_ema44:
            return None

        # --- 2. FETCH & ANALYZE TRIGGER (RETRACEMENT) TIMEFRAME ---
        df_trig = stock.history(period=trigger_cfg["period"], interval=trigger_cfg["interval"])
        if df_trig.empty or len(df_trig) < 50: return None
        if df_trig.index.tz is not None: df_trig.index = df_trig.index.tz_localize(None)
        df_trig = df_trig.ffill().dropna(subset=['Close', 'High', 'Low', 'Volume'])
        
        df_trig['EMA_21'] = df_trig['Close'].ewm(span=21, adjust=False).mean()
        df_trig['EMA_44'] = df_trig['Close'].ewm(span=44, adjust=False).mean()
        df_trig['Vol_Avg'] = df_trig['Volume'].rolling(20).mean()
        
        trig_close = df_trig['Close'].iloc[-1]
        trig_low = df_trig['Low'].iloc[-1]
        trig_ema21 = df_trig['EMA_21'].iloc[-1]
        trig_ema44 = df_trig['EMA_44'].iloc[-1]
        trig_vol_avg = df_trig['Vol_Avg'].iloc[-1]
        
        # TRIGGER RULE 1: Trend Alignment (21 > 44)
        if trig_ema21 <= trig_ema44:
            return None
            
        # TRIGGER RULE 2: Prior Move (Price must have expanded at least 2.5% above the 21 EMA recently)
        recent_high_15 = df_trig['High'].iloc[-15:].max()
        if recent_high_15 < (trig_ema21 * 1.025):
            return None
            
        # TRIGGER RULE 3: The Retracement (Low touches/breaks 21 EMA, Close holds above 44 EMA)
        is_in_ema_zone = (trig_low <= (trig_ema21 * 1.005)) and (trig_close >= (trig_ema44 * 0.99))
        if not is_in_ema_zone:
            return None
            
        # TRIGGER RULE 4: Volume Exhaustion (Average volume of last 3 bars < 75% of 20-bar Average)
        pullback_vol = df_trig['Volume'].iloc[-3:].mean()
        if pullback_vol >= (trig_vol_avg * 0.75):
            return None
            
        vol_dryness_pct = round((pullback_vol / trig_vol_avg) * 100, 1)
        
        return {
            "Ticker": ticker.replace('.NS', ''),
            "Live Price": f"₹{round(trig_close, 2)}",
            "Macro Trend": "✅ Aligned (Price > 21 > 44)",
            "Micro Pullback": "🎯 In 21/44 EMA Zone",
            "Retracement Volume": f"🔇 {vol_dryness_pct}% of Avg (Dry)",
            "Status": "🚀 Ready for Reversal"
        }
                
    except Exception:
        return None

# --- SIDEBAR INTERFACE: TOTAL USER CONTROL ---
with st.sidebar:
    st.header("1. Target Sector")
    sector_input = st.selectbox("Market Universe:", [
        "NIFTY 500", "NIFTY 50", "NIFTY NEXT 50", 
        "NIFTY BANK", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 250"
    ])
    
    st.divider()
    st.header("2. Setup Your Timeframes")
    
    macro_tf = st.selectbox(
        "Macro Trend (The Big Picture):", 
        ["1 Month", "1 Week", "1 Day", "1 Hour"], 
        index=1,
        help="Checks if the higher timeframe is in a strong uptrend."
    )
    
    trigger_tf = st.selectbox(
        "Retracement Trigger (The Pullback):", 
        ["1 Week", "1 Day", "1 Hour", "15 Minutes"], 
        index=1,
        help="Checks where the actual low-volume accumulation is happening."
    )
    
    st.divider()
    st.success(f"**Scanner Will Look For:**\n\n1. Uptrend on **{macro_tf}** chart.\n2. Low Volume Pullback on **{trigger_tf}** chart.")
    execute_button = st.button("🚀 EXECUTE CUSTOM SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    # Mapping user selections to yfinance API parameters
    tf_configs = {
        "1 Month": {"period": "20y", "interval": "1mo"},
        "1 Week": {"period": "10y", "interval": "1wk"},
        "1 Day": {"period": "2y", "interval": "1d"},
        "1 Hour": {"period": "729d", "interval": "1h"},
        "15 Minutes": {"period": "59d", "interval": "15m"}
    }
    
    macro_cfg = tf_configs[macro_tf]
    trigger_cfg = tf_configs[trigger_tf]

    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for {macro_tf} Trend + {trigger_tf} Retracement...")
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(analyze_custom_mtf, ticker, macro_cfg, trigger_cfg): ticker 
            for ticker in symbols_list
        }
        
        completed_count = 0
        for future in as_completed(futures_map):
            completed_count += 1
            result = future.result()
            if result:
                confirmed_setups.append(result)
            
            percent_complete = completed_count / len(symbols_list)
            progress_ui.progress(percent_complete, text=f"Analyzing Custom Timeframes: {completed_count}/{len(symbols_list)}")
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        results_df['Raw_Vol'] = results_df['Retracement Volume'].str.extract(r'(\d+\.\d+)%').astype(float)
        results_df = results_df.sort_values(by='Raw_Vol', ascending=True).drop(columns=['Raw_Vol'])
        
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks matching your exact timeframe combinations.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks currently match all conditions. This means no {macro_tf} uptrending stocks are currently experiencing a low-volume {trigger_tf} pullback.")
