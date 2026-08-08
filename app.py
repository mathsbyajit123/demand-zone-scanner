import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. APEX TERMINAL UI & CUSTOM CSS
# ==========================================
st.set_page_config(page_title="Apex Live Retest Terminal", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Dark Matter Background */
    .stApp { background-color: #090B10; color: #E2E8F0; }
    
    /* Cyber-Gold & Cyan Typography */
    .gradient-text {
        font-weight: 900; font-size: 46px; letter-spacing: -1px;
        background: -webkit-linear-gradient(45deg, #00F2FE, #4FACFE, #F6D365);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px; padding-bottom: 0px; text-transform: uppercase;
    }
    .sub-text { font-size: 15px; color: #64748B; margin-top: -5px; margin-bottom: 35px; letter-spacing: 1px; text-transform: uppercase; font-weight: 600;}

    /* Execution Button */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #00C6FF 0%, #0072FF 100%);
        color: white; border: none; border-radius: 6px;
        padding: 14px 24px; font-size: 16px; font-weight: 700; letter-spacing: 2px;
        box-shadow: 0 4px 20px rgba(0, 198, 255, 0.4);
        transition: all 0.3s ease; width: 100%; text-transform: uppercase;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px); box-shadow: 0 6px 25px rgba(0, 198, 255, 0.6);
    }
    
    /* Sidebar & Metrics */
    .css-1d391kg { background-color: #11151C; border-right: 1px solid #1E293B; }
    div[data-testid="metric-container"] {
        background-color: #11151C; border-radius: 8px; padding: 20px;
        border: 1px solid #1E293B; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    div[data-testid="metric-container"] label { color: #4FACFE !important; font-weight: 600; letter-spacing: 1px; }
    div[data-testid="metric-container"] div { color: #F8FAFC !important; }
    </style>
""", unsafe_allow_html=True)

# Circular UI Injector
def render_hud_progress(progress, status_text):
    html = f"""
    <div style="display: flex; flex-direction: column; align-items: center; margin: 50px 0px;">
        <div style="
            width: 180px; height: 180px; border-radius: 50%;
            background: conic-gradient(#00C6FF {progress}%, #1E293B 0);
            display: flex; justify-content: center; align-items: center;
            box-shadow: 0 0 30px rgba(0, 198, 255, 0.2);
        ">
            <div style="
                width: 165px; height: 165px; border-radius: 50%;
                background-color: #090B10; display: flex; flex-direction: column;
                justify-content: center; align-items: center;
                font-size: 38px; font-weight: 900; color: #F8FAFC;
            ">
                {int(progress)}<span style="font-size: 16px; color: #64748B;">%</span>
            </div>
        </div>
        <p style="color: #4FACFE; font-size: 16px; margin-top: 25px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">{status_text}</p>
    </div>
    """
    return html

st.markdown('<p class="gradient-text">APEX RETEST TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Active Zone Penetration & Execution Engine</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER (SIDEBAR)
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()

    st.markdown("#### 🌍 DATA FEED")
    sector_options = [
        "F&O Stocks (~223+)", "Non-F&O Stocks (Nifty 500 base)", 
        "Nifty 50", "Nifty 500", "Nifty Midcap 100"
    ]
    selected_sector = st.selectbox("Market Universe", sector_options, index=0, label_visibility="collapsed")

    st.markdown("#### ⏱️ TIMEFRAME")
    tf_options = {"1 Day": "1d", "75 Min": "75m", "1 Week": "1wk"}
    tf_label = st.selectbox("Resolution", list(tf_options.keys()), index=0)
    timeframe = tf_options[tf_label]

    st.markdown("#### 🎯 VECTOR")
    direction = st.radio("Execution Bias", ("🟢 Long (Live in Demand)", "🔴 Short (Live in Supply)"))

    st.markdown("#### 📐 GEOMETRY STRICTNESS")
    st.info("Locked to Max 2 Bases & 2 Leg-Outs for strict institutional structure.")
    max_base_body = st.slider("Max Base Body %", 10, 50, 40)
    min_leg_body = st.slider("Min Leg-Out Body %", 60, 100, 70)

# ==========================================
# 3. UNIVERSE ROUTING
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
# 4. ACTIVE RETEST ENGINE 
# ==========================================
def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

def check_active_retest(df, is_bullish, b_body_max, l_body_min):
    # Enforce freshness: We only care about zones formed in the last 45 bars.
    # This prevents the "running for a month with no result" issue.
    df = df.tail(45) 
    if len(df) < 10: return None
    
    current_price = df.iloc[-1]['Close']
    current_low = df.iloc[-1]['Low']
    current_high = df.iloc[-1]['High']
    
    for i in range(len(df) - 3, 0, -1):
        for b_len in [1, 2]:
            for l_len in [1, 2]:
                if i + b_len + l_len >= len(df): continue
                
                base_slice = df.iloc[i : i + b_len]
                legout_slice = df.iloc[i + b_len : i + b_len + l_len]
                
                # Verify Base Squeeze
                base_valid = True
                for _, candle in base_slice.iterrows():
                    rng = candle['High'] - candle['Low']
                    body_pct = 0 if rng == 0 else (abs(candle['Close'] - candle['Open']) / rng) * 100
                    if body_pct > b_body_max:
                        base_valid = False
                        break
                if not base_valid: continue
                
                # Verify Leg-Out Power
                legout_valid = True
                for _, candle in legout_slice.iterrows():
                    rng = candle['High'] - candle['Low']
                    body_pct = 0 if rng == 0 else (abs(candle['Close'] - candle['Open']) / rng) * 100
                    if body_pct < l_body_min: legout_valid = False
                    if is_bullish and candle['Close'] <= candle['Open']: legout_valid = False
                    if not is_bullish and candle['Close'] >= candle['Open']: legout_valid = False
                if not legout_valid: continue
                
                # Define Zone Bounds (Body to Wick)
                if is_bullish:
                    highest_body = max(base_slice['Open'].max(), base_slice['Close'].max())
                    proximal = highest_body
                    distal = base_slice['Low'].min()
                    if legout_slice['Close'].iloc[-1] <= proximal: continue
                else:
                    lowest_body = min(base_slice['Open'].min(), base_slice['Close'].min())
                    proximal = lowest_body
                    distal = base_slice['High'].max()
                    if legout_slice['Close'].iloc[-1] >= proximal: continue
                    
                # -------------------------------------------------------------
                # THE LIVE RETEST FILTER
                # -------------------------------------------------------------
                future_data = df.iloc[i + b_len + l_len : -1] # Everything between leg-out and CURRENT live candle
                
                is_stale_or_broken = False
                time_in_zone = 0
                
                if not future_data.empty:
                    for _, past_candle in future_data.iterrows():
                        # Did it break the zone completely?
                        if is_bullish and past_candle['Close'] < distal: is_stale_or_broken = True
                        if not is_bullish and past_candle['Close'] > distal: is_stale_or_broken = True
                        
                        # Has it been chopping inside the zone for too long? (> 5 candles inside = stale)
                        if is_bullish and (past_candle['Low'] <= proximal and past_candle['Close'] >= distal): time_in_zone += 1
                        if not is_bullish and (past_candle['High'] >= proximal and past_candle['Close'] <= distal): time_in_zone += 1
                        
                if time_in_zone > 5: is_stale_or_broken = True
                
                # Is it trading inside the zone RIGHT NOW?
                is_active_now = False
                if is_bullish:
                    if current_low <= proximal and current_price >= distal: is_active_now = True
                else:
                    if current_high >= proximal and current_price <= distal: is_active_now = True
                
                # Final Execution Trigger
                if not is_stale_or_broken and is_active_now:
                    risk_pct = (abs(proximal - distal) / max(proximal, 0.01)) * 100
                    return {
                        "Zone Type": "🟢 Active Demand" if is_bullish else "🔴 Active Supply",
                        "Live Price": round(current_price, 2),
                        "Entry (Proximal)": round(proximal, 2),
                        "SL (Distal)": round(distal, 2),
                        "Risk %": f"{risk_pct:.2f}%",
                        "Status": "🎯 TRADING IN ZONE"
                    }
    return None

# ==========================================
# 5. EXECUTION 
# ==========================================
col1, col2, col3 = st.columns([1, 1, 1])

if st.button("⚡ EXECUTE SYSTEM SCAN", type="primary"):
    is_bull_setup = "Long" in direction
    
    with st.spinner("Authenticating Data Feed..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        with col1: st.metric("TRACKING", f"{len(ticker_list)} ASSETS")
        with col2: st.metric("RESOLUTION", f"{tf_label}")
        with col3: st.metric("VECTOR", "LONG" if is_bull_setup else "SHORT")

        period_val = "1y" if timeframe == "1wk" else ("60d" if timeframe == "75m" else "6mo")
        interval_val = "15m" if timeframe == "75m" else timeframe
        
        tickers_str = " ".join(ticker_list)
        
        progress_ui = st.empty()
        progress_ui.markdown(render_hud_progress(5, "PULLING MARKET DATA..."), unsafe_allow_html=True)
        
        market_data = yf.download(tickers_str, period=period_val, interval=interval_val, group_by='ticker', threads=True)
        progress_ui.markdown(render_hud_progress(50, "ISOLATING LIVE RETESTS..."), unsafe_allow_html=True)
        
        results = []
        total_tickers = len(ticker_list)
        
        for i, ticker in enumerate(ticker_list):
            try:
                df = market_data if len(ticker_list) == 1 else market_data[ticker]
                df = df.dropna()
                
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    
                    setup = check_active_retest(df, is_bull_setup, max_base_body, min_leg_body)
                    
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except Exception:
                pass
            
            if i % 15 == 0 or i == total_tickers - 1:
                current_prog = 50 + ((i + 1) / total_tickers * 50)
                progress_ui.markdown(render_hud_progress(current_prog, f"SCANNING {ticker.replace('.NS', '')}"), unsafe_allow_html=True)
                
        progress_ui.empty()
        
        st.divider()
        st.markdown(f"### 🎯 ACTIONABLE TARGETS ACQUIRED")
        
        if results:
            final_df = pd.DataFrame(results)[['Asset', 'Zone Type', 'Live Price', 'Entry (Proximal)', 'SL (Distal)', 'Risk %', 'Status']]
            
            styled_df = final_df.style.set_properties(**{
                'background-color': '#11151C',
                'color': '#F8FAFC',
                'border-color': '#1E293B'
            }).map(lambda v: 'color: #00F2FE; font-weight: 800;' if 'TRADING IN ZONE' in str(v) else ('color: #4FACFE;' if 'Demand' in str(v) else 'color: #FF512F;'), subset=['Status', 'Zone Type'])
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.warning("0 MATCHES. No assets are actively testing an unmitigated zone right now.")
