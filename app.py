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
st.set_page_config(page_title="Advanced Structure S&D Scanner", layout="wide")
st.title("🎯 Trend & Structure S&D Scanner (LIVE)")
st.markdown("Scans for stocks strictly in-trend, requiring a <40% Boring Candle, Break of Structure (BOS), and a low-volume retracement into the zone.")

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

timeframe = st.sidebar.selectbox("Timeframe", ["1h", "1d", "1wk", "1mo"], index=1)

st.sidebar.header("🎯 Pattern Settings")

direction = st.sidebar.radio(
    "Scan Direction & Trend Filter",
    ("🟢 Demand (Only in Uptrend)", "🔴 Supply (Only in Downtrend)")
)

min_base, max_base = st.sidebar.slider("Number of Base Candles (Min - Max)", 
                                       min_value=1, max_value=3, value=(1, 3))

base_body_pct = st.sidebar.slider("Max Base Candle Body %", min_value=10, max_value=50, value=40, 
                                  help="Set to 40%. The body takes up max 40% of the candle's total high-to-low range.")

min_legout, max_legout = st.sidebar.slider("Number of Leg-out Candles (Min - Max)", 
                                           min_value=1, max_value=6, value=(1, 4))


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
# 3. CORE LOGIC: TREND, BOS, & STRICT ZONE
# ==========================================
def check_setup(df, dir_choice, min_b, max_b, min_leg, max_leg, body_pct):
    df = df.dropna()
    
    if len(df) < 200: return None # Need 200 periods for the 200 EMA Trend Filter
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    # Calculate Trend EMAs
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    is_bullish = "Demand" in dir_choice
    current = df.iloc[-1] # The LIVE market price right now
    
    # --- MACRO TREND FILTER ---
    # If looking for Demand, stock MUST be in an uptrend (Price > 50 EMA > 200 EMA)
    if is_bullish:
        if current['Close'] < current['EMA_50'] or current['EMA_50'] < current['EMA_200']:
            return None 
    # If looking for Supply, stock MUST be in a downtrend (Price < 50 EMA < 200 EMA)
    else:
        if current['Close'] > current['EMA_50'] or current['EMA_50'] > current['EMA_200']:
            return None 

    zones = []
    
    # Scan through history for the pattern matches
    for i in range(10, len(df) - max_b - max_leg - 1):
        setup_found = False
        
        for bases in range(min_b, max_b + 1):
            if setup_found: break 
            
            # 1. Base Candle Verification (< 40% Body Rule)
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
                
            # 2. Leg-out Streak Verification
            current_streak = 0
            vols = []
            
            for L in range(max_leg):
                idx = i + bases + L
                is_green = df['Close'].iloc[idx] > df['Open'].iloc[idx]
                
                if is_bullish and is_green:
                    current_streak += 1
                    vols.append(df['Volume'].iloc[idx])
                elif not is_bullish and not is_green:
                    current_streak += 1
                    vols.append(df['Volume'].iloc[idx])
                else:
                    break
                    
            if current_streak >= min_leg:
                actual_leg_len = min(current_streak, max_leg)
                avg_breakout_vol = sum(vols[:actual_leg_len]) / actual_leg_len
            else:
                continue
                
            # 3. Calculate Zone & Break of Structure (BOS)
            base_slice = df.iloc[i : i + bases]
            final_leg_close = df['Close'].iloc[i + bases + actual_leg_len - 1]
            
            if is_bullish:
                proximal = base_slice['High'].max()
                distal = base_slice['Low'].min()
                
                # BOS RULE: Break above the recent local swing high (Drop into the Base)
                local_swing_high = df['High'].iloc[max(0, i-3):i].max() if i > 3 else proximal
                bos_level = max(proximal, local_swing_high)
                
                if final_leg_close <= bos_level: 
                    continue 
            else:
                proximal = base_slice['Low'].min()
                distal = base_slice['High'].max()
                
                # BOS RULE: Break below the recent local swing low (Rally into the Base)
                local_swing_low = df['Low'].iloc[max(0, i-3):i].min() if i > 3 else proximal
                bos_level = min(proximal, local_swing_low)
                
                if final_leg_close >= bos_level: 
                    continue
                    
            zones.append({
                'proximal': proximal,
                'distal': distal,
                'breakout_vol': avg_breakout_vol,
                'index': i + bases + actual_leg_len - 1
            })
            setup_found = True 

    # Validate Zones: True Retracement (Must have departed the zone) & Not Broken
    valid_zones = []
    for z in zones:
        future_data = df.iloc[z['index']+1 : -1] 
        if len(future_data) == 0: continue
        
        if is_bullish:
            if future_data['High'].max() < (z['proximal'] * 1.015): continue
            if not (future_data['Close'] < z['distal']).any():
                valid_zones.append(z)
        else:
            if future_data['Low'].min() > (z['proximal'] * 0.985): continue
            if not (future_data['Close'] > z['distal']).any():
                valid_zones.append(z)

    if not valid_zones: return None
    
    # 4. Check ALL valid zones to see if the LIVE price is STRICTLY INSIDE one right now
    for z in reversed(valid_zones): 
        
        volume_is_less = current['Volume'] < z['breakout_vol']
        in_zone = False
        
        if is_bullish:
            # STRICT DEMAND: Live Low touched Proximal AND Live Close is still above Distal
            in_zone = (current['Low'] <= z['proximal']) and (current['Close'] >= z['distal'])
        else:
            # STRICT SUPPLY: Live High touched Proximal AND Live Close is still below Distal
            in_zone = (current['High'] >= z['proximal']) and (current['Close'] <= z['distal'])

        if in_zone and volume_is_less:
            risk_pct = (abs(z['proximal'] - z['distal']) / z['proximal']) * 100
            
            return {
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "Zone Risk": f"{risk_pct:.2f}%",
                "Vol Dry-Up": "✅ Yes",
                "Trend": "Uptrend" if is_bullish else "Downtrend"
            }
            
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Start Structured Scan", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for Structure Breaks & Low Volume Pullbacks...")
        
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
                    setup = check_setup(df, direction, min_base, max_base, min_legout, max_legout, base_body_pct)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append({
                            "Ticker": setup['Ticker'],
                            "Trend": setup['Trend'],
                            "Live Price": setup['Live Price'],
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
        st.subheader(f"📊 LIVE {direction[:2]} 'In Zone' Results ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Target acquired. Stocks listed are actively trading inside a Trend-Aligned, BOS-Confirmed zone on lower volume.")
        else:
            st.warning(f"No stocks found. The market is either not aligned with the trend, or no pullbacks match the strict BOS criteria right now.")
