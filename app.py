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
st.set_page_config(page_title="S&D + 44 EMA Scanner", layout="wide")
st.title("🎯 S&D + 44 EMA Dynamic Support Scanner (LIVE)")
st.markdown("Scans for stocks retracing into a verified Boring Candle Demand/Supply Zone that perfectly coincides with the 44 EMA as dynamic Support/Resistance.")

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
    ("🟢 Demand (At 44 EMA Support)", "🔴 Supply (At 44 EMA Resistance)")
)

min_base, max_base = st.sidebar.slider("Number of Base (Boring) Candles (Min - Max)", 
                                       min_value=1, max_value=5, value=(1, 3))

base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=60, value=40, 
                                  help="40% means it's a true doji/boring candle (body is small compared to wicks).")

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
# 3. CORE LOGIC: ZONES + 44 EMA + LIVE CHECK
# ==========================================
def check_setup(df, dir_choice, min_b, max_b, body_pct):
    df = df.dropna()
    if len(df) < 100: return None
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    
    is_bullish = "Demand" in dir_choice
    current = df.iloc[-1] # The LIVE market price right now
    
    zones = []
    
    # Scan through history for the pattern matches (leaving room for leg-outs and live price)
    for i in range(10, len(df) - max_b - 2):
        setup_found = False
        
        for bases in range(min_b, max_b + 1):
            if setup_found: break 
            
            # 1. Base Candle Verification (Strictly smaller than max body %)
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
                
            # 2. Leg-out Verification (Must be a strong explosive move away from the base)
            leg_idx = i + bases
            is_green = df['Close'].iloc[leg_idx] > df['Open'].iloc[leg_idx]
            leg_body_pct = (df['Body'].iloc[leg_idx] / df['Range'].iloc[leg_idx]) * 100 if df['Range'].iloc[leg_idx] > 0 else 0
            
            # Leg out must be healthy (body > 50% of its range) and in the right direction
            if is_bullish:
                if not is_green or leg_body_pct < 50: continue
            else:
                if is_green or leg_body_pct < 50: continue
                
            # 3. Calculate Zone
            base_slice = df.iloc[i : i + bases]
            final_leg_close = df['Close'].iloc[leg_idx]
            
            if is_bullish:
                proximal = base_slice['High'].max()
                distal = base_slice['Low'].min()
                if final_leg_close <= proximal: continue 
            else:
                proximal = base_slice['Low'].min()
                distal = base_slice['High'].max()
                if final_leg_close >= proximal: continue
                    
            zones.append({
                'proximal': proximal,
                'distal': distal,
                'breakout_vol': df['Volume'].iloc[leg_idx],
                'index': leg_idx
            })
            setup_found = True 

    # 4. Validate Zones: Must have reacted away previously, and not been broken yet
    valid_zones = []
    for z in zones:
        future_data = df.iloc[z['index']+1 : -1] 
        if len(future_data) == 0: continue
        
        if is_bullish:
            # Reaction Check: Price must have pushed at least 2% away from the zone before coming back
            if future_data['High'].max() < (z['proximal'] * 1.02): continue
            # Invalidation Check: Price must never have closed below the stop loss line
            if not (future_data['Close'] < z['distal']).any():
                valid_zones.append(z)
        else:
            if future_data['Low'].min() > (z['proximal'] * 0.98): continue
            if not (future_data['Close'] > z['distal']).any():
                valid_zones.append(z)

    if not valid_zones: return None
    
    # 5. Check LIVE Price & 44 EMA Confluence
    for z in reversed(valid_zones): 
        
        live_ema = current['EMA_44']
        in_zone = False
        ema_confluence = False
        
        if is_bullish:
            # RULE A: In Zone? (Live Low touched Proximal, Live Close above Distal)
            in_zone = (current['Low'] <= z['proximal']) and (current['Close'] >= z['distal'])
            
            # RULE B: 44 EMA Support? (Live price is above EMA, AND EMA is sitting near/inside the zone)
            price_above_ema = current['Close'] > live_ema
            ema_at_zone = (live_ema >= z['distal'] * 0.98) and (live_ema <= z['proximal'] * 1.02)
            ema_confluence = price_above_ema and ema_at_zone
            
        else:
            # RULE A: In Zone? (Live High touched Proximal, Live Close below Distal)
            in_zone = (current['High'] >= z['proximal']) and (current['Close'] <= z['distal'])
            
            # RULE B: 44 EMA Resistance? (Live price is below EMA, AND EMA is sitting near/inside the zone)
            price_below_ema = current['Close'] < live_ema
            ema_at_zone = (live_ema <= z['distal'] * 1.02) and (live_ema >= z['proximal'] * 0.98)
            ema_confluence = price_below_ema and ema_at_zone

        # Check Volume Dry Up
        volume_is_less = current['Volume'] < z['breakout_vol']

        if in_zone and ema_confluence and volume_is_less:
            risk_pct = (abs(z['proximal'] - z['distal']) / z['proximal']) * 100
            
            return {
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "44 EMA": round(live_ema, 2),
                "Risk %": f"{risk_pct:.2f}%",
                "Setup Valid": "✅ Yes"
            }
            
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan Market", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for {min_base}-{max_base} Base Zones at 44 EMA Support/Resistance...")
        
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
                    setup = check_setup(df, direction, min_base, max_base, base_body_pct)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append({
                            "Ticker": setup['Ticker'],
                            "Live Price": setup['Live Price'],
                            "44 EMA": setup['44 EMA'],
                            "Zone Entry": setup['Zone Entry'],
                            "Stop Loss": setup['Stop Loss'],
                            "Risk %": setup['Risk %']
                        })
            except:
                pass
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 LIVE S&D + 44 EMA Results ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Target acquired. Stocks listed are actively trading inside a valid zone that is directly supported by the 44 EMA.")
        else:
            st.warning(f"No stocks found. None are currently pulling back to a zone that aligns perfectly with the 44 EMA.")
