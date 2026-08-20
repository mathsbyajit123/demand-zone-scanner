import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import io, requests
import time

warnings.filterwarnings('ignore')

# ==========================================
# 1. UI & STYLING
# ==========================================
st.set_page_config(page_title="Apex GTF + SMA Trend Scanner", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #090B10; color: #E2E8F0; }
    .gradient-text {
        font-weight: 900; font-size: 36px; letter-spacing: -1px;
        background: -webkit-linear-gradient(45deg, #00F2FE, #4FACFE, #F6D365);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px; padding-bottom: 0px; text-transform: uppercase;
    }
    .sub-text { font-size: 14px; color: #64748B; margin-top: -5px; margin-bottom: 30px; letter-spacing: 1px; font-weight: 600;}
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #00C6FF 0%, #0072FF 100%);
        color: white; border: none; border-radius: 6px;
        padding: 14px 24px; font-size: 16px; font-weight: 700; letter-spacing: 2px;
        box-shadow: 0 4px 20px rgba(0, 198, 255, 0.4); width: 100%; text-transform: uppercase;
    }
    .metric-box {
        background-color: #11151C; border-radius: 8px; padding: 20px;
        border: 1px solid #1E293B; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        text-align: center;
    }
    .metric-box span { color: #4FACFE; font-weight: 600; letter-spacing: 1px; font-size: 14px; }
    .metric-box h2 { color: #F8FAFC; margin: 0; padding-top: 5px; font-size: 24px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">APEX GTF + 50 SMA TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Strict Breakouts | Volume Verification | Macro Timeframe Engine</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    
    sector_options = ["F&O Stocks (~242)", "Nifty 50", "Nifty 500", "Nifty Smallcap 250"]
    selected_sector = st.selectbox("Market Universe", sector_options, index=0)
    
    # RESTORED MACRO TIMEFRAMES
    tf_options = {
        "15 Min": "15m", 
        "75 Min": "75m", 
        "1 Day": "1d", 
        "1 Week": "1wk",
        "1 Month": "1mo",
        "3 Month": "3mo"
    }
    tf_label = st.selectbox("Resolution (Timeframe)", list(tf_options.keys()), index=2)
    timeframe = tf_options[tf_label]
    
    st.divider()
    direction = st.radio("Trend Direction", ("🟢 Demand (Uptrend)", "🔴 Supply (Downtrend)"))

# ==========================================
# 3. FIXED NSE DATA ROUTER
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
    if "F&O" in sector_name: return [f"{t}.NS" for t in fo_stocks_list]
    
    url = ""
    if "500" in sector_name: url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    elif "250" in sector_name: url = "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv"
    elif "50" in sector_name: url = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.nseindia.com", timeout=10) 
        time.sleep(1) 
        response = session.get(url, timeout=10) 
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            return [f"{s.strip()}.NS" for s in df['Symbol']]
    except: pass
    return [f"{t}.NS" for t in fo_stocks_list]

def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

def resample_custom_months(df, months):
    """Stitches 1-month candles into Quarterly (3-Month) institutional blocks."""
    rule = f'{months}ME'
    return df.resample(rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

# ==========================================
# 4. MASTER ENGINE: STRICT BOS + SLOPE + VOLUME
# ==========================================
def analyze_gtf_candles(df):
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    conditions = [
        (df['Body_Pct'] > 55) & (df['Close'] > df['Open']),  
        (df['Body_Pct'] > 55) & (df['Close'] < df['Open']),  
        (df['Body_Pct'] <= 55)                               
    ]
    choices = ['Green Exciting', 'Red Exciting', 'Base']
    df['GTF_Type'] = np.select(conditions, choices, default='Unknown')
    return df

def check_sma_slope(sma_series, lookback=10):
    try:
        # Prevent lookback errors on higher timeframes like 3mo which have fewer candles
        actual_lookback = min(lookback, len(sma_series) - 1)
        if actual_lookback < 2: return 0
        
        past_sma = sma_series.iloc[-actual_lookback]
        curr_sma = sma_series.iloc[-1]
        slope_pct = ((curr_sma - past_sma) / past_sma) * 100
        return slope_pct
    except: return 0

def scan_master_zones(df, is_bullish):
    # Reduced minimum candle requirement to allow for 3mo charts (which generate far fewer candles)
    if len(df) < 30: return None
    
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df = analyze_gtf_candles(df)
    
    search_df = df.tail(300) 
    last_idx = len(search_df) - 1
    today_candle = search_df.iloc[last_idx]
    live_price = today_candle['Close']
    current_50_sma = today_candle['SMA_50']
    
    # --- 1. SIDEWAYS CHOP FILTER (TRAJECTORY) ---
    sma_slope = check_sma_slope(df['SMA_50'], 5) # Adjusted lookback for macro TFs
    
    if pd.notna(current_50_sma):
        if is_bullish:
            if live_price <= current_50_sma or sma_slope < 0: return None 
        else:
            if live_price >= current_50_sma or sma_slope > 0: return None 
        
    for i in range(1, last_idx - 1):
        leg_in = search_df.iloc[i-1]
        if leg_in['GTF_Type'] == 'Base': continue 
        
        base_count = 0
        leg_out_idx = None
        
        for j in range(i, min(i + 5, last_idx)):
            curr = search_df.iloc[j]
            if curr['GTF_Type'] == 'Base': base_count += 1
            else:
                leg_out_idx = j
                break
                
        if base_count == 0 or base_count > 3: continue 
        if leg_out_idx is None or leg_out_idx >= last_idx: continue
        
        base_candles = search_df.iloc[i : leg_out_idx]
        leg_out = search_df.iloc[leg_out_idx]
        
        pattern = None
        
        # --- 2. ABSOLUTE STRUCTURAL BREAK (STRICT) ---
        if is_bullish:
            highest_resistance = max(leg_in['High'], base_candles['High'].max())
            if leg_out['GTF_Type'] == 'Green Exciting' and leg_out['Close'] > highest_resistance:
                proximal = max(base_candles['Open'].max(), base_candles['Close'].max())
                distal = base_candles['Low'].min()
                pattern = 'DBR' if leg_in['GTF_Type'] == 'Red Exciting' else 'RBR'

        elif not is_bullish:
            lowest_support = min(leg_in['Low'], base_candles['Low'].min())
            if leg_out['GTF_Type'] == 'Red Exciting' and leg_out['Close'] < lowest_support:
                proximal = min(base_candles['Open'].min(), base_candles['Close'].min())
                distal = base_candles['High'].max()
                pattern = 'RBD' if leg_in['GTF_Type'] == 'Green Exciting' else 'DBD'
                
        if not pattern: continue
        
        # --- 3. VOLUME VERIFICATION ---
        avg_base_volume = base_candles['Volume'].mean()
        if leg_out['Volume'] < (avg_base_volume * 1.1): continue 
        
        # --- 4. FRESHNESS CHECK ---
        future_data = search_df.iloc[leg_out_idx + 1 : last_idx]
        is_tested = False
        if not future_data.empty:
            for _, past_candle in future_data.iterrows():
                if is_bullish and past_candle['Low'] <= proximal: is_tested = True
                elif not is_bullish and past_candle['High'] >= proximal: is_tested = True
        if is_tested: continue
        
        # --- 5. ACTIVE TOUCH ---
        trading_at_zone = False
        if is_bullish:
            if today_candle['Low'] <= (proximal * 1.025) and live_price >= distal: trading_at_zone = True
        else:
            if today_candle['High'] >= (proximal * 0.975) and live_price <= distal: trading_at_zone = True
        
        if trading_at_zone:
            trend_label = "✅ Validated" 
            return {
                "Setup": f"🟢 {pattern}" if is_bullish else f"🔴 {pattern}",
                "Breakout": "✅ Absolute Clear",
                "Volume": "🔥 Confirmed",
                "Macro Filter": trend_label,
                "Live Price": round(live_price, 2),
                "Entry": round(proximal, 2),
                "Stop Loss": round(distal, 2)
            }
    return None

# ==========================================
# 5. EXECUTION & DYNAMIC PROGRESS
# ==========================================
if st.button("🔥 RUN MASTER SCANNER", type="primary"):
    is_bull = "Demand" in direction
    ticker_list = get_index_tickers(selected_sector)
    total_stocks = len(ticker_list)
    
    if ticker_list:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1: st.markdown(f"<div class='metric-box'><span>UNIVERSE</span><h2>{selected_sector}</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-box'><span>RESOLUTION</span><h2>{tf_label}</h2></div>", unsafe_allow_html=True)
        with col3: st.markdown(f"<div class='metric-box'><span>MODE</span><h2>STRICT RULES</h2></div>", unsafe_allow_html=True)

        st.write("")
        progress_text = st.empty()
        progress_bar = st.progress(0)
        progress_text.markdown("#### ⏳ Building Multi-Timeframe Candles & Validating Structures...")
        
        # LOGIC UPDATE: Handle Macro Fetching Properly
        if timeframe in ["1mo", "3mo"]: 
            period_val, interval_val = "max", "1mo"
        elif timeframe == "1wk": 
            period_val, interval_val = "10y", "1wk"
        elif timeframe == "1d": 
            period_val, interval_val = "3y", "1d"
        else: 
            period_val, interval_val = "60d", "15m"
        
        market_data = yf.download(" ".join(ticker_list), period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        results = []
        for i, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Validating {i + 1} / {total_stocks} ({ticker.replace('.NS', '')})")
            progress_bar.progress((i + 1) / total_stocks)
            try:
                df = market_data[ticker].dropna() if total_stocks > 1 else market_data.dropna()
                if not df.empty:
                    # Apply specific resampling rules
                    if timeframe == '75m': 
                        df = resample_to_75m(df)
                    elif timeframe == '3mo': 
                        df = resample_custom_months(df, 3)
                        
                    setup = scan_master_zones(df, is_bull)
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except: pass
                
        progress_text.empty()
        progress_bar.empty()
        st.divider()
        
        if results:
            st.success(f"Isolated {len(results)} perfect assets matching the required timeframe parameters.")
            final_df = pd.DataFrame(results)[['Asset', 'Setup', 'Breakout', 'Volume', 'Macro Filter', 'Live Price', 'Entry', 'Stop Loss']]
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else ('color: #FF0000; font-weight: 800;' if '🔴' in str(v) else ''), subset=['Setup'])\
              .map(lambda v: 'color: #4FACFE; font-weight: 800;', subset=['Breakout'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Volume', 'Macro Filter'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. The structural breakout and macroeconomic volume parameters are incredibly strict today.")
