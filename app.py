import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE SETUP ---
st.set_page_config(page_title="Institutional Setup Scanner", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #00C853; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #607D8B; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📈 Advanced Drop-Base-Rally Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for Authentic Institutional Demand & Supply Zones across 500+ stocks.</p>', unsafe_allow_html=True)

# --- LOAD SYMBOLS ---
@st.cache_data(ttl=86400)
def load_symbols(index_name):
    try:
        if index_name == "NIFTY 50":
            url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
        else:
            url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        df = pd.read_csv(url)
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        # Fallback list if NSE server blocks the request
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "TATAMOTORS.NS"]

# --- FAST BULK DATA DOWNLOAD ---
@st.cache_data(show_spinner=False)
def fetch_bulk_data(tickers, timeframe):
    # For higher timeframes, we download monthly data and build the candles ourselves
    if timeframe in ['1mo', '3mo', '6mo', '12mo']:
        data = yf.download(tickers, period='10y', interval='1mo', group_by='ticker', threads=True, progress=False)
    elif timeframe == '1wk':
        data = yf.download(tickers, period='5y', interval='1wk', group_by='ticker', threads=True, progress=False)
    else: # 1d
        data = yf.download(tickers, period='2y', interval='1d', group_by='ticker', threads=True, progress=False)
    return data

def resample_data(df, timeframe):
    if timeframe == '3mo':
        return df.resample('3ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif timeframe == '6mo':
        return df.resample('6ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif timeframe == '12mo':
        return df.resample('YE').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    return df

# --- SIDEBAR UI ---
with st.sidebar:
    st.header("1. Select Market")
    scan_mode = st.radio("Universe", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY 500 (504 Stocks)"])
    
    st.divider()
    st.header("2. Strategy Settings")
    timeframe = st.selectbox("Timeframe", ["1d", "1wk", "1mo", "3mo", "6mo", "12mo"])
    zone_type = st.radio("Look For", ["Demand Zone (Buy)", "Supply Zone (Sell)"])
    
    st.divider()
    run_scan = st.button("🚀 SCAN MARKET NOW", type="primary", use_container_width=True)

# Load correct ticker list
if "NIFTY 50" in scan_mode and "500" not in scan_mode:
    symbols_to_scan = load_symbols("NIFTY 50")
elif "NIFTY 500" in scan_mode:
    symbols_to_scan = load_symbols("NIFTY 500")
else:
    symbols_to_scan = load_symbols("NIFTY 500")[:10]

# --- CORE ALGORITHM ---
def process_stock(df, ticker, mode):
    df['Body'] = (df['Close'] - df['Open']).abs()
    df['Range'] = df['High'] - df['Low']
    
    # Base Candle: Body is less than 50% of the total range (like the Doji in your image)
    df['Is_Base'] = df['Body'] < (0.5 * df['Range'])
    # Exciting Candle: Body is massive, greater than 60% of the range
    df['Is_Exciting'] = df['Body'] >= (0.6 * df['Range'])
    
    matches = []
    
    for i in range(10, len(df) - 1):
        legout_idx = i + 1
        
        # 1. Check if we have an Explosive Leg-Out
        if mode == "Demand Zone (Buy)":
            valid_legout = (df['Close'].iloc[legout_idx] > df['Open'].iloc[legout_idx]) and df['Is_Exciting'].iloc[legout_idx]
        else:
            valid_legout = (df['Close'].iloc[legout_idx] < df['Open'].iloc[legout_idx]) and df['Is_Exciting'].iloc[legout_idx]
            
        if not valid_legout: continue
        
        # 2. Check for 1 to 3 tight Base Candles
        base_count = 0
        for check_idx in range(i, i - 4, -1):
            if df['Is_Base'].iloc[check_idx]: base_count += 1
            else: break
            
        if 1 <= base_count <= 3:
            leg_in_idx = i - base_count
            
            base_data = df.iloc[i-base_count+1 : i+1]
            legin_data = df.iloc[leg_in_idx]
            legout_data = df.iloc[legout_idx]
            
            # 3. Identify Pattern and Apply Exceptional Marking (Lowest Wick)
            if mode == "Demand Zone (Buy)":
                leg_in_drop = df['Close'].iloc[leg_in_idx] < df['Open'].iloc[leg_in_idx]
                pattern = "Drop-Base-Rally (DBR) 🚀" if leg_in_drop else "Rally-Base-Rally (RBR) 🚀"
                
                proximal = max(base_data['Open'].max(), base_data['Close'].max())
                distal = min(legin_data['Low'], base_data['Low'].min(), legout_data['Low'])
                
                # Check for Break of Structure (Pivot Break)
                pivot_high = df['High'].iloc[max(0, leg_in_idx - 10) : leg_in_idx].max()
                if df['Close'].iloc[legout_idx] <= pivot_high: continue
                
            else: # Supply Zone
                leg_in_rally = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
                pattern = "Rally-Base-Drop (RBD) 🩸" if leg_in_rally else "Drop-Base-Drop (DBD) 🩸"
                
                proximal = min(base_data['Open'].min(), base_data['Close'].min())
                distal = max(legin_data['High'], base_data['High'].max(), legout_data['High'])
                
                # Check for Break of Structure (Pivot Break)
                pivot_low = df['Low'].iloc[max(0, leg_in_idx - 10) : leg_in_idx].min()
                if df['Close'].iloc[legout_idx] >= pivot_low: continue

            # 4. Remove Dead/Tested Zones
            future_data = df.iloc[legout_idx + 1 :]
            if not future_data.empty:
                if mode == "Demand Zone (Buy)" and future_data['Low'].min() <= proximal: continue
                elif mode == "Supply Zone (Sell)" and future_data['High'].max() >= proximal: continue
            
            matches.append({
                "Ticker": ticker.replace('.NS', ''),
                "Date Formed": df.index[legout_idx].strftime('%Y-%m-%d'),
                "Pattern": pattern,
                "Base Candles": base_count,
                "Entry (Proximal)": round(proximal, 2),
                "SL (Distal)": round(distal, 2),
                "Status": "Fresh 🟢"
            })
    return matches

# --- RUN EXECUTION ---
if run_scan:
    results = []
    
    with st.spinner(f"Downloading bulk data for {len(symbols_to_scan)} stocks... Please wait 15-30 seconds."):
        raw_data = fetch_bulk_data(symbols_to_scan, timeframe)
    
    bar = st.progress(0, text="Analyzing price action...")
    total = len(symbols_to_scan)
    
    for idx, ticker in enumerate(symbols_to_scan):
        bar.progress((idx + 1) / total, text=f"Scanning {ticker}...")
        
        try:
            # Handle yfinance multi-index structure
            if total > 1: df = raw_data[ticker].dropna()
            else: df = raw_data.dropna()
                
            if df.empty: continue
            
            # Resample for higher timeframes
            df = resample_data(df, timeframe)
            if len(df) < 15: continue
            
            res = process_stock(df, ticker, zone_type)
            if res: results.extend(res)
                
        except Exception:
            pass # Skip silently on missing data
            
    bar.empty()
    
    if results:
        df_display = pd.DataFrame(results)
        df_display = df_display.sort_values(by="Date Formed", ascending=False)
        st.success(f"🎯 Scan Complete! Found **{len(df_display)}** setups perfectly matching your criteria.")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning("No patterns found. The market hasn't formed this specific setup recently.")
