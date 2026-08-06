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
st.set_page_config(page_title="Advanced S&D + BOS Flipper", layout="wide")
st.title("🎯 Advanced S&D + BOS Flip Scanner")
st.markdown("Scans for pure Demand/Supply bases OR old zones that have been broken with high volume and flipped their role (Supply turned Demand).")

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

st.sidebar.header("🎯 Trade Strategy")
direction = st.sidebar.radio(
    "Select Setup Direction",
    ("🟢 Bullish (Buy Setups)", "🔴 Bearish (Sell Setups)")
)

zone_strategy = st.sidebar.radio(
    "Select Zone Strategy",
    (
        "Standard (Pure S&D Zones)", 
        "Flipped / BOS Retest (Role Reversal)"
    ),
    help="Flipped searches for old Supply that was shattered upside with volume, and is now acting as Demand."
)

st.sidebar.header("📐 Base Candle Settings")
min_base, max_base = st.sidebar.slider("Number of Base Candles (Min - Max)", min_value=1, max_value=5, value=(1, 3))
base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=80, value=45)

st.sidebar.header("📈 Optional EMA Confluence")
ema_filter = st.sidebar.radio(
    "Require EMA Support/Resistance at the Zone?",
    (
        "None (Price Action Only)", 
        "Must be near 44 EMA", 
        "Must be near 200 EMA"
    )
)

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
# 3. CORE LOGIC: S&D + BOS FLIPS
# ==========================================
def resample_to_75m(df):
    resampled = df.resample('75min', offset='15min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return resampled

def check_setup(df, dir_choice, strategy_choice, min_b, max_b, body_pct, ema_choice):
    df = df.dropna()
    if len(df) < 200: return None 
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Vol_SMA'] = df['Volume'].rolling(window=20).mean()
    
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    is_bullish = "Bullish" in dir_choice
    is_flipped = "Flipped" in strategy_choice
    current = df.iloc[-1]
    
    target_zones = []
    
    # 1. SCAN HISTORY FOR ALL PATTERNS
    for i in range(2, len(df) - max_b - 1):
        setup_found = False
        
        for bases in range(min_b, max_b + 1):
            if setup_found: break 
            
            leg_in_idx = i - 1
            leg_in_is_green = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
            leg_in_type = "R" if leg_in_is_green else "D" 
            
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
                
            leg_idx = i + bases
            leg_is_green = df['Close'].iloc[leg_idx] > df['Open'].iloc[leg_idx]
            leg_range = df['Range'].iloc[leg_idx]
            leg_body_pct = (df['Body'].iloc[leg_idx] / leg_range) * 100 if leg_range > 0 else 0
            
            if leg_body_pct < 50:
                continue
                
            base_slice = df.iloc[i : i + bases]
            highest_base = base_slice['High'].max()
            lowest_base = base_slice['Low'].min()
            
            # Record Raw Zones
            if leg_is_green and df['Close'].iloc[leg_idx] > highest_base:
                target_zones.append({
                    'raw_type': 'Demand',
                    'pattern': f"{leg_in_type}BR",
                    'proximal': highest_base,  
                    'distal': lowest_base,     
                    'index': leg_idx
                })
                setup_found = True
            elif not leg_is_green and df['Close'].iloc[leg_idx] < lowest_base:
                target_zones.append({
                    'raw_type': 'Supply',
                    'pattern': f"{leg_in_type}BD",
                    'proximal': lowest_base,   
                    'distal': highest_base,    
                    'index': leg_idx
                })
                setup_found = True

    # 2. FILTER & PROCESS BASED ON USER STRATEGY
    final_zones = []
    
    for z in target_zones:
        future_data = df.iloc[z['index']+1 : -1] 
        
        if not is_flipped:
            # STANDARD S&D LOGIC
            if len(future_data) == 0:
                if (is_bullish and z['raw_type'] == 'Demand') or (not is_bullish and z['raw_type'] == 'Supply'):
                    final_zones.append(z)
                continue
                
            if is_bullish and z['raw_type'] == 'Demand':
                if not (future_data['Close'] < z['distal']).any():
                    final_zones.append(z)
            elif not is_bullish and z['raw_type'] == 'Supply':
                if not (future_data['Close'] > z['distal']).any():
                    final_zones.append(z)
                    
        else:
            # FLIPPED / BOS RETEST LOGIC
            if len(future_data) == 0: continue
            
            if is_bullish and z['raw_type'] == 'Supply':
                # Looking for an old Supply zone that was broken upside with high volume
                breakouts = future_data[future_data['Close'] > z['distal']]
                
                if not breakouts.empty:
                    bos_idx = breakouts.index[0]
                    # Ensure it broke out with above average volume (The KALYAN JEWELLERS rule)
                    if df['Volume'].loc[bos_idx] > df['Vol_SMA'].loc[bos_idx]:
                        
                        # Verify it hasn't been destroyed downside since flipping
                        post_bos_data = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
                        
                        if post_bos_data.empty or not (post_bos_data['Close'] < z['proximal']).any():
                            final_zones.append({
                                'pattern': f"Flipped {z['pattern']} (BOS)",
                                'proximal': z['distal'],  # Old top becomes new entry floor
                                'distal': z['proximal'],  # Old bottom becomes new SL
                                'index': bos_idx
                            })
                            
            elif not is_bullish and z['raw_type'] == 'Demand':
                # Looking for an old Demand zone that was broken downside with high volume
                breakdowns = future_data[future_data['Close'] < z['distal']]
                
                if not breakdowns.empty:
                    bos_idx = breakdowns.index[0]
                    if df['Volume'].loc[bos_idx] > df['Vol_SMA'].loc[bos_idx]:
                        
                        post_bos_data = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
                        
                        if post_bos_data.empty or not (post_bos_data['Close'] > z['proximal']).any():
                            final_zones.append({
                                'pattern': f"Flipped {z['pattern']} (BOS)",
                                'proximal': z['distal'],  # Old bottom becomes new entry ceiling
                                'distal': z['proximal'],  # Old top becomes new SL
                                'index': bos_idx
                            })

    if not final_zones: return None
    
    # 3. LIVE PRICE & EMA CHECK
    for z in reversed(final_zones): 
        is_in_zone = False
        ema_passed = True
        
        if is_bullish:
            # Low taps zone, Close hasn't hit stop loss
            is_in_zone = (current['Low'] <= z['proximal']) and (current['Close'] >= z['distal'])
        else:
            # High taps zone, Close hasn't hit stop loss
            is_in_zone = (current['High'] >= z['proximal']) and (current['Close'] <= z['distal'])

        # Check Optional EMA Filter
        if "44 EMA" in ema_choice:
            ema_val = current['EMA_44']
            ema_distance = abs(ema_val - z['proximal']) / z['proximal']
            if ema_distance > 0.03: ema_passed = False
                
        elif "200 EMA" in ema_choice:
            ema_val = current['EMA_200']
            ema_distance = abs(ema_val - z['proximal']) / z['proximal']
            if ema_distance > 0.03: ema_passed = False

        if is_in_zone and ema_passed:
            risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
            
            ema_col_text = "N/A"
            if "44 EMA" in ema_choice: ema_col_text = f"44 EMA: {current['EMA_44']:.2f}"
            if "200 EMA" in ema_choice: ema_col_text = f"200 EMA: {current['EMA_200']:.2f}"
            
            return {
                "Pattern": z['pattern'],
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "Risk %": f"{risk_pct:.2f}%",
                "EMA Confluence": ema_col_text,
                "Status": "✅ IN ZONE"
            }
            
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Launch Scanner", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for active {direction[:2]} setups...")
        
        if timeframe == '75m':
            fetch_period, fetch_interval = "60d", "15m"
        elif timeframe == '1d':
            fetch_period, fetch_interval = "2y", "1d"
        elif timeframe == '1wk':
            fetch_period, fetch_interval = "5y", "1wk"
        else:
            fetch_period, fetch_interval = "10y", "1mo"
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=fetch_interval)
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                        
                    setup = check_setup(df, direction, zone_strategy, min_base, max_base, base_body_pct, ema_filter)
                    
                    if setup:
                        results.append({
                            'Ticker': ticker.replace(".NS", ""),
                            'Pattern': setup['Pattern'],
                            'Live Price': setup['Live Price'],
                            'Zone Entry': setup['Zone Entry'],
                            'Stop Loss': setup['Stop Loss'],
                            'Risk %': setup['Risk %'],
                            'EMA Confluence': setup['EMA Confluence'],
                            'Status': setup['Status']
                        })
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
            cols = ['Ticker', 'Pattern', 'Live Price', 'Zone Entry', 'Stop Loss', 'Risk %', 'EMA Confluence', 'Status']
            final_df = final_df[cols]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Scan Complete. Target setups acquired.")
        else:
            st.warning(f"No stocks found. The market is not presenting this exact setup on this timeframe right now.")
