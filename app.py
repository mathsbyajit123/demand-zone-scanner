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
st.set_page_config(page_title="S&D + 44/200 EMA Scanner", layout="wide")
st.title("🎯 S&D + Dynamic Trend (44 & 200 EMA) Scanner")
st.markdown("Scans for stocks retracing into a verified Boring Candle Zone, perfectly aligned with your chosen EMA confluence.")

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
    ("🟢 Demand (Bullish)", "🔴 Supply (Bearish)")
)

min_base, max_base = st.sidebar.slider("Number of Base (Boring) Candles (Min - Max)", 
                                       min_value=1, max_value=5, value=(1, 3))

base_body_pct = st.sidebar.slider("Max Boring Candle Body %", min_value=10, max_value=60, value=40, 
                                  help="40% means it's a true doji/boring candle (body is small compared to wicks).")

st.sidebar.header("📈 Trend Filter Options")

trend_option = st.sidebar.radio(
    "Select EMA Confluence Rule",
    (
        "1. 44 EMA Support (Must be at Zone)", 
        "2. Above 200 EMA (Macro Trend Only, 44 EMA anywhere)", 
        "3. Both (44 EMA at Zone + Above 200 EMA)"
    )
)

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
# 3. CORE LOGIC: ZONES + 44/200 EMA + LIVE CHECK
# ==========================================
def check_setup(df, dir_choice, min_b, max_b, body_pct, trend_choice):
    df = df.dropna()
    if len(df) < 200: return None # Need 200 periods for the 200 EMA
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    is_bullish = "Demand" in dir_choice
    current = df.iloc[-1] # LIVE market price
    
    zones = []
    
    # Scan through history for the pattern matches
    for i in range(10, len(df) - max_b - 2):
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
                
            # 2. Leg-out Verification
            leg_idx = i + bases
            is_green = df['Close'].iloc[leg_idx] > df['Open'].iloc[leg_idx]
            leg_body_pct = (df['Body'].iloc[leg_idx] / df['Range'].iloc[leg_idx]) * 100 if df['Range'].iloc[leg_idx] > 0 else 0
            
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
            if future_data['High'].max() < (z['proximal'] * 1.02): continue
            if not (future_data['Close'] < z['distal']).any():
                valid_zones.append(z)
        else:
            if future_data['Low'].min() > (z['proximal'] * 0.98): continue
            if not (future_data['Close'] > z['distal']).any():
                valid_zones.append(z)

    if not valid_zones: return None
    
    # 5. Check LIVE Price & EMA Confluence Rules
    for z in reversed(valid_zones): 
        
        live_ema_44 = current['EMA_44']
        live_ema_200 = current['EMA_200']
        
        in_zone = False
        ema_44_confluence = True
        ema_200_confluence = True
        
        # Determine which rules are active based on UI choice
        req_44 = "44 EMA" in trend_choice or "Both" in trend_choice
        req_200 = "200 EMA" in trend_choice or "Both" in trend_choice
        
        if is_bullish:
            # In Zone?
            in_zone = (current['Low'] <= z['proximal']) and (current['Close'] >= z['distal'])
            
            if req_44:
                price_above_44 = current['Close'] > live_ema_44
                ema_at_zone = (live_ema_44 >= z['distal'] * 0.98) and (live_ema_44 <= z['proximal'] * 1.02)
                ema_44_confluence = price_above_44 and ema_at_zone
                
            if req_200:
                # 44 EMA > 200 EMA and Price > 200 EMA
                ema_200_confluence = (live_ema_44 > live_ema_200) and (current['Close'] > live_ema_200)
            
        else:
            # In Zone?
            in_zone = (current['High'] >= z['proximal']) and (current['Close'] <= z['distal'])
            
            if req_44:
                price_below_44 = current['Close'] < live_ema_44
                ema_at_zone = (live_ema_44 <= z['distal'] * 1.02) and (live_ema_44 >= z['proximal'] * 0.98)
                ema_44_confluence = price_below_44 and ema_at_zone
                
            if req_200:
                # 44 EMA < 200 EMA and Price < 200 EMA
                ema_200_confluence = (live_ema_44 < live_ema_200) and (current['Close'] < live_ema_200)

        # Check Volume Dry Up
        volume_is_less = current['Volume'] < z['breakout_vol']

        if in_zone and ema_44_confluence and ema_200_confluence and volume_is_less:
            risk_pct = (abs(z['proximal'] - z['distal']) / z['proximal']) * 100
            
            return {
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "44 EMA": round(live_ema_44, 2),
                "200 EMA": round(live_ema_200, 2),
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
        st.info(f"Loaded {len(ticker_list)} stocks. Executing Strict S&D EMA Scan...")
        
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
                    setup = check_setup(df, direction, min_base, max_base, base_body_pct, trend_option)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append({
                            "Ticker": setup['Ticker'],
                            "Live Price": setup['Live Price'],
                            "44 EMA": setup['44 EMA'],
                            "200 EMA": setup['200 EMA'],
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
        st.subheader(f"📊 LIVE S&D Results ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Target acquired. Stocks listed match your exact S&D parameters and EMA trend rules.")
        else:
            st.warning(f"No stocks found. None are currently pulling back to a zone that matches your strict EMA trend filters.")
