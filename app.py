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

st.markdown('<p class="main-title">👁️ Price Action & Trendline Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for Horizontal Zones, Role Reversals, and True Diagonal Trendline Breakouts.</p>', unsafe_allow_html=True)

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
    
    st.markdown("**--- HORIZONTAL ZONES ---**")
    hunt_horizontal = st.radio("Horizontal Setups:", [
        "None",
        "Resistance becomes Support (Role Reversal)",
        "Bounce off Heavy Support Zone",
        "Rejection at Heavy Resistance Zone",
        "Horizontal Breakout (Smashing Up)",
        "Horizontal Breakdown (Smashing Down)"
    ])
    
    st.markdown("**--- DIAGONAL TRENDLINES ---**")
    hunt_trendline = st.radio("Trendline Setups:", [
        "None",
        "Dynamic Trendline Support (Bounce)",
        "Dynamic Trendline Resistance (Rejection)",
        "Trendline Breakout (Smashing Up)",
        "Trendline Breakdown (Smashing Down)"
    ])
    
    st.divider()
    zone_thickness = st.slider("Zone Thickness Tolerance (%)", 0.5, 5.0, 2.0, help="For horizontal zones only.")
    run_scan = st.button("🚀 EXECUTE SCAN", type="primary", use_container_width=True)

if "Test" in index_choice:
    symbols_to_scan = load_symbols("NIFTY 50")[:10]
else:
    symbols_to_scan = load_symbols(index_choice)

# --- CORE LOGIC ---
def analyze_price_action(df, hunt_horiz, hunt_trend, thickness_pct):
    df_recent = df.tail(200)
    if len(df_recent) < 50: return None
    
    latest_close = df_recent.iloc[-1]['Close']
    latest_high = df_recent.iloc[-1]['High']
    latest_low = df_recent.iloc[-1]['Low']
    prev_close = df_recent.iloc[-2]['Close']
    
    body = abs(latest_close - df_recent.iloc[-1]['Open'])
    rng = latest_high - latest_low if latest_high != latest_low else 0.001
    is_strong_green = (latest_close > df_recent.iloc[-1]['Open']) and (body / rng > 0.5)
    is_strong_red = (latest_close < df_recent.iloc[-1]['Open']) and (body / rng > 0.5)
    
    # 1. FIND ALL PIVOTS (Indices and Values)
    peak_indices = argrelextrema(df_recent['High'].values, np.greater_equal, order=5)[0]
    valley_indices = argrelextrema(df_recent['Low'].values, np.less_equal, order=5)[0]
    
    peaks = df_recent.iloc[peak_indices]['High'].values
    valleys = df_recent.iloc[valley_indices]['Low'].values
    
    # ==========================================
    # TRENDLINE LOGIC (DIAGONAL SLOPE)
    # ==========================================
    if hunt_trend != "None":
        current_idx = len(df_recent) - 1
        
        # Trendline Support / Breakdown (Using Valleys)
        if hunt_trend in ["Dynamic Trendline Support (Bounce)", "Trendline Breakdown (Smashing Down)"]:
            if len(valley_indices) >= 2:
                idx1, idx2 = valley_indices[-2], valley_indices[-1]
                p1, p2 = valleys[-2], valleys[-1]
                
                # Must be an upward sloping trendline
                if p2 > p1 and idx2 > idx1:
                    slope = (p2 - p1) / (idx2 - idx1)
                    projected_support = p2 + slope * (current_idx - idx2)
                    
                    if hunt_trend == "Dynamic Trendline Support (Bounce)":
                        if latest_low <= projected_support * 1.01 and latest_close > projected_support:
                            return f"Trendline Bounce at ₹{round(projected_support, 2)} 📈"
                            
                    elif hunt_trend == "Trendline Breakdown (Smashing Down)":
                        if prev_close > projected_support and latest_close < projected_support and is_strong_red:
                            return f"Trendline Breakdown below ₹{round(projected_support, 2)} 🩸"
                            
        # Trendline Resistance / Breakout (Using Peaks)
        elif hunt_trend in ["Dynamic Trendline Resistance (Rejection)", "Trendline Breakout (Smashing Up)"]:
            if len(peak_indices) >= 2:
                idx1, idx2 = peak_indices[-2], peak_indices[-1]
                p1, p2 = peaks[-2], peaks[-1]
                
                # Must be a downward sloping trendline
                if p2 < p1 and idx2 > idx1:
                    slope = (p2 - p1) / (idx2 - idx1)
                    projected_resistance = p2 + slope * (current_idx - idx2)
                    
                    if hunt_trend == "Dynamic Trendline Resistance (Rejection)":
                        if latest_high >= projected_resistance * 0.99 and latest_close < projected_resistance:
                            return f"Trendline Rejection at ₹{round(projected_resistance, 2)} 📉"
                            
                    elif hunt_trend == "Trendline Breakout (Smashing Up)":
                        if prev_close < projected_resistance and latest_close > projected_resistance and is_strong_green:
                            return f"Trendline Breakout above ₹{round(projected_resistance, 2)} 🚀"

    # ==========================================
    # HORIZONTAL ZONE LOGIC
    # ==========================================
    if hunt_horiz != "None":
        all_pivots = np.sort(np.concatenate((peaks, valleys)))
        if len(all_pivots) == 0: return None
        
        zones = []
        current_zone = [all_pivots[0]]
        for i in range(1, len(all_pivots)):
            if (all_pivots[i] - current_zone[0]) / current_zone[0] <= (thickness_pct / 100.0):
                current_zone.append(all_pivots[i])
            else:
                if len(current_zone) >= 3:
                    zones.append({'floor': min(current_zone), 'ceiling': max(current_zone), 'center': sum(current_zone)/len(current_zone)})
                current_zone = [all_pivots[i]]
                
        if len(current_zone) >= 3:
            zones.append({'floor': min(current_zone), 'ceiling': max(current_zone), 'center': sum(current_zone)/len(current_zone)})

        for zone in zones:
            z_floor, z_ceil, z_center = zone['floor'], zone['ceiling'], zone['center']
            zone_peaks = len([p for p in peaks if z_floor * 0.99 <= p <= z_ceil * 1.01])
            zone_valleys = len([v for v in valleys if z_floor * 0.99 <= v <= z_ceil * 1.01])
            
            if hunt_horiz == "Resistance becomes Support (Role Reversal)":
                if latest_close > z_ceil:
                    recent_low = df_recent.tail(5)['Low'].min()
                    if z_floor * 0.98 <= recent_low <= z_ceil * 1.02 and zone_peaks >= 2:
                        return f"Role Reversal at ₹{round(z_center, 2)} 🔄"
                            
            elif hunt_horiz == "Bounce off Heavy Support Zone":
                if latest_close > z_ceil and latest_low <= (z_ceil * 1.02) and is_strong_green and zone_valleys >= 2:
                    return f"Support Bounce at ₹{round(z_center, 2)} 🟢"
                    
            elif hunt_horiz == "Rejection at Heavy Resistance Zone":
                if latest_close < z_floor and latest_high >= (z_floor * 0.98) and is_strong_red and zone_peaks >= 2:
                    return f"Resistance Rejection at ₹{round(z_center, 2)} 🔴"
                    
            elif hunt_horiz == "Horizontal Breakout (Smashing Up)":
                if prev_close < z_floor and latest_close > z_ceil and is_strong_green and zone_peaks >= 2:
                    return f"Breakout Above ₹{round(z_ceil, 2)} 🚀"
                    
            elif hunt_horiz == "Horizontal Breakdown (Smashing Down)":
                if prev_close > z_ceil and latest_close < z_floor and is_strong_red and zone_valleys >= 2:
                    return f"Breakdown Below ₹{round(z_floor, 2)} 🩸"

    return None

# --- EXECUTION LOGIC ---
if run_scan:
    if hunt_horizontal == "None" and hunt_trendline == "None":
        st.error("Please select at least one setup to hunt for!")
    else:
        results = []
        
        with st.spinner(f"Downloading {timeframe} data for {len(symbols_to_scan)} stocks..."):
            raw_data = fetch_bulk_data(symbols_to_scan, timeframe)
        
        bar = st.progress(0, text="Calculating slopes and horizontal zones...")
        total = len(symbols_to_scan)
        
        for idx, ticker in enumerate(symbols_to_scan):
            bar.progress((idx + 1) / total, text=f"Analyzing {ticker}...")
            
            try:
                if total > 1: df = raw_data[ticker].dropna()
                else: df = raw_data.dropna()
                    
                if df.empty: continue
                
                if timeframe in ['3mo', '6mo', '12mo']:
                    df = resample_data(df, timeframe)
                    
                status = analyze_price_action(df, hunt_horizontal, hunt_trendline, zone_thickness)
                
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
            st.warning(f"No stocks found matching your criteria on the {timeframe} timeframe.")
