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
st.set_page_config(page_title="Dual-Option EMA Scanner", layout="wide")

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

st.markdown('<p class="gradient-text">DUAL-OPTION EMA SCANNER</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">BOS Filtered 20-50 Range | 200 EMA Support & Resistance</p>', unsafe_allow_html=True)

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
    st.markdown("### **SCANNER CONFIGURATION**")
    direction = st.radio("Trend Direction", ("🟢 Bullish (Uptrends)", "🔴 Bearish (Downtrends)"))
    
    st.write("")
    st.markdown("**Target EMA Option**")
    target_setup = st.radio("Select Strategy Engine", [
        "🔵 Option 1: 20 & 50 EMA Range (with BOS)",
        "🟣 Option 2: 200 EMA Support / Resistance"
    ], label_visibility="collapsed")

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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'text/html,application/xhtml+xml',
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
    except:
        return [f"{t}.NS" for t in fo_stocks_list]

def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

# ==========================================
# 4. EMA MATHEMATICS ENGINE + BOS
# ==========================================
def calculate_ema_angle(ema_series):
    """Calculates the exact slope trajectory of the EMA."""
    try:
        y1 = ema_series.iloc[-4] 
        y2 = ema_series.iloc[-1] 
        roc_pct = ((y2 - y1) / y1) * 100 
        angle = np.degrees(np.arctan(roc_pct * 5)) 
        return round(angle, 1)
    except:
        return 0

def scan_pure_ema(df, is_bullish, target_setup):
    if len(df) < 205: return None 
    
    # Calculate Core Moving Averages
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    c = df.iloc[-1]
    live_price = c['Close']
    
    # ==========================================
    # BULLISH LOGIC (UPTRENDS)
    # ==========================================
    if is_bullish:
        # OPTION 1: 20 & 50 EMA RANGE + BOS
        if "Option 1" in target_setup:
            # Macro Alignment ensures overall uptrend
            if not (c['EMA_20'] > c['EMA_50'] > c['EMA_200']): return None
            
            angle = calculate_ema_angle(df['EMA_50'])
            if angle <= 0: return None # Strict Upward Slope Filter
            
            # --- BREAK OF STRUCTURE (BOS) LOGIC ---
            # Recent Peak (last 20 periods) must be HIGHER than Prior Peak (periods 20 to 40 ago)
            recent_peak = df['High'].iloc[-20:-1].max()
            prior_peak = df['High'].iloc[-40:-20].max()
            if recent_peak <= prior_peak: return None # Discard if it didn't break structure
            
            # Price must be physically inside the 20 and 50 gap pulling back
            if c['EMA_50'] <= live_price <= c['EMA_20']:
                return {
                    "Setup": "🟢 Bullish 20-50 Range",
                    "Structure Validated": "✅ BOS Confirmed",
                    "Live Price": round(live_price, 2),
                    "Action Zone": f"E20: {round(c['EMA_20'], 2)} | E50: {round(c['EMA_50'], 2)}",
                    "Trend Slope": f"↗️ {angle}° Up",
                    "Status": "🎯 BUY THE RANGE"
                }

        # OPTION 2: 200 EMA SUPPORT (Untouched)
        elif "Option 2" in target_setup:
            # Macro Alignment: 50 > 200 (Ensures it's an uptrend pullback)
            if c['EMA_50'] <= c['EMA_200']: return None
            
            angle = calculate_ema_angle(df['EMA_200'])
            if angle <= 0: return None 
            
            # Price must be resting on top of the 200 EMA (within 5% buffer)
            if c['EMA_200'] <= live_price <= (c['EMA_200'] * 1.05):
                distance = round(((live_price - c['EMA_200']) / c['EMA_200']) * 100, 2)
                return {
                    "Setup": "🟢 Bullish 200 Support",
                    "Structure Validated": "N/A (200 Setup)",
                    "Live Price": round(live_price, 2),
                    "Action Zone": f"E200: {round(c['EMA_200'], 2)}",
                    "Trend Slope": f"↗️ {angle}° Up",
                    "Status": f"🎯 BUY SUPPORT (+{distance}%)"
                }

    # ==========================================
    # BEARISH LOGIC (DOWNTRENDS)
    # ==========================================
    elif not is_bullish:
        # OPTION 1: 20 & 50 EMA RANGE + BOS
        if "Option 1" in target_setup:
            # Macro Alignment ensures overall downtrend
            if not (c['EMA_20'] < c['EMA_50'] < c['EMA_200']): return None
            
            angle = calculate_ema_angle(df['EMA_50'])
            if angle >= 0: return None # Strict Downward Slope Filter
            
            # --- BREAK OF STRUCTURE (BOS) LOGIC ---
            # Recent Trough (last 20 periods) must be LOWER than Prior Trough (periods 20 to 40 ago)
            recent_trough = df['Low'].iloc[-20:-1].min()
            prior_trough = df['Low'].iloc[-40:-20].min()
            if recent_trough >= prior_trough: return None # Discard if it didn't break structure
            
            # Price must be physically inside the 20 and 50 gap pulling up into resistance
            if c['EMA_20'] <= live_price <= c['EMA_50']:
                return {
                    "Setup": "🔴 Bearish 20-50 Range",
                    "Structure Validated": "✅ BOS Confirmed",
                    "Live Price": round(live_price, 2),
                    "Action Zone": f"E20: {round(c['EMA_20'], 2)} | E50: {round(c['EMA_50'], 2)}",
                    "Trend Slope": f"↘️ {angle}° Down",
                    "Status": "🎯 SELL THE RANGE"
                }

        # OPTION 2: 200 EMA RESISTANCE (Untouched)
        elif "Option 2" in target_setup:
            # Macro Alignment: 50 < 200 (Ensures it's a downtrend pullback)
            if c['EMA_50'] >= c['EMA_200']: return None
            
            angle = calculate_ema_angle(df['EMA_200'])
            if angle >= 0: return None 
            
            # Price must be rejecting off the bottom of the 200 EMA (within 5% below)
            if (c['EMA_200'] * 0.95) <= live_price <= c['EMA_200']:
                distance = round(((c['EMA_200'] - live_price) / c['EMA_200']) * 100, 2)
                return {
                    "Setup": "🔴 Bearish 200 Resistance",
                    "Structure Validated": "N/A (200 Setup)",
                    "Live Price": round(live_price, 2),
                    "Action Zone": f"E200: {round(c['EMA_200'], 2)}",
                    "Trend Slope": f"↘️ {angle}° Down",
                    "Status": f"🎯 SELL RESISTANCE (-{distance}%)"
                }

    return None

# ==========================================
# 5. EXECUTION & DYNAMIC PROGRESS
# ==========================================
if st.button("🔥 RUN EMA OPTION SCANNER", type="primary"):
    is_bull = "Bullish" in direction
    ticker_list = get_index_tickers(selected_sector)
    total_stocks = len(ticker_list)
    
    if ticker_list:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1: st.markdown(f"<div class='metric-box'><span>UNIVERSE</span><h2>{selected_sector}</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-box'><span>RESOLUTION</span><h2>{tf_label}</h2></div>", unsafe_allow_html=True)
        
        mode_label = "20-50 + BOS" if "Option 1" in target_setup else "200 SUPPORT/RES"
        with col3: st.markdown(f"<div class='metric-box'><span>MODE</span><h2>{mode_label}</h2></div>", unsafe_allow_html=True)

        st.write("")
        
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        progress_text.markdown("#### ⏳ Filtering Options & Validating Structural Swings...")
        
        if timeframe == "1mo": period_val, interval_val = "max", "1mo"
        elif timeframe == "1wk": period_val, interval_val = "10y", "1wk"
        elif timeframe == "1d": period_val, interval_val = "3y", "1d"
        else: period_val, interval_val = "60d", "15m"
        
        market_data = yf.download(" ".join(ticker_list), period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        results = []
        for i, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Processing Asset {i + 1} out of {total_stocks} ({ticker.replace('.NS', '')})")
            progress_bar.progress((i + 1) / total_stocks)
            try:
                df = market_data[ticker].dropna() if total_stocks > 1 else market_data.dropna()
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    setup = scan_pure_ema(df, is_bull, target_setup)
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except: pass
                
        progress_text.empty()
        progress_bar.empty()
        st.divider()
        
        if results:
            st.success(f"Isolated {len(results)} assets matching your specific {mode_label} logic.")
            final_df = pd.DataFrame(results)[['Asset', 'Setup', 'Structure Validated', 'Live Price', 'Action Zone', 'Trend Slope', 'Status']]
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else ('color: #FF0000; font-weight: 800;' if '🔴' in str(v) else ''), subset=['Setup'])\
              .map(lambda v: 'color: #4FACFE; font-weight: 800;' if '✅' in str(v) else 'color: #64748B;', subset=['Structure Validated'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Trend Slope'])\
              .map(lambda v: 'color: #00F2FE; font-weight: 900;', subset=['Status'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error(f"0 MATCHES. No stocks currently satisfy the logic for the '{mode_label}' option.")
