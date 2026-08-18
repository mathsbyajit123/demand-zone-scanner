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
st.set_page_config(page_title="Apex Multi-EMA Scanner", layout="wide")

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

st.markdown('<p class="gradient-text">MULTI-EMA TACTICAL SCANNER</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Absolute Macro Uptrend Lock | Pure Support Pullbacks Only</p>', unsafe_allow_html=True)

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
        "1 Month": "1mo",
        "3 Month": "3mo",
        "6 Month": "6mo"
    }
    tf_label = st.selectbox("Resolution (Timeframe)", list(tf_options.keys()), index=2)
    timeframe = tf_options[tf_label]
    
    st.divider()
    setup_options = [
        "🟣 200 EMA Support (0% to +5% Above)",
        "🔵 Between 20 & 50 EMA (Strict Fan)",
        "🟡 Near 44 EMA Bounce (Strict Uptrend)"
    ]
    target_setup = st.radio("Target Setup Architecture", setup_options)

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
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
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
        else:
            return [f"{t}.NS" for t in fo_stocks_list]
    except Exception as e:
        return [f"{t}.NS" for t in fo_stocks_list]

def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

def resample_custom_months(df, months):
    rule = f'{months}ME'
    return df.resample(rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

# ==========================================
# 4. MULTI-EMA MATHEMATICAL ENGINE & SLOPE
# ==========================================
def calculate_ema_angle(ema_series):
    """Calculates the upward angle of the EMA using 3-period Arctangent Math."""
    try:
        y1 = ema_series.iloc[-4] 
        y2 = ema_series.iloc[-1] 
        roc_pct = ((y2 - y1) / y1) * 100 
        angle = np.degrees(np.arctan(roc_pct * 5)) 
        return round(angle, 1)
    except:
        return 0

def scan_emas(df, target_setup):
    if len(df) < 205: return None 
    
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    c = df.iloc[-1]
    live_price = c['Close']
    
    # ==========================================================
    # ABSOLUTE MACRO UPTREND LAW
    # If the 200 EMA is not at the absolute bottom, it is a DOWNTREND. Trash it instantly.
    # ==========================================================
    if c['EMA_50'] <= c['EMA_200'] or c['EMA_20'] <= c['EMA_200']:
        return None
    
    # SETUP 1: 200 EMA Support
    if "200 EMA" in target_setup:
        # Require a strict upward slope of the 200 EMA
        angle = calculate_ema_angle(df['EMA_200'])
        if angle <= 1: return None 
        
        # Price must be physically ABOVE the 200 EMA (acting as a floor) and within 5% of it.
        if c['EMA_200'] <= live_price <= (c['EMA_200'] * 1.05):
            return {
                "Setup Filter": "🟣 200 EMA Support",
                "Live Price": round(live_price, 2),
                "Key Level": f"EMA 200: {round(c['EMA_200'], 2)}",
                "Distance": f"+{round(((live_price - c['EMA_200']) / c['EMA_200']) * 100, 2)}% Above",
                "EMA Angle": f"↗️ {angle}°",
                "Action": "🎯 BUY THE DIP"
            }
            
    # SETUP 2: Between 20 & 50 EMA Trap
    elif "Between 20 & 50" in target_setup:
        # PERFECT FAN LAW: 20 > 50 > 200 must be perfectly aligned
        if not (c['EMA_20'] > c['EMA_50'] > c['EMA_200']): return None
        
        angle = calculate_ema_angle(df['EMA_50'])
        if angle <= 1: return None 
        
        if c['EMA_50'] <= live_price <= c['EMA_20']:
            return {
                "Setup Filter": "🔵 20-50 EMA Trap",
                "Live Price": round(live_price, 2),
                "Key Level": f"E20: {round(c['EMA_20'], 2)} | E50: {round(c['EMA_50'], 2)}",
                "Distance": "Sandwiched",
                "EMA Angle": f"↗️ {angle}°",
                "Action": "🎯 ACCUMULATE"
            }

    # SETUP 3: Near 44 EMA Bounce
    elif "Near 44 EMA" in target_setup:
        # PERFECT UPTREND LAW: 44 must be strictly above 200
        if c['EMA_44'] <= c['EMA_200']: return None
        
        angle = calculate_ema_angle(df['EMA_44'])
        if angle <= 1: return None 
        
        lower_band = c['EMA_44'] * 0.985
        upper_band = c['EMA_44'] * 1.015
        
        if lower_band <= live_price <= upper_band:
            return {
                "Setup Filter": "🟡 44 EMA Bounce",
                "Live Price": round(live_price, 2),
                "Key Level": f"EMA 44: {round(c['EMA_44'], 2)}",
                "Distance": f"{round(((live_price - c['EMA_44']) / c['EMA_44']) * 100, 2)}% Away",
                "EMA Angle": f"↗️ {angle}°",
                "Action": "🎯 WATCH REVERSAL"
            }
            
    return None

# ==========================================
# 5. EXECUTION & DYNAMIC PROGRESS
# ==========================================
if st.button("🔥 RUN STRICT UPTREND SCANNER", type="primary"):
    ticker_list = get_index_tickers(selected_sector)
    total_stocks = len(ticker_list)
    
    if ticker_list:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1: st.markdown(f"<div class='metric-box'><span>UNIVERSE</span><h2>{total_stocks} ASSETS</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-box'><span>RESOLUTION</span><h2>{tf_label}</h2></div>", unsafe_allow_html=True)
        with col3: st.markdown(f"<div class='metric-box'><span>ALGORITHM</span><h2>STRICT UPTREND</h2></div>", unsafe_allow_html=True)

        st.write("")
        
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        progress_text.markdown("#### ⏳ Fetching Deep History & Purging Downtrend Garbage...")
        
        if timeframe in ["6mo", "3mo", "1mo"]:
            interval_val = "1mo"
            period_val = "max"
        elif timeframe == "1wk":
            interval_val = "1wk"
            period_val = "10y" 
        elif timeframe == "1d":
            interval_val = "1d"
            period_val = "3y" 
        elif timeframe == "75m":
            interval_val = "15m"
            period_val = "60d"
        else: # 15m
            interval_val = "15m"
            period_val = "60d"
        
        market_data = yf.download(" ".join(ticker_list), period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        results = []
        
        for i, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Enforcing Uptrend Laws: {i + 1} out of {total_stocks} ({ticker.replace('.NS', '')})")
            progress_bar.progress((i + 1) / total_stocks)
            
            try:
                df = market_data[ticker].dropna() if total_stocks > 1 else market_data.dropna()
                
                if not df.empty:
                    if timeframe == '6mo': df = resample_custom_months(df, 6)
                    elif timeframe == '3mo': df = resample_custom_months(df, 3)
                    elif timeframe == '75m': df = resample_to_75m(df)
                    
                    setup = scan_emas(df, target_setup)
                    
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except:
                pass
                
        progress_text.empty()
        progress_bar.empty()
        st.divider()
        
        if results:
            st.success(f"Successfully isolated {len(results)} assets in a FLAWLESS MACRO UPTREND pulling back to targets.")
            
            final_df = pd.DataFrame(results)[['Asset', 'Setup Filter', 'Live Price', 'Key Level', 'Distance', 'EMA Angle', 'Action']]
            
            color = '#00F2FE'
            if '200' in target_setup: color = '#B19CD9'
            elif '20-50' in target_setup: color = '#4FACFE'
            elif '44' in target_setup: color = '#F6D365'
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: f'color: {color}; font-weight: 800;', subset=['Setup Filter'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['EMA Angle'])\
              .map(lambda v: 'color: #00FF00; font-weight: 800;', subset=['Action'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error(f"0 MATCHES. The Strict Uptrend Law filtered out all the noise. No stocks meet the perfect Fan criteria right now.")
