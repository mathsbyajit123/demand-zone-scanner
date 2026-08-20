import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import time
import requests
import io

warnings.filterwarnings('ignore')

# ==========================================
# 1. UI & STYLING CONFIGURATION
# ==========================================
st.set_page_config(page_title="MTF GTF BOS Scanner", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #090B10; color: #E2E8F0; }
    .gradient-text {
        font-weight: 900; font-size: 34px; letter-spacing: -1px;
        background: -webkit-linear-gradient(45deg, #00F2FE, #4FACFE, #F6D365);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px; padding-bottom: 0px; text-transform: uppercase;
    }
    .sub-text { font-size: 14px; color: #64748B; margin-top: -5px; margin-bottom: 25px; font-weight: 600;}
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #00C6FF 0%, #0072FF 100%);
        color: white; border: none; border-radius: 6px;
        padding: 12px 24px; font-size: 16px; font-weight: 700; letter-spacing: 1px;
        box-shadow: 0 4px 20px rgba(0, 198, 255, 0.4); width: 100%; text-transform: uppercase;
    }
    .metric-box {
        background-color: #11151C; border-radius: 8px; padding: 15px;
        border: 1px solid #1E293B; text-align: center;
    }
    .metric-box span { color: #4FACFE; font-weight: 600; font-size: 13px; }
    .metric-box h3 { color: #F8FAFC; margin: 0; padding-top: 5px; font-size: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">MTF GTF + VOLUME TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">HTF Demand Interaction | LTF Supply Break of Structure | Volume Spikes</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    
    sector_options = ["F&O Stocks (~242)", "Nifty 50", "Nifty 500", "Nifty Smallcap 250"]
    selected_sector = st.selectbox("Market Universe", sector_options, index=0)
    
    tf_pairs = {
        "HTF: Monthly ➔ LTF: Weekly": {"htf": "1mo", "ltf": "1wk", "period": "5y"},
        "HTF: Weekly ➔ LTF: Daily": {"htf": "1wk", "ltf": "1d", "period": "2y"},
        "HTF: Daily ➔ LTF: 75 Min": {"htf": "1d", "ltf": "75m", "period": "60d"}
    }
    selected_pair = st.selectbox("Multi-Timeframe Engine", list(tf_pairs.keys()), index=1)
    tf_config = tf_pairs[selected_pair]
    
    st.divider()
    vol_multiplier = st.slider("LTF Volume Confirmation (x Avg)", min_value=1.0, max_value=3.0, value=1.5, step=0.1)

# ==========================================
# 3. ROBUST NSE DATA ROUTER
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

def get_clean_ohlc(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()

def fetch_mtf_data(ticker, htf_interval, ltf_interval, period):
    if ltf_interval == "75m":
        ltf_raw = yf.download(ticker, period=period, interval="15m", progress=False)
        ltf_clean = get_clean_ohlc(ltf_raw)
        if not ltf_clean.empty:
            ltf_data = ltf_clean.resample('75min', offset='15min').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
            }).dropna()
        else:
            ltf_data = pd.DataFrame()
    else:
        ltf_raw = yf.download(ticker, period=period, interval=ltf_interval, progress=False)
        ltf_data = get_clean_ohlc(ltf_raw)
        
    htf_raw = yf.download(ticker, period=period, interval=htf_interval, progress=False)
    htf_data = get_clean_ohlc(htf_raw)
    
    return htf_data, ltf_data

# ==========================================
# 4. GTF LOGIC ENGINE
# ==========================================
def analyze_gtf_candles(df):
    df = df.copy()
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    conditions = [
        (df['Body_Pct'] > 50) & (df['Close'] > df['Open']),  
        (df['Body_Pct'] > 50) & (df['Close'] < df['Open']),  
        (df['Body_Pct'] <= 50)                               
    ]
    choices = ['Green Exciting', 'Red Exciting', 'Base']
    df['GTF_Type'] = np.select(conditions, choices, default='Base')
    return df

def get_latest_htf_demand(df):
    """Finds the most recent untested HTF Demand Zone."""
    df = analyze_gtf_candles(df)
    last_idx = len(df) - 1
    
    for i in range(last_idx - 1, 0, -1):
        leg_out = df.iloc[i]
        if leg_out['GTF_Type'] != 'Green Exciting': continue
        
        # Scan backward for 1-3 bases
        base_count = 0
        leg_in_idx = None
        for j in range(i-1, max(-1, i-5), -1):
            if df.iloc[j]['GTF_Type'] == 'Base':
                base_count += 1
            else:
                leg_in_idx = j
                break
                
        if base_count == 0 or base_count > 3 or leg_in_idx is None: continue
        leg_in = df.iloc[leg_in_idx]
        
        base_candles = df.iloc[leg_in_idx+1 : i]
        
        if leg_out['Close'] > base_candles['High'].max():
            proximal = max(base_candles['Open'].max(), base_candles['Close'].max())
            distal = base_candles['Low'].min()
            
            # Check Freshness
            future_data = df.iloc[i+1:]
            if not future_data.empty and (future_data['Low'] <= proximal).any():
                continue # Tested
            
            return proximal, distal
    return None, None

def get_latest_ltf_supply(df):
    """Finds the most recent LTF Supply Zone formed during the pullback."""
    df = analyze_gtf_candles(df)
    last_idx = len(df) - 1
    
    # We look backward to find the nearest valid supply zone
    for i in range(last_idx - 1, 0, -1):
        leg_out = df.iloc[i]
        if leg_out['GTF_Type'] != 'Red Exciting': continue
        
        base_count = 0
        leg_in_idx = None
        for j in range(i-1, max(-1, i-5), -1):
            if df.iloc[j]['GTF_Type'] == 'Base':
                base_count += 1
            else:
                leg_in_idx = j
                break
                
        if base_count == 0 or base_count > 3 or leg_in_idx is None: continue
        
        base_candles = df.iloc[leg_in_idx+1 : i]
        
        if leg_out['Close'] < base_candles['Low'].min():
            proximal = min(base_candles['Open'].min(), base_candles['Close'].min())
            distal = base_candles['High'].max()
            return proximal, distal, i # Return index to check breakout later
    return None, None, None

# ==========================================
# 5. SCANNER EXECUTION
# ==========================================
if st.button("🔥 RUN MTF SCANNER", type="primary"):
    ticker_list = get_index_tickers(selected_sector)
    total_stocks = len(ticker_list)
    
    if ticker_list:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1: st.markdown(f"<div class='metric-box'><span>UNIVERSE</span><h3>{selected_sector}</h3></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-box'><span>HTF -> LTF ENGINE</span><h3>{selected_pair.split(' ')[1]} -> {selected_pair.split(' ')[4]}</h3></div>", unsafe_allow_html=True)
        with col3: st.markdown(f"<div class='metric-box'><span>TARGET</span><h3>DEMAND + BOS</h3></div>", unsafe_allow_html=True)

        st.write("")
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        alerts = []
        
        for idx, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Tracing MTF Footprints ({idx+1}/{total_stocks}): `{ticker.replace('.NS', '')}`")
            progress_bar.progress((idx + 1) / total_stocks)
            
            try:
                htf, ltf = fetch_mtf_data(ticker, tf_config['htf'], tf_config['ltf'], tf_config['period'])
                
                if len(htf) < 20 or len(ltf) < 20: continue
                
                # 1. Map HTF Demand
                htf_prox, htf_dist = get_latest_htf_demand(htf)
                if not htf_prox: continue
                
                live_price = ltf['Close'].iloc[-1]
                
                # 2. Check Interaction (Is Price in/near HTF Demand?)
                if not (live_price <= htf_prox * 1.02 and live_price >= htf_dist): continue
                
                # 3. Map LTF Supply
                ltf_prox, ltf_dist, supply_idx = get_latest_ltf_supply(ltf)
                if not ltf_dist: continue
                
                # 4. Check LTF Break of Structure (Close > Supply Distal)
                ltf['Vol_SMA'] = ltf['Volume'].rolling(20).mean()
                
                future_ltf = ltf.iloc[supply_idx+1:]
                bos_achieved = False
                vol_confirmed = False
                bos_vol_ratio = 0
                
                for _, candle in future_ltf.iterrows():
                    if candle['Close'] > ltf_dist: 
                        bos_achieved = True
                        avg_v = candle['Vol_SMA']
                        if avg_v > 0 and candle['Volume'] > (avg_v * vol_multiplier):
                            vol_confirmed = True
                            bos_vol_ratio = round(candle['Volume'] / avg_v, 1)
                        break # We only need the first BOS candle
                
                if bos_achieved and vol_confirmed:
                    alerts.append({
                        "Asset": ticker.replace(".NS", ""),
                        "HTF Demand": f"₹{round(htf_prox, 1)}",
                        "LTF Supply Broken": f"₹{round(ltf_dist, 1)}",
                        "Live Price": f"₹{round(live_price, 1)}",
                        "Volume Jump": f"🔥 {bos_vol_ratio}x Avg",
                        "Status": "✅ MTF SYNCED"
                    })
            except Exception as e:
                pass
                
        progress_text.empty()
        progress_bar.empty()
        st.divider()
        
        if alerts:
            st.success(f"Isolated {len(alerts)} setup(s). Market has tapped HTF Demand and violently shattered LTF Supply.")
            results_df = pd.DataFrame(alerts)
            
            styled = results_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;', subset=['Status'])\
              .map(lambda v: 'color: #4FACFE; font-weight: 800;', subset=['HTF Demand'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Volume Jump'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. No stocks are currently bridging HTF Demand with a volume-confirmed LTF Break of Structure.")
