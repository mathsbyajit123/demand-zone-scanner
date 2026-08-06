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
st.set_page_config(page_title="Pure 1-Base S&D Scanner", layout="wide")
st.title("🎯 Pure 1-Base Candle S&D Scanner")
st.markdown("Scans strictly for 1 Base Candle setups, demanding either 2 strong leg-out candles or 1 massive leg-out candle.")

st.sidebar.header("⚙️ Market Settings")
sector_options = [
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Auto"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options, index=1)

timeframe_options = {
    "1 Day": "1d",
    "75 Minutes (Intraday)": "75m",
    "1 Week": "1wk",
    "1 Month": "1mo"
}
selected_tf_label = st.sidebar.selectbox("Timeframe", list(timeframe_options.keys()))
timeframe = timeframe_options[selected_tf_label]

st.sidebar.header("🎯 Scan Direction")
direction = st.sidebar.radio(
    "Select Setup Direction",
    ("🟢 Bullish (Demand: RBR, DBR)", "🔴 Bearish (Supply: RBD, DBD)")
)

st.sidebar.header("📍 Proximity Filter")
proximity_filter = st.sidebar.radio(
    "Where is the Live Price?",
    (
        "Any (In Zone or Near Zone)",
        "Strictly IN Zone",
        "Strictly NEAR Zone (Approaching)"
    )
)

st.sidebar.header("🧲 Zone Hit-Box")
hitbox_buffer = st.sidebar.slider(
    "Near Zone Buffer %", 
    min_value=0.0, max_value=5.0, value=2.0, step=0.5,
    help="How far away the price can be to still be considered 'Near'."
)

st.sidebar.header("📐 Base Candle Settings")
st.sidebar.info("Base candles are locked to exactly ONE (1) candle as requested.")
base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=80, value=45, help="Body size relative to its High-Low range.")

# ==========================================
# 2. DATA FETCHER
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
            
    st.sidebar.error("⚠️ Unable to fetch ticker list.")
    return []

# ==========================================
# 3. CORE LOGIC
# ==========================================
def resample_to_75m(df):
    resampled = df.resample('75min', offset='15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    return resampled

def check_setup(df, dir_choice, prox_choice, body_pct, buffer_pct):
    df = df[['Open', 'High', 'Low', 'Close']].dropna()
    # Need at least a few candles to check leg-in, base, and 2 leg-outs
    if len(df) < 20: return None 
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    is_bullish = "Bullish" in dir_choice
    current = df.iloc[-1]
    
    target_zones = []
    
    # 1. SCAN HISTORY FOR EXACTLY 1 BASE CANDLE PATTERNS
    # Loop needs to stop 3 candles before the end to check leg1 and leg2 safely
    for i in range(1, len(df) - 3):
        leg_in_idx = i - 1
        base_idx = i
        leg1_idx = i + 1
        leg2_idx = i + 2
        
        # --- A. LEG-IN CHECK ---
        leg_in_is_green = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
        leg_in_type = "R" if leg_in_is_green else "D" 
        
        # --- B. BASE CANDLE CHECK (Exactly 1) ---
        base_range = df['Range'].iloc[base_idx]
        if base_range == 0: continue
        
        candle_body_pct = (df['Body'].iloc[base_idx] / base_range) * 100
        if candle_body_pct > body_pct: continue
            
        base_high = df['High'].iloc[base_idx]
        base_low = df['Low'].iloc[base_idx]
        
        # --- C. LEG-OUT LOGIC (1 Massive OR 2 Strong) ---
        leg1_range = df['Range'].iloc[leg1_idx]
        leg1_body_pct = (df['Body'].iloc[leg1_idx] / leg1_range) * 100 if leg1_range > 0 else 0
        
        leg2_range = df['Range'].iloc[leg2_idx]
        leg2_body_pct = (df['Body'].iloc[leg2_idx] / leg2_range) * 100 if leg2_range > 0 else 0
        
        leg1_green = df['Close'].iloc[leg1_idx] > df['Open'].iloc[leg1_idx]
        leg2_green = df['Close'].iloc[leg2_idx] > df['Open'].iloc[leg2_idx]
        
        # Define Strength
        leg1_strong = leg1_body_pct >= 50
        leg2_strong = leg2_body_pct >= 50
        # "Big" candle = body > 65% and its total range is at least 1.5x bigger than the base candle's range
        leg1_very_strong = leg1_body_pct >= 65 and leg1_range >= (base_range * 1.5)
        
        setup_found = False
        
        if is_bullish:
            # Must close above the base
            if leg1_green and df['Close'].iloc[leg1_idx] > base_high:
                # 1 Massive OR 2 Strong
                if leg1_very_strong or (leg2_green and leg1_strong and leg2_strong):
                    target_zones.append({
                        'pattern': f"{leg_in_type}BR",
                        'proximal': base_high, 
                        'distal': base_low, 
                        'index': leg2_idx if (not leg1_very_strong) else leg1_idx
                    })
                    setup_found = True
        else:
            # Must close below the base
            if not leg1_green and df['Close'].iloc[leg1_idx] < base_low:
                # 1 Massive OR 2 Strong
                if leg1_very_strong or (not leg2_green and leg1_strong and leg2_strong):
                    target_zones.append({
                        'pattern': f"{leg_in_type}BD",
                        'proximal': base_low, 
                        'distal': base_high, 
                        'index': leg2_idx if (not leg1_very_strong) else leg1_idx
                    })
                    setup_found = True

    # 2. VALIDATE ZONES (Eliminate Broken Zones)
    valid_zones = []
    for z in target_zones:
        future_data = df.iloc[z['index']+1 : -1] 
        
        if len(future_data) == 0:
            valid_zones.append(z)
        else:
            if is_bullish:
                if not (future_data['Close'] < z['distal']).any(): valid_zones.append(z)
            else:
                if not (future_data['Close'] > z['distal']).any(): valid_zones.append(z)

    if not valid_zones: return None
    
    # 3. PROXIMITY CHECK (Live Price)
    buffer_mult_bull = 1 + (buffer_pct / 100)
    buffer_mult_bear = 1 - (buffer_pct / 100)
    
    for z in reversed(valid_zones): 
        is_in_zone = False
        is_near = False
        
        if is_bullish:
            if current['Close'] < z['distal']: continue # Broken Stop Loss
            
            # In Zone: Low tapped entry, Close is above SL
            is_in_zone = (current['Low'] <= z['proximal']) and (current['Close'] >= z['distal'])
            # Near Zone: Hovering just above the Entry line
            is_near = (current['Low'] > z['proximal']) and (current['Low'] <= (z['proximal'] * buffer_mult_bull))
            
        else:
            if current['Close'] > z['distal']: continue # Broken Stop Loss
            
            # In Zone: High tapped entry, Close is below SL
            is_in_zone = (current['High'] >= z['proximal']) and (current['Close'] <= z['distal'])
            # Near Zone: Hovering just below the Entry line
            is_near = (current['High'] < z['proximal']) and (current['High'] >= (z['proximal'] * buffer_mult_bear))

        # Apply User Filter
        if "Strictly IN Zone" in prox_choice and not is_in_zone: continue
        if "Strictly NEAR Zone" in prox_choice and not is_near: continue
        if "Any" in prox_choice and not (is_in_zone or is_near): continue

        risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
        status = "✅ IN ZONE" if is_in_zone else f"⏳ NEAR ZONE (<{buffer_pct}%)"
        
        return {
            "Pattern": z['pattern'],
            "Live Price": round(current['Close'], 2),
            "Zone Entry": round(z['proximal'], 2),
            "Stop Loss": round(z['distal'], 2),
            "Risk %": f"{risk_pct:.2f}%",
            "Status": status
        }
            
    return None

# ==========================================
# 4. EXECUTION
# ==========================================
if st.sidebar.button(f"Launch Scanner", type="primary"):
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for Pure 1-Base setups...")
        
        if timeframe == '75m': fetch_period, fetch_interval = "60d", "15m"
        elif timeframe == '1d': fetch_period, fetch_interval = "2y", "1d"
        elif timeframe == '1wk': fetch_period, fetch_interval = "5y", "1wk"
        else: fetch_period, fetch_interval = "10y", "1mo"
        
        progress_bar = st.progress(0)
        results = []
        
        for i, ticker in enumerate(ticker_list):
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=fetch_interval)
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    setup = check_setup(df, direction, proximity_filter, base_body_pct, hitbox_buffer)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append(setup)
            except: pass
            progress_bar.progress((i + 1) / len(ticker_list))
            
        progress_bar.empty()
        
        st.subheader(f"📊 Scan Results ({selected_tf_label})")
        if results:
            final_df = pd.DataFrame(results)[['Ticker', 'Pattern', 'Live Price', 'Zone Entry', 'Stop Loss', 'Risk %', 'Status']]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Target setups acquired successfully.")
        else:
            st.warning(f"0 matches. No stocks currently satisfy the strict 1-Base & strong 2-leg-out rules.")
