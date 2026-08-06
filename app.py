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
st.set_page_config(page_title="Ultra-Strict S&D Engine", layout="wide")
st.title("🎯 Ultra-Strict Base & Flip Scanner")
st.markdown("Scans for zones built exclusively from truly small base candles (capped by timeframe). No massive dojis allowed.")

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
    "Select Setup Direction",
    ("🟢 Bullish (Buy Setups)", "🔴 Bearish (Sell Setups)")
)

st.sidebar.header("🔄 Zone Type to Scan")
zone_filter = st.sidebar.radio(
    "Filter by Zone History",
    (
        "All Zones (Standard + Flipped)", 
        "Standard Zones Only", 
        "Flipped Zones Only (Role Reversal)"
    )
)

st.sidebar.header("📐 Base Settings")
min_base, max_base = st.sidebar.slider("Number of Base Candles (Min - Max)", min_value=1, max_value=5, value=(1, 3))
base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=60, value=40, 
                                  help="The body must be max 40% of the total candle range.")

# ==========================================
# 2. DATA FETCHER (FIREWALL-PROOF)
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
# 3. CORE LOGIC: ULTRA-STRICT BASES
# ==========================================
def resample_to_75m(df):
    """Converts 15-minute data into 75-minute data matching the Indian market open."""
    resampled = df.resample('75min', offset='15min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return resampled

def check_setup(df, dir_choice, zone_choice, min_b, max_b, body_pct, buffer_pct, max_candle_range_pct):
    df = df.dropna()
    if len(df) < 30: return None 
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    # Calculate Total Candle Size as a percentage of the closing price
    df['Candle_Size_Pct'] = (df['Range'] / df['Close']) * 100
    
    is_bullish = "Bullish" in dir_choice
    current = df.iloc[-1]
    
    all_historical_zones = []
    
    # 1. SCAN HISTORY FOR ALL PATTERNS (RBR, DBR, RBD, DBD)
    for i in range(2, len(df) - max_b - 1):
        setup_found = False
        
        for bases in range(min_b, max_b + 1):
            if setup_found: break 
            
            leg_in_idx = i - 1
            leg_in_is_green = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
            leg_in_type = "R" if leg_in_is_green else "D" 
            
            # A. ULTRA-STRICT BASE VERIFICATION
            base_valid = True
            for b in range(bases):
                idx = i + b
                if df['Range'].iloc[idx] == 0: 
                    base_valid = False
                    break
                
                # Rule 1: Body must be < X% of the range (Shape)
                candle_body_pct = (df['Body'].iloc[idx] / df['Range'].iloc[idx]) * 100
                if candle_body_pct > body_pct:
                    base_valid = False
                    break
                    
                # Rule 2: Total candle size must be STRICTLY smaller than timeframe limit (Size)
                if df['Candle_Size_Pct'].iloc[idx] > max_candle_range_pct:
                    base_valid = False
                    break
                    
            if not base_valid:
                continue
                
            # B. Leg-Out Strength & Close
            leg_idx = i + bases
            leg_is_green = df['Close'].iloc[leg_idx] > df['Open'].iloc[leg_idx]
            leg_range = df['Range'].iloc[leg_idx]
            leg_body_pct = (df['Body'].iloc[leg_idx] / leg_range) * 100 if leg_range > 0 else 0
            
            # Leg out must be a strong momentum candle
            if leg_body_pct < 50:
                continue
                
            base_slice = df.iloc[i : i + bases]
            highest_base = base_slice['High'].max()
            lowest_base = base_slice['Low'].min()
            
            # C. Categorize the Zone
            if leg_is_green and df['Close'].iloc[leg_idx] > highest_base:
                # Demand Zone
                all_historical_zones.append({
                    'type': f"{leg_in_type}BR",
                    'category': 'Demand',
                    'proximal': highest_base,  
                    'distal': lowest_base,     
                    'index': leg_idx
                })
                setup_found = True
                
            elif not leg_is_green and df['Close'].iloc[leg_idx] < lowest_base:
                # Supply Zone
                all_historical_zones.append({
                    'type': f"{leg_in_type}BD",
                    'category': 'Supply',
                    'proximal': lowest_base,   
                    'distal': highest_base,    
                    'index': leg_idx
                })
                setup_found = True

    # 2. VALIDATE ZONES & PROCESS FLIPS
    active_target_zones = []
    
    for z in all_historical_zones:
        future_data = df.iloc[z['index']+1 : -1] 
        
        if z['category'] == 'Demand':
            if len(future_data) == 0:
                if is_bullish: active_target_zones.append(z)
                continue
                
            broken_downside = future_data[future_data['Close'] < z['distal']]
            
            if broken_downside.empty:
                if is_bullish: active_target_zones.append(z)
            else:
                if not is_bullish:
                    break_idx = broken_downside.index[0]
                    post_flip = df.loc[break_idx+1 : current.name - pd.Timedelta(days=1)]
                    
                    if post_flip.empty or not (post_flip['Close'] > z['proximal']).any():
                        active_target_zones.append({
                            'type': f"Flipped {z['type']}",
                            'category': 'Supply',
                            'proximal': z['distal'], 
                            'distal': z['proximal'], 
                            'index': break_idx
                        })
                        
        elif z['category'] == 'Supply':
            if len(future_data) == 0:
                if not is_bullish: active_target_zones.append(z)
                continue
                
            broken_upside = future_data[future_data['Close'] > z['distal']]
            
            if broken_upside.empty:
                if not is_bullish: active_target_zones.append(z)
            else:
                if is_bullish:
                    break_idx = broken_upside.index[0]
                    post_flip = df.loc[break_idx+1 : current.name - pd.Timedelta(days=1)]
                    
                    if post_flip.empty or not (post_flip['Close'] < z['proximal']).any():
                        active_target_zones.append({
                            'type': f"Flipped {z['type']}",
                            'category': 'Demand',
                            'proximal': z['distal'], 
                            'distal': z['proximal'], 
                            'index': break_idx
                        })

    # 3. FILTER BY USER'S ZONE CHOICE
    filtered_zones = []
    for z in active_target_zones:
        is_flipped = "Flipped" in z['type']
        
        if "Standard" in zone_choice and is_flipped: continue
        if "Flipped" in zone_choice and not is_flipped: continue
            
        filtered_zones.append(z)

    if not filtered_zones: return None
    
    # 4. STRICT LIVE PRICE PROXIMITY
    buffer_mult_bull = 1 + (buffer_pct / 100)
    buffer_mult_bear = 1 - (buffer_pct / 100)
    
    for z in reversed(filtered_zones): 
        in_zone = False
        
        if is_bullish: 
            # LIVE CLOSE must be strictly >= Distal and <= (Proximal + Buffer)
            close_held = current['Close'] >= z['distal']
            close_near = current['Close'] <= (z['proximal'] * buffer_mult_bull)
            in_zone = close_held and close_near
        else: 
            # LIVE CLOSE must be strictly <= Distal and >= (Proximal - Buffer)
            close_held = current['Close'] <= z['distal']
            close_near = current['Close'] >= (z['proximal'] * buffer_mult_bear)
            in_zone = close_held and close_near

        if in_zone:
            risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
            
            if is_bullish:
                status = "✅ IN ZONE" if current['Close'] <= z['proximal'] else f"⏳ NEAR ZONE"
            else:
                status = "✅ IN ZONE" if current['Close'] >= z['proximal'] else f"⏳ NEAR ZONE"
            
            return {
                "Pattern": z['type'],
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "Risk %": f"{risk_pct:.2f}%",
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
        # Determine Dynamic Proximity Buffer based on Timeframe
        dynamic_buffer = {
            "75m": 0.5,
            "1d": 2.0,
            "1wk": 3.0,
            "1mo": 5.0
        }.get(timeframe, 2.0)

        # STRICT MAXIMUM CANDLE SIZE (Total High to Low Range)
        max_candle_range = {
            "75m": 2.0,  # Max 2% move
            "1d": 5.0,   # Max 5% move
            "1wk": 10.0, # Max 10% move
            "1mo": 15.0  # Max 15% move
        }.get(timeframe, 5.0)
        
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for {direction[:2]} patterns on {selected_tf_label}.")
        st.caption(f"Strict Timeframe Rules Applied -> Max Base Size: {max_candle_range}% | Entry Buffer: {dynamic_buffer}%")
        
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
                        
                    setup = check_setup(df, direction, zone_filter, min_base, max_base, base_body_pct, dynamic_buffer, max_candle_range)
                    
                    if setup:
                        results.append({
                            'Ticker': ticker.replace(".NS", ""),
                            'Pattern': setup['Pattern'],
                            'Live Price': setup['Live Price'],
                            'Zone Entry': setup['Zone Entry'],
                            'Stop Loss': setup['Stop Loss'],
                            'Risk %': setup['Risk %'],
                            'Status': setup['Status']
                        })
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
            cols = ['Ticker', 'Pattern', 'Live Price', 'Zone Entry', 'Stop Loss', 'Risk %', 'Status']
            final_df = final_df[cols]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Scan Complete. Found stocks strictly adhering to the small-candle constraints and active entry zones.")
        else:
            st.warning(f"No stocks found. The strictly capped candle size limits ({max_candle_range}%) filtered out all false setups.")
