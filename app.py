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
st.set_page_config(page_title="Confluence Demand Scanner", layout="wide")
st.title("🎯 Structural Confluence Demand Scanner (LIVE)")
st.markdown("Scans for Demand Zones (Boring Bases + Strong Leg-Out) that formed exactly at **Traditional Support/Resistance** (Swing Pivots) in a strict Uptrend.")

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
    "1 Month": "1mo",
    "3 Months": "3mo"
}
selected_tf_label = st.sidebar.selectbox("Timeframe", list(timeframe_options.keys()))
timeframe = timeframe_options[selected_tf_label]

st.sidebar.header("🎯 Pattern Settings")
min_base, max_base = st.sidebar.slider("Number of Base (Boring) Candles", min_value=1, max_value=3, value=(1, 2))
base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=50, value=40)

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
# 3. CORE LOGIC: ZONES + S/R CONFLUENCE + TEND
# ==========================================
def get_dynamic_tf_settings(tf):
    """Adjusts zone width and S/R overlap buffer based on timeframe."""
    if tf == '1d':
        return 0.05, 0.02  # Max Zone width 5%, Pivot Overlap Buffer 2%
    elif tf == '1wk':
        return 0.10, 0.04  # Max Zone width 10%, Pivot Overlap Buffer 4%
    elif tf == '1mo':
        return 0.20, 0.08  # Max Zone width 20%, Pivot Overlap Buffer 8%
    elif tf == '3mo':
        return 0.30, 0.12  # Max Zone width 30%, Pivot Overlap Buffer 12%
    return 0.05, 0.02

def identify_pivots(df, window=5):
    """Finds historical Swing Highs and Swing Lows (Traditional S/R)"""
    df['Swing_High'] = df['High'] == df['High'].rolling(window=2*window+1, center=True).max()
    df['Swing_Low'] = df['Low'] == df['Low'].rolling(window=2*window+1, center=True).min()
    return df

def check_setup(df, tf, min_b, max_b, body_pct):
    df = df.dropna()
    if len(df) < 50: return None 
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    # EMAs for Trend
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    current = df.iloc[-1]
    
    # 1. MACRO TREND FILTER: Price >= 44 EMA and 44 EMA > 200 EMA
    if current['Close'] < current['EMA_44'] * 0.99 or current['EMA_44'] < current['EMA_200']:
        return None
        
    # Get Dynamic Settings based on TF
    max_zone_width, sr_buffer = get_dynamic_tf_settings(tf)
    
    df = identify_pivots(df)
    
    zones = []
    
    # 2. Find Confluence Demand Zones
    for i in range(15, len(df) - max_b - 2):
        setup_found = False
        
        for bases in range(min_b, max_b + 1):
            if setup_found: break 
            
            # Verify Boring Candles
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
                
            # Verify Strong Leg-out
            leg_idx = i + bases
            is_green = df['Close'].iloc[leg_idx] > df['Open'].iloc[leg_idx]
            leg_body_pct = (df['Body'].iloc[leg_idx] / df['Range'].iloc[leg_idx]) * 100 if df['Range'].iloc[leg_idx] > 0 else 0
            
            if not is_green or leg_body_pct < 50: 
                continue
                
            base_slice = df.iloc[i : i + bases]
            proximal = base_slice['High'].max()
            distal = base_slice['Low'].min()
            
            if df['Close'].iloc[leg_idx] <= proximal: 
                continue 
                
            # Filter 1: Check Dynamic Zone Width
            zone_width = (proximal - distal) / proximal
            if zone_width > max_zone_width:
                continue
                
            # Filter 2: STRUCTURAL CONFLUENCE (Must align with a historical pivot)
            # We look at all historical pivot points that happened *before* this zone was created
            historical_slice = df.iloc[:i]
            past_highs = historical_slice[historical_slice['Swing_High']]['High'].values
            past_lows = historical_slice[historical_slice['Swing_Low']]['Low'].values
            all_pivots = list(past_highs) + list(past_lows)
            
            has_confluence = False
            for pivot in all_pivots:
                # Does the pivot fall near our new Demand zone? (Using TF Buffer)
                if pivot >= distal * (1 - sr_buffer) and pivot <= proximal * (1 + sr_buffer):
                    has_confluence = True
                    break
                    
            if not has_confluence:
                continue # Zone is floating in the middle of nowhere. Reject it.
                    
            zones.append({
                'proximal': proximal,
                'distal': distal,
                'breakout_vol': df['Volume'].iloc[leg_idx],
                'index': leg_idx
            })
            setup_found = True 

    # 3. Validate Zones (Must not be broken)
    valid_zones = []
    for z in zones:
        future_data = df.iloc[z['index']+1 : -1] 
        if len(future_data) == 0: continue
        
        # Must have departed the zone slightly before returning
        if future_data['High'].max() < (z['proximal'] * 1.01): continue
        # Must not have closed below Distal (Stop Loss) line
        if not (future_data['Close'] < z['distal']).any():
            valid_zones.append(z)

    if not valid_zones: return None
    
    # 4. Check if LIVE Price is actively in the Demand Zone
    for z in reversed(valid_zones): 
        
        # Price dropped into Proximal, and hasn't broken Distal
        in_zone = (current['Low'] <= z['proximal'] * 1.01) and (current['Close'] >= z['distal'])
        volume_is_less = current['Volume'] < z['breakout_vol']

        if in_zone and volume_is_less:
            risk_pct = (abs(z['proximal'] - z['distal']) / z['proximal']) * 100
            
            return {
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "44 EMA": round(current['EMA_44'], 2),
                "Risk %": f"{risk_pct:.2f}%",
                "Confluence": "✅ S/R Verified"
            }
            
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan for Confluence Setups", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for structurally verified Demand Zones on {selected_tf_label}...")
        
        # Use max data to ensure 200 EMA and Historical Pivots can form on high TFs like 3-Month
        fetch_period = "max"
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=timeframe)
                if not df.empty:
                    setup = check_setup(df, timeframe, min_base, max_base, base_body_pct)
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
        st.subheader(f"📊 LIVE Confluence Demand Results ({selected_tf_label})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Target acquired. Stocks listed are in an active uptrend (Price $\ge$ 44 EMA $>$ 200 EMA) and have retraced into a structurally verified Demand Zone.")
        else:
            st.warning(f"No stocks found. No valid Demand Zones are aligning with traditional S/R pivots while maintaining the strict uptrend on the {selected_tf_label} timeframe.")
