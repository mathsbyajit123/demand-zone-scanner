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
st.markdown('<p class="sub-title">Authentic Imbalances + Pivot Break (Swing Structure) Validation.</p>', unsafe_allow_html=True)

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
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "TATAMOTORS.NS"]

# --- SIDEBAR MENU ---
with st.sidebar:
    st.header("🎛️ Scanner Settings")
    scan_mode = st.radio("Scan Universe", ["Test Scan (10 Stocks)", "NIFTY 50", "Full NIFTY 500"])
    
    st.divider()
    
    timeframe = st.selectbox("⏳ Timeframe", ["1d", "1wk", "1mo", "3mo", "6mo", "12mo"])
    zone_type = st.selectbox("📈 Zone Type", ["Bullish Demand Zone", "Bearish Supply Zone"])
    
    st.divider()
    st.markdown("### 🏛️ Pivot & Structure Rules")
    require_pivot = st.checkbox("Require Pivot/Swing Break", value=True, help="Leg-Out rally MUST close past the previous structural turning point.")
    pivot_lookback = st.slider("Pivot Lookback (Candles)", 5, 30, 15, help="How far back before the base to search for the highest/lowest pivot.")

    st.divider()
    st.markdown("### 🕯️ Imbalance (Authenticity)")
    base_limit = st.slider("Max Base Candles", 1, 6, 4)
    legout_range = st.slider("Min & Max Leg-Out Candles", 1, 5, (1, 3))
    min_legout, max_legout = legout_range
    exciting_pct = st.slider("Exciting Candle Body (%)", 50, 100, 60)
    
    st.divider()
    st.markdown("### 💼 Tradeable Rules")
    max_risk_pct = st.slider("Max Zone Width / Risk (%)", 1, 15, 6)
    
    status_filter = st.multiselect("Show Zones That Are:", 
                                   ["Fresh 🟢", "Approaching 🚶‍♂️", "In Zone (Consolidating) ⏳", "Mitigated/Tested 🟡"],
                                   default=["Fresh 🟢", "Approaching 🚶‍♂️", "In Zone (Consolidating) ⏳"])

if "NIFTY 50" in scan_mode and "Full" not in scan_mode:
    symbols_to_scan = load_symbols("NIFTY 50")
elif "NIFTY 500" in scan_mode:
    symbols_to_scan = load_symbols("NIFTY 500")
else:
    symbols_to_scan = load_symbols("NIFTY 500")[:10]

# --- CORE ALGORITHM ---
def scan_zones(ticker, tf, mode, max_base, min_leg, max_leg, exc_pct, max_risk, req_pivot, p_lookback):
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
        df['Is_Exciting'] = df['Body'] >= (exc_pct / 100.0) * df['Range']
        
        matches = []
        
        for i in range(5, len(df) - max_leg):
            
            # 1. Count consecutive EXCITING Leg-Out candles
            consecutive_legs = 0
            for k in range(1, max_leg + 1):
                idx = i + k
                if mode == "Bullish Demand Zone":
                    valid_candle = (df['Close'].iloc[idx] > df['Open'].iloc[idx]) and df['Is_Exciting'].iloc[idx]
                else:
                    valid_candle = (df['Close'].iloc[idx] < df['Open'].iloc[idx]) and df['Is_Exciting'].iloc[idx]
                
                if valid_candle: consecutive_legs += 1
                else: break 
            
            if consecutive_legs < min_leg: continue
            
            # 2. Count Base Candles backwards
            base_count = 0
            for check_idx in range(i, i - max_base - 1, -1):
                if df['Is_Base'].iloc[check_idx]: base_count += 1
                else: break
                
            if 1 <= base_count <= max_base:
                leg_in_idx = i - base_count
                final_legout_idx = i + consecutive_legs
                final_legout_close = df['Close'].iloc[final_legout_idx]
                
                # --- 3. PIVOT (SWING) BREAK LOGIC ---
                lookback_start = max(0, leg_in_idx - p_lookback)
                
                if mode == "Bullish Demand Zone":
                    # Find highest peak before the base formed
                    pivot_price = df['High'].iloc[lookback_start : leg_in_idx + 1].max()
                    pivot_broken = final_legout_close > pivot_price
                else:
                    # Find lowest valley before the base formed
                    pivot_price = df['Low'].iloc[lookback_start : leg_in_idx + 1].min()
                    pivot_broken = final_legout_close < pivot_price
                
                # Skip if pivot break is required but failed
                if req_pivot and not pivot_broken:
                    continue

                # --- 4. IDENTIFY PATTERN & ZONE PRICES ---
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
                    
                zone_width_pct = ((z_ceil - z_floor) / z_floor) * 100
                    
                # --- 5. ADVANCED STATUS CHECK ---
                future_data = df.iloc[final_legout_idx + 1 :]
                status = "Fresh 🟢"
                
                if not future_data.empty:
                    latest_close = future_data['Close'].iloc[-1]
                    latest_low = future_data['Low'].iloc[-1]
                    latest_high = future_data['High'].iloc[-1]
                    recent_candles = future_data.tail(6)
                    
                    if mode == "Bullish Demand Zone":
                        if future_data['Close'].min() < z_floor: continue 
                        in_zone_count = sum((recent_candles['Close'] <= z_ceil) & (recent_candles['Close'] >= z_floor))
                        if in_zone_count >= 2 and (latest_close <= z_ceil and latest_close >= z_floor):
                            status = f"In Zone (Consolidating) ⏳"
                        elif future_data['Low'].min() <= z_ceil:
                            status = "Mitigated/Tested 🟡"
                        elif latest_low <= (z_ceil * 1.03): 
                            status = "Approaching 🚶‍♂️"
                            
                    else: 
                        if future_data['Close'].max() > z_ceil: continue
                        in_zone_count = sum((recent_candles['Close'] <= z_ceil) & (recent_candles['Close'] >= z_floor))
                        if in_zone_count >= 2 and (latest_close <= z_ceil and latest_close >= z_floor):
                            status = f"In Zone (Consolidating) ⏳"
                        elif future_data['High'].max() >= z_floor:
                            status = "Mitigated/Tested 🟡"
                        elif latest_high >= (z_floor * 0.97): 
                            status = "Approaching 🚶‍♂️"

                if not any(filt in status for filt in status_filter):
                    continue
                
                # --- 6. AUTHENTICITY & TRADEABILITY GRADING ---
                is_authentic = base_count <= 3
                # Tradeable = Authentic + Not Mitigated + Zone Risk OK + Pivot Broken
                is_tradeable = is_authentic and ("Mitigated" not in status) and (zone_width_pct <= max_risk) and pivot_broken

                matches.append({
                    "Ticker": ticker.replace('.NS', ''),
                    "Date": df.index[final_legout_idx].strftime('%Y-%m-%d') if hasattr(df.index[final_legout_idx], 'strftime') else str(df.index[final_legout_idx]),
                    "Status": status,
                    "Tradeable 🎯": "✅ Yes" if is_tradeable else "❌ No",
                    "Authentic 💎": "✅ Yes" if is_authentic else "❌ No",
                    "Pivot Broke": "✅" if pivot_broken else "❌",
                    "Risk %": f"{round(zone_width_pct, 1)}%",
                    "Base": base_count,
                    "Legs": consecutive_legs,
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
        res = scan_zones(ticker, timeframe, zone_type, base_limit, min_legout, max_legout, exciting_pct, max_risk_pct, require_pivot, pivot_lookback)
        if res: results.extend(res)
            
    bar.empty()
    
    if results:
        df_display = pd.DataFrame(results)
        df_display['Date'] = pd.to_datetime(df_display['Date'])
        df_display = df_display.sort_values(by="Date", ascending=False)
        df_display['Date'] = df_display['Date'].dt.strftime('%Y-%m-%d')
        
        authentic_count = len(df_display[df_display['Authentic 💎'] == '✅ Yes'])
        tradeable_count = len(df_display[df_display['Tradeable 🎯'] == '✅ Yes'])
        
        col1, col2, col3 = st.columns(3)
        col1.success(f"🎯 Total Zones: **{len(df_display)}**")
        col2.info(f"💎 Authentic Imbalances: **{authentic_count}**")
        col3.warning(f"💼 Ready to Trade: **{tradeable_count}**")
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No patterns found matching these strict criteria.")
