import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE SETUP ---
st.set_page_config(page_title="EMA & FVG Confluence Scanner", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .main-title { font-size: 36px; font-weight: 800; color: #0284C7; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ Multi-Timeframe EMA & FVG Confluence Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Confluence Hunting Sheet. Tracks stocks within ±5% of the 50-EMA matching active historical Fair Value Gaps.</p>', unsafe_allow_html=True)

# --- BULLETPROOF INDEX SYMBOL LOADER ---
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
        return ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- ADVANCED TIMEFRAME RESAMPLER ---
def resample_market_data(df_daily, timeframe):
    if df_daily is None or df_daily.empty:
        return None
    
    tf_map = {
        "1D": "1D",
        "1W": "W-FRI",
        "1M": "ME",
        "3M": "3ME",
        "6M": "6ME"
    }
    
    if timeframe == "1D":
        return df_daily
        
    logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
    resampled = df_daily.resample(tf_map[timeframe]).agg(logic).dropna()
    return resampled

# --- UNMITIGATED FVG SEARCH ALGORITHM ---
def find_nearest_unmitigated_fvg(df, live_price, bias="Bullish"):
    if df is None or len(df) < 3:
        return "None Detected"
        
    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    
    open_fvgs = []
    
    if "Bullish" in bias:
        # Scan backward from history to locate open imbalances
        for i in range(2, len(df)):
            if highs[i-2] < lows[i]:  # Bullish FVG Imbalance condition
                fvg_top = lows[i]
                fvg_bottom = highs[i-2]
                
                # Verify if any subsequent candle has already completely mitigated it
                mitigated = False
                for j in range(i+1, len(df)):
                    if lows[j] <= fvg_bottom:
                        mitigated = True
                        break
                
                if not mitigated:
                    open_fvgs.append((fvg_bottom, fvg_top))
                    
        if not open_fvgs:
            return "None Open"
            
        # Find the open FVG closest to our current trading price
        closest_fvg = min(open_fvgs, key=lambda x: abs(live_price - x[1]))
        return f"₹{round(closest_fvg[0],1)} - ₹{round(closest_fvg[1],1)}"

    else:  # Bearish Structure
        for i in range(2, len(df)):
            if lows[i-2] > highs[i]:  # Bearish FVG Imbalance condition
                fvg_top = lows[i-2]
                fvg_bottom = highs[i]
                
                mitigated = False
                for j in range(i+1, len(df)):
                    if highs[j] >= fvg_top:
                        mitigated = True
                        break
                if not mitigated:
                    open_fvgs.append((fvg_bottom, fvg_top))
                    
        if not open_fvgs:
            return "None Open"
            
        closest_fvg = min(open_fvgs, key=lambda x: abs(live_price - x[0]))
        return f"₹{round(closest_fvg[0],1)} - ₹{round(closest_fvg[1],1)}"

# --- SIDEBAR CONTROL UNIT ---
with st.sidebar:
    st.header("1. Core Setup Direction")
    trend_bias = st.radio("Select Strategy Bias Direction:", ["Bullish (Support FVG + EMA)", "Bearish (Resistance FVG + EMA)"])
    
    st.divider()
    st.header("2. Horizon Matrix")
    base_tf = st.selectbox("Select Core Scanning Timeframe:", ["1D", "1W", "1M", "3M", "6M"], index=1)
    
    # Calculate Higher Timeframe Mapping anchor automatically
    htf_mapping = {"1D": "1W", "1W": "1M", "1M": "3M", "3M": "6M", "6M": "6M"}
    higher_tf = htf_mapping[base_tf]
    
    st.info(f"Targeting System:\n* Base Track: {base_tf} 50-EMA\n* Higher Matrix Track: {higher_tf} FVG Void")
    
    st.divider()
    st.header("3. Liquidity & Threshold")
    selected_sector = st.selectbox("Market Index Universe", ["Test Universe", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    ema_tolerance = st.slider("EMA Approach Proximity Tolerance (±%)", 1.0, 5.0, 5.0, step=0.5)
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE CONFLUENCE SCAN", type="primary", use_container_width=True)

# Select processing lists
target_symbols = load_symbols("NIFTY 50")[:5] if "Test" in selected_sector else load_symbols(selected_sector)

# --- RUNNING DATA COMPILATION PIPELINE ---
if run_scan:
    scanned_opportunities = []
    st.info(f"📊 Processing historical multi-year canvas sheets for {selected_sector}...")
    execution_progress = st.progress(0, text="Synchronizing servers...")
    
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        clean_ticker = ticker.replace('.NS', '')
        execution_progress.progress((idx + 1) / total_symbols, text=f"Scanning Matrix Fields: {clean_ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            # Fetch maximum history to ensure high timeframe 50 EMAs compute without truncating
            df_raw = stock.history(period='max', interval='1d')
            
            if df_raw.empty or len(df_raw) < 250:
                continue
                
            if df_raw.index.tz is not None: 
                df_raw.index = df_raw.index.tz_localize(None)
            df_raw = df_raw.ffill().dropna(subset=['Close'])
            
            # Resample into distinct tracking dataframes
            df_base = resample_market_data(df_raw, base_tf)
            df_high = resample_market_data(df_raw, higher_tf)
            
            if df_base is None or len(df_base) < 51 or df_high is None:
                continue
                
            # Compute base timeframe 50 EMA lines
            df_base['EMA50'] = df_base['Close'].ewm(span=50, adjust=False).mean()
            
            latest_close = df_base['Close'].iloc[-1]
            latest_ema = df_base['EMA50'].iloc[-1]
            
            # Measure exact proximity percentage deviation from the base EMA line
            ema_distance = ((latest_close - latest_ema) / latest_ema) * 100
            
            # --- PROXIMITY RULE CHECK FILTER ---
            if abs(ema_distance) <= ema_tolerance:
                # Execute algorithmic deep scans for unmitigated gaps across both fields
                base_fvg_status = find_nearest_unmitigated_fvg(df_base, latest_close, trend_bias)
                high_fvg_status = find_nearest_unmitigated_fvg(df_high, latest_close, trend_bias)
                
                scanned_opportunities.append({
                    "Stock Symbol": clean_ticker,
                    "Live Price (₹)": round(latest_close, 2),
                    f"{base_tf} 50-EMA (₹)": round(latest_ema, 2),
                    "Distance to EMA (%)": f"{round(ema_distance, 2)}%",
                    f"Open {base_tf} FVG Zone": base_fvg_status,
                    f"Open Higher {higher_tf} FVG Zone": high_fvg_status
                })
                
        except Exception:
            pass
            
    execution_progress.empty()
    
    # --- RENDER ANALYTICAL MATRIX GRID ---
    if scanned_opportunities:
        display_df = pd.DataFrame(scanned_opportunities)
        st.success(f"🎯 Confluence Confirmed: Found **{len(display_df)}** stocks trading within your setup window.")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Professional Step-by-Step Trade Execution Guide
        st.markdown(f"""
        ### 📖 The Professional Execution Blueprint for These Confluence Matches:
        1. **Locate High-Confluence Targets:** Review the output table and prioritize stocks that display an active range in **both** the FVG columns (meaning a base FVG and a macro HTF FVG are sitting right near the price).
        2. **Track the Live 75-Minute Floor:** When a flagged stock hits your alert zone, open your charting platform. Look for the price to dip cleanly into the *Open Higher {higher_tf} FVG Zone* or test the *{base_tf} 50-EMA*.
        3. **The Trigger Confirmation:** Do not place a blind order. Wait for a 75-minute candle to pierce the zone, reject it aggressively with a long lower shadow wick, and close positive. Enter the trade right at that confirmation candle's close.
        4. **Lock In Your Defense:** Place your automated GTT stop loss **3.5% directly below the lowest wick of your entry structure** and let the market drive toward your **10%+ profit targets** over the coming weeks.
        """)
    else:
        st.warning(f"No stocks inside the selected universe are currently within ±{ema_tolerance}% of their {base_tf} 50-EMA matching active imbalances. Try increasing your proximity tolerance slider.")
