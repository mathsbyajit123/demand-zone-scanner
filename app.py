import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from scipy.stats import linregress

# --- PAGE SETUP ---
st.set_page_config(page_title="Master SMC Confluence", layout="wide", page_icon="👑")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #FFD700; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #E0E0E0; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">👑 The Master Confluence Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">HTF Sweep -> LTF Breakout -> Momentum > 50 -> Safe Entry.</p>', unsafe_allow_html=True)

# --- MARKET SYMBOLS ---
@st.cache_data(ttl=86400)
def load_symbols(index_name):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[index_name])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- DATA PIPELINE ---
@st.cache_data(show_spinner=False)
def fetch_master_data(tickers, matrix_mode):
    if matrix_mode == "1 Day HTF -> 15 Min LTF":
        df_htf = yf.download(tickers, period='2y', interval='1d', group_by='ticker', threads=True, progress=False)
        df_ltf = yf.download(tickers, period='60d', interval='15m', group_by='ticker', threads=True, progress=False)
    else: # 1 Week HTF -> 1 Day LTF
        df_htf = yf.download(tickers, period='5y', interval='1wk', group_by='ticker', threads=True, progress=False)
        df_ltf = yf.download(tickers, period='2y', interval='1d', group_by='ticker', threads=True, progress=False)
    return df_htf, df_ltf

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    return 100 - (100 / (1 + gain / loss))

# --- MASTER LOGIC ENGINE ---
def evaluate_master_setup(df_htf, df_ltf, max_zone_w):
    if len(df_htf) < 30 or len(df_ltf) < 20: 
        return None

    df_ltf['RSI'] = calculate_rsi(df_ltf['Close'])
    df_htf = df_htf.dropna()
    df_ltf = df_ltf.dropna()
    
    if df_htf.empty or df_ltf.empty: return None

    # Current State
    current_ltf_idx = len(df_ltf) - 1
    latest_ltf = df_ltf.iloc[-1]
    prev_ltf = df_ltf.iloc[-2]

    # ==========================================
    # STEP 1: HTF SUPPORT MAPPING
    # ==========================================
    htf_valley_idx = argrelextrema(df_htf['Low'].values, np.less_equal, order=5)[0]
    if len(htf_valley_idx) < 2: return None
    
    htf_valleys = df_htf['Low'].iloc[htf_valley_idx].values
    all_swings = np.sort(htf_valleys)
    
    valid_support_floor = None
    valid_support_ceiling = None
    
    # Cluster valleys into zones
    current_zone = [all_swings[0]]
    for i in range(1, len(all_swings)):
        if (all_swings[i] - current_zone[0]) / current_zone[0] <= (max_zone_w / 100.0):
            current_zone.append(all_swings[i])
        else:
            if len(current_zone) >= 2:
                valid_support_floor = min(current_zone)
                valid_support_ceiling = max(current_zone)
            current_zone = [all_swings[i]]
            
    if len(current_zone) >= 2 and valid_support_floor is None:
        valid_support_floor = min(current_zone)
        valid_support_ceiling = max(current_zone)

    if valid_support_floor is None: return None

    # ==========================================
    # STEP 2: THE LIQUIDITY SWEEP (TRAP)
    # ==========================================
    # Look at recent LTF candles. Did price drop below the HTF floor, then recover?
    recent_ltf_candles = df_ltf.tail(15) 
    sweep_confirmed = False
    sweep_low = float('inf')
    
    for idx in range(len(recent_ltf_candles)):
        c = recent_ltf_candles.iloc[idx]
        # Pierced the floor, but closed above the floor
        if c['Low'] < valid_support_floor and c['Close'] > valid_support_floor:
            sweep_confirmed = True
            sweep_low = min(sweep_low, c['Low'])
            
    if not sweep_confirmed: return None

    # ==========================================
    # STEP 3: LTF TRENDLINE BREAKOUT
    # ==========================================
    ltf_peak_idx = argrelextrema(df_ltf['High'].values, np.greater_equal, order=4)[0]
    if len(ltf_peak_idx) < 2: return None
    
    # Draw descending resistance line
    recent_peaks_idx = ltf_peak_idx[-2:]
    recent_peaks_vals = df_ltf['High'].iloc[recent_peaks_idx].values
    
    slope, intercept, _, _, _ = linregress(recent_peaks_idx, recent_peaks_vals)
    
    if slope >= 0: return None # Must be a descending trendline
    
    projected_resistance = (slope * current_ltf_idx) + intercept

    # Did we just break above it?
    if prev_ltf['Close'] < projected_resistance and latest_ltf['Close'] > projected_resistance:
        
        # ==========================================
        # STEP 4: MOMENTUM & CANDLE HEALTH
        # ==========================================
        if latest_ltf['RSI'] > 50:
            
            body = latest_ltf['Close'] - latest_ltf['Open']
            rng = latest_ltf['High'] - latest_ltf['Low'] if latest_ltf['High'] != latest_ltf['Low'] else 0.001
            
            # Healthy green candle (body is > 55% of the total candle size)
            if body > 0 and (body / rng) > 0.55:
                
                # Calculate R/R Distance
                entry_price = latest_ltf['Close']
                risk_amt = entry_price - sweep_low
                
                return {
                    "signal": "🔥 Master Setup Active",
                    "entry": entry_price,
                    "sl": sweep_low,
                    "risk_pct": (risk_amt / entry_price) * 100
                }

    return None

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Execution Matrix")
    matrix_selection = st.selectbox("HTF Map -> LTF Entry", ["1 Day HTF -> 15 Min LTF", "1 Week HTF -> 1 Day LTF"])
    
    st.divider()
    st.info("**Execution Logic:**\n1. Find HTF Support\n2. Confirm Liquidity Sweep (Trap)\n3. LTF Trendline Breakout\n4. Breakout Candle RSI > 50\n5. Stop Loss = Bottom of Sweep")
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE MASTER SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:10] if "Test" in selected_sector else load_symbols(selected_sector)

# --- PROCESSING SYSTEM ---
if run_scan:
    scanned_opportunities = []
    
    with st.spinner("Downloading multi-timeframe structural data..."):
        htf_raw, ltf_raw = fetch_master_data(target_symbols, matrix_selection)
        
    execution_progress = st.progress(0, text="Evaluating institutional traps and breakouts...")
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing order flow for {ticker}...")
        
        try:
            if total_symbols > 1:
                df_h = htf_raw[ticker].copy()
                df_l = ltf_raw[ticker].copy()
            else:
                df_h = htf_raw.copy()
                df_l = ltf_raw.copy()
                
            outcome = evaluate_master_setup(df_h, df_l, max_zone_w=4.0)
            
            if outcome:
                scanned_opportunities.append({
                    "Ticker Symbol": ticker.replace('.NS', ''),
                    "Status": outcome["signal"],
                    "Entry Price": round(outcome["entry"], 2),
                    "Strict Stop Loss": round(outcome["sl"], 2),
                    "Risk % to SL": f"{round(outcome['risk_pct'], 2)}%"
                })
        except Exception:
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(display_dataframe)}** flawless institutional setups.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
        st.balloons()
    else:
        st.warning("No assets met all 5 strict conditions today. The market hasn't sprung the trap yet.")
