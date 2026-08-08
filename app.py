import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import concurrent.futures

warnings.filterwarnings('ignore')

# ==========================================
# 1. PREMIUM UI / UX & CUSTOM CSS
# ==========================================
st.set_page_config(page_title="Apex Pivot S&R Engine", layout="wide", initial_sidebar_state="expanded")

# Injecting Custom CSS for a Professional Terminal Feel
st.markdown("""
    <style>
    /* Main Background & Text */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* Gradient Title */
    .gradient-text {
        font-weight: 800;
        font-size: 42px;
        background: -webkit-linear-gradient(45deg, #00C6FF, #0072FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
        padding-bottom: 0px;
    }
    .sub-text {
        font-size: 16px;
        color: #8892B0;
        margin-top: -10px;
        margin-bottom: 30px;
    }

    /* Styled Buttons */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 18px;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(56, 239, 125, 0.4);
        transition: all 0.3s ease;
        width: 100%;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(56, 239, 125, 0.6);
    }

    /* Sidebar Styling */
    .css-1d391kg {
        background-color: #1A1D24;
    }
    
    /* Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #1A1D24;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #2D3748;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">APEX PIVOT ENGINE</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">High-Speed Support & Resistance Breakout/Retest Terminal</p>', unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR DASHBOARD
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2942/2942265.png", width=60)
    st.markdown("### **Terminal Configuration**")
    st.divider()

    st.markdown("#### 🌍 Market Universe")
    sector_options = [
        "F&O Stocks (~223+)",
        "Non-F&O Stocks (Nifty 500 base)",
        "Nifty 50",
        "Nifty 500",
        "Nifty Midcap 100"
    ]
    selected_sector = st.selectbox("Select Asset Class", sector_options, index=0, label_visibility="collapsed")

    st.markdown("#### ⏱️ Timeframe Architecture")
    col1, col2 = st.columns(2)
    with col1:
        macro_options = {"6 Months": "6mo", "3 Months": "3mo", "1 Month": "1mo", "1 Week": "1wk", "1 Day": "1d"}
        macro_label = st.selectbox("Macro Trend", list(macro_options.keys()), index=2)
        macro_tf = macro_options[macro_label]
    with col2:
        exec_options = {"1 Month": "1mo", "1 Week": "1wk", "1 Day": "1d", "75 Min": "75m"}
        exec_label = st.selectbox("Execution", list(exec_options.keys()), index=2)
        exec_tf = exec_options[exec_label]

    st.markdown("#### 🛡️ Trend Validation")
    require_macro_ema = st.toggle("Require Macro 44>200 EMA", value=False)
    exec_ema_filter = st.selectbox("Execution EMA Confluence", ["None (Pure PA)", "Near 44 EMA", "Near 200 EMA"])

    st.markdown("#### 🎯 Execution Strategy")
    direction = st.radio("Trade Vector", ("🟢 Long (Support Retest)", "🔴 Short (Resistance Retest)"))

    st.markdown("#### ⚙️ Engine Tolerances")
    swing_length = st.slider("Pivot Strength (Candles)", 3, 15, 5)
    atr_multiplier = st.slider("ATR Hit-Box Buffer", 0.1, 2.0, 0.5, 0.1)

# ==========================================
# 3. DATA ARCHITECTURE
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
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

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return np.max(ranges, axis=1).rolling(window=period).mean()

def check_macro_trend(df, is_bullish):
    if len(df) < 200: return False
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    curr = df.iloc[-1]
    if is_bullish: return (curr['Close'] > curr['EMA_44']) and (curr['EMA_44'] > curr['EMA_200'])
    else: return (curr['Close'] < curr['EMA_44']) and (curr['EMA_44'] < curr['EMA_200'])

def check_snr_retest(df, is_bullish, swing_len, atr_mult, ema_choice):
    if len(df) < 100: return None
    df['ATR'] = calculate_atr(df)
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    window = swing_len * 2 + 1
    df['Swing_High'] = df['High'][(df['High'] == df['High'].rolling(window, center=True).max())]
    df['Swing_Low'] = df['Low'][(df['Low'] == df['Low'].rolling(window, center=True).min())]
    
    current = df.iloc[-1]
    current_atr = current['ATR'] if not pd.isna(current['ATR']) else (current['High'] - current['Low'])
    
    valid_setups = []
    
    if is_bullish:
        swing_highs = df['Swing_High'].dropna()
        for idx, resistance_price in swing_highs.items():
            if df.index.get_loc(idx) > len(df) - (swing_len + 3): continue
            future_data = df.loc[idx:]
            
            breakouts = future_data[future_data['Close'] > resistance_price]
            if breakouts.empty: continue
            
            bos_idx = breakouts.index[0]
            post_bos = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
            if not post_bos.empty and (post_bos['Close'] < resistance_price).any(): continue 
                
            atr_allowance = current_atr * atr_mult
            if current['Low'] <= (resistance_price + atr_allowance) and current['Close'] >= resistance_price:
                ema_passed = True
                ema_str = "—"
                if "44" in ema_choice:
                    ema_passed = (current['EMA_44'] >= resistance_price) and (current['EMA_44'] <= resistance_price + (current_atr * 2))
                    ema_str = f"{current['EMA_44']:.1f}"
                elif "200" in ema_choice:
                    ema_passed = (current['EMA_200'] >= resistance_price) and (current['EMA_200'] <= resistance_price + (current_atr * 2))
                    ema_str = f"{current['EMA_200']:.1f}"
                    
                if ema_passed:
                    valid_setups.append({
                        "Signal": "🟢 Long Retest",
                        "Live Price": round(current['Close'], 2),
                        "Pivot Line": round(resistance_price, 2),
                        "EMA Match": ema_str,
                        "Status": "Active"
                    })
    else:
        swing_lows = df['Swing_Low'].dropna()
        for idx, support_price in swing_lows.items():
            if df.index.get_loc(idx) > len(df) - (swing_len + 3): continue
            future_data = df.loc[idx:]
            
            breakdowns = future_data[future_data['Close'] < support_price]
            if breakdowns.empty: continue
            
            bos_idx = breakdowns.index[0]
            post_bos = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
            if not post_bos.empty and (post_bos['Close'] > support_price).any(): continue 
                
            atr_allowance = current_atr * atr_mult
            if current['High'] >= (support_price - atr_allowance) and current['Close'] <= support_price:
                ema_passed = True
                ema_str = "—"
                if "44" in ema_choice:
                    ema_passed = (current['EMA_44'] <= support_price) and (current['EMA_44'] >= support_price - (current_atr * 2))
                    ema_str = f"{current['EMA_44']:.1f}"
                elif "200" in ema_choice:
                    ema_passed = (current['EMA_200'] <= support_price) and (current['EMA_200'] >= support_price - (current_atr * 2))
                    ema_str = f"{current['EMA_200']:.1f}"
                    
                if ema_passed:
                    valid_setups.append({
                        "Signal": "🔴 Short Retest",
                        "Live Price": round(current['Close'], 2),
                        "Pivot Line": round(support_price, 2),
                        "EMA Match": ema_str,
                        "Status": "Active"
                    })

    if valid_setups: return valid_setups[-1]
    return None

# ==========================================
# 5. EXECUTION & DASHBOARD METRICS
# ==========================================
col1, col2, col3 = st.columns([1, 1, 1])

if st.button("🚀 INITIATE APEX SCAN", type="primary"):
    is_bull_setup = "Long" in direction
    
    with st.spinner("Establishing Secure Connection & Fetching Market Universe..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        # Dashboard Metrics Update
        with col1: st.metric("Universe Loaded", f"{len(ticker_list)} Assets")
        with col2: st.metric("Macro Trend Filter", f"{'Enabled' if require_macro_ema else 'Disabled'}")
        with col3: st.metric("Status", "Processing Packets...")

        macro_period_val = "max" if macro_tf in ['3mo', '6mo'] else "10y"
        macro_interval_val = "1mo" if macro_tf in ['3mo', '6mo'] else macro_tf
        exec_period_val = {"1mo": "15y", "1wk": "10y", "1d": "5y", "75m": "60d"}.get(exec_tf, "5y")
        exec_interval_val = "15m" if exec_tf == "75m" else exec_tf
        
        tickers_str = " ".join(ticker_list)
        
        progress_bar = st.progress(10)
        
        macro_data = None
        if require_macro_ema:
            # Removed show_errors=False to fix the yfinance version compatibility issue
            macro_data = yf.download(tickers_str, period=macro_period_val, interval=macro_interval_val, group_by='ticker', threads=True)
            
        progress_bar.progress(50)
        # Removed show_errors=False to fix the yfinance version compatibility issue
        exec_data = yf.download(tickers_str, period=exec_period_val, interval=exec_interval_val, group_by='ticker', threads=True)
        
        progress_bar.progress(85)
        
        results = []
        for ticker in ticker_list:
            try:
                macro_passed = True
                
                if require_macro_ema and macro_data is not None:
                    macro_passed = False
                    df_macro = macro_data if len(ticker_list) == 1 else macro_data[ticker]
                    df_macro = df_macro.dropna()
                    
                    if not df_macro.empty:
                        if macro_tf == '3mo': df_macro = resample_macro(df_macro, '3ME')
                        if macro_tf == '6mo': df_macro = resample_macro(df_macro, '6ME')
                        if len(df_macro) > 200:
                            macro_passed = check_macro_trend(df_macro, is_bull_setup)
                
                if macro_passed:
                    df_exec = exec_data if len(ticker_list) == 1 else exec_data[ticker]
                    df_exec = df_exec.dropna()
                    
                    if not df_exec.empty:
                        if exec_tf == '75m': df_exec = resample_to_75m(df_exec)
                        setup = check_snr_retest(df_exec, is_bull_setup, swing_length, atr_multiplier, exec_ema_filter)
                        if setup:
                            setup['Asset'] = ticker.replace(".NS", "")
                            results.append(setup)
                            
            except Exception:
                pass
                
        progress_bar.progress(100)
        progress_bar.empty()
        
        st.divider()
        st.markdown("### 📊 Active Execution Signals")
        
        if results:
            final_df = pd.DataFrame(results)[['Asset', 'Signal', 'Live Price', 'Pivot Line', 'EMA Match', 'Status']]
            
            # Apply styling to the dataframe
            styled_df = final_df.style.set_properties(**{
                'background-color': '#1A1D24',
                'color': '#FAFAFA',
                'border-color': '#2D3748'
            }).map(lambda v: 'color: #00e676; font-weight: bold;' if 'Long' in str(v) else ('color: #ff5252; font-weight: bold;' if 'Short' in str(v) else ''), subset=['Signal'])
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info("No active signals found matching the current terminal parameters.")
