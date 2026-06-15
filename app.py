import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

# --- PAGE SETUP ---
st.set_page_config(page_title="Pure Zone Engine", layout="wide", page_icon="🧱")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #FF9800; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #607D8B; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🧱 Pure S/R & Demand/Supply Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Maps pure structural pivot clusters and institutional imbalance origin zones.</p>', unsafe_allow_html=True)

# --- MARKET SYMBOLS ---
@st.cache_data(ttl=86400)
def load_symbols(index_name):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[index_name])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- DATA PIPELINE & 75m RESAMPLER ---
@st.cache_data(show_spinner=False)
def fetch_raw_data(tickers, tf):
    if tf in ['15m', '75m']: 
        period, interval = '60d', '15m'  # We fetch 15m for 75m to build custom candles
    elif tf == '1h': period, interval = '730d', '1h'
    elif tf == '1d': period, interval = '5y', '1d'
    elif tf == '1wk': period, interval = '10y', '1wk'
    elif tf == '1mo': period, interval = '20y', '1mo'
    
    return yf.download(tickers, period=period, interval=interval, group_by='ticker', threads=True, progress=False)

def resample_to_75m(df):
    if df.empty: return df
    # Resample 15m data into 75m blocks
    df_75 = df.resample('75min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return df_75

# --- THE PURE ZONE ENGINE ---
def map_institutional_zones(df, zone_mode, max_zone_w):
    if len(df) < 50: return None

    latest_close = df.iloc[-1]['Close']
    latest_high = df.iloc[-1]['High']
    latest_low = df.iloc[-1]['Low']

    active_zones = []

    # ==========================================
    # ENGINE A: STRUCTURAL SUPPORT & RESISTANCE
    # ==========================================
    if "Support/Resistance" in zone_mode:
        peaks = df.iloc[argrelextrema(df['High'].values, np.greater_equal, order=5)[0]]['High'].values
        valleys = df.iloc[argrelextrema(df['Low'].values, np.less_equal, order=5)[0]]['Low'].values
        
        all_swings = np.sort(np.concatenate((peaks, valleys)))
        
        if len(all_swings) > 0:
            current_cluster = [all_swings[0]]
            for i in range(1, len(all_swings)):
                if (all_swings[i] - current_cluster[0]) / current_cluster[0] <= (max_zone_w / 100.0):
                    current_cluster.append(all_swings[i])
                else:
                    if len(current_cluster) >= 3: # Must have 3 touches to be valid S/R
                        active_zones.append({
                            'type': 'Support' if latest_close > max(current_cluster) else 'Resistance',
                            'floor': min(current_cluster), 
                            'ceiling': max(current_cluster),
                            'strength': len(current_cluster)
                        })
                    current_cluster = [all_swings[i]]
            if len(current_cluster) >= 3:
                active_zones.append({
                    'type': 'Support' if latest_close > max(current_cluster) else 'Resistance',
                    'floor': min(current_cluster), 'ceiling': max(current_cluster), 'strength': len(current_cluster)
                })

    # ==========================================
    # ENGINE B: SUPPLY & DEMAND (ORDER BLOCKS)
    # ==========================================
    if "Demand/Supply" in zone_mode:
        # Calculate moving average of candle bodies to spot "Imbalance/Explosive" moves
        df['Body'] = abs(df['Close'] - df['Open'])
        df['Avg_Body'] = df['Body'].rolling(window=20).mean()
        
        for i in range(2, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i-1]
            
            is_explosive_green = (curr['Close'] > curr['Open']) and (curr['Body'] > curr['Avg_Body'] * 2)
            is_explosive_red = (curr['Close'] < curr['Open']) and (curr['Body'] > curr['Avg_Body'] * 2)
            is_base_candle = (prev['Body'] < prev['Avg_Body'] * 0.8) # Tight consolidation before the move
            
            # Rally-Base-Rally or Drop-Base-Rally (DEMAND)
            if is_explosive_green and is_base_candle:
                active_zones.append({
                    'type': 'Demand Zone (Order Block)',
                    'floor': prev['Low'],
                    'ceiling': prev['High'],
                    'strength': 'Institutional Imbalance'
                })
                
            # Rally-Base-Drop or Drop-Base-Drop (SUPPLY)
            elif is_explosive_red and is_base_candle:
                active_zones.append({
                    'type': 'Supply Zone (Order Block)',
                    'floor': prev['Low'],
                    'ceiling': prev['High'],
                    'strength': 'Institutional Imbalance'
                })

    # ==========================================
    # EVALUATE LIVE PRICE INTERACTION
    # ==========================================
    for zone in active_zones:
        f, c = zone['floor'], zone['ceiling']
        z_type = zone['type']
        
        # Is live price inside or deeply testing the zone right now?
        if f * 0.99 <= latest_low <= c * 1.01 or f * 0.99 <= latest_high <= c * 1.01:
            
            if 'Demand' in z_type or 'Support' in z_type:
                # Price is at a floor
                if latest_close >= f:
                    return {"signal": f"Testing {z_type} 🟢", "zone": f"₹{round(f,1)} - ₹{round(c,1)}", "info": zone['strength']}
            
            elif 'Supply' in z_type or 'Resistance' in z_type:
                # Price is at a ceiling
                if latest_close <= c:
                    return {"signal": f"Testing {z_type} 🔴", "zone": f"₹{round(f,1)} - ₹{round(c,1)}", "info": zone['strength']}

    return None

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (10 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Execution Timeframe")
    selected_tf = st.selectbox("Timeframe Map", ["15m", "75m", "1h", "1d", "1wk", "1mo"])
    if selected_tf == '75m':
        st.caption("⚙️ *Custom Engine: Resampling 15m blocks into precise 75m institutional structures.*")
    
    st.divider()
    st.header("3. Zone Methodology")
    execution_bias = st.selectbox("Map Type:", [
        "Support/Resistance (Pivot Clusters)", 
        "Demand/Supply (Imbalance Bases)",
        "Both (Hybrid Mode)"
    ])
    
    st.divider()
    max_w = st.slider("Max S/R Zone Width (%)", 0.5, 8.0, 3.0, help="Only applies to S/R Pivot clustering.")
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE ZONE SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:10] if "Test" in selected_sector else load_symbols(selected_sector)

# --- PROCESSING SYSTEM ---
if run_scan:
    scanned_opportunities = []
    
    with st.spinner(f"Downloading historical datasets..."):
        raw_market_data = fetch_raw_data(target_symbols, selected_tf)
        
    execution_progress = st.progress(0, text="Mapping institutional bases and structural clusters...")
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing order blocks for {ticker}...")
        
        try:
            if total_symbols > 1: df = raw_market_data[ticker].copy()
            else: df = raw_market_data.copy()
            
            # Apply the custom 75-minute resampler if selected
            if selected_tf == '75m':
                df = resample_to_75m(df)
                
            df = df.dropna()
            
            if df.empty: continue
                
            outcome = map_institutional_zones(df, execution_bias, max_w)
            
            if outcome:
                scanned_opportunities.append({
                    "Ticker Symbol": ticker.replace('.NS', ''),
                    "Status": outcome["signal"],
                    "Zone Boundaries": outcome["zone"],
                    "Validation Strength": outcome["info"],
                    "Live Price": round(df.iloc[-1]['Close'], 2)
                })
        except Exception:
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        st.success(f"🎯 Analysis Complete! Uncovered **{len(display_dataframe)}** active zone interactions.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No assets are currently inside your defined {selected_tf} structural zones right now.")
