import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. PREMIUM UI / UX & CUSTOM CSS
# ==========================================
st.set_page_config(page_title="Institutional S&D Engine", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    
    .gradient-text {
        font-weight: 800; font-size: 42px;
        background: -webkit-linear-gradient(45deg, #FF512F, #DD2476);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px; padding-bottom: 0px;
    }
    .sub-text { font-size: 16px; color: #8892B0; margin-top: -10px; margin-bottom: 30px; }

    div.stButton > button:first-child {
        background: linear-gradient(90deg, #FF512F 0%, #DD2476 100%);
        color: white; border: none; border-radius: 8px;
        padding: 12px 24px; font-size: 18px; font-weight: 600;
        box-shadow: 0 4px 15px rgba(221, 36, 118, 0.4);
        transition: all 0.3s ease; width: 100%;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px); box-shadow: 0 6px 20px rgba(221, 36, 118, 0.6);
    }
    
    .css-1d391kg { background-color: #1A1D24; }
    div[data-testid="metric-container"] {
        background-color: #1A1D24; border-radius: 10px; padding: 15px;
        border: 1px solid #2D3748; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">INSTITUTIONAL S&D ENGINE</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">High-Speed Base & Leg-Out Zone Locator</p>', unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR DASHBOARD
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2942/2942265.png", width=60)
    st.markdown("### **Terminal Configuration**")
    st.divider()

    st.markdown("#### 🌍 Market Universe")
    sector_options = [
        "F&O Stocks (~223+)", "Non-F&O Stocks (Nifty 500 base)", 
        "Nifty 50", "Nifty 500", "Nifty Midcap 100"
    ]
    selected_sector = st.selectbox("Select Asset Class", sector_options, index=0, label_visibility="collapsed")

    st.markdown("#### ⏱️ Timeframe Architecture")
    tf_options = {"6 Months": "6mo", "3 Months": "3mo", "1 Month": "1mo", "1 Week": "1wk", "1 Day": "1d", "75 Min": "75m"}
    tf_label = st.selectbox("Scan Timeframe", list(tf_options.keys()), index=4)
    timeframe = tf_options[tf_label]

    st.markdown("#### 🎯 Sector Direction")
    direction = st.radio("Trade Vector", ("🟢 Bullish (Demand Zones)", "🔴 Bearish (Supply Zones)"))

    st.markdown("#### 📐 Structural Strictness")
    base_count = st.slider("Base Candles (Min - Max)", 1, 10, (1, 3))
    legout_count = st.slider("Leg-Out Candles (Min - Max)", 1, 5, (1, 2))
    
    base_body = st.slider("Base Body Size % (Min - Max)", 0, 100, (0, 50))
    legout_body = st.slider("Leg-Out Body Size % (Min - Max)", 50, 100, (75, 100))

# ==========================================
# 3. DATA ARCHITECTURE
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    import requests, io
    fo_stocks_list = [
        "360ONE", "AARTIIND", "ABB", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ACC", "ADANIENSOL", "ADANIENT", "ADANIPORTS", 
        "ADANIPOWER", "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE", "APLAPOLLO", "APOLLOHOSP", "APOLLOTYRE", "ASHOKLEY", 
        "ASIANPAINT", "ASTRAL", "ATUL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJAJHLDNG", 
        "BAJFINANCE", "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BANKBARODA", "BANKINDIA", "BATAINDIA", "BDL", "BEL", 
        "BERGEPAINT", "BHARATFORG", "BHARTIARTL", "BHEL", "BIOCON", "BLUESTARCO", "BOSCHLTD", "BPCL", "BRITANNIA", "BSE", 
        "BSOFT", "CAMS", "CANBK", "CANFINHOME", "CDSL", "CEATLTD", "CGPOWER", "CHAMBLFERT", "CHOLAFIN", "CIPLA", 
        "COALINDIA", "COCHINSHIP", "COFORGE", "COLPAL", "CONCOR", "COROMANDEL", "CROMPTON", "CUB", "CUMMINSIND", "CYIENT", 
        "DABUR", "DALBHARAT", "DEEPAKNTR", "DIVISLAB", "DIXON", "DLF", "DRREDDY", "EICHERMOT", "ESCORTS", "EXIDEIND", 
        "FEDERALBNK", "FORCEMOT", "FORTIS", "GAIL", "GLENMARK", "GMRINFRA", "GNFC", "GODFRYPHLP", "GODREJCP", "GODREJPROP", 
        "GRANULES", "GRASIM", "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", 
        "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "HUDCO", "HYUNDAI", "ICICIBANK", "ICICIGI", "ICICIPRULI", 
        "IDEA", "IDFCFIRSTB", "IEX", "IGL", "INDHOTEL", "INDIACEM", "INDIAMART", "INDIGO", "INDUSINDBK", "INDUSTOWER", 
        "INFY", "INTELLECT", "IOC", "IPCALAB", "IRCTC", "IRFC", "ITC", "JINDALSTEL", "JIOFIN", "JKCEMENT", "JSWENERGY", 
        "JSWSTEEL", "JUBLFOOD", "KALYANKJIL", "KAYNES", "KEI", "KFINTECH", "KOTAKBANK", "KPITTECH", "LALPATHLAB", 
        "LAURUSLABS", "LICHSGFIN", "LT", "LTIM", "LTTS", "LUPIN", "M&M", "M&MFIN", "MANAPPURAM", "MANKIND", "MARICO", 
        "MARUTI", "MAXHEALTH", "MAZDOCK", "MCDOWELL-N", "MCX", "METROPOLIS", "MFSL", "MGL", "MOTHERSON", "MOTILALOFS", 
        "MPHASIS", "MRF", "MUTHOOTFIN", "NAM-INDIA", "NATIONALUM", "NAUKRI", "NAVINFLUOR", "NCC", "NESTLEIND", "NHPC", 
        "NMDC", "NTPC", "NUVAMA", "OBEROIRLTY", "OFSS", "OIL", "ONGC", "ORACLE", "PAGEIND", "PEL", "PERSISTENT", 
        "PETRONET", "PFC", "PGEL", "PHARMA", "PIDILITIND", "PIIND", "PNB", "POLYCAB", "POONAWALLA", "POWERGRID", 
        "POWERINDIA", "PPLPHARMA", "PREMIERENE", "PRESTIGE", "PVRINOX", "RAMCOCEM", "RBLBANK", "RECLTD", "RELIANCE", 
        "RVNL", "SAIL", "SAMMAANCAP", "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SJVN", 
        "SONACOMS", "SRF", "SUNPHARMA", "SUNTV", "SUPREMEIND", "SUZLON", "SWIGGY", "SYNGENE", "TATACHEM", "TATACOMM", 
        "TATACONSUM", "TATAELXSI", "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TITAN", "TORNTPHARM", 
        "TORNTPOWER", "TRENT", "TVSMOTOR", "UBL", "ULTRACEMCO", "UNIONBANK", "UPLLTD", "VEDL", "VMM", "VOLTAS", 
        "WAAREEENER", "WIPRO", "YESBANK", "ZEEL", "ZOMATO", "ZYDUSLIFE"
    ]
    if "F&O Stocks" in sector_name: return [f"{ticker}.NS" for ticker in fo_stocks_list]
        
    csv_file = {
        "Nifty 50": "ind_nifty50list.csv", "Nifty 500": "ind_nifty500list.csv",
        "Non-F&O Stocks (Nifty 500 base)": "ind_nifty500list.csv", "Nifty Midcap 100": "ind_niftymidcap100list.csv"
    }.get(sector_name, "ind_nifty500list.csv")
    
    mirrors = [
        f"https://raw.githubusercontent.com/althk/zerobha/main/{csv_file}",
        f"https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/{csv_file}"
    ]
    
    fetched_list = []
    for url in mirrors:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                symbol_col = next((col for col in df.columns if 'Symbol' in col or 'SYMBOL' in col), None)
                if symbol_col:
                    fetched_list = [str(s).strip() for s in df[symbol_col]]
                    break 
        except Exception: continue
            
    if not fetched_list: return []
    if "Non-F&O" in sector_name:
        return [f"{ticker}.NS" for ticker in fetched_list if ticker not in fo_stocks_list]
    return [f"{ticker}.NS" for ticker in fetched_list]

# ==========================================
# 4. MATH & SIGNAL LOGIC
# ==========================================
def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

def resample_macro(df, period):
    return df.resample(period).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

def check_sd_zone(df, is_bullish, b_min, b_max, l_min, l_max, b_body_min, b_body_max, l_body_min, l_body_max):
    if len(df) < 50: return None
    
    current_price = df.iloc[-1]['Close']
    valid_zones = []
    
    max_window = b_max + l_max
    
    for i in range(1, len(df) - max_window):
        # Test all combinations of base length and leg-out length within user limits
        for b_len in range(b_min, b_max + 1):
            for l_len in range(l_min, l_max + 1):
                
                base_slice = df.iloc[i : i + b_len]
                legout_slice = df.iloc[i + b_len : i + b_len + l_len]
                
                # --- Base Validation ---
                base_valid = True
                for _, candle in base_slice.iterrows():
                    rng = candle['High'] - candle['Low']
                    body_pct = 0 if rng == 0 else (abs(candle['Close'] - candle['Open']) / rng) * 100
                    if not (b_body_min <= body_pct <= b_body_max):
                        base_valid = False
                        break
                if not base_valid: continue
                
                # --- Leg-Out Validation ---
                legout_valid = True
                for _, candle in legout_slice.iterrows():
                    rng = candle['High'] - candle['Low']
                    body_pct = 0 if rng == 0 else (abs(candle['Close'] - candle['Open']) / rng) * 100
                    
                    if not (l_body_min <= body_pct <= l_body_max):
                        legout_valid = False
                        break
                        
                    # Direction check
                    if is_bullish and candle['Close'] <= candle['Open']: legout_valid = False
                    if not is_bullish and candle['Close'] >= candle['Open']: legout_valid = False
                        
                if not legout_valid: continue
                
                # --- Zone Mapping ---
                base_high = base_slice['High'].max()
                base_low = base_slice['Low'].min()
                
                # Leg-out must clear the base explicitly
                if is_bullish:
                    if legout_slice['Close'].iloc[-1] <= base_high: continue
                    proximal = base_high
                    distal = base_low
                else:
                    if legout_slice['Close'].iloc[-1] >= base_low: continue
                    proximal = base_low
                    distal = base_high
                    
                # --- Freshness Validation (Unbroken) ---
                future_data = df.iloc[i + b_len + l_len :]
                zone_broken = False
                
                if not future_data.empty:
                    if is_bullish and (future_data['Close'] < distal).any(): zone_broken = True
                    if not is_bullish and (future_data['Close'] > distal).any(): zone_broken = True
                        
                if not zone_broken:
                    zone_type = "Demand Zone" if is_bullish else "Supply Zone"
                    valid_zones.append({
                        "Zone Type": zone_type,
                        "Base Pattern": f"{b_len} Base ➔ {l_len} Leg-Out",
                        "Live Price": round(current_price, 2),
                        "Entry (Proximal)": round(proximal, 2),
                        "SL (Distal)": round(distal, 2),
                        "Risk %": f"{((abs(proximal - distal) / max(proximal, 0.01)) * 100):.2f}%"
                    })
                    
    # Return the most recent fresh zone found
    if valid_zones: return valid_zones[-1]
    return None

# ==========================================
# 5. EXECUTION & DASHBOARD METRICS
# ==========================================
col1, col2, col3 = st.columns([1, 1, 1])

if st.button("🚀 INITIATE S&D BATCH SCAN", type="primary"):
    is_bull_setup = "Demand" in direction
    
    with st.spinner("Establishing Secure Connection & Fetching Market Universe..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        with col1: st.metric("Universe Loaded", f"{len(ticker_list)} Assets")
        with col2: st.metric("Timeframe", f"{tf_label}")
        with col3: st.metric("Status", "Processing Data Packets...")

        period_val = "max" if timeframe in ['3mo', '6mo'] else {"1mo": "15y", "1wk": "10y", "1d": "5y", "75m": "60d"}.get(timeframe, "5y")
        interval_val = "1mo" if timeframe in ['3mo', '6mo'] else ("15m" if timeframe == "75m" else timeframe)
        
        tickers_str = " ".join(ticker_list)
        progress_bar = st.progress(10)
        
        # Batch Download Data
        market_data = yf.download(tickers_str, period=period_val, interval=interval_val, group_by='ticker', threads=True)
        progress_bar.progress(60)
        
        results = []
        for ticker in ticker_list:
            try:
                df = market_data if len(ticker_list) == 1 else market_data[ticker]
                df = df.dropna()
                
                if not df.empty:
                    if timeframe == '3mo': df = resample_macro(df, '3ME')
                    elif timeframe == '6mo': df = resample_macro(df, '6ME')
                    elif timeframe == '75m': df = resample_to_75m(df)
                    
                    setup = check_sd_zone(
                        df, is_bull_setup, 
                        base_count[0], base_count[1], 
                        legout_count[0], legout_count[1], 
                        base_body[0], base_body[1], 
                        legout_body[0], legout_body[1]
                    )
                    
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except Exception:
                pass
                
        progress_bar.progress(100)
        progress_bar.empty()
        
        st.divider()
        st.markdown(f"### 📊 Active {direction[:2]} Signals")
        
        if results:
            final_df = pd.DataFrame(results)[['Asset', 'Zone Type', 'Base Pattern', 'Live Price', 'Entry (Proximal)', 'SL (Distal)', 'Risk %']]
            
            styled_df = final_df.style.set_properties(**{
                'background-color': '#1A1D24',
                'color': '#FAFAFA',
                'border-color': '#2D3748'
            }).map(lambda v: 'color: #00e676; font-weight: bold;' if 'Demand' in str(v) else ('color: #ff5252; font-weight: bold;' if 'Supply' in str(v) else ''), subset=['Zone Type'])
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info("No active zones found matching your strict structural parameters on this timeframe.")
