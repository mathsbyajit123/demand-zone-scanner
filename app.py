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
st.set_page_config(page_title="EMA Proximity Scanner", layout="wide")
st.title("🎯 Pure EMA Proximity & Bounce Scanner")
st.markdown("Scans for stocks interacting with the 44 EMA or 200 EMA. Features dynamic F&O vs. Cash Segment separation.")

st.sidebar.header("⚙️ Market Settings")
sector_options = [
    "F&O Stocks (~223+)",
    "Non-F&O Stocks (Nifty 500 base)",
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Auto"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options, index=0)

timeframe_options = {
    "1 Day": "1d",
    "75 Minutes (Intraday)": "75m",
    "1 Week": "1wk",
    "1 Month": "1mo"
}
selected_tf_label = st.sidebar.selectbox("Timeframe", list(timeframe_options.keys()))
timeframe = timeframe_options[selected_tf_label]

st.sidebar.header("🎯 Trade Setup")
direction = st.sidebar.radio(
    "Select Setup Direction",
    ("🟢 Bullish (Support / Bounce)", "🔴 Bearish (Resistance / Rejection)")
)

st.sidebar.header("📈 Target EMA")
ema_target = st.sidebar.radio(
    "Which EMA are you tracking?",
    ("44 EMA", "200 EMA", "Both (Must tap either)")
)

st.sidebar.header("🧲 Tolerance & Wicks")
approach_buffer = st.sidebar.slider(
    "Approach Buffer (%)", 
    min_value=0.0, max_value=5.0, value=2.0, step=0.5,
    help="How close the wick (High/Low) must get to the EMA to count as a touch."
)

cross_allowance = st.sidebar.slider(
    "Max Penetration / Cross Allowance (%)", 
    min_value=0.0, max_value=5.0, value=1.0, step=0.5,
    help="How far the closing price is allowed to cross past the EMA before the setup is considered broken/invalid."
)

# ==========================================
# 2. DATA FETCHER (F&O vs NON-F&O LOGIC)
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    # Master list of 223+ F&O stocks (Updated to include recent 2025/2026 additions)
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
    
    # If the user specifically selects F&O, return the hardcoded list immediately
    if "F&O Stocks" in sector_name:
        return [f"{ticker}.NS" for ticker in fo_stocks_list]
        
    # Otherwise, prepare to fetch the requested CSV index file
    csv_file = {
        "Nifty 50": "ind_nifty50list.csv",
        "Nifty 500": "ind_nifty500list.csv",
        "Non-F&O Stocks (Nifty 500 base)": "ind_nifty500list.csv", # Fetch Nifty 500 to subtract from
        "Nifty Midcap 100": "ind_niftymidcap100list.csv",
        "Nifty Bank": "ind_niftybanklist.csv",
        "Nifty IT": "ind_niftyitlist.csv",
        "Nifty Auto": "ind_niftyautolist.csv"
    }.get(sector_name, "ind_nifty500list.csv")
    
    mirrors = [
        f"https://raw.githubusercontent.com/althk/zerobha/main/{csv_file}",
        f"https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/{csv_file}",
        f"https://raw.githubusercontent.com/faizanahemad/data-science-utils/master/data_science_utils/financial/{csv_file}"
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
                    break # Stop if successful
        except Exception:
            continue
            
    if not fetched_list:
        st.sidebar.error("⚠️ Unable to fetch ticker list.")
        return []
        
    # The pure Non-F&O Extraction Engine
    if "Non-F&O" in sector_name:
        # Subtract any ticker present in the fo_stocks_list
        non_fo_list = [ticker for ticker in fetched_list if ticker not in fo_stocks_list]
        return [f"{ticker}.NS" for ticker in non_fo_list]
        
    return [f"{ticker}.NS" for ticker in fetched_list]

# ==========================================
# 3. CORE LOGIC: EMA PROXIMITY
# ==========================================
def resample_to_75m(df):
    resampled = df.resample('75min', offset='15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    return resampled

def check_ema_setup(df, dir_choice, ema_choice, approach_pct, cross_pct):
    df = df[['Open', 'High', 'Low', 'Close']].dropna()
    if len(df) < 200: return None 
        
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    is_bullish = "Bullish" in dir_choice
    current = df.iloc[-1]
    
    app_mult_bull = 1 + (approach_pct / 100)
    app_mult_bear = 1 - (approach_pct / 100)
    
    cross_mult_bull = 1 - (cross_pct / 100)
    cross_mult_bear = 1 + (cross_pct / 100)
    
    targets = []
    if "44" in ema_choice or "Both" in ema_choice: targets.append(("44 EMA", current['EMA_44']))
    if "200" in ema_choice or "Both" in ema_choice: targets.append(("200 EMA", current['EMA_200']))
    
    matched_emas = []
    
    for ema_name, ema_val in targets:
        if is_bullish:
            # 1. Did the Low tap the EMA (or come within the approach buffer)?
            tapped_ema = current['Low'] <= (ema_val * app_mult_bull)
            
            # 2. Did the Close respect the Cross Allowance? (Not crashing straight through)
            held_ema = current['Close'] >= (ema_val * cross_mult_bull)
            
            if tapped_ema and held_ema:
                dist_pct = ((current['Close'] - ema_val) / ema_val) * 100
                matched_emas.append({
                    "Target": ema_name,
                    "EMA Value": round(ema_val, 2),
                    "Distance": f"{dist_pct:+.2f}%"
                })
        else:
            # 1. Did the High tap the EMA (or come within the approach buffer)?
            tapped_ema = current['High'] >= (ema_val * app_mult_bear)
            
            # 2. Did the Close respect the Cross Allowance? (Not breaking straight through upside)
            held_ema = current['Close'] <= (ema_val * cross_mult_bear)
            
            if tapped_ema and held_ema:
                dist_pct = ((current['Close'] - ema_val) / ema_val) * 100
                matched_emas.append({
                    "Target": ema_name,
                    "EMA Value": round(ema_val, 2),
                    "Distance": f"{dist_pct:+.2f}%"
                })

    if not matched_emas:
        return None
        
    primary_match = matched_emas[0]
    
    # Determine visual status based on close price vs EMA
    status = "N/A"
    if is_bullish:
        if current['Close'] < primary_match['EMA Value']:
            status = "⚠️ Slight Cross Down"
        elif current['Close'] > current['Open']:
            status = "✅ Bouncing (Green)"
        else:
            status = "⏳ Resting on EMA"
    else:
        if current['Close'] > primary_match['EMA Value']:
            status = "⚠️ Slight Cross Up"
        elif current['Close'] < current['Open']:
            status = "✅ Rejecting (Red)"
        else:
            status = "⏳ Resting on EMA"

    return {
        "Live Price": round(current['Close'], 2),
        "EMA Target": primary_match['Target'],
        "EMA Value": primary_match['EMA Value'],
        "Close vs EMA": primary_match['Distance'],
        "Action Status": status
    }

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Launch EMA Scanner", type="primary"):
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Scanning for {direction[:2]} EMA interactions...")
        
        if timeframe == '75m': fetch_period, fetch_interval = "60d", "15m"
        elif timeframe == '1d': fetch_period, fetch_interval = "2y", "1d"
        elif timeframe == '1wk': fetch_period, fetch_interval = "5y", "1wk"
        else: fetch_period, fetch_interval = "10y", "1mo"
        
        progress_bar = st.progress(0)
        results = []
        
        for i, ticker in enumerate(ticker_list):
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=fetch_interval)
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    
                    setup = check_ema_setup(df, direction, ema_target, approach_buffer, cross_allowance)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append(setup)
            except: pass
            progress_bar.progress((i + 1) / len(ticker_list))
            
        progress_bar.empty()
        
        st.subheader(f"📊 Scan Results ({selected_tf_label})")
        if results:
            final_df = pd.DataFrame(results)[['Ticker', 'Live Price', 'EMA Target', 'EMA Value', 'Close vs EMA', 'Action Status']]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Results acquired. These stocks are interacting with the specified EMA.")
        else:
            st.warning(f"0 matches found. The market is not presenting this EMA setup right now. Adjust your Tolerance sliders.")
