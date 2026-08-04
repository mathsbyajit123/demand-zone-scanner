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
st.set_page_config(page_title="Unlocked Demand Scanner", layout="wide")
st.title("🎯 Unlocked Demand & Flip Scanner")
st.markdown("Fully customizable search engine. You control exactly how strict the pullbacks and breakouts need to be.")

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
    "1 Day": "1d",
    "1 Week": "1wk",
    "1 Month": "1mo"
}
selected_tf_label = st.sidebar.selectbox("Timeframe", list(timeframe_options.keys()))
timeframe = timeframe_options[selected_tf_label]

st.sidebar.header("🎯 Pattern Settings")
min_base, max_base = st.sidebar.slider("Number of Base Candles (Min - Max)", min_value=1, max_value=5, value=(1, 3))
base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=80, value=45, 
                                  help="Set higher (e.g., 50%) to be more forgiving on what counts as a 'boring' candle.")

st.sidebar.header("🔓 Strictness Controls")
legout_strength = st.sidebar.slider("Leg-Out Candle Strength %", min_value=20, max_value=80, value=40,
                                    help="How big the green breakout candle's body needs to be relative to its total range. Lower = more results.")

# THE CRITICAL FIX: Gives the user the ability to expand the hit-box of the zone
zone_buffer_pct = st.sidebar.slider("Entry Zone Buffer % (Above Proximal)", min_value=0.0, max_value=10.0, value=3.0, step=0.5,
                                    help="If set to 3%, the scanner will catch stocks actively INSIDE the zone, OR up to 3% above the entry line.")

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
# 3. CORE LOGIC: DEMAND & FLIP ZONES
# ==========================================
def check_setup(df, min_b, max_b, body_pct, leg_strength, entry_buffer):
    df = df.dropna()
    if len(df) < 30: return None 
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    # Isolate the live/current candle
    current = df.iloc[-1]
    
    zones = []
    
    # 1. SCAN HISTORY FOR BASES (excluding the live candle)
    for i in range(2, len(df) - max_b - 1):
        setup_found = False
        
        for bases in range(min_b, max_b + 1):
            if setup_found: break 
            
            # Check Boring Candles
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
                
            # Check Leg-Out Strength using user's slider
            leg_idx = i + bases
            is_green = df['Close'].iloc[leg_idx] > df['Open'].iloc[leg_idx]
            is_red = df['Close'].iloc[leg_idx] < df['Open'].iloc[leg_idx]
            
            leg_range = df['Range'].iloc[leg_idx]
            leg_body_pct = (df['Body'].iloc[leg_idx] / leg_range) * 100 if leg_range > 0 else 0
            
            if leg_body_pct < leg_strength:
                continue
                
            base_slice = df.iloc[i : i + bases]
            highest_base = base_slice['High'].max()
            lowest_base = base_slice['Low'].min()
            
            # Identify Pure Demand (Breakout above highest wick of the base)
            if is_green and df['Close'].iloc[leg_idx] > highest_base:
                zones.append({
                    'type': 'Pure Demand',
                    'proximal': highest_base,  
                    'distal': lowest_base,     
                    'index': leg_idx
                })
                setup_found = True
                
            # Identify Pure Supply (Breakdown below lowest wick of the base)
            elif is_red and df['Close'].iloc[leg_idx] < lowest_base:
                zones.append({
                    'type': 'Supply',
                    'proximal': lowest_base,   
                    'distal': highest_base,    
                    'index': leg_idx
                })
                setup_found = True

    # 2. VALIDATE ZONES & IDENTIFY FLIPS
    active_demand_zones = []
    
    for z in zones:
        # Get all data AFTER the breakout candle, up to yesterday's close
        future_data = df.iloc[z['index']+1 : -1] 
        
        if z['type'] == 'Pure Demand':
            if len(future_data) == 0:
                active_demand_zones.append(z)
            elif not (future_data['Close'] < z['distal']).any():
                # If no candle ever closed below the stop loss, it's valid
                active_demand_zones.append(z)
                
        elif z['type'] == 'Supply':
            if len(future_data) > 0:
                # Did price close ABOVE the supply zone's distal line? (Broken upside)
                broken_upside = (future_data['Close'] > z['distal']).any()
                
                if broken_upside:
                    flipped_proximal = z['distal']
                    flipped_distal = z['proximal']
                    
                    # Ensure it hasn't been broken downside since it flipped
                    breakout_idx = future_data[future_data['Close'] > z['distal']].index[0]
                    post_breakout_data = df.loc[breakout_idx+1 : current.name - pd.Timedelta(days=1)]
                    
                    broken_downside = False
                    if len(post_breakout_data) > 0 and (post_breakout_data['Close'] < flipped_distal).any():
                        broken_downside = True
                        
                    if not broken_downside:
                        active_demand_zones.append({
                            'type': 'Supply Turned Demand (Flip)',
                            'proximal': flipped_proximal,
                            'distal': flipped_distal,
                            'index': z['index']
                        })

    if not active_demand_zones: return None
    
    # 3. LIVE PRICE CHECK WITH USER BUFFER
    buffer_multiplier = 1 + (entry_buffer / 100)
    
    for z in reversed(active_demand_zones): 
        
        # RULE 1: Live Close must be ABOVE the Stop Loss line (Distal)
        close_held = current['Close'] >= z['distal']
        
        # RULE 2: Live Close must be BELOW the Proximal Line + Your Custom Buffer
        close_in_range = current['Close'] <= (z['proximal'] * buffer_multiplier)
        
        # If both are true, the stock is currently trading right where you want it
        if close_held and close_in_range:
            risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
            
            # Determine proximity text
            if current['Close'] <= z['proximal']:
                status = "✅ INSIDE ZONE"
            else:
                dist_pct = ((current['Close'] - z['proximal']) / z['proximal']) * 100
                status = f"⏳ Approaching ({dist_pct:.1f}% above)"
            
            return {
                "Zone Type": z['type'],
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "Risk %": f"{risk_pct:.2f}%",
                "Status": status
            }
            
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan for Setups", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Running Unlocked Scanner on {selected_tf_label}...")
        
        if timeframe == '1d':
            fetch_period = "2y"
        elif timeframe == '1wk':
            fetch_period = "5y"
        else:
            fetch_period = "10y"
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=timeframe)
                if not df.empty:
                    setup = check_setup(df, min_base, max_base, base_body_pct, legout_strength, zone_buffer_pct)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append(setup)
            except:
                pass
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 LIVE Demand & Flip Results ({selected_tf_label})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Found {len(results)} matches based on your exact slider settings.")
        else:
            st.warning(f"No stocks found. Try increasing your 'Entry Zone Buffer %' or lowering the 'Leg-Out Strength %' in the sidebar.")
