import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

# --- PAGE SETUP ---
st.set_page_config(page_title="Pro S&R Zone Scanner", layout="wide", page_icon="🧱")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #FF9800; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #607D8B; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🧱 Dynamic Support & Resistance Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Multi-timeframe pivot clustering with advanced price action status.</p>', unsafe_allow_html=True)

# --- LOAD SYMBOLS ---
@st.cache_data(ttl=86400)
def load_symbols(index_name):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY Smallcap 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[index_name])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

# --- DATA FETCHING ---
@st.cache_data(show_spinner=False)
def fetch_bulk_data(tickers, timeframe):
    # Determine the lookback period based on Yahoo Finance limits
    if timeframe == '15m':
        period, interval = '60d', '15m'
    elif timeframe == '1h':
        period, interval = '730d', '1h'
    elif timeframe in ['1d', '1wk']:
        period, interval = '5y', timeframe
    else: # 1mo, 3mo, 6mo, 12mo
        period, interval = '10y', '1mo'
        
    data = yf.download(tickers, period=period, interval=interval, group_by='ticker', threads=True, progress=False)
    return data

def resample_data(df, timeframe):
    if timeframe == '3mo': return df.resample('3ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif timeframe == '6mo': return df.resample('6ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif timeframe == '12mo': return df.resample('YE').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    return df

# --- S&R LOGIC ---
def find_zones(df, zone_type, tolerance_pct, min_touches, max_touches, lookback=10):
    if len(df) < lookback * 2: return []
    
    # 1. Find all Pivot Points
    if zone_type == "Support":
        pivots = df.iloc[argrelextrema(df['Low'].values, np.less_equal, order=lookback)[0]]['Low']
    else:
        pivots = df.iloc[argrelextrema(df['High'].values, np.greater_equal, order=lookback)[0]]['High']
        
    # 2. Cluster Pivots into Zones
    zones = []
    for price in pivots:
        matched = False
        for zone in zones:
            # If price is within the tolerance % of the zone center, group it
            if abs(price - zone['center']) / zone['center'] <= (tolerance_pct / 100):
                zone['touches'] += 1
                zone['ceiling'] = max(zone['ceiling'], price)
                zone['floor'] = min(zone['floor'], price)
                zone['center'] = (zone['ceiling'] + zone['floor']) / 2
                matched = True
                break
        if not matched:
            zones.append({'center': price, 'ceiling': price, 'floor': price, 'touches': 1})
            
    # 3. Filter by User Touch Constraints
    return [z for z in zones if min_touches <= z['touches'] <= max_touches]

def evaluate_status(df, zone, zone_type, proximity_pct):
    latest = df.iloc[-1]
    recent_candles = df.tail(3)
    
    close, high, low = latest['Close'], latest['High'], latest['Low']
    body_size = abs(close - latest['Open'])
    candle_range = high - low if high != low else 0.001
    is_strong_candle = (body_size / candle_range) > 0.60 # Strong momentum closing candle
    
    floor, ceiling = zone['floor'], zone['ceiling']
    
    status = None
    
    # Check Breakouts / Breakdowns first
    if zone_type == "Support":
        if close < floor and is_strong_candle:
            return "Support Broken 🚨"
        
        # Is it Inside?
        if floor <= close <= ceiling:
            return "In The Zone ⏳"
            
        # Is it Approaching? (Slightly above the zone)
        if ceiling < low <= ceiling * (1 + (proximity_pct/100)):
            return "Approaching 🚶‍♂️"
            
        # Did it Just React? (Recently touched the zone and bounced up)
        touched_recently = any(recent_candles['Low'] <= ceiling)
        if touched_recently and close > ceiling * (1 + (proximity_pct/100)):
            return "Just Away (Reacted) 🚀"
            
    else: # Resistance
        if close > ceiling and is_strong_candle:
            return "Resistance Broken 🚨"
            
        # Is it Inside?
        if floor <= close <= ceiling:
            return "In The Zone ⏳"
            
        # Is it Approaching? (Slightly below the zone)
        if floor > high >= floor * (1 - (proximity_pct/100)):
            return "Approaching 🚶‍♂️"
            
        # Did it Just React? (Recently touched the zone and dropped)
        touched_recently = any(recent_candles['High'] >= floor)
        if touched_recently and close < floor * (1 - (proximity_pct/100)):
            return "Just Away (Reacted) 🩸"

    return status

# --- SIDEBAR UI ---
with st.sidebar:
    st.header("1. Market Selection")
    index_choice = st.selectbox("Index Universe", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY Midcap 100", "NIFTY Smallcap 250", "NIFTY 500"])
    
    st.divider()
    st.header("2. Strategy Settings")
    timeframe = st.selectbox("Timeframe", ["15m", "1h", "1d", "1wk", "1mo", "3mo", "6mo", "12mo"])
    zone_type = st.radio("Look For", ["Support", "Resistance"])
    
    st.divider()
    st.header("3. Zone Rules")
    touches = st.slider("Required Touches (Min - Max)", 2, 15, (3, 6))
    zone_width = st.slider("Zone Clustering Tolerance (%)", 1.0, 5.0, 2.0, help="How close pivot points need to be to merge into a single zone.")
    prox_dist = st.slider("Approaching Distance (%)", 0.5, 3.0, 1.5, help="Distance from zone to be considered 'Approaching'.")
    
    st.divider()
    st.header("4. Output Filters")
    status_filters = st.multiselect("Show Stocks That Are:", 
                                   ["Approaching 🚶‍♂️", "In The Zone ⏳", "Just Away (Reacted) 🚀", "Just Away (Reacted) 🩸", "Support Broken 🚨", "Resistance Broken 🚨"],
                                   default=["Approaching 🚶‍♂️", "In The Zone ⏳"])
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE SCAN", type="primary", use_container_width=True)

if "Test" in index_choice:
    symbols_to_scan = load_symbols("NIFTY 50")[:10]
else:
    symbols_to_scan = load_symbols(index_choice)

# --- EXECUTION LOGIC ---
if run_scan:
    results = []
    
    with st.spinner(f"Downloading {timeframe} data for {len(symbols_to_scan)} stocks..."):
        raw_data = fetch_bulk_data(symbols_to_scan, timeframe)
    
    bar = st.progress(0, text="Calculating multi-touch S&R Zones...")
    total = len(symbols_to_scan)
    
    for idx, ticker in enumerate(symbols_to_scan):
        bar.progress((idx + 1) / total, text=f"Analyzing {ticker}...")
        
        try:
            if total > 1: df = raw_data[ticker].dropna()
            else: df = raw_data.dropna()
                
            if df.empty: continue
            
            if timeframe in ['3mo', '6mo', '12mo']:
                df = resample_data(df, timeframe)
                
            if len(df) < 20: continue
            
            # Find zones matching touch criteria
            zones = find_zones(df, zone_type, zone_width, touches[0], touches[1])
            
            for zone in zones:
                status = evaluate_status(df, zone, zone_type, prox_dist)
                
                if status and status in status_filters:
                    results.append({
                        "Ticker": ticker.replace('.NS', ''),
                        "Status": status,
                        "Zone Floor": round(zone['floor'], 2),
                        "Zone Ceiling": round(zone['ceiling'], 2),
                        "Total Touches": zone['touches']
                    })
                    
        except Exception:
            pass 
            
    bar.empty()
    
    if results:
        df_display = pd.DataFrame(results)
        
        col1, col2 = st.columns(2)
        col1.success(f"🎯 Scan Complete! Found **{len(df_display)}** setups.")
        col2.info(f"📊 Parameters: {zone_type} | {touches[0]}-{touches[1]} Touches | {timeframe}")
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks found matching these criteria on the {timeframe} timeframe.")
