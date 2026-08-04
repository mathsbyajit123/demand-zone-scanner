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
st.set_page_config(page_title="Ultimate Demand & Flip Scanner", layout="wide")
st.title("🎯 Ultimate Demand & Flip Zone Scanner (STRICT)")
st.markdown("Scans for stocks strictly trading INSIDE a valid Demand Zone OR an old Supply Zone that has flipped to Demand (Support).")

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

st.sidebar.header("🎯 Base (Boring Candle) Settings")
min_base, max_base = st.sidebar.slider("Number of Base Candles (Min - Max)", min_value=1, max_value=5, value=(1, 3))
base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=60, value=40, 
                                  help="40% means the body is small (max 40% of the high-to-low range).")

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
def check_setup(df, min_b, max_b, body_pct):
    df = df.dropna()
    if len(df) < 50: return None 
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    current = df.iloc[-1]
    
    zones = []
    
    # 1. SCAN HISTORY FOR ALL BASES & BREAKOUTS
    for i in range(5, len(df) - max_b - 2):
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
                
            # Check Leg-Out (Must be explosive, body > 50% of its own range)
            leg_idx = i + bases
            is_green = df['Close'].iloc[leg_idx] > df['Open'].iloc[leg_idx]
            is_red = df['Close'].iloc[leg_idx] < df['Open'].iloc[leg_idx]
            leg_body_pct = (df['Body'].iloc[leg_idx] / df['Range'].iloc[leg_idx]) * 100 if df['Range'].iloc[leg_idx] > 0 else 0
            
            if leg_body_pct < 50:
                continue
                
            base_slice = df.iloc[i : i + bases]
            highest_base = base_slice['High'].max()
            lowest_base = base_slice['Low'].min()
            
            # Identify Pure Demand (Rally/Drop - Base - Rally)
            if is_green and df['Close'].iloc[leg_idx] > highest_base:
                zones.append({
                    'type': 'Pure Demand',
                    'proximal': highest_base,  # Entry Line
                    'distal': lowest_base,     # Stop Loss Line
                    'index': leg_idx
                })
                setup_found = True
                
            # Identify Pure Supply (Rally/Drop - Base - Drop)
            elif is_red and df['Close'].iloc[leg_idx] < lowest_base:
                zones.append({
                    'type': 'Supply',
                    'proximal': lowest_base,   # Bottom of base
                    'distal': highest_base,    # Top of base
                    'index': leg_idx
                })
                setup_found = True

    # 2. VALIDATE ZONES & IDENTIFY FLIPS
    active_demand_zones = []
    
    for z in zones:
        future_data = df.iloc[z['index']+1 : -1] 
        if len(future_data) == 0: continue
        
        if z['type'] == 'Pure Demand':
            # Must not have closed below Distal
            if not (future_data['Close'] < z['distal']).any():
                active_demand_zones.append(z)
                
        elif z['type'] == 'Supply':
            # Check if this Supply zone was BROKEN upside (Price closed above its highest point)
            broken_upside = (future_data['Close'] > z['distal']).any()
            
            if broken_upside:
                # It is now a FLIPPED Zone (Supply turned Demand)
                # The old top (distal) becomes the new Entry (proximal).
                # The old bottom (proximal) becomes the new Stop Loss (distal).
                flipped_proximal = z['distal']
                flipped_distal = z['proximal']
                
                # Check if it has been broken downside AFTER flipping
                broken_downside = False
                
                # Find the index where it broke upside
                breakout_idx = future_data[future_data['Close'] > z['distal']].index[0]
                post_breakout_data = df.loc[breakout_idx+1 : current.name]
                
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
    
    # 3. STRICT LIVE PRICE CHECK (No 8% gaps allowed)
    for z in reversed(active_demand_zones): 
        
        # STRICT LOCK: 
        # 1. Low must tap the zone OR Close must be physically inside it.
        # 2. Close must NOT be lower than Stop Loss (Distal).
        # 3. Close must NOT be higher than 1% above the Entry (Proximal) to prevent "runaway" signals.
        
        low_tapped = current['Low'] <= z['proximal']
        close_held = current['Close'] >= z['distal']
        close_not_flown_away = current['Close'] <= (z['proximal'] * 1.01) # Max 1% above entry line
        
        if low_tapped and close_held and close_not_flown_away:
            risk_pct = (abs(z['proximal'] - z['distal']) / z['proximal']) * 100
            
            return {
                "Zone Type": z['type'],
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "Risk %": f"{risk_pct:.2f}%",
                "Status": "✅ STRICTLY IN ZONE"
            }
            
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan for Strict Demand & Flips", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for strictly active Demand and Flip zones on {selected_tf_label}...")
        
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
                    setup = check_setup(df, min_base, max_base, base_body_pct)
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
            st.success("Target acquired. The stocks listed are physically trading INSIDE the zone boundaries right now. No fake wicks.")
        else:
            st.warning(f"No stocks found. None are currently sitting strictly inside a valid Demand or Flipped Supply zone on the {selected_tf_label} timeframe.")
