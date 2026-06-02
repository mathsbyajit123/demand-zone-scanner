import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE SETUP & COLORS ---
st.set_page_config(page_title="TCS Style Zone Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: 800; color: #00C853; margin-bottom: 0px; }
    .sub-title { font-size: 18px; color: #607D8B; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 Pure Demand & Supply Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Auto-calculates Exceptional Marking, Authenticity, and Tradability.</p>', unsafe_allow_html=True)

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
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

# --- SUPER SIMPLE SIDEBAR ---
with st.sidebar:
    st.header("1. Select Stocks")
    scan_mode = st.radio("Universe", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY 500"])
    
    st.divider()
    st.header("2. Strategy")
    timeframe = st.selectbox("Timeframe", ["1d", "1wk", "1mo"])
    zone_type = st.radio("Look For", ["Demand Zone (Buy)", "Supply Zone (Sell)"])
    
    st.divider()
    run_scan = st.button("🚀 SCAN NOW", type="primary", use_container_width=True)

if "NIFTY 50" in scan_mode and "Full" not in scan_mode:
    symbols_to_scan = load_symbols("NIFTY 50")
elif "NIFTY 500" in scan_mode:
    symbols_to_scan = load_symbols("NIFTY 500")
else:
    symbols_to_scan = load_symbols("NIFTY 500")[:10]

# --- CORE ALGORITHM (TCS RULES HARDCODED) ---
def scan_zones(ticker, tf, mode):
    try:
        df = yf.Ticker(ticker).history(period='5y', interval=tf)
        if len(df) < 20: return None
        
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = df['High'] - df['Low']
        
        # Base = Body < 50%. Exciting = Body > 60%.
        df['Is_Base'] = df['Body'] < (0.5 * df['Range'])
        df['Is_Exciting'] = df['Body'] >= (0.6 * df['Range'])
        
        matches = []
        
        for i in range(10, len(df) - 1):
            
            # Step 1: Find an Exciting Leg-Out
            legout_idx = i + 1
            if mode == "Demand Zone (Buy)":
                valid_legout = (df['Close'].iloc[legout_idx] > df['Open'].iloc[legout_idx]) and df['Is_Exciting'].iloc[legout_idx]
            else:
                valid_legout = (df['Close'].iloc[legout_idx] < df['Open'].iloc[legout_idx]) and df['Is_Exciting'].iloc[legout_idx]
                
            if not valid_legout: continue
            
            # Step 2: Ensure Authenticity (Tight Base, Max 3 Candles)
            base_count = 0
            for check_idx in range(i, i - 4, -1):
                if df['Is_Base'].iloc[check_idx]: base_count += 1
                else: break
                
            if 1 <= base_count <= 3:
                leg_in_idx = i - base_count
                
                # Step 3: Exceptional Marking (Checking Leg-In/Out Wicks)
                base_data = df.iloc[i-base_count+1 : i+1]
                legin_data = df.iloc[leg_in_idx]
                legout_data = df.iloc[legout_idx]
                
                if mode == "Demand Zone (Buy)":
                    pattern = "RBR" if df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx] else "DBR"
                    # Proximal = Highest body of the base
                    proximal = max(base_data['Open'].max(), base_data['Close'].max())
                    # Distal = Lowest wick of the ENTIRE formation (Exception check)
                    distal = min(legin_data['Low'], base_data['Low'].min(), legout_data['Low'])
                else:
                    pattern = "DBD" if df['Close'].iloc[leg_in_idx] < df['Open'].iloc[leg_in_idx] else "RBD"
                    # Proximal = Lowest body of the base
                    proximal = min(base_data['Open'].min(), base_data['Close'].min())
                    # Distal = Highest wick of the ENTIRE formation (Exception check)
                    distal = max(legin_data['High'], base_data['High'].max(), legout_data['High'])
                
                # Step 4: Tradability (Must break the previous turning point)
                lookback_start = max(0, leg_in_idx - 10)
                if mode == "Demand Zone (Buy)":
                    pivot_high = df['High'].iloc[lookback_start : leg_in_idx].max()
                    if df['Close'].iloc[legout_idx] <= pivot_high: continue # Failed to break structure
                else:
                    pivot_low = df['Low'].iloc[lookback_start : leg_in_idx].min()
                    if df['Close'].iloc[legout_idx] >= pivot_low: continue # Failed to break structure
                    
                # Step 5: Ignore Tested/Dead Zones
                future_data = df.iloc[legout_idx + 1 :]
                if not future_data.empty:
                    if mode == "Demand Zone (Buy)" and future_data['Low'].min() <= proximal:
                        continue # Price already tested this demand, ignore it.
                    elif mode == "Supply Zone (Sell)" and future_data['High'].max() >= proximal:
                        continue # Price already tested this supply, ignore it.
                
                # If we get here, it is Authentic, Tradable, Fresh, and correctly marked!
                matches.append({
                    "Ticker": ticker.replace('.NS', ''),
                    "Formation Date": df.index[legout_idx].strftime('%Y-%m-%d'),
                    "Pattern": pattern,
                    "Proximal (Entry)": round(proximal, 2),
                    "Distal (Stop Loss)": round(distal, 2),
                    "Status": "Fresh & Ready 🟢"
                })
        return matches
    except Exception:
        return None

# --- RUN BUTTON LOGIC ---
if run_scan:
    results = []
    bar = st.progress(0, text="Initializing Scanner...")
    
    for idx, ticker in enumerate(symbols_to_scan):
        bar.progress((idx + 1) / len(symbols_to_scan), text=f"Scanning {ticker}...")
        res = scan_zones(ticker, timeframe, zone_type)
        if res: results.extend(res)
            
    bar.empty()
    
    if results:
        df_display = pd.DataFrame(results)
        df_display = df_display.sort_values(by="Formation Date", ascending=False)
        st.success(f"🎯 Found **{len(df_display)}** Highly Authentic & Tradable Zones.")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No patterns found. The market did not create any clean setups.")
