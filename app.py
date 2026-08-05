import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SETTINGS
# ==========================================
st.set_page_config(page_title="Dynamic S&D Search Engine", layout="wide")
st.title("🎯 S&D Base & Dynamic Proximity Search Engine")
st.markdown("Scans for stocks retracing into validated Supply or Demand zones. Automatically scales 'Near Zone' proximity limits based on your selected timeframe.")

st.sidebar.header("⚙️ Market Settings")

sector_options = [
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Auto"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options)

timeframe_options = {
    "75 Minutes (Intraday)": "75m",
    "1 Day": "1d",
    "1 Week": "1wk",
    "1 Month": "1mo"
}
selected_tf_label = st.sidebar.selectbox("Timeframe", list(timeframe_options.keys()))
timeframe = timeframe_options[selected_tf_label]

st.sidebar.header("🎯 Scan Direction")
direction = st.sidebar.radio(
    "Select Setup Type",
    ("🟢 Bullish (Demand Zone)", "🔴 Bearish (Supply Zone)")
)

st.sidebar.header("📐 Zone Settings")
min_base, max_base = st.sidebar.slider("Number of Base Candles (Min - Max)", min_value=1, max_value=5, value=(1, 3))
base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=60, value=40, 
                                  help="40% means the body is max 40% of the total candle range.")

st.sidebar.header("📊 Volume Verification")
require_low_vol = st.sidebar.checkbox("✅ Require Lower Volume on Retracement", value=True, 
                                      help="If checked, the pullback volume MUST be strictly lower than the original breakout candle volume.")

# ==========================================
# 2. DYNAMIC TIMEFRAME BUFFER ENGINE
# ==========================================
def get_timeframe_buffer(tf):
    """Returns the exact allowable proximity percentage based on timeframe."""
    buffers = {
        "1mo": 5.0,  # 0 to 5% far
        "1wk": 3.0,  # 0 to 3% far
        "1d": 2.0,   # 0 to 2% far
        "75m": 0.5   # 0 to 0.5% far
    }
    return buffers.get(tf, 2.0)

# Display active dynamic buffer in sidebar
active_buffer = get_timeframe_buffer(timeframe)
st.sidebar.info(f"⚡ **Active Proximity Rule:** Stocks must be within **0% to {active_buffer}%** of the Zone Entry for the `{selected_tf_label}` timeframe.")

# ==========================================
# 3. DATA FETCHER (FIREWALL-PROOF)
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    csv_file = {
        "Nifty 50": "ind_nifty50list.csv",
        "Nifty 500": "ind_nifty500list.csv",
        "Nifty Midcap 100": "ind_niftymidcap100list.csv",
        "Nifty Bank": "ind_niftybanklist.csv",
        "Nifty IT": "ind_niftyitlist.csv",
        "Nifty Auto": "ind_niftyautolist.csv"
    }.get(sector_name, "ind_nifty500list.csv")
    
    mirrors = [
        f"https://raw.githubusercontent.com/althk/zerobha/main/{csv_file}",
        f"https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/{csv_file}",
        f"https://raw.githubusercontent.com/rohanmadhale/Python-Portfolio-Optimisation/main/{csv_file}",
        f"https://raw.githubusercontent.com/faizanahemad/data-science-utils/master/data_science_utils/financial/{csv_file}"
    ]
    
    for url in mirrors:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                symbol_col = next((col for col in df.columns if 'Symbol' in col or 'SYMBOL' in col), None)
                if symbol_col:
                    return [str(s).strip() + ".NS" for s in df[symbol_col]]
        except Exception:
            continue
            
    st.sidebar.error("⚠️ Critical Error: Unable to fetch ticker list.")
    return []

# ==========================================
# 4. CORE LOGIC: ZONE & DYNAMIC PROXIMITY
# ==========================================
def resample_to_75m(df):
    """Converts 15-minute data into 75-minute candles matching the Indian market open (9:15 AM)."""
    resampled = df.resample('75min', offset='15min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return resampled

def check_setup(df, dir_choice, min_b, max_b, body_pct, tf_buffer_pct, req_low_vol):
    df = df.dropna()
    if len(df) < 20: return None 
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    is_bullish = "Bullish" in dir_choice
    current = df.iloc[-1]
    
    zones = []
    
    # 1. SCAN HISTORY FOR ZONES
    for i in range(2, len(df) - max_b - 1):
        setup_found = False
        
        for bases in range(min_b, max_b + 1):
            if setup_found: break 
            
            # A. Check if Base Candles are "Boring"
            base_valid = True
            for b in range(bases):
                idx = i + b
                if df['Range'].iloc[idx] == 0: 
                    base_valid = False
                    break
                
                candle_body_pct = (df['Body'].iloc[idx] / df['Range'].iloc[idx]) * 100
                if candle_body_pct > body_pct:
                    base_valid = False
                    break
                    
            if not base_valid:
                continue
                
            # B. Check Leg-Out Candle Strength
            leg_idx = i + bases
            is_green = df['Close'].iloc[leg_idx] > df['Open'].iloc[leg_idx]
            is_red = df['Close'].iloc[leg_idx] < df['Open'].iloc[leg_idx]
            leg_range = df['Range'].iloc[leg_idx]
            leg_body_pct = (df['Body'].iloc[leg_idx] / leg_range) * 100 if leg_range > 0 else 0
            
            # Leg out must be healthy (Body > 50% of its range)
            if leg_body_pct < 50:
                continue
                
            base_slice = df.iloc[i : i + bases]
            highest_base = base_slice['High'].max()
            lowest_base = base_slice['Low'].min()
            
            # C. Define Zone Boundaries based on Direction
            if is_bullish:
                if is_green and df['Close'].iloc[leg_idx] > highest_base:
                    zones.append({
                        'proximal': highest_base,  # Top of base (Entry)
                        'distal': lowest_base,     # Bottom of base (Stop Loss)
                        'breakout_vol': df['Volume'].iloc[leg_idx],
                        'index': leg_idx
                    })
                    setup_found = True
            else:
                if is_red and df['Close'].iloc[leg_idx] < lowest_base:
                    zones.append({
                        'proximal': lowest_base,   # Bottom of base (Entry)
                        'distal': highest_base,    # Top of base (Stop Loss)
                        'breakout_vol': df['Volume'].iloc[leg_idx],
                        'index': leg_idx
                    })
                    setup_found = True

    # 2. VALIDATE ZONES (Ensure they are not broken)
    valid_zones = []
    for z in zones:
        future_data = df.iloc[z['index']+1 : -1] 
        if len(future_data) == 0: 
            valid_zones.append(z)
            continue
            
        if is_bullish:
            if not (future_data['Close'] < z['distal']).any():
                valid_zones.append(z)
        else:
            if not (future_data['Close'] > z['distal']).any():
                valid_zones.append(z)

    if not valid_zones: return None
    
    # 3. LIVE PRICE PROXIMITY USING DYNAMIC TIMEFRAME BUFFER
    buffer_mult_bull = 1 + (tf_buffer_pct / 100)
    buffer_mult_bear = 1 - (tf_buffer_pct / 100)
    
    for z in reversed(valid_zones): 
        
        in_zone = False
        
        if is_bullish:
            # Must not have closed below Stop Loss (Distal)
            # Must be within 0% to X% above the Entry Line (Proximal), or actively inside
            low_tapped = current['Low'] <= (z['proximal'] * buffer_mult_bull)
            close_held = current['Close'] >= z['distal']
            close_near = current['Close'] <= (z['proximal'] * buffer_mult_bull)
            in_zone = low_tapped and close_held and close_near
        else:
            # Must not have closed above Stop Loss (Distal)
            # Must be within 0% to X% below the Entry Line (Proximal), or actively inside
            high_tapped = current['High'] >= (z['proximal'] * buffer_mult_bear)
            close_held = current['Close'] <= z['distal']
            close_near = current['Close'] >= (z['proximal'] * buffer_mult_bear)
            in_zone = high_tapped and close_held and close_near

        # Volume Condition
        vol_passed = True
        if req_low_vol:
            if current['Volume'] >= z['breakout_vol']:
                vol_passed = False

        if in_zone and vol_passed:
            risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
            
            # Precise Distance Calculation & Status Display
            if is_bullish:
                if current['Close'] <= z['proximal']:
                    status = "✅ INSIDE ZONE"
                else:
                    dist_pct = ((current['Close'] - z['proximal']) / z['proximal']) * 100
                    status = f"⏳ Near Zone (+{dist_pct:.2f}% above)"
            else:
                if current['Close'] >= z['proximal']:
                    status = "✅ INSIDE ZONE"
                else:
                    dist_pct = ((z['proximal'] - current['Close']) / z['proximal']) * 100
                    status = f"⏳ Near Zone (-{dist_pct:.2f}% below)"
            
            return {
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "Risk %": f"{risk_pct:.2f}%",
                "Vol Dry-Up": "✅ Yes" if current['Volume'] < z['breakout_vol'] else "❌ No",
                "Status": status
            }
            
    return None

# ==========================================
# 5. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Launch Scanner", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for {direction[:2]} zones on `{selected_tf_label}` (Max Buffer: **{active_buffer}%**)...")
        
        if timeframe == '75m':
            fetch_period = "60d"
            fetch_interval = "15m"
        elif timeframe == '1d':
            fetch_period = "2y"
            fetch_interval = "1d"
        elif timeframe == '1wk':
            fetch_period = "5y"
            fetch_interval = "1wk"
        else:
            fetch_period = "10y"
            fetch_interval = "1mo"
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=fetch_interval)
                
                if not df.empty:
                    if timeframe == '75m':
                        df = resample_to_75m(df)
                        
                    setup = check_setup(df, direction, min_base, max_base, base_body_pct, active_buffer, require_low_vol)
                    
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append(setup)
            except:
                pass
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 6. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 {direction[:2]} Scan Results ({selected_tf_label})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Scan Complete. Found {len(results)} stocks matching your exact Base, Volume, and {active_buffer}% Proximity rule.")
        else:
            st.warning(f"No stocks found within the strict 0% to {active_buffer}% proximity limit on `{selected_tf_label}` right now.")
