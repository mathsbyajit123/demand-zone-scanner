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
st.set_page_config(page_title="Pure GTF + 50 SMA Scanner", layout="wide")

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

st.markdown('<p class="gradient-text">PURE GTF + 50 SMA TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Strict GTF Notes Implementation | 1-3 Base Candles | Macro Timeframes</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    
    sector_options = ["F&O Stocks (~242)", "Nifty 50", "Nifty 500", "Nifty Smallcap 250"]
    selected_sector = st.selectbox("Market Universe", sector_options, index=2)
    
    tf_options = {
        "1 Day": "1d", 
        "1 Week": "1wk",
        "1 Month": "1mo",
        "3 Month": "3mo"
    }
    tf_label = st.selectbox("Resolution (Timeframe)", list(tf_options.keys()), index=0)
    timeframe = tf_options[tf_label]
    
    st.divider()
    direction = st.radio("Trend Direction", ("🟢 Demand (Above 50 SMA)", "🔴 Supply (Below 50 SMA)"))

# ==========================================
# 3. ROBUST NSE DATA ROUTER
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    # Static F&O fallback in case NSE servers block the request
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
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
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

def resample_custom_months(df, months):
    """Stitches 1-month candles into Quarterly (3-Month) institutional blocks."""
    rule = f'{months}ME'
    return df.resample(rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

# ==========================================
# 4. PURE GTF ENGINE
# ==========================================
def analyze_gtf_candles(df):
    """Classifies candles purely based on GTF 50% Body-to-Range rule."""
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    # Prevent division by zero
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    conditions = [
        (df['Body_Pct'] > 50) & (df['Close'] > df['Open']),  # Green Exciting
        (df['Body_Pct'] > 50) & (df['Close'] < df['Open']),  # Red Exciting
        (df['Body_Pct'] <= 50)                               # Base Candle
    ]
    choices = ['Green Exciting', 'Red Exciting', 'Base']
    df['GTF_Type'] = np.select(conditions, choices, default='Base')
    return df

def scan_gtf_zones(df, is_bullish):
    # Need at least 50 candles to calculate a 50 SMA
    if len(df) < 55: return None
    
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df = analyze_gtf_candles(df)
    
    # We only need to search the recent history for active zones
    search_df = df.tail(150) 
    last_idx = len(search_df) - 1
    today_candle = search_df.iloc[last_idx]
    live_price = today_candle['Close']
    current_50_sma = today_candle['SMA_50']
    
    # --- 1. 50 SMA MACRO FILTER ---
    if pd.isna(current_50_sma): return None
    
    if is_bullish and live_price <= current_50_sma: 
        return None # Stock is below 50 SMA, ignore demand
    elif not is_bullish and live_price >= current_50_sma: 
        return None # Stock is above 50 SMA, ignore supply
        
    for i in range(1, last_idx - 1):
        leg_in = search_df.iloc[i-1]
        
        # GTF zones can have exciting leg-ins or occasionally start from a gap. 
        # For strictness, we ensure the leg-in is NOT a base candle.
        if leg_in['GTF_Type'] == 'Base': continue 
        
        base_count = 0
        leg_out_idx = None
        
        # Count consecutive base candles (GTF rule: 1 to 3 max)
        for j in range(i, min(i + 5, last_idx)):
            curr = search_df.iloc[j]
            if curr['GTF_Type'] == 'Base': 
                base_count += 1
            else:
                leg_out_idx = j
                break
                
        if base_count == 0 or base_count > 3: continue 
        if leg_out_idx is None or leg_out_idx >= last_idx: continue
        
        base_candles = search_df.iloc[i : leg_out_idx]
        leg_out = search_df.iloc[leg_out_idx]
        
        pattern = None
        
        # --- 2. ZONE CREATION & VALIDATION ---
        if is_bullish:
            # GTF rule: Leg Out must be Green Exciting and close above base candles
            if leg_out['GTF_Type'] == 'Green Exciting' and leg_out['Close'] > base_candles['High'].max():
                # GTF Proximal for Demand: Highest Body (Open or Close) of bases
                proximal = max(base_candles['Open'].max(), base_candles['Close'].max())
                # GTF Distal for Demand: Lowest Low of bases
                distal = base_candles['Low'].min()
                pattern = 'DBR' if leg_in['GTF_Type'] == 'Red Exciting' else 'RBR'

        elif not is_bullish:
            # GTF rule: Leg Out must be Red Exciting and close below base candles
            if leg_out['GTF_Type'] == 'Red Exciting' and leg_out['Close'] < base_candles['Low'].min():
                # GTF Proximal for Supply: Lowest Body (Open or Close) of bases
                proximal = min(base_candles['Open'].min(), base_candles['Close'].min())
                # GTF Distal for Supply: Highest High of bases
                distal = base_candles['High'].max()
                pattern = 'RBD' if leg_in['GTF_Type'] == 'Green Exciting' else 'DBD'
                
        if not pattern: continue
        
        # --- 3. FRESHNESS CHECK (Untested Zone) ---
        future_data = search_df.iloc[leg_out_idx + 1 : last_idx]
        is_tested = False
        
        if not future_data.empty:
            for _, past_candle in future_data.iterrows():
                if is_bullish and past_candle['Low'] <= proximal: 
                    is_tested = True
                    break
                elif not is_bullish and past_candle['High'] >= proximal: 
                    is_tested = True
                    break
                    
        if is_tested: continue
        
        # --- 4. ACTIVE TOUCH (Are we in the zone TODAY?) ---
        trading_at_zone = False
        
        if is_bullish:
            # Allow a tiny 1% buffer above proximal to catch entries just before they hit
            if today_candle['Low'] <= (proximal * 1.01) and live_price >= distal: 
                trading_at_zone = True
        else:
            if today_candle['High'] >= (proximal * 0.99) and live_price <= distal: 
                trading_at_zone = True
        
        if trading_at_zone:
            distance_to_sma = round(((live_price - current_50_sma) / current_50_sma) * 100, 2)
            
            return {
                "GTF Setup": f"🟢 {pattern}" if is_bullish else f"🔴 {pattern}",
                "Structure": f"{base_count} Base",
                "50 SMA Context": f"✅ +{distance_to_sma}% Above" if is_bullish else f"✅ {distance_to_sma}% Below",
                "Live Price": round(live_price, 2),
                "Proximal (Entry)": round(proximal, 2),
                "Distal (SL)": round(distal, 2)
            }
            
    return None

# ==========================================
# 5. EXECUTION & DYNAMIC PROGRESS
# ==========================================
if st.button("🔥 RUN GTF SCANNER", type="primary"):
    is_bull = "Demand" in direction
    ticker_list = get_index_tickers(selected_sector)
    total_stocks = len(ticker_list)
    
    if ticker_list:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1: st.markdown(f"<div class='metric-box'><span>UNIVERSE</span><h2>{selected_sector}</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-box'><span>RESOLUTION</span><h2>{tf_label}</h2></div>", unsafe_allow_html=True)
        with col3: st.markdown(f"<div class='metric-box'><span>VECTOR</span><h2>{'LONG' if is_bull else 'SHORT'}</h2></div>", unsafe_allow_html=True)

        st.write("")
        progress_text = st.empty()
        progress_bar = st.progress(0)
        progress_text.markdown("#### ⏳ Fetching Data & Identifying GTF Zones...")
        
        # Adjusting data fetch windows based on timeframe
        if timeframe in ["1mo", "3mo"]: 
            period_val, interval_val = "max", "1mo"
        elif timeframe == "1wk": 
            period_val, interval_val = "10y", "1wk"
        else: 
            period_val, interval_val = "3y", "1d"
        
        market_data = yf.download(" ".join(ticker_list), period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        results = []
        for i, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Analyzing Price Action: {i + 1} / {total_stocks} ({ticker.replace('.NS', '')})")
            progress_bar.progress((i + 1) / total_stocks)
            try:
                df = market_data[ticker].dropna() if total_stocks > 1 else market_data.dropna()
                if not df.empty:
                    if timeframe == '3mo': 
                        df = resample_custom_months(df, 3)
                        
                    setup = scan_gtf_zones(df, is_bull)
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except: pass
                
        progress_text.empty()
        progress_bar.empty()
        st.divider()
        
        if results:
            st.success(f"Isolated {len(results)} assets showing a fresh GTF zone actively aligned with the 50 SMA.")
            final_df = pd.DataFrame(results)[['Asset', 'GTF Setup', 'Structure', '50 SMA Context', 'Live Price', 'Proximal (Entry)', 'Distal (SL)']]
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else ('color: #FF0000; font-weight: 800;' if '🔴' in str(v) else ''), subset=['GTF Setup'])\
              .map(lambda v: 'color: #4FACFE; font-weight: 800;', subset=['50 SMA Context'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Structure'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. No fresh 1-3 Base GTF zones are actively being tested today under these conditions.")

