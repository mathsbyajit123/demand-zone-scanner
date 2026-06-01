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
st.markdown('<p class="sub-title">Advanced Supply & Demand algorithmic filtering across NIFTY 500.</p>', unsafe_allow_html=True)

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
    num_legout = st.slider("Required Leg-Out Candles", 1, 3, 2)
    legout_strength = st.slider("Min Leg-Out Body Size (%)", 50, 90, 50)

symbols_to_scan = nifty500_list[:10] if "Test" in scan_mode else nifty500_list

# --- CORE ALGORITHM ---
def scan_zones(ticker, tf, mode, max_base, leg_count, leg_pct):
    try:
        # Custom Timeframes (6M, 12M) fetch 15 years to ensure enough data
        if tf in ["6mo", "12mo"]:
            raw_data = yf.Ticker(ticker).history(period='15y', interval='1mo')
            if len(raw_data) < 12: return None
            months_to_merge = 6 if tf == "6mo" else 12
            raw_data = raw_data.iloc[::-1].copy() 
            raw_data['group'] = np.arange(len(raw_data)) // months_to_merge
            df = raw_data.groupby('group').agg({'Open': 'last', 'High': 'max', 'Low': 'min', 'Close': 'first'}).iloc[::-1]
            df.index = raw_data.groupby('group').apply(lambda x: x.index.min()).iloc[::-1]
        else:
            # Standard Timeframes upgraded to 10 YEARS of history
            df = yf.Ticker(ticker).history(period='10y', interval=tf)
            if len(df) < 15: return None
        
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = df['High'] - df['Low']
        
        # Base condition: Body < 50%
        df['Is_Base'] = df['Body'] < (0.5 * df['Range'])
        matches = []
        
        # Loop through chart
        for i in range(5, len(df) - leg_count):
            
            # 1. Check Leg-Out validity based on user input
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
                
                # 3. Identify Pattern & Calculate Zone Prices
                if mode == "Bullish Demand Zone":
                    leg_in_bullish = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
                    pattern = "RBR (Rally-Base-Rally) 🚀" if leg_in_bullish else "DBR (Drop-Base-Rally) 📉🚀"
                    z_ceil = round(df['Close'].iloc[i-base_count+1 : i+1].max(), 2)
                    z_floor = round(df['Low'].iloc[i-base_count+1 : i+1].min(), 2)
                    
                    # Check if tested
                    future_data = df.iloc[i + leg_count + 1 :]
                    status = "Fresh 🟢"
                    if not future_data.empty and future_data['Low'].min() <= z_ceil:
                        status = "Mitigated/Tested 🟡"
                        
                else:
                    leg_in_bearish = df['Close'].iloc[leg_in_idx] < df['Open'].iloc[leg_in_idx]
                    pattern = "DBD (Drop-Base-Drop) 🩸" if leg_in_bearish else "RBD (Rally-Base-Drop) 🚀🩸"
                    z_ceil = round(df['High'].iloc[i-base_count+1 : i+1].max(), 2)
                    z_floor = round(df['Close'].iloc[i-base_count+1 : i+1].min(), 2)
                    
                    # Check if tested
                    future_data = df.iloc[i + leg_count + 1 :]
                    status = "Fresh 🟢"
                    if not future_data.empty and future_data['High'].max() >= z_floor:
                        status = "Mitigated/Tested 🟡"

                matches.append({
                    "Ticker": ticker.replace('.NS', ''),
                    "Date Detected": df.index[i + leg_count].strftime('%Y-%m-%d') if hasattr(df.index[i+leg_count], 'strftime') else str(df.index[i+leg_count]),
                    "Zone Status": status,
                    "Exact Pattern": pattern,
                    "Base Candles": base_count,
                    "Leg-Outs": leg_count,
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
