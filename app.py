import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SETTINGS
# ==========================================
st.set_page_config(page_title="Pure S&R Retest Scanner", layout="wide")
st.title("⚡ Pure Support & Resistance (Break & Retest) Scanner")
st.markdown("Scans strictly for major horizontal Swing Highs/Lows that were broken and are now being retested. Zero Supply/Demand mechanics.")

st.sidebar.header("⚙️ Market Settings")
sector_options = [
    "F&O Stocks (~223+)",
    "Non-F&O Stocks (Nifty 500 base)",
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options, index=0)

st.sidebar.header("⏱️ Timeframe Alignment")
htf_options = {"6 Months": "6mo", "3 Months": "3mo", "1 Month": "1mo", "1 Week": "1wk", "1 Day": "1d"}
ltf_options = {"1 Month": "1mo", "1 Week": "1wk", "1 Day": "1d", "75 Minutes (Intraday)": "75m"}

htf_label = st.sidebar.selectbox("Higher Timeframe (HTF)", list(htf_options.keys()), index=2)
ltf_label = st.sidebar.selectbox("Lower Timeframe (LTF) - Trading TF", list(ltf_options.keys()), index=2)

htf = htf_options[htf_label]
ltf = ltf_options[ltf_label]

st.sidebar.header("📈 Trend & EMA Settings")
require_htf_ema = st.sidebar.checkbox(
    "✅ Require HTF Trend (44 > 200 EMA)", 
    value=False, 
    help="Uncheck if using 3M/6M HTF to bypass the 200 EMA data limit."
)
ltf_ema_filter = st.sidebar.radio(
    "Require LTF EMA Support at S&R Line?",
    ("None (Pure Price Action)", "Near 44 EMA", "Near 200 EMA")
)

st.sidebar.header("🎯 Setup Direction")
direction = st.sidebar.radio("Trade Setup", ("🟢 Bullish (Broken Resistance flipped to Support)", "🔴 Bearish (Broken Support flipped to Resistance)"))

st.sidebar.header("📐 Swing Point Strictness")
swing_length = st.sidebar.slider(
    "Swing Point Strength (Candles)", 
    min_value=3, max_value=15, value=5, 
    help="How major the Support/Resistance level must be. '5' means the peak was higher than the 5 candles before and after it."
)
atr_multiplier = st.sidebar.slider("ATR Touch Hit-Box", min_value=0.1, max_value=2.0, value=0.5, step=0.1, help="How close the live price must get to the horizontal line to count as a retest.")

# ==========================================
# 2. DATA FETCHER 
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
        "Non-F&O Stocks (Nifty 500 base)": "ind_nifty500list.csv", "Nifty Midcap 100": "ind_niftymidcap100list.csv",
        "Nifty Bank": "ind_niftybanklist.csv"
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
# 3. CORE LOGIC ENGINE (PURE S&R)
# ==========================================
def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

def resample_macro(df, period):
    return df.resample(period).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return np.max(ranges, axis=1).rolling(window=period).mean()

def check_htf_trend(df, is_bullish):
    if len(df) < 200: return False
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    curr = df.iloc[-1]
    if is_bullish: return (curr['Close'] > curr['EMA_44']) and (curr['EMA_44'] > curr['EMA_200'])
    else: return (curr['Close'] < curr['EMA_44']) and (curr['EMA_44'] < curr['EMA_200'])

def check_snr_retest(df, is_bullish, swing_len, atr_mult, ltf_ema_choice):
    if len(df) < 100: return None
    df['ATR'] = calculate_atr(df)
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # Identify true Swing Highs and Swing Lows
    window = swing_len * 2 + 1
    df['Swing_High'] = df['High'][(df['High'] == df['High'].rolling(window, center=True).max())]
    df['Swing_Low'] = df['Low'][(df['Low'] == df['Low'].rolling(window, center=True).min())]
    
    current = df.iloc[-1]
    current_atr = current['ATR'] if not pd.isna(current['ATR']) else (current['High'] - current['Low'])
    
    valid_setups = []
    
    if is_bullish:
        # Look for old Resistance (Swing Highs) that were broken and are now Support
        swing_highs = df['Swing_High'].dropna()
        
        for idx, resistance_price in swing_highs.items():
            # Only look at swing highs that are not the absolute most recent candles
            if df.index.get_loc(idx) > len(df) - (swing_len + 3): continue
                
            future_data = df.loc[idx:]
            
            # 1. Was the Resistance broken? (Did price close above it?)
            breakouts = future_data[future_data['Close'] > resistance_price]
            if breakouts.empty: continue
            
            bos_idx = breakouts.index[0]
            
            # 2. Has the new Support been completely broken back down since the breakout?
            post_bos = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
            if not post_bos.empty and (post_bos['Close'] < resistance_price).any():
                continue # Failed support, skip it
                
            # 3. Is the live price currently retesting this horizontal line?
            atr_allowance = current_atr * atr_mult
            
            is_testing = False
            # Hit-box logic: Low touched the line, but close didn't break down
            if current['Low'] <= (resistance_price + atr_allowance) and current['Close'] >= resistance_price:
                is_testing = True
                
            if is_testing:
                # 4. EMA Confluence Check
                ema_passed = True
                ema_str = "N/A"
                if "44" in ltf_ema_choice:
                    ema_passed = (current['EMA_44'] >= resistance_price) and (current['EMA_44'] <= resistance_price + (current_atr * 2))
                    ema_str = f"44 EMA: {current['EMA_44']:.2f}"
                elif "200" in ltf_ema_choice:
                    ema_passed = (current['EMA_200'] >= resistance_price) and (current['EMA_200'] <= resistance_price + (current_atr * 2))
                    ema_str = f"200 EMA: {current['EMA_200']:.2f}"
                    
                if ema_passed:
                    valid_setups.append({
                        "Setup": "Broken Resistance ➔ New Support",
                        "Live Price": round(current['Close'], 2),
                        "S&R Line": round(resistance_price, 2),
                        "LTF EMA": ema_str,
                        "Status": "🎯 Testing S&R Line"
                    })
    else:
        # Look for old Support (Swing Lows) that were broken and are now Resistance
        swing_lows = df['Swing_Low'].dropna()
        
        for idx, support_price in swing_lows.items():
            if df.index.get_loc(idx) > len(df) - (swing_len + 3): continue
                
            future_data = df.loc[idx:]
            
            breakdowns = future_data[future_data['Close'] < support_price]
            if breakdowns.empty: continue
            
            bos_idx = breakdowns.index[0]
            
            post_bos = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
            if not post_bos.empty and (post_bos['Close'] > support_price).any():
                continue 
                
            atr_allowance = current_atr * atr_mult
            
            is_testing = False
            if current['High'] >= (support_price - atr_allowance) and current['Close'] <= support_price:
                is_testing = True
                
            if is_testing:
                ema_passed = True
                ema_str = "N/A"
                if "44" in ltf_ema_choice:
                    ema_passed = (current['EMA_44'] <= support_price) and (current['EMA_44'] >= support_price - (current_atr * 2))
                    ema_str = f"44 EMA: {current['EMA_44']:.2f}"
                elif "200" in ltf_ema_choice:
                    ema_passed = (current['EMA_200'] <= support_price) and (current['EMA_200'] >= support_price - (current_atr * 2))
                    ema_str = f"200 EMA: {current['EMA_200']:.2f}"
                    
                if ema_passed:
                    valid_setups.append({
                        "Setup": "Broken Support ➔ New Resistance",
                        "Live Price": round(current['Close'], 2),
                        "S&R Line": round(support_price, 2),
                        "LTF EMA": ema_str,
                        "Status": "🎯 Testing S&R Line"
                    })

    if valid_setups:
        # Return the most recent valid setup
        return valid_setups[-1]
    return None

# ==========================================
# 4. HIGH-SPEED BATCH ENGINE 
# ==========================================
if st.sidebar.button("⚡ Launch S&R Scanner", type="primary"):
    is_bull_setup = "Bullish" in direction
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Executing High-Speed Pure S&R Scan...")
        
        htf_period_val = "max" if htf in ['3mo', '6mo'] else "10y"
        htf_interval_val = "1mo" if htf in ['3mo', '6mo'] else htf
        
        ltf_period_val = {"1mo": "15y", "1wk": "10y", "1d": "5y", "75m": "60d"}.get(ltf, "5y")
        ltf_interval_val = "15m" if ltf == "75m" else ltf
        
        tickers_str = " ".join(ticker_list)
        
        progress_bar = st.progress(10)
        status_text = st.empty()
        
        htf_data = None
        if require_htf_ema:
            status_text.text("📥 Payload 1/2: Downloading Higher Timeframe Market Data...")
            htf_data = yf.download(tickers_str, period=htf_period_val, interval=htf_interval_val, group_by='ticker', threads=True, show_errors=False)
            
        progress_bar.progress(50)
        status_text.text("📥 Payload 2/2: Downloading Lower Timeframe Market Data...")
        ltf_data = yf.download(tickers_str, period=ltf_period_val, interval=ltf_interval_val, group_by='ticker', threads=True, show_errors=False)
        
        progress_bar.progress(85)
        status_text.text("🧠 Processing Pure Horizontal Support & Resistance Logic...")
        
        results = []
        
        for ticker in ticker_list:
            try:
                htf_passed = True
                
                if require_htf_ema and htf_data is not None:
                    htf_passed = False
                    df_htf = htf_data if len(ticker_list) == 1 else htf_data[ticker]
                    df_htf = df_htf.dropna()
                    
                    if not df_htf.empty:
                        if htf == '3mo': df_htf = resample_macro(df_htf, '3ME')
                        if htf == '6mo': df_htf = resample_macro(df_htf, '6ME')
                        if len(df_htf) > 200:
                            htf_passed = check_htf_trend(df_htf, is_bull_setup)
                
                if htf_passed:
                    df_ltf = ltf_data if len(ticker_list) == 1 else ltf_data[ticker]
                    df_ltf = df_ltf.dropna()
                    
                    if not df_ltf.empty:
                        if ltf == '75m': df_ltf = resample_to_75m(df_ltf)
                        
                        setup = check_snr_retest(df_ltf, is_bull_setup, swing_length, atr_multiplier, ltf_ema_filter)
                        if setup:
                            setup['Ticker'] = ticker.replace(".NS", "")
                            results.append(setup)
                            
            except Exception:
                pass
                
        progress_bar.progress(100)
        status_text.empty()
        progress_bar.empty()
        
        st.subheader(f"📊 Pure S&R Break & Retest Results")
        if results:
            final_df = pd.DataFrame(results)[['Ticker', 'Setup', 'Live Price', 'S&R Line', 'LTF EMA', 'Status']]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Lightning Batch Scan Complete. Horizontal Pivot Support/Resistance isolates found.")
        else:
            st.warning("0 matches. No stocks are currently retesting a major horizontal swing pivot under your parameters.")
