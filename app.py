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
st.markdown('<p class="sub-title">Advanced Supply & Demand algorithmic filtering across NIFTY indices.</p>', unsafe_allow_html=True)

# --- LOAD NIFTY SYMBOLS ---
@st.cache_data
def load_symbols(index_name):
    try:
        if index_name == "NIFTY 50":
            url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
        else:
            url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
            
        df = pd.read_csv(url)
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        # Fallback list if NSE website blocks the download temporarily
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "TATAMOTORS.NS"]

# --- SIDEBAR MENU ---
with st.sidebar:
    st.header("🎛️ Scanner Settings")
    scan_mode = st.radio("Scan Universe", ["Test Scan (10 Stocks)", "NIFTY 50", "Full NIFTY 500"])
    
    st.divider()
    
    timeframe = st.selectbox("⏳ Timeframe", ["1d", "1wk", "1mo", "3mo", "6mo", "12mo"])
    zone_type = st.selectbox("📈 Zone Type", ["Bullish Demand Zone", "Bearish Supply Zone"])
    
    st.divider()
    st.markdown("### 🎯 Output Filters")
    status_filter = st.multiselect("Show Zones That Are:", 
                                   ["Fresh 🟢", "Approaching 🚶‍♂️", "In Zone (Consolidating) ⏳", "Mitigated/Tested 🟡"],
                                   default=["Fresh 🟢", "Approaching 🚶‍♂️", "In Zone (Consolidating) ⏳"])
    
    st.divider()
    st.markdown("### 🕯️ Candle Strictness")
    base_limit = st.slider("Max Base Candles Allowed", 1, 6, 5)
    num_legout = st.slider("Required Leg-Out Candles", 1, 3, 2)
    legout_strength = st.slider("Min Leg-Out Body Size (%)", 50, 90, 50)

# Select the right list of stocks based on user choice
if "NIFTY 50" in scan_mode and "Full" not in scan_mode:
    symbols_to_scan = load_symbols("NIFTY 50")
elif "NIFTY 500" in scan_mode:
    symbols_to_scan = load_symbols("NIFTY 500")
else:
    symbols_to_scan = load_symbols("NIFTY 500")[:10]

# --- CORE ALGORITHM ---
def scan_zones(ticker, tf, mode, max_base, leg_count, leg_pct):
    try:
        if tf in ["6mo", "12mo"]:
            raw_data = yf.Ticker(ticker).history(period='15y', interval='1mo')
            if len(raw_data) < 12: return None
            months_to_merge = 6 if tf == "6mo" else 12
            raw_data = raw_data.iloc[::-1].copy() 
            raw_data['group'] = np.arange(len(raw_data)) // months_to_merge
            df = raw_data.groupby('group').agg({'Open': 'last', 'High': 'max', 'Low': 'min', 'Close': 'first'}).iloc[::-1]
            df.index = raw_data.groupby('group').apply(lambda x: x.index.min()).iloc[::-1]
        else:
            df = yf.Ticker(ticker).history(period='10y', interval=tf)
            if len(df) < 15: return None
        
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = df['High'] - df['Low']
        df['Is_Base'] = df['Body'] < (0.5 * df['Range'])
        matches = []
        
        for i in range(5, len(df) - leg_count):
            
            # 1. Check Leg-Out validity
            legout_valid = True
            for k in range(1, leg_count + 1):
                idx = i + k
                body_ratio = (leg_pct / 100.0) * df['Range'].iloc[idx]
                if mode == "Bullish Demand Zone":
                    if not (df['Close'].iloc[idx] > df['Open'].iloc[idx] and df['Body'].iloc[idx] >= body_ratio):
                        legout_valid = False; break
                else:
                    if not (df['Close'].iloc[idx] < df['Open'].iloc[idx] and df['Body'].iloc[idx] >= body_ratio):
                        legout_valid = False; break
            
            if not legout_valid: continue
            
            # 2. Count Base Candles backwards
            base_count = 0
            for check_idx in range(i, i - max_base - 1, -1):
                if df['Is_Base'].iloc[check_idx]: base_count += 1
                else: break
                
            if 1 <= base_count <= max_base:
                leg_in_idx = i - base_count
                
                # 3. Identify Pattern & Prices
                if mode == "Bullish Demand Zone":
                    leg_in_bullish = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
                    pattern = "RBR 🚀" if leg_in_bullish else "DBR 📉🚀"
                    z_ceil = round(df['Close'].iloc[i-base_count+1 : i+1].max(), 2)
                    z_floor = round(df['Low'].iloc[i-base_count+1 : i+1].min(), 2)
                else:
                    leg_in_bearish = df['Close'].iloc[leg_in_idx] < df['Open'].iloc[leg_in_idx]
                    pattern = "DBD 🩸" if leg_in_bearish else "RBD 🚀🩸"
                    z_ceil = round(df['High'].iloc[i-base_count+1 : i+1].max(), 2)
                    z_floor = round(df['Close'].iloc[i-base_count+1 : i+1].min(), 2)
                    
                # 4. Advanced Status Check (Fresh, Approaching, In Zone, Mitigated)
                future_data = df.iloc[i + leg_count + 1 :]
                status = "Fresh 🟢"
                
                if not future_data.empty:
                    latest_close = future_data['Close'].iloc[-1]
                    latest_low = future_data['Low'].iloc[-1]
                    latest_high = future_data['High'].iloc[-1]
                    
                    # Look at the last 6 candles to see if price is consolidating inside the zone
                    recent_candles = future_data.tail(6)
                    
                    if mode == "Bullish Demand Zone":
                        # Did it break completely below the zone? Skip it entirely.
                        if future_data['Close'].min() < z_floor:
                            continue 
                            
                        in_zone_count = sum((recent_candles['Close'] <= z_ceil) & (recent_candles['Close'] >= z_floor))
                        
                        if in_zone_count >= 2 and (latest_close <= z_ceil and latest_close >= z_floor):
                            status = f"In Zone (Consolidating) ⏳"
                        elif future_data['Low'].min() <= z_ceil:
                            status = "Mitigated/Tested 🟡"
                        elif latest_low <= (z_ceil * 1.03): # Within 3% of the zone
                            status = "Approaching 🚶‍♂️"
                            
                    else: # Bearish Supply Zone
                        # Did it break completely above the zone? Skip it entirely.
                        if future_data['Close'].max() > z_ceil:
                            continue
                            
                        in_zone_count = sum((recent_candles['Close'] <= z_ceil) & (recent_candles['Close'] >= z_floor))
                        
                        if in_zone_count >= 2 and (latest_close <= z_ceil and latest_close >= z_floor):
                            status = f"In Zone (Consolidating) ⏳"
                        elif future_data['High'].max() >= z_floor:
                            status = "Mitigated/Tested 🟡"
                        elif latest_high >= (z_floor * 0.97): # Within 3% of the zone
                            status = "Approaching 🚶‍♂️"

                # Filter out statuses the user doesn't want to see
                if not any(filt in status for filt in status_filter):
                    continue

                matches.append({
                    "Ticker": ticker.replace('.NS', ''),
                    "Date Detected": df.index[i + leg_count].strftime('%Y-%m-%d') if hasattr(df.index[i+leg_count], 'strftime') else str(df.index[i+leg_count]),
                    "Status": status,
                    "Pattern": pattern,
                    "Base": base_count,
                    "Legs": leg_count,
                    "Ceiling": z_ceil,
                    "Floor": z_floor
                })
        return matches
    except Exception:
        return None

# --- RUN BUTTON ---
if st.button("🔍 Execute Advanced Scan", type="primary", use_container_width=True):
    results = []
    bar = st.progress(0, text="Initializing Scanner...")
    
    for idx, ticker in enumerate(symbols_to_scan):
        bar.progress((idx + 1) / len(symbols_to_scan), text=f"Scanning {ticker}...")
        res = scan_zones(ticker, timeframe, zone_type, base_limit, num_legout, legout_strength)
        if res: results.extend(res)
            
    bar.empty()
    
    if results:
        df_display = pd.DataFrame(results)
        df_display['Date Detected'] = pd.to_datetime(df_display['Date Detected'])
        df_display = df_display.sort_values(by="Date Detected", ascending=False)
        df_display['Date Detected'] = df_display['Date Detected'].dt.strftime('%Y-%m-%d')
        
        # Display Metrics
        col1, col2, col3 = st.columns(3)
        col1.success(f"🎯 Total Zones: **{len(df_display)}**")
        col2.info(f"🟢 Fresh: **{len(df_display[df_display['Status'].str.contains('Fresh')])}**")
        col3.warning(f"⏳ In Zone: **{len(df_display[df_display['Status'].str.contains('In Zone')])}**")
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No patterns found matching these strict criteria.")
