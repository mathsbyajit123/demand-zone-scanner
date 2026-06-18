import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE SETUP ---
st.set_page_config(page_title="Quantitative Footprint Engine", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .main-title { font-size: 36px; font-weight: 800; color: #0F172A; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">📊 Quantitative Institutional Footprint Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Pure Data Matrix. Scans historical block deals & institutional entry floors with zero charts.</p>', unsafe_allow_html=True)

# --- INDEX SYMBOL LOADER ---
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
        return ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "LT.NS"]

# --- QUANT CELL ANALYSIS ENGINE ---
def run_quantitative_scan(df, lookback_window, vol_multiplier, max_prox):
    if df is None or len(df) < 30:
        return None
        
    latest_close = df['Close'].iloc[-1]
    
    # Establish baseline retail volume (20-Day moving average)
    df['Vol_Baseline'] = df['Volume'].rolling(window=20).mean()
    
    # Slice the historical data sheet to look back into past weeks/days
    total_rows = len(df)
    start_idx = max(20, total_rows - lookback_window)
    historical_sheet = df.iloc[start_idx:].copy()
    
    # Algorithmic anomaly search: locate volume expansions
    anomalies = historical_sheet[historical_sheet['Volume'] > (vol_multiplier * historical_sheet['Vol_Baseline'])]
    
    if anomalies.empty:
        return None
        
    # Isolate the day with the absolute largest institutional volume spike
    anchor_day_idx = anomalies['Volume'].idxmax()
    anchor_row = anomalies.loc[anchor_day_idx]
    
    # Calculate Institutional Cost Basis Floor (Typical Price of the block deal day)
    inst_floor = (anchor_row['High'] + anchor_row['Low'] + anchor_row['Close']) / 3
    
    # Measure percentage distance from today's live price to the historical floor
    proximity = ((latest_close - inst_floor) / inst_floor) * 100
    
    # Filter out extended stocks: only keep if sitting within our proximity matrix
    if -0.5 <= proximity <= max_prox:
        actual_multiplier = anchor_row['Volume'] / anchor_row['Vol_Baseline']
        
        # Automatic Risk & Yield Management Math
        stop_loss_val = inst_floor * 0.965  # Hard 3.5% Stop Loss
        target_val = inst_floor * 1.10     # Clear 10% Profit Target
        
        return {
            "floor_price": round(inst_floor, 2),
            "proximity": round(proximity, 2),
            "block_date": anchor_day_idx.strftime('%Y-%m-%d'),
            "vol_strength": round(actual_multiplier, 1),
            "target": round(target_val, 2),
            "stop": round(stop_loss_val, 2)
        }
    return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Core Universe")
    selected_sector = st.selectbox("Market Index", ["Test Group", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Historical Microstructure")
    historical_lookback = st.slider("Historical Lookback Window (Days)", 10, 60, 30, step=5,
                                    help="How many previous days/weeks of historical data to check for block deals.")
    
    volume_surge_target = st.slider("Required Volume Multiplier", 2.0, 5.0, 3.0, step=0.5,
                                    help="Finds historical days where volume was X times greater than normal baseline retail traffic.")
    
    st.divider()
    st.header("3. Live Execution Matrix")
    proximity_buffer = st.slider("Max Proximity Buffer (%)", 0.5, 5.0, 2.0, step=0.1,
                                 help="Filters stocks currently trading within this percentage above the institutional floor.")
    
    st.divider()
    execute_calculation = st.button("🚀 RUN QUANT SCANNER", type="primary", use_container_width=True)

# Process array lists
target_symbols = load_symbols("NIFTY 50")[:6] if "Test" in selected_sector else load_symbols(selected_sector)

# --- LOGIC PIPELINE EXECUTION ---
if execute_calculation:
    compiled_data_sheet = []
    st.info("📊 Processing deep historical data frames...")
    scanner_bar = st.progress(0, text="Initializing data arrays...")
    
    total_tickers = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        clean_ticker = ticker.replace('.NS', '')
        scanner_bar.progress((idx + 1) / total_tickers, text=f"Analyzing data tracks for: {clean_ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            # Fetch daily data (safely reads history across previous days and weeks)
            df_historical = stock.history(period='1y', interval='1d')
            
            if df_historical.empty or len(df_historical) < 30:
                continue
                
            if df_historical.index.tz is not None:
                df_historical.index = df_historical.index.tz_localize(None)
            df_historical = df_historical.ffill().dropna(subset=['Close'])
            
            # Execute mathematical scanning metrics
            q_metrics = run_quantitative_scan(df_historical, historical_lookback, volume_surge_target, proximity_buffer)
            
            if q_metrics:
                compiled_data_sheet.append({
                    "Stock Symbol": clean_ticker,
                    "Live Market Price (₹)": round(df_historical['Close'].iloc[-1], 2),
                    "Institutional Cost Floor (₹)": q_metrics["floor_price"],
                    "Proximity to Floor (%)": f"{q_metrics['proximity']}%",
                    "Block Deal Historical Date": q_metrics["block_date"],
                    "Volume Anomaly Strength": f"{q_metrics['vol_strength']}x Normal",
                    "AUTOMATED BUY ORDER (₹)": q_metrics["floor_price"],
                    "AUTOMATED TARGET SELL (₹)": q_metrics["target"],
                    "AUTOMATED STOP LOSS (₹)": q_metrics["stop"]
                })
                
        except Exception:
            pass
            
    scanner_bar.empty()
    
    # --- RENDER DATA MATRIX SHEET ---
    if compiled_data_sheet:
        final_dataframe = pd.DataFrame(compiled_data_sheet)
        st.success(f"📊 Quantitative Map Complete: Isolated **{len(final_dataframe)}** institutional footprints.")
        st.dataframe(final_dataframe, use_container_width=True, hide_index=True)
        
        # Operational Execution Guide
        st.markdown("""
        ### 📉 How to Execute This Matrix inside Your Broker Terminal (Zero Charts Required):
        1. **The Core Philosophy:** You do not care about chart trends, indicators, or visual patterns. The rows above represent structural pricing anomalies backed by verified cash deployment.
        2. **Order Placement:** Copy the values directly from the **AUTOMATED BUY ORDER (₹)**, **AUTOMATED TARGET SELL (₹)**, and **AUTOMATED STOP LOSS (₹)** columns. 
        3. **Live Execution:** Enter these figures directly into your broker platform (Zerodha, Upstox, etc.) as a **GTT OCO Branded Order**. The moment the live price matches the institutional floor, you are filled. The math handles your exit completely automatically in the background.
        """)
    else:
        st.warning("No historical volume anomalies match your active settings within the current proximity buffer. Try expanding the Proximity Buffer or lowering the Volume Multiplier slider.")
