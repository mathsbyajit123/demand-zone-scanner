import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE SETUP & COLORS ---
st.set_page_config(page_title="Pro Institutional Scanner", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .main-title { font-size: 42px; font-weight: 800; color: #1E88E5; margin-bottom: 0px; }
    .sub-title { font-size: 18px; color: #607D8B; margin-bottom: 25px; }
    .stProgress .st-bo { background-color: #1E88E5; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ Elite Institutional Zone Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Strict Boring Candle (<50%) & Advanced Supply/Demand algorithmic filtering across NIFTY 500.</p>', unsafe_allow_html=True)

# --- LOAD NIFTY 500 ---
@st.cache_data
def load_nifty500_symbols():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        df = pd.read_csv(url)
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "TATAMOTORS.NS"]

nifty500_list = load_nifty500_symbols()

# --- SIDEBAR MENU (ATTRACTIVE LAYOUT) ---
with st.sidebar:
    st.header("🎛️ Scanner Settings")
    scan_mode = st.radio("Scan Range", ["Test Scan (10 Stocks)", "Full NIFTY 500"])
    
    st.divider()
    timeframe = st.selectbox("⏳ Timeframe", ["1d", "1wk", "1mo", "3mo", "6mo", "12mo"])
    zone_type = st.selectbox("📈 Zone Type", ["Bullish Demand Zone", "Bearish Supply Zone"])
    
    st.divider()
    st.markdown("### 🕯️ Candle Strictness")
    base_limit = st.slider("Max Base Candles Allowed", 1, 6, 5)
    
    min_legout, max_legout = st.slider("Leg-Out Candles (Min - Max)", 1, 6, (1, 3))
    
    # NEW: Min/Max slider for Leg-out body size (51% to 100%)
    min_leg_pct, max_leg_pct = st.slider("Leg-Out Body Size (%)", 51, 100, (60, 100), help="Minimum and maximum body percentage for an explosive leg-out.")

symbols_to_scan = nifty500_list[:10] if "Test" in scan_mode else nifty500_list

# --- CORE ALGORITHM ---
def scan_zones(ticker, tf, mode, max_base, min_leg, max_leg, min_leg_pct, max_leg_pct):
    try:
        if tf in ["6mo", "12mo"]:
            raw_data = yf.Ticker(ticker).history(period='15y', interval='1mo')
            if len(raw_data) < 12: return None
            raw_data['Year'] = raw_data.index.year
            if tf == "6mo":
                raw_data['Half'] = (raw_data.index.month - 1) // 6
                df = raw_data.groupby(['Year', 'Half']).agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
                df.index = [pd.Timestamp(year=y, month=1 if h==0 else 7, day=1) for y, h in df.index]
            else:
                df = raw_data.groupby('Year').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
                df.index = [pd.Timestamp(year=y, month=1, day=1) for y in df.index]
        else:
            df = yf.Ticker(ticker).history(period='10y', interval=tf)
            if len(df) < 15: return None
        
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = df['High'] - df['Low']
        
        # 1. STRICT BORING CANDLE RULE (Body strictly < 50% of Range)
        df['Is_Base'] = df['Body'] < (0.5 * df['Range'])
        
        # 2. Pre-Calculate Strong Leg-Out Candles based on Min & Max body percentages
        min_body_req = (min_leg_pct / 100.0) * df['Range']
        max_body_req = (max_leg_pct / 100.0) * df['Range']
        
        if mode == "Bullish Demand Zone":
            df['Is_Strong'] = (df['Close'] > df['Open']) & (df['Body'] >= min_body_req) & (df['Body'] <= max_body_req)
        else:
            df['Is_Strong'] = (df['Close'] < df['Open']) & (df['Body'] >= min_body_req) & (df['Body'] <= max_body_req)
            
        matches = []
        
        i = 1
        # Left-to-Right Sequential Scanner
        while i < len(df) - min_leg:
            if df['Is_Base'].iloc[i]:
                base_start = i
                base_end = i
                
                # Count consecutive boring candles
                while base_end + 1 < len(df) and df['Is_Base'].iloc[base_end + 1]:
                    base_end += 1
                
                base_count = base_end - base_start + 1
                
                # If base count is within allowed limit
                if base_count <= max_base:
                    legout_start = base_end + 1
                    legout_count = 0
                    
                    # Count consecutive explosive leg-out candles
                    while legout_start + legout_count < len(df) and df['Is_Strong'].iloc[legout_start + legout_count]:
                        legout_count += 1
                        
                    # Check if actual leg-outs fall perfectly within your Min and Max slider setting
                    if min_leg <= legout_count <= max_leg:
                        leg_in_idx = base_start - 1
                        
                        if leg_in_idx >= 0:
                            base_opens = df['Open'].iloc[base_start : base_end + 1]
                            base_closes = df['Close'].iloc[base_start : base_end + 1]
                            base_lows = df['Low'].iloc[base_start : base_end + 1]
                            base_highs = df['High'].iloc[base_start : base_end + 1]
                            
                            if mode == "Bullish Demand Zone":
                                leg_in_bullish = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
                                pattern = "RBR 🚀" if leg_in_bullish else "DBR 📉🚀"
                                
                                z_ceil = round(max(base_opens.max(), base_closes.max()), 2)
                                z_floor = round(base_lows.min(), 2)
                                
                                future_data = df.iloc[legout_start + legout_count :]
                                status = "Fresh 🟢"
                                if not future_data.empty and future_data['Low'].min() <= z_ceil:
                                    status = "Mitigated/Tested 🟡"
                                    
                            else:
                                leg_in_bearish = df['Close'].iloc[leg_in_idx] < df['Open'].iloc[leg_in_idx]
                                pattern = "DBD 🩸" if leg_in_bearish else "RBD 🚀🩸"
                                
                                z_ceil = round(base_highs.max(), 2)
                                z_floor = round(min(base_opens.min(), base_closes.min()), 2)
                                
                                future_data = df.iloc[legout_start + legout_count :]
                                status = "Fresh 🟢"
                                if not future_data.empty and future_data['High'].max() >= z_floor:
                                    status = "Mitigated/Tested 🟡"

                            date_detected = df.index[legout_start].strftime('%Y-%m-%d') if hasattr(df.index[legout_start], 'strftime') else str(df.index[legout_start])
                            
                            matches.append({
                                "Ticker": ticker.replace('.NS', ''),
                                "Date Detected": date_detected,
                                "Zone Status": status,
                                "Exact Pattern": pattern,
                                "Base Candles": base_count,
                                "Leg-Outs": legout_count,
                                "Ceiling (Proximal)": z_ceil,
                                "Floor (Distal)": z_floor
                            })
                # Skip forward past this base to continue scanning correctly
                i = base_end + 1
            else:
                i += 1
                
        return matches
    except Exception:
        return None

# --- RUN BUTTON ---
if st.button("🔍 Execute Advanced Scan", type="primary", use_container_width=True):
    results = []
    bar = st.progress(0, text="Initializing Scanner...")
    
    for idx, ticker in enumerate(symbols_to_scan):
        bar.progress((idx + 1) / len(symbols_to_scan), text=f"Scanning {ticker}...")
        res = scan_zones(ticker, timeframe, zone_type, base_limit, min_legout, max_legout, min_leg_pct, max_leg_pct)
        if res: results.extend(res)
            
    bar.empty()
    
    if results:
        # Sort Latest to Oldest
        df_display = pd.DataFrame(results)
        df_display['Date Detected'] = pd.to_datetime(df_display['Date Detected'])
        df_display = df_display.sort_values(by="Date Detected", ascending=False)
        df_display['Date Detected'] = df_display['Date Detected'].dt.strftime('%Y-%m-%d')
        
        # Display Metrics
        col1, col2 = st.columns(2)
        col1.success(f"🎯 Found **{len(df_display)}** Institutional Zones.")
        col2.info(f"🟢 **{len(df_display[df_display['Zone Status'] == 'Fresh 🟢'])}** Zones are Fresh.")
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No patterns found matching these strict institutional criteria.")
