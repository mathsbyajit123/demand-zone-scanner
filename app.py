import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE SETUP ---
st.set_page_config(page_title="Human-Eye Price Action Scanner", layout="wide", page_icon="👁️")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #E91E63; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #607D8B; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">👁️ Human-Eye Price Action Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for visual zones, role reversals (Res->Supp), and Trendline Breakouts.</p>', unsafe_allow_html=True)

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
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "CIPLA.NS"]

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

# --- SIMPLE HUMAN UI ---
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
    zone_thickness = st.slider("Zone Thickness (1=Thin Line, 5=Thick Band)", 1, 5, 2)
    run_scan = st.button("🚀 EXECUTE SCAN", type="primary", use_container_width=True)

if "Test" in index_choice:
    symbols_to_scan = load_symbols("NIFTY 50")[:10]
else:
    symbols_to_scan = load_symbols(index_choice)

# --- CORE LOGIC (PRICE DENSITY) ---
def analyze_price_action(df, hunt, thickness):
    # Use last 150 candles for context
    df_recent = df.tail(150)
    if len(df_recent) < 50: return None
    
    latest = df_recent.iloc[-1]
    prev = df_recent.iloc[-2]
    
    latest_close = latest['Close']
    latest_high = latest['High']
    latest_low = latest['Low']
    
    # Calculate strong closing candle
    body = abs(latest_close - latest['Open'])
    rng = latest_high - latest_low if latest_high != latest_low else 0.001
    is_strong_green = (latest_close > latest['Open']) and (body / rng > 0.6)
    is_strong_red = (latest_close < latest['Open']) and (body / rng > 0.6)
    
    # Create Price Bins (Horizontal Bands) based on Thickness slider
    max_p = df_recent['High'].max()
    min_p = df_recent['Low'].min()
    bin_size = (max_p - min_p) / (50 / thickness) # Thicker zones = fewer, wider bins
    
    if bin_size == 0: return None
    
    bins = np.arange(min_p, max_p + bin_size, bin_size)
    
    # Count how many highs/lows touch each bin
    hist, bin_edges = np.histogram(pd.concat([df_recent['High'], df_recent['Low']]), bins=bins)
    
    # Find the heavily touched zones (top 15% most touched areas)
    threshold = np.percentile(hist, 85)
    heavy_zones = []
    
    for i, count in enumerate(hist):
        if count >= threshold:
            heavy_zones.append({
                'floor': bin_edges[i],
                'ceiling': bin_edges[i+1],
                'center': (bin_edges[i] + bin_edges[i+1]) / 2,
                'touches': count
            })
            
    # If no clear zones found, skip
    if not heavy_zones: return None
    
    # Evaluate against what the user is hunting
    for zone in heavy_zones:
        z_floor = zone['floor']
        z_ceil = zone['ceiling']
        z_center = zone['center']
        
        # 1. RESISTANCE BECOMES SUPPORT (Like the CIPLA image)
        if hunt == "Resistance becomes Support (Role Reversal)":
            # Price must be above the zone currently
            if latest_close > z_ceil:
                # The lowest wick of recent candles must be touching the zone (testing it)
                if latest_low <= z_ceil * 1.01 and latest_low >= z_floor * 0.99:
                    # Historically, most closes were BELOW this zone (acted as resistance)
                    past_closes = df_recent.head(100)['Close']
                    if len(past_closes[past_closes < z_floor]) > len(past_closes[past_closes > z_ceil]):
                        return f"Role Reversal at ₹{round(z_center, 2)} 🔄"
                        
        # 2. BOUNCE OFF SUPPORT
        elif hunt == "Bounce off Heavy Support Zone":
            if latest_close > z_ceil and latest_low <= (z_ceil * 1.015) and is_strong_green:
                return f"Support Bounce at ₹{round(z_center, 2)} 🟢"
                
        # 3. REJECTION AT RESISTANCE
        elif hunt == "Rejection at Heavy Resistance Zone":
            if latest_close < z_floor and latest_high >= (z_floor * 0.985) and is_strong_red:
                return f"Resistance Rejection at ₹{round(z_center, 2)} 🔴"
                
        # 4. ZONE BREAKOUT (UP)
        elif hunt == "Strong Zone Breakout (Up)":
            # Previous candle closed below zone, current closed above with strong momentum
            if prev['Close'] < z_floor and latest_close > z_ceil and is_strong_green:
                return f"Breakout Above ₹{round(z_ceil, 2)} 🚀"
                
        # 5. ZONE BREAKDOWN (DOWN)
        elif hunt == "Strong Zone Breakdown (Down)":
            if prev['Close'] > z_ceil and latest_close < z_floor and is_strong_red:
                return f"Breakdown Below ₹{round(z_floor, 2)} 🩸"

    # 6. TRENDLINE BOUNCE (Simplified: 3 consecutive higher lows + bounce off 20 SMA)
    if hunt == "Trendline Bounce (Higher Lows)":
        df_recent['SMA_20'] = df_recent['Close'].rolling(20).mean()
        if len(df_recent) > 5:
            l1, l2, l3 = df_recent.iloc[-3]['Low'], df_recent.iloc[-2]['Low'], df_recent.iloc[-1]['Low']
            sma20 = df_recent.iloc[-1]['SMA_20']
            
            if l3 > l2 > l1 and (abs(latest_low - sma20) / sma20 < 0.01) and is_strong_green:
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
        st.warning(f"No stocks found matching '{hunt_type}' on the {timeframe} timeframe right now.")
