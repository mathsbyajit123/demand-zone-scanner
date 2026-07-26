import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import math
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SETTINGS
# ==========================================
st.set_page_config(page_title="Ultimate 44 EMA & S/R Scanner", layout="wide")
st.title("🎯 The Ultimate 44 EMA & Zone Scanner")
st.markdown("Multi-timeframe scanner for EMA touches, boring candles, slope angles, and supply/demand zones.")

st.sidebar.header("⚙️ Scanner Settings")

# Sector & Index Options
sector_options = {
    "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
    "Nifty Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
    "Nifty Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
    "Nifty IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
    "Nifty Auto": "https://archives.nseindia.com/content/indices/ind_niftyautolist.csv",
    "Nifty Metal": "https://archives.nseindia.com/content/indices/ind_niftymetallist.csv"
}
selected_sector = st.sidebar.selectbox("Select Sector / Index", list(sector_options.keys()))

timeframe = st.sidebar.selectbox("Timeframe", ["1d", "1wk", "1mo"], index=0)

st.sidebar.subheader("🎯 Scan Condition")
scan_mode = st.sidebar.radio(
    "What are you looking for?",
    (
        "Near 44 EMA (Within 2%)", 
        "Just Touched 44 EMA", 
        "Price Between 20 & 44 EMA"
    )
)

# ==========================================
# 2. DATA FETCHER
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = sector_options.get(sector_name)
    try:
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol']]
    except:
        return []

# ==========================================
# 3. CORE MATHEMATICS & ZONE LOGIC
# ==========================================
def calculate_zones_and_boring(df):
    """Calculates S/R Zones and identifies Boring Candles (Base/Pause Candles)."""
    latest_close = df.iloc[-1]['Close']
    
    # 1. Boring Candles (Body is less than 50% of the total candle range)
    # Check the last 3 candles to see if we are in a boring/basing zone
    boring_count = 0
    for i in range(-3, 0):
        candle = df.iloc[i]
        range_tot = candle['High'] - candle['Low']
        body = abs(candle['Close'] - candle['Open'])
        if range_tot > 0 and (body / range_tot) <= 0.5:
            boring_count += 1

    # 2. Support & Resistance Pivot Clustering
    window = 10
    highs = df['High'].values
    lows = df['Low'].values
    raw_levels = []

    for i in range(window, len(df) - window):
        if max(highs[i-window:i+window+1]) == highs[i]: raw_levels.append(highs[i])
        if min(lows[i-window:i+window+1]) == lows[i]: raw_levels.append(lows[i])

    if not raw_levels:
        return boring_count, "N/A", "N/A"

    raw_levels = sorted(list(set(raw_levels)))
    zones = []
    current_cluster = [raw_levels[0]]

    for level in raw_levels[1:]:
        if level <= current_cluster[0] * 1.02: 
            current_cluster.append(level)
        else:
            zones.append(np.median(current_cluster))
            current_cluster = [level]
    zones.append(np.median(current_cluster))

    supports = [z for z in zones if z < latest_close]
    resistances = [z for z in zones if z > latest_close]
    
    s1 = max(supports) if supports else "N/A"
    r1 = min(resistances) if resistances else "N/A"
    
    return boring_count, s1, r1

def check_setup(df, scan_mode):
    df = df.dropna()
    if len(df) > 0: df = df.iloc[:-1] # Ignore live unclosed candle

    if len(df) < 50: return None
        
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    
    latest = df.iloc[-1]
    close = latest['Close']
    ema20 = latest['EMA_20']
    ema44 = latest['EMA_44']
    
    # 1. Trend Status
    trend = "🟢 Bullish" if ema20 > ema44 else "🔴 Bearish"
    
    # 2. Percentage Distance from 44 EMA (+ is above, - is below)
    pct_dist = ((close - ema44) / ema44) * 100
    
    # 3. EMA Slope / Angle (Rate of change of 44 EMA over last 5 periods)
    past_ema44 = df.iloc[-6]['EMA_44']
    slope_pct = ((ema44 - past_ema44) / past_ema44) * 100
    
    # Convert slope % to a visual angle proxy (rough estimation for UI)
    angle = round(math.degrees(math.atan(slope_pct)), 1)
    angle_str = f"{angle}° {'Up ↗' if angle > 0 else 'Down ↘'}"
    
    # 4. Check Scanner Conditions
    condition_met = False
    
    if scan_mode == "Near 44 EMA (Within 2%)":
        if abs(pct_dist) <= 2.0:
            condition_met = True
            
    elif scan_mode == "Just Touched 44 EMA":
        # Low went below or touched EMA, High went above or touched EMA
        if latest['Low'] <= ema44 and latest['High'] >= ema44:
            condition_met = True
            
    elif scan_mode == "Price Between 20 & 44 EMA":
        # Price is sandwiched between the two moving averages
        if (ema20 >= close >= ema44) or (ema44 >= close >= ema20):
            condition_met = True

    if condition_met:
        boring_qty, s1, r1 = calculate_zones_and_boring(df)
        
        # Format S1 and R1
        s1_fmt = round(s1, 2) if s1 != "N/A" else "N/A"
        r1_fmt = round(r1, 2) if r1 != "N/A" else "N/A"
        
        return {
            "Trend": trend,
            "Price": round(close, 2),
            "Dist from 44EMA": f"{pct_dist:+.2f}%",
            "44EMA Angle": angle_str,
            "Boring Candles": f"{boring_qty} in last 3",
            "Nearest Support": s1_fmt,
            "Nearest Res/Supply": r1_fmt
        }
        
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan {selected_sector}", type="primary"):
    
    ticker_list = get_index_tickers(selected_sector)
    
    if not ticker_list:
        st.error("Failed to load ticker list.")
    else:
        st.info(f"Scanning {len(ticker_list)} stocks in {selected_sector}...")
        
        # Adjust data download period based on timeframe to ensure enough data for 44 EMA
        period = "1y"
        if timeframe == "1wk": period = "2y"
        if timeframe == "1mo": period = "5y"
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                df = yf.Ticker(ticker).history(period=period, interval=timeframe)
                if not df.empty:
                    setup = check_setup(df, scan_mode)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        # Reorder dict for dataframe
                        results.append({
                            "Ticker": setup['Ticker'],
                            "Trend": setup['Trend'],
                            "Price": setup['Price'],
                            "Dist from 44EMA": setup['Dist from 44EMA'],
                            "44EMA Angle": setup['44EMA Angle'],
                            "Nearest Support": setup['Nearest Support'],
                            "Nearest Res/Supply": setup['Nearest Res/Supply'],
                            "Boring Candles": setup['Boring Candles']
                        })
            except:
                pass
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 {selected_sector} Scan Results: {scan_mode} ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"No stocks found matching '{scan_mode}' in {selected_sector} right now.")
