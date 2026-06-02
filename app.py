import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

# --- PAGE SETUP ---
st.set_page_config(page_title="Human-Eye Price Action Scanner", layout="wide", page_icon="👁️")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #E91E63; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #607D8B; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">👁️ Human-Eye Price Action Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Uses Pivot Clustering to see zones exactly like a human trader.</p>', unsafe_allow_html=True)

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
        return ["RELIANCE.NS", "TCS.NS", "CIPLA.NS", "INFY.NS", "ICICIBANK.NS"]

# --- DATA FETCHING ---
@st.cache_data(show_spinner=False)
def fetch_bulk_data(tickers, timeframe):
    if timeframe == '15m': period, interval = '60d', '15m'
    elif timeframe == '1h': period, interval = '730d', '1h'
    elif timeframe in ['1d', '1wk']: period, interval = '5y', timeframe
    else: period, interval = '10y', '1mo'
        
    data = yf.download(tickers, period=period, interval=interval, group_by='ticker', threads=True, progress=False)
    return data

def resample_data(df, timeframe):
    if timeframe == '3mo': return df.resample('3ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif timeframe == '6mo': return df.resample('6ME').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif timeframe == '12mo': return df.resample('YE').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    return df

# --- UI SETTINGS ---
with st.sidebar:
    st.header("1. Choose Market")
    index_choice = st.selectbox("Index", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY Midcap 100", "NIFTY Smallcap 250", "NIFTY 500"])
    
    st.divider()
    st.header("2. Choose Timeframe")
    timeframe = st.selectbox("Timeframe", ["15m", "1h", "1d", "1wk", "1mo", "3mo", "6mo", "12mo"])
    
    st.divider()
    st.header("3. What are we hunting?")
    hunt_type = st.radio("Select Setup:", [
        "Resistance becomes Support (Role Reversal)",
        "Bounce off Heavy Support Zone",
        "Rejection at Heavy Resistance Zone",
        "Strong Zone Breakout (Up)",
        "Strong Zone Breakdown (Down)",
        "Trendline Bounce (Higher Lows)"
    ])
    
    st.divider()
    zone_thickness = st.slider("Zone Thickness Tolerance (%)", 0.5, 5.0, 2.0, help="Groups swing highs/lows that are within this % of each other into a single thick zone.")
    run_scan = st.button("🚀 EXECUTE SCAN", type="primary", use_container_width=True)

if "Test" in index_choice:
    symbols_to_scan = load_symbols("NIFTY 50")[:10]
else:
    symbols_to_scan = load_symbols(index_choice)

# --- CORE LOGIC (PIVOT CLUSTERING) ---
def analyze_price_action(df, hunt, thickness_pct):
    df_recent = df.tail(200)
    if len(df_recent) < 50: return None
    
    latest_close = df_recent.iloc[-1]['Close']
    latest_high = df_recent.iloc[-1]['High']
    latest_low = df_recent.iloc[-1]['Low']
    prev_close = df_recent.iloc[-2]['Close']
    
    # Identify Momentum
    body = abs(latest_close - df_recent.iloc[-1]['Open'])
    rng = latest_high - latest_low if latest_high != latest_low else 0.001
    is_strong_green = (latest_close > df_recent.iloc[-1]['Open']) and (body / rng > 0.5)
    is_strong_red = (latest_close < df_recent.iloc[-1]['Open']) and (body / rng > 0.5)
    
    # 1. Find all structural Swing Highs and Swing Lows
    peaks = df_recent.iloc[argrelextrema(df_recent['High'].values, np.greater_equal, order=5)[0]]['High'].values
    valleys = df_recent.iloc[argrelextrema(df_recent['Low'].values, np.less_equal, order=5)[0]]['Low'].values
    
    all_pivots = np.sort(np.concatenate((peaks, valleys)))
    if len(all_pivots) == 0: return None
    
    # 2. Cluster Pivots into Zones
    zones = []
    current_zone = [all_pivots[0]]
    
    for i in range(1, len(all_pivots)):
        # If the pivot is within the thickness % of the start of the zone, group it
        if (all_pivots[i] - current_zone[0]) / current_zone[0] <= (thickness_pct / 100.0):
            current_zone.append(all_pivots[i])
        else:
            # Must have at least 3 touches to be considered a major zone
            if len(current_zone) >= 3:
                zones.append({'floor': min(current_zone), 'ceiling': max(current_zone), 'center': sum(current_zone)/len(current_zone)})
            current_zone = [all_pivots[i]]
            
    if len(current_zone) >= 3:
        zones.append({'floor': min(current_zone), 'ceiling': max(current_zone), 'center': sum(current_zone)/len(current_zone)})

    if not zones: return None
    
    # 3. Evaluate the setup
    for zone in zones:
        z_floor = zone['floor']
        z_ceil = zone['ceiling']
        z_center = zone['center']
        
        # Count peak touches vs valley touches in this zone
        zone_peaks = len([p for p in peaks if z_floor * 0.99 <= p <= z_ceil * 1.01])
        zone_valleys = len([v for v in valleys if z_floor * 0.99 <= v <= z_ceil * 1.01])
        
        if hunt == "Resistance becomes Support (Role Reversal)":
            if latest_close > z_ceil:
                # Look at the last 5 candles. Did the wick dip into or near the zone ceiling?
                recent_low = df_recent.tail(5)['Low'].min()
                if z_floor * 0.98 <= recent_low <= z_ceil * 1.02: # 2% buffer for front-running
                    # Was it heavily acting as Resistance before the breakout?
                    if zone_peaks >= 2:
                        return f"Role Reversal at ₹{round(z_center, 2)} 🔄"
                        
        elif hunt == "Bounce off Heavy Support Zone":
            if latest_close > z_ceil and latest_low <= (z_ceil * 1.02) and is_strong_green:
                if zone_valleys >= 2:
                    return f"Support Bounce at ₹{round(z_center, 2)} 🟢"
                
        elif hunt == "Rejection at Heavy Resistance Zone":
            if latest_close < z_floor and latest_high >= (z_floor * 0.98) and is_strong_red:
                if zone_peaks >= 2:
                    return f"Resistance Rejection at ₹{round(z_center, 2)} 🔴"
                
        elif hunt == "Strong Zone Breakout (Up)":
            if prev_close < z_floor and latest_close > z_ceil and is_strong_green:
                if zone_peaks >= 2:
                    return f"Breakout Above ₹{round(z_ceil, 2)} 🚀"
                
        elif hunt == "Strong Zone Breakdown (Down)":
            if prev_close > z_ceil and latest_close < z_floor and is_strong_red:
                if zone_valleys >= 2:
                    return f"Breakdown Below ₹{round(z_floor, 2)} 🩸"

    if hunt == "Trendline Bounce (Higher Lows)":
        df_recent['SMA_20'] = df_recent['Close'].rolling(20).mean()
        if len(df_recent) > 5:
            l1, l2, l3 = df_recent.iloc[-3]['Low'], df_recent.iloc[-2]['Low'], df_recent.iloc[-1]['Low']
            sma20 = df_recent.iloc[-1]['SMA_20']
            
            if l3 > l2 > l1 and (abs(latest_low - sma20) / sma20 < 0.015) and is_strong_green:
                return "Trendline / Dynamic Support Bounce 📈"

    return None

# --- EXECUTION LOGIC ---
if run_scan:
    results = []
    
    with st.spinner(f"Downloading {timeframe} data for {len(symbols_to_scan)} stocks..."):
        raw_data = fetch_bulk_data(symbols_to_scan, timeframe)
    
    bar = st.progress(0, text=f"Hunting for {hunt_type}...")
    total = len(symbols_to_scan)
    
    for idx, ticker in enumerate(symbols_to_scan):
        bar.progress((idx + 1) / total, text=f"Analyzing {ticker}...")
        
        try:
            if total > 1: df = raw_data[ticker].dropna()
            else: df = raw_data.dropna()
                
            if df.empty: continue
            
            if timeframe in ['3mo', '6mo', '12mo']:
                df = resample_data(df, timeframe)
                
            status = analyze_price_action(df, hunt_type, zone_thickness)
            
            if status:
                results.append({
                    "Ticker": ticker.replace('.NS', ''),
                    "Setup Found": status,
                    "Current Price": round(df.iloc[-1]['Close'], 2)
                })
                    
        except Exception:
            pass 
            
    bar.empty()
    
    if results:
        df_display = pd.DataFrame(results)
        st.success(f"🎯 Scan Complete! Found **{len(df_display)}** setups.")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks found matching '{hunt_type}' on the {timeframe} timeframe.")
