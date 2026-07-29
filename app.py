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
st.title("🎯 Strict 'In The Zone' S&D Scanner (LIVE MARKET)")
st.markdown("Scans for stocks where the LIVE price has pulled back and is STRICTLY INSIDE a previously made Base Zone.")

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
    "Scan Direction",
    ("🟢 Bullish (Demand Zone)", "🔴 Bearish (Supply Zone)")
)

min_base, max_base = st.sidebar.slider("Number of Base Candles (Min - Max)", 
                                       min_value=1, max_value=6, value=(1, 4))

base_body_pct = st.sidebar.slider("Max Base Candle Body %", min_value=20, max_value=80, value=50, 
                                  help="50% means the body takes up max half of the candle's total high-to-low range.")

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
# 3. CORE LOGIC: STRICT ZONE CHECK & VOLUME
# ==========================================
def check_setup(df, dir_choice, min_b, max_b, min_leg, max_leg, body_pct):
    df = df.dropna()
    
    # CRITICAL FIX: Removed `df = df.iloc[:-1]` so the scanner evaluates the LIVE unclosed candle.
    if len(df) < 50: return None
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    is_bullish = "Bullish" in dir_choice
    zones = []
    
    # Scan through history for the pattern matches
    for i in range(10, len(df) - max_b - max_leg - 1):
        
        setup_found = False
        
        for bases in range(min_b, max_b + 1):
            if setup_found: break 
            
            # 1. Base Candle Verification
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
                
            # 3. Calculate Zone Entry & SL
            base_slice = df.iloc[i : i + bases]
            final_leg_close = df['Close'].iloc[i + bases + actual_leg_len - 1]
            
            if is_bullish:
                proximal = base_slice['High'].max()
                distal = base_slice['Low'].min()
                if final_leg_close <= proximal: 
                    continue 
            else:
                proximal = base_slice['Low'].min()
                distal = base_slice['High'].max()
                if final_leg_close >= proximal: 
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
        future_data = df.iloc[z['index']+1 : -1] # Look at all candles between breakout and today
        if len(future_data) == 0: continue
        
        if is_bullish:
            # Must have departed at least 1.5% away from zone
            if future_data['High'].max() < (z['proximal'] * 1.015):
                continue
            # Must not have closed below stop loss
            if not (future_data['Close'] < z['distal']).any():
                valid_zones.append(z)
        else:
            if future_data['Low'].min() > (z['proximal'] * 0.985):
                continue
            if not (future_data['Close'] > z['distal']).any():
                valid_zones.append(z)

    if not valid_zones: return None
    
    current = df.iloc[-1] # The LIVE market price right now
    
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
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for {min_base}-{max_base} Base, {min_legout}-{max_legout} Legout {direction} Zones...")
        
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
        st.subheader(f"📊 LIVE {direction} 'In Zone' Results ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Target acquired. The stocks listed have their live market price sitting strictly inside a valid zone on low volume.")
        else:
            st.warning(f"No stocks found sitting exactly inside a zone matching your criteria right now.")
