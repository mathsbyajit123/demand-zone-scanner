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
st.set_page_config(page_title="Custom S&D Scanner", layout="wide")
st.title("🎯 Fully Custom Supply & Demand Scanner")
st.markdown("Scan exactly the way you trade. Define your own Base and Leg-Out rules.")

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

# Added 1h timeframe
timeframe = st.sidebar.selectbox("Timeframe", ["1h", "1d", "1wk", "1mo"], index=1)

st.sidebar.header("🎯 Pattern Settings")

direction = st.sidebar.radio(
    "Scan Direction",
    ("🟢 Bullish (Demand Zone)", "🔴 Bearish (Supply Zone)")
)

num_base = st.sidebar.slider("Number of Base Candles", min_value=1, max_value=6, value=2)

# Slider to control how "small" the base candle has to be (e.g., 50% means body is half the total range)
base_body_pct = st.sidebar.slider("Max Base Candle Body %", min_value=20, max_value=80, value=50, 
                                  help="50% means the body takes up max half of the candle's total high-to-low range.")

num_legout = st.sidebar.slider("Number of Leg-out Candles", min_value=1, max_value=6, value=1)


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
# 3. CORE LOGIC: CUSTOM PATTERNS & VOLUME
# ==========================================
def check_setup(df, dir_choice, bases, legouts, body_pct):
    df = df.dropna()
    if len(df) > 0: df = df.iloc[:-1] # Ignore current unclosed candle
    if len(df) < 50: return None
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    is_bullish = "Bullish" in dir_choice
    zones = []
    
    total_len = bases + legouts
    
    # Scan through history for the exact pattern match
    for i in range(10, len(df) - total_len - 1):
        
        # 1. Check if the sequence has the exact number of Base Candles
        base_valid = True
        for b in range(bases):
            idx = i + b
            # Prevent divide by zero if range is 0
            if df['Range'].iloc[idx] == 0: 
                base_valid = False
                break
            
            candle_body_pct = (df['Body'].iloc[idx] / df['Range'].iloc[idx]) * 100
            if candle_body_pct > body_pct:
                base_valid = False
                break
                
        if not base_valid:
            continue
            
        # 2. Check if the sequence has the exact number of Leg-out Candles
        legout_valid = True
        legout_vols = []
        for L in range(legouts):
            idx = i + bases + L
            is_green = df['Close'].iloc[idx] > df['Open'].iloc[idx]
            
            if is_bullish and not is_green:
                legout_valid = False
                break
            if not is_bullish and is_green:
                legout_valid = False
                break
                
            legout_vols.append(df['Volume'].iloc[idx])
            
        if not legout_valid:
            continue
            
        # 3. Calculate Zone and verify true breakout
        base_slice = df.iloc[i : i + bases]
        final_leg_close = df['Close'].iloc[i + bases + legouts - 1]
        
        if is_bullish:
            proximal = base_slice['High'].max()
            distal = base_slice['Low'].min()
            if final_leg_close <= proximal: # Breakout must clear the highest base point
                continue 
        else:
            proximal = base_slice['Low'].min()
            distal = base_slice['High'].max()
            if final_leg_close >= proximal: # Breakdown must clear the lowest base point
                continue
                
        avg_breakout_vol = sum(legout_vols) / len(legout_vols)
        
        zones.append({
            'proximal': proximal,
            'distal': distal,
            'breakout_vol': avg_breakout_vol,
            'index': i + bases + legouts - 1
        })

    # Validate Zones: Make sure price hasn't already broken the stop loss level
    valid_zones = []
    for z in zones:
        future_data = df.iloc[z['index']+2 : ]
        if len(future_data) == 0: continue
        
        if is_bullish:
            if not (future_data['Close'] < z['distal']).any():
                valid_zones.append(z)
        else:
            if not (future_data['Close'] > z['distal']).any():
                valid_zones.append(z)

    if not valid_zones: return None
    
    # Check the most recent valid zone against today's price
    latest_zone = valid_zones[-1] 
    current = df.iloc[-1]
    
    # 4. Retracement Rule & Volume Rule
    volume_is_less = current['Volume'] < latest_zone['breakout_vol']
    
    if is_bullish:
        # Near Demand: Low is within 1.5% above proximal, Close is strictly above distal
        near_zone = current['Low'] <= (latest_zone['proximal'] * 1.015) and current['Close'] >= latest_zone['distal']
    else:
        # Near Supply: High is within 1.5% below proximal, Close is strictly below distal
        near_zone = current['High'] >= (latest_zone['proximal'] * 0.985) and current['Close'] <= latest_zone['distal']

    if near_zone and volume_is_less:
        risk_pct = (abs(latest_zone['proximal'] - latest_zone['distal']) / latest_zone['proximal']) * 100
        
        return {
            "Price": round(current['Close'], 2),
            "Zone Entry": round(latest_zone['proximal'], 2),
            "Stop Loss": round(latest_zone['distal'], 2),
            "Zone Risk": f"{risk_pct:.2f}%",
            "Vol Dry-Up": "✅ Yes"
        }
        
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Start Custom Scan", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for {num_base}-Base, {num_legout}-Legout {direction} Zones...")
        
        # yfinance limits 1h data to max 730 days. Auto-adjusting periods to prevent crashes.
        if timeframe == '1h':
            fetch_period = "730d"
        elif timeframe == '1d':
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
                    setup = check_setup(df, direction, num_base, num_legout, base_body_pct)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append({
                            "Ticker": setup['Ticker'],
                            "Price": setup['Price'],
                            "Zone Entry": setup['Zone Entry'],
                            "Stop Loss": setup['Stop Loss'],
                            "Risk %": setup['Zone Risk'],
                            "Volume Check": setup['Vol Dry-Up']
                        })
            except:
                pass
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 {direction} Results ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Target acquired. Stocks listed match your exact Base and Leg-out rules on lower retracement volume.")
        else:
            st.warning(f"No stocks found pulling back to a zone matching your specific criteria right now.")
