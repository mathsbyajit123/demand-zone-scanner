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
st.set_page_config(page_title="Advanced S&D Zone & Flip Engine", layout="wide")
st.title("🎯 S&D Pattern & Flip Zone Scanner")
st.markdown("Identifies strict RBR, DBR, RBD, DBD patterns and tracks old zones that have flipped (e.g., Supply turned Demand).")

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
    ("🟢 Bullish (Demand & Flipped Supply)", "🔴 Bearish (Supply & Flipped Demand)")
)

st.sidebar.header("📐 Zone Settings")
min_base, max_base = st.sidebar.slider("Number of Base Candles (Min - Max)", min_value=1, max_value=5, value=(1, 3))
base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=60, value=40, 
                                  help="40% means the body is max 40% of the total candle range.")

st.sidebar.header("🔓 Volume Rules")
require_low_vol = st.sidebar.checkbox("✅ Require Lower Volume on Retracement", value=True, 
                                      help="If checked, the pullback volume MUST be strictly lower than the breakout volume.")

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
# 3. CORE LOGIC: ZONE CALCULATION & FLIPS
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

def check_setup(df, dir_choice, min_b, max_b, body_pct, buffer_pct, req_low_vol):
    df = df.dropna()
    if len(df) < 30: return None 
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    is_bullish = "Bullish" in dir_choice
    current = df.iloc[-1]
    
    all_historical_zones = []
    
    # 1. SCAN HISTORY FOR ALL PATTERNS (RBR, DBR, RBD, DBD)
    for i in range(2, len(df) - max_b - 1):
        setup_found = False
        
        for bases in range(min_b, max_b + 1):
            if setup_found: break 
            
            # A. Evaluate Leg-In (Candle before the base)
            leg_in_idx = i - 1
            leg_in_is_green = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
            leg_in_type = "R" if leg_in_is_green else "D" # Rally or Drop
            
            # B. Check if Base Candles are "Boring"
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
                
            # C. Evaluate Leg-Out Strength & Close
            leg_idx = i + bases
            leg_is_green = df['Close'].iloc[leg_idx] > df['Open'].iloc[leg_idx]
            leg_range = df['Range'].iloc[leg_idx]
            leg_body_pct = (df['Body'].iloc[leg_idx] / leg_range) * 100 if leg_range > 0 else 0
            
            if leg_body_pct < 50:
                continue
                
            base_slice = df.iloc[i : i + bases]
            highest_base = base_slice['High'].max()
            lowest_base = base_slice['Low'].min()
            
            # D. Categorize the Zone
            if leg_is_green and df['Close'].iloc[leg_idx] > highest_base:
                # Demand Zone
                pattern = f"{leg_in_type}BR" # RBR or DBR
                all_historical_zones.append({
                    'type': pattern,
                    'category': 'Demand',
                    'proximal': highest_base,  
                    'distal': lowest_base,     
                    'breakout_vol': df['Volume'].iloc[leg_idx],
                    'index': leg_idx
                })
                setup_found = True
                
            elif not leg_is_green and df['Close'].iloc[leg_idx] < lowest_base:
                # Supply Zone
                pattern = f"{leg_in_type}BD" # RBD or DBD
                all_historical_zones.append({
                    'type': pattern,
                    'category': 'Supply',
                    'proximal': lowest_base,   
                    'distal': highest_base,    
                    'breakout_vol': df['Volume'].iloc[leg_idx],
                    'index': leg_idx
                })
                setup_found = True

    # 2. VALIDATE ZONES & PROCESS FLIPS
    active_target_zones = []
    
    for z in all_historical_zones:
        future_data = df.iloc[z['index']+1 : -1] # Up to yesterday
        
        if z['category'] == 'Demand':
            if len(future_data) == 0:
                if is_bullish: active_target_zones.append(z)
                continue
                
            # Did it break downside?
            broken_downside = future_data[future_data['Close'] < z['distal']]
            
            if broken_downside.empty:
                # Unbroken Demand Zone
                if is_bullish: active_target_zones.append(z)
            else:
                # Flipped to Supply Zone
                if not is_bullish:
                    break_idx = broken_downside.index[0]
                    post_flip = df.loc[break_idx+1 : current.name - pd.Timedelta(days=1)]
                    
                    # Ensure it wasn't re-broken upside after flipping
                    if post_flip.empty or not (post_flip['Close'] > z['proximal']).any():
                        active_target_zones.append({
                            'type': f"Flipped {z['type']}",
                            'category': 'Supply',
                            'proximal': z['distal'], # Old bottom becomes new entry
                            'distal': z['proximal'], # Old top becomes new SL
                            'breakout_vol': df['Volume'].loc[break_idx],
                            'index': break_idx
                        })
                        
        elif z['category'] == 'Supply':
            if len(future_data) == 0:
                if not is_bullish: active_target_zones.append(z)
                continue
                
            # Did it break upside?
            broken_upside = future_data[future_data['Close'] > z['distal']]
            
            if broken_upside.empty:
                # Unbroken Supply Zone
                if not is_bullish: active_target_zones.append(z)
            else:
                # Flipped to Demand Zone
                if is_bullish:
                    break_idx = broken_upside.index[0]
                    post_flip = df.loc[break_idx+1 : current.name - pd.Timedelta(days=1)]
                    
                    # Ensure it wasn't re-broken downside after flipping
                    if post_flip.empty or not (post_flip['Close'] < z['proximal']).any():
                        active_target_zones.append({
                            'type': f"Flipped {z['type']}",
                            'category': 'Demand',
                            'proximal': z['distal'], # Old top becomes new entry
                            'distal': z['proximal'], # Old bottom becomes new SL
                            'breakout_vol': df['Volume'].loc[break_idx],
                            'index': break_idx
                        })

    if not active_target_zones: return None
    
    # 3. LIVE PRICE PROXIMITY & VOLUME CHECK
    buffer_mult_bull = 1 + (buffer_pct / 100)
    buffer_mult_bear = 1 - (buffer_pct / 100)
    
    for z in reversed(active_target_zones): 
        in_zone = False
        
        if is_bullish: # Checking Active Demand or Flipped Supply
            low_tapped = current['Low'] <= (z['proximal'] * buffer_mult_bull)
            close_held = current['Close'] >= z['distal']
            close_near = current['Close'] <= (z['proximal'] * buffer_mult_bull)
            in_zone = low_tapped and close_held and close_near
        else: # Checking Active Supply or Flipped Demand
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
            
            # Status Text
            if is_bullish:
                status = "✅ IN ZONE" if current['Close'] <= z['proximal'] else f"⏳ NEAR ZONE (<{buffer_pct}%)"
            else:
                status = "✅ IN ZONE" if current['Close'] >= z['proximal'] else f"⏳ NEAR ZONE (<{buffer_pct}%)"
            
            return {
                "Pattern": z['type'],
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "Risk %": f"{risk_pct:.2f}%",
                "Vol Dry-Up": "✅ Yes" if current['Volume'] < z['breakout_vol'] else "❌ No",
                "Status": status
            }
            
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Launch Scanner", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        # Determine Dynamic Buffer based on Timeframe
        dynamic_buffer = {
            "75m": 0.5,
            "1d": 2.0,
            "1wk": 3.0,
            "1mo": 5.0
        }.get(timeframe, 2.0)
        
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for {direction[:2]} patterns on the {selected_tf_label} timeframe (Dynamic Buffer: {dynamic_buffer}%)...")
        
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
                        
                    setup = check_setup(df, direction, min_base, max_base, base_body_pct, dynamic_buffer, require_low_vol)
                    
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
        st.subheader(f"📊 {direction[:2]} Scan Results ({selected_tf_label})")
        
        if results:
            final_df = pd.DataFrame(results)
            # Reorder columns for readability
            cols = ['Ticker', 'Pattern', 'Live Price', 'Zone Entry', 'Stop Loss', 'Risk %', 'Vol Dry-Up', 'Status']
            final_df = final_df[cols]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Scan Complete. Found stocks actively testing labeled zones within your {dynamic_buffer}% timeframe allowance.")
        else:
            st.warning(f"No stocks found matching the criteria right now within the {dynamic_buffer}% allowance.")
