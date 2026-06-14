import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from scipy.stats import linregress

# --- PAGE SETUP ---
st.set_page_config(page_title="Master Sector & Structure Scanner", layout="wide", page_icon="🌐")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #3F51B5; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #546E7A; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🌐 Master Sector & Structure Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Multi-Timeframe scanning for Horizontal & Trendline Institutional Sweeps across NSE Sectors.</p>', unsafe_allow_html=True)

# --- SECTOR & SYMBOL MAPPING ---
@st.cache_data(ttl=86400)
def load_symbols(category):
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
        fallbacks = {
            "NIFTY Bank": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"],
            "NIFTY IT": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS"],
            "NIFTY Auto": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS"]
        }
        return fallbacks.get(category, ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "SBIN.NS"])

# --- DATA FETCHING PIPELINE ---
@st.cache_data(show_spinner=False)
def fetch_master_data(tickers, matrix_mode):
    if matrix_mode == "1 Day HTF -> 15 Min LTF":
        df_htf = yf.download(tickers, period='2y', interval='1d', group_by='ticker', threads=True, progress=False)
        df_ltf = yf.download(tickers, period='60d', interval='15m', group_by='ticker', threads=True, progress=False)
    elif matrix_mode == "1 Week HTF -> 1 Day LTF":
        df_htf = yf.download(tickers, period='5y', interval='1wk', group_by='ticker', threads=True, progress=False)
        df_ltf = yf.download(tickers, period='2y', interval='1d', group_by='ticker', threads=True, progress=False)
    elif matrix_mode == "1 Month HTF -> 1 Week LTF":
        df_htf = yf.download(tickers, period='10y', interval='1mo', group_by='ticker', threads=True, progress=False)
        df_ltf = yf.download(tickers, period='5y', interval='1wk', group_by='ticker', threads=True, progress=False)
    else: # 3 Month HTF -> 1 Month LTF
        df_htf = yf.download(tickers, period='20y', interval='3mo', group_by='ticker', threads=True, progress=False)
        df_ltf = yf.download(tickers, period='10y', interval='1mo', group_by='ticker', threads=True, progress=False)
    return df_htf, df_ltf

# --- DUAL-STRUCTURE LOGIC ENGINE ---
def evaluate_market_structure(df_htf, df_ltf, bias, max_zone_w):
    if len(df_htf) < 20 or len(df_ltf) < 10: 
        return None

    df_htf = df_htf.dropna()
    df_ltf = df_ltf.dropna()
    if df_htf.empty or df_ltf.empty: return None

    latest_ltf = df_ltf.iloc[-1]
    current_htf_idx = len(df_htf) - 1

    # ==========================================
    # HTF LINE CHART MATH (CLOSES ONLY)
    # ==========================================
    peak_idx = argrelextrema(df_htf['Close'].values, np.greater_equal, order=4)[0]
    valley_idx = argrelextrema(df_htf['Close'].values, np.less_equal, order=4)[0]
    
    status_flags = []
    sweep_data = {"is_sweep": False, "wick_extreme": None}

    # --- BULLISH SCENARIO (SUPPORT) ---
    if "Bullish" in bias:
        if len(valley_idx) >= 2:
            # 1. HORIZONTAL SUPPORT MAPPING
            all_valleys = np.sort(df_htf['Close'].iloc[valley_idx].values)
            zones = []
            if len(all_valleys) > 0:
                current_zone = [all_valleys[0]]
                for i in range(1, len(all_valleys)):
                    if (all_valleys[i] - current_zone[0]) / current_zone[0] <= (max_zone_w / 100.0):
                        current_zone.append(all_valleys[i])
                    else:
                        if len(current_zone) >= 2: zones.append({'floor': min(current_zone), 'ceiling': max(current_zone)})
                        current_zone = [all_valleys[i]]
                if len(current_zone) >= 2: zones.append({'floor': min(current_zone), 'ceiling': max(current_zone)})

            # 2. TRENDLINE SUPPORT MAPPING
            recent_v_idx = valley_idx[-2:]
            recent_v_vals = df_htf['Close'].iloc[recent_v_idx].values
            slope, intercept, _, _, _ = linregress(recent_v_idx, recent_v_vals)
            
            projected_trend_sup = None
            if slope > 0: # Ascending trendline valid
                projected_trend_sup = (slope * current_htf_idx) + intercept

            # 3. LTF CANDLESTICK SWEEP EVALUATION (Wicks piercing HTF lines)
            for z in zones:
                f = z['floor']
                # Pierced the floor, closed above it
                if latest_ltf['Low'] < f and latest_ltf['Close'] > f:
                    status_flags.append(f"Horizontal Sweep ✅ (₹{round(f,1)})")
                    sweep_data = {"is_sweep": True, "wick_extreme": latest_ltf['Low']}
            
            if projected_trend_sup:
                if latest_ltf['Low'] < projected_trend_sup and latest_ltf['Close'] > projected_trend_sup:
                    status_flags.append(f"Trendline Sweep 📈 (₹{round(projected_trend_sup,1)})")
                    sweep_data = {"is_sweep": True, "wick_extreme": min(sweep_data.get("wick_extreme", float('inf')), latest_ltf['Low'])}

    # --- BEARISH SCENARIO (RESISTANCE) ---
    elif "Bearish" in bias:
        if len(peak_idx) >= 2:
            # 1. HORIZONTAL RESISTANCE MAPPING
            all_peaks = np.sort(df_htf['Close'].iloc[peak_idx].values)
            zones = []
            if len(all_peaks) > 0:
                current_zone = [all_peaks[0]]
                for i in range(1, len(all_peaks)):
                    if (all_peaks[i] - current_zone[0]) / current_zone[0] <= (max_zone_w / 100.0):
                        current_zone.append(all_peaks[i])
                    else:
                        if len(current_zone) >= 2: zones.append({'floor': min(current_zone), 'ceiling': max(current_zone)})
                        current_zone = [all_peaks[i]]
                if len(current_zone) >= 2: zones.append({'floor': min(current_zone), 'ceiling': max(current_zone)})

            # 2. TRENDLINE RESISTANCE MAPPING
            recent_p_idx = peak_idx[-2:]
            recent_p_vals = df_htf['Close'].iloc[recent_p_idx].values
            slope, intercept, _, _, _ = linregress(recent_p_idx, recent_p_vals)
            
            projected_trend_res = None
            if slope < 0: # Descending trendline valid
                projected_trend_res = (slope * current_htf_idx) + intercept

            # 3. LTF CANDLESTICK SWEEP EVALUATION
            for z in zones:
                c = z['ceiling']
                # Pierced the ceiling, closed below it
                if latest_ltf['High'] > c and latest_ltf['Close'] < c:
                    status_flags.append(f"Horizontal Sweep 🚨 (₹{round(c,1)})")
                    sweep_data = {"is_sweep": True, "wick_extreme": latest_ltf['High']}
            
            if projected_trend_res:
                if latest_ltf['High'] > projected_trend_res and latest_ltf['Close'] < projected_trend_res:
                    status_flags.append(f"Trendline Sweep 📉 (₹{round(projected_trend_res,1)})")
                    sweep_data = {"is_sweep": True, "wick_extreme": max(sweep_data.get("wick_extreme", 0), latest_ltf['High'])}

    # ==========================================
    # FINAL OUTPUT GENERATION
    # ==========================================
    if status_flags:
        # Check if it's a massive confluence (Both Horizontal and Trendline hit at once)
        if len(status_flags) > 1:
            final_status = "🔥 DUAL CONFLUENCE SWEEP: " + " & ".join(status_flags)
        else:
            final_status = status_flags[0]
            
        return {
            "signal": final_status,
            "entry": latest_ltf['Close'],
            "sl": sweep_data["wick_extreme"]
        }

    return None

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Sector Index", [
        "NIFTY 50", "NIFTY Bank", "NIFTY IT", "NIFTY Auto", 
        "NIFTY Metal", "NIFTY Pharma", "NIFTY FMCG", "NIFTY Realty", 
        "NIFTY Energy", "NIFTY 500"
    ])
    
    st.divider()
    st.header("2. Structural Matrix")
    matrix_selection = st.selectbox("HTF Map -> LTF Sweep", [
        "1 Day HTF -> 15 Min LTF", 
        "1 Week HTF -> 1 Day LTF",
        "1 Month HTF -> 1 Week LTF",
        "3 Month HTF -> 1 Month LTF"
    ])
    
    st.divider()
    st.header("3. Setup Direction")
    execution_bias = st.radio("Institutional Trap Type:", [
        "Bullish Traps (Hunting at Support)", 
        "Bearish Traps (Hunting at Resistance)"
    ])
    
    if "1 Day" in matrix_selection: def_max = 2.0
    elif "1 Week" in matrix_selection: def_max = 4.0
    elif "1 Month" in matrix_selection: def_max = 6.0
    else: def_max = 8.0
        
    st.divider()
    max_w = st.slider("Max HTF Horizontal Width (%)", 1.0, 15.0, def_max, help="Tolerance for grouping HTF closes into horizontal zones.")
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE STRUCTURE SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols(selected_sector)

# --- PROCESSING SYSTEM ---
if run_scan:
    scanned_opportunities = []
    
    with st.spinner(f"Downloading {matrix_selection} data for {selected_sector}..."):
        htf_raw, ltf_raw = fetch_master_data(target_symbols, matrix_selection)
        
    execution_progress = st.progress(0, text="Evaluating HTF structure and LTF liquidity grabs...")
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        execution_progress.progress((idx + 1) / total_symbols, text=f"Scanning multi-dimensional planes for {ticker}...")
        
        try:
            if total_symbols > 1:
                df_h = htf_raw[ticker].copy()
                df_l = ltf_raw[ticker].copy()
            else:
                df_h = htf_raw.copy()
                df_l = ltf_raw.copy()
                
            outcome = evaluate_market_structure(df_h, df_l, execution_bias, max_w)
            
            if outcome:
                # Calculate risk percent
                risk_amt = abs(outcome["entry"] - outcome["sl"])
                risk_pct = (risk_amt / outcome["entry"]) * 100
                
                scanned_opportunities.append({
                    "Ticker Symbol": ticker.replace('.NS', ''),
                    "Sector": selected_sector,
                    "Institutional Footprint": outcome["signal"],
                    "LTF Execution Price": round(outcome["entry"], 2),
                    "Strict Wick Stop Loss": round(outcome["sl"], 2),
                    "Risk % to SL": f"{round(risk_pct, 2)}%"
                })
        except Exception:
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(display_dataframe)}** clear structural sweeps in {selected_sector}.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No assets in {selected_sector} are exhibiting LTF sweeps at HTF structural levels right now.")
