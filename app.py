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
st.set_page_config(page_title="50 SMA + GTF Hybrid Scanner", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #090B10; color: #E2E8F0; }
    .gradient-text {
        font-weight: 900; font-size: 38px; letter-spacing: -1px;
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

st.markdown('<p class="gradient-text">50 SMA + GTF HYBRID TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">1-3 Base Zone Tracking | 50 SMA Macro Filter | Fresh Pullback Entries</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    
    sector_options = ["F&O Stocks (~242)", "Nifty 50", "Nifty 500", "Nifty Smallcap 250"]
    selected_sector = st.selectbox("Market Universe", sector_options, index=2)
    
    tf_options = {
        "15 Min": "15m",
        "75 Min": "75m",
        "1 Day": "1d", 
        "1 Week": "1wk",
        "1 Month": "1mo"
    }
    tf_label = st.selectbox("Resolution (Timeframe)", list(tf_options.keys()), index=2)
    timeframe = tf_options[tf_label]
    
    st.divider()
    direction = st.radio("Trend Direction", ("🟢 Demand (Above 50 SMA)", "🔴 Supply (Below 50 SMA)"))

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
        else:
            return [f"{t}.NS" for t in fo_stocks_list]
    except:
        return [f"{t}.NS" for t in fo_stocks_list]

def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

# ==========================================
# 4. HYBRID SMA & GTF ENGINE
# ==========================================
def analyze_gtf_candles(df):
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    # Using 55% as the Base Candle threshold to mimic human visual analysis
    conditions = [
        (df['Body_Pct'] > 55) & (df['Close'] > df['Open']),  
        (df['Body_Pct'] > 55) & (df['Close'] < df['Open']),  
        (df['Body_Pct'] <= 55)                               
    ]
    choices = ['Green Exciting', 'Red Exciting', 'Base']
    df['GTF_Type'] = np.select(conditions, choices, default='Unknown')
    return df

def scan_hybrid_zones(df, is_bullish):
    if len(df) < 55: return None
    
    # Calculate Macro Trend 50 SMA
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    
    df = analyze_gtf_candles(df)
    
    search_df = df.tail(300) 
    last_idx = len(search_df) - 1
    today_candle = search_df.iloc[last_idx]
    live_price = today_candle['Close']
    current_50_sma = today_candle['SMA_50']
    
    # ==========================================
    # 50 SMA MACRO TREND FILTER
    # ==========================================
    if is_bullish and live_price <= current_50_sma:
        return None # Must be ABOVE 50 SMA for Demand
    elif not is_bullish and live_price >= current_50_sma:
        return None # Must be BELOW 50 SMA for Supply
        
    for i in range(1, last_idx - 1):
        leg_in = search_df.iloc[i-1]
        
        # Must start with an exciting Leg-In candle
        if leg_in['GTF_Type'] == 'Base': continue 
        
        base_count = 0
        leg_out_idx = None
        
        # Scan forward for 1 to 3 base candles
        for j in range(i, min(i + 5, last_idx)):
            curr = search_df.iloc[j]
            if curr['GTF_Type'] == 'Base':
                base_count += 1
            else:
                leg_out_idx = j
                break
                
        # Must be exactly 1 to 3 bases
        if base_count == 0 or base_count > 3: continue 
        if leg_out_idx is None or leg_out_idx >= last_idx: continue
        
        base_candles = search_df.iloc[i : leg_out_idx]
        leg_out = search_df.iloc[leg_out_idx]
        
        pattern = None
        
        # ==========================================
        # STRUCTURAL VALIDATION (CLOSE > LEG-IN)
        # ==========================================
        if is_bullish:
            # Leg Out must close strictly ABOVE Leg In high
            if leg_out['GTF_Type'] == 'Green Exciting' and leg_out['Close'] > leg_in['High']:
                proximal = max(base_candles['Open'].max(), base_candles['Close'].max())
                distal = base_candles['Low'].min()
                pattern = 'DBR' if leg_in['GTF_Type'] == 'Red Exciting' else 'RBR'

        elif not is_bullish:
            # Leg Out must close strictly BELOW Leg In low
            if leg_out['GTF_Type'] == 'Red Exciting' and leg_out['Close'] < leg_in['Low']:
                proximal = min(base_candles['Open'].min(), base_candles['Close'].min())
                distal = base_candles['High'].max()
                pattern = 'RBD' if leg_in['GTF_Type'] == 'Green Exciting' else 'DBD'
                
        if not pattern: continue
        
        # ==========================================
        # FRESHNESS VALIDATION
        # ==========================================
        future_data = search_df.iloc[leg_out_idx + 1 : last_idx]
        is_tested = False
        
        if not future_data.empty:
            for _, past_candle in future_data.iterrows():
                if is_bullish:
                    if past_candle['Low'] <= proximal: is_tested = True
                else:
                    if past_candle['High'] >= proximal: is_tested = True
                    
        if is_tested: continue
        
        # ==========================================
        # ACTIVE TOUCH TRIGGER (TODAY)
        # ==========================================
        trading_at_zone = False
        
        if is_bullish:
            if today_candle['Low'] <= (proximal * 1.025) and live_price >= distal: 
                trading_at_zone = True
        else:
            if today_candle['High'] >= (proximal * 0.975) and live_price <= distal:
                trading_at_zone = True
        
        if trading_at_zone:
            distance_to_sma = round(((live_price - current_50_sma) / current_50_sma) * 100, 2)
            
            return {
                "GTF Setup": f"🟢 {pattern}" if is_bullish else f"🔴 {pattern}",
                "Structure": f"{base_count} Base Candles",
                "50 SMA Alignment": f"✅ +{distance_to_sma}% Above SMA" if is_bullish else f"✅ {distance_to_sma}% Below SMA",
                "Live Price": round(live_price, 2),
                "Entry (Prox)": round(proximal, 2),
                "SL (Distal)": round(distal, 2),
                "Action": "🎯 TRADE HYBRID SETUP"
            }
            
    return None

# ==========================================
# 5. EXECUTION & DYNAMIC PROGRESS
# ==========================================
if st.button("🔥 RUN HYBRID SMA SCANNER", type="primary"):
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
        
        progress_text.markdown("#### ⏳ Filtering by 50 SMA & Verifying 1-3 Base Structures...")
        
        if timeframe == "1mo": period_val, interval_val = "max", "1mo"
        elif timeframe == "1wk": period_val, interval_val = "10y", "1wk"
        elif timeframe == "1d": period_val, interval_val = "3y", "1d"
        else: period_val, interval_val = "60d", "15m"
        
        market_data = yf.download(" ".join(ticker_list), period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        results = []
        for i, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Analyzing Price Action {i + 1} out of {total_stocks} ({ticker.replace('.NS', '')})")
            progress_bar.progress((i + 1) / total_stocks)
            try:
                df = market_data[ticker].dropna() if total_stocks > 1 else market_data.dropna()
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    setup = scan_hybrid_zones(df, is_bull)
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except: pass
                
        progress_text.empty()
        progress_bar.empty()
        st.divider()
        
        if results:
            st.success(f"Isolated {len(results)} assets showing a fresh GTF zone actively aligned with the 50 SMA.")
            final_df = pd.DataFrame(results)[['Asset', 'GTF Setup', 'Structure', '50 SMA Alignment', 'Live Price', 'Entry (Prox)', 'SL (Distal)', 'Action']]
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else ('color: #FF0000; font-weight: 800;' if '🔴' in str(v) else ''), subset=['GTF Setup'])\
              .map(lambda v: 'color: #4FACFE; font-weight: 800;', subset=['50 SMA Alignment'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Structure'])\
              .map(lambda v: 'color: #00F2FE; font-weight: 900;', subset=['Action'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. The Hybrid Filter is incredibly strict. No fresh 1-3 Base zones are currently aligned with the 50 SMA today.")
