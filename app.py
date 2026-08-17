import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import io, requests

warnings.filterwarnings('ignore')

# ==========================================
# 1. UI & STYLING
# ==========================================
st.set_page_config(page_title="GTF Fresh S&D Scanner", layout="wide")

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

st.markdown('<p class="gradient-text">GTF FRESH ZONE TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">1-2 Base | 8-20% Rally | Untested Zones | Active Fresh Retest</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    
    sector_options = ["F&O Stocks (~225)", "Nifty 50", "Nifty 500", "Nifty Smallcap 250"]
    selected_sector = st.selectbox("Market Universe", sector_options, index=0)
    
    tf_options = {
        "1 Day": "1d", 
        "1 Week": "1wk",
        "1 Month": "1mo",
        "3 Month": "3mo",
        "6 Month": "6mo"
    }
    tf_label = st.selectbox("Resolution (Timeframe)", list(tf_options.keys()), index=0)
    timeframe = tf_options[tf_label]
    
    st.divider()
    direction = st.radio("Target Zone Vector", ("🟢 Demand (Buy Fresh Pullbacks)", "🔴 Supply (Sell Fresh Pullbacks)"))

# ==========================================
# 3. DATA ROUTING & RESAMPLING
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
    
    csv_file = ""
    if "500" in sector_name: csv_file = "ind_nifty500list.csv"
    elif "250" in sector_name: csv_file = "ind_niftysmallcap250list.csv"
    elif "50" in sector_name: csv_file = "ind_nifty50list.csv"
    
    try:
        response = requests.get(f"https://raw.githubusercontent.com/althk/zerobha/main/{csv_file}", timeout=10)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            return [f"{s.strip()}.NS" for s in df['Symbol']]
        else:
            raise Exception("File not found")
    except:
        return [f"{t}.NS" for t in fo_stocks_list]

def resample_custom_months(df, months):
    rule = f'{months}ME'
    return df.resample(rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

# ==========================================
# 4. STRICT GTF ENGINE WITH "FRESH" LOGIC
# ==========================================
def analyze_gtf_candles(df):
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    conditions = [
        (df['Body_Pct'] > 50) & (df['Close'] > df['Open']),  
        (df['Body_Pct'] > 50) & (df['Close'] < df['Open']),  
        (df['Body_Pct'] <= 50)                               
    ]
    choices = ['Green Exciting', 'Red Exciting', 'Base']
    df['GTF_Type'] = np.select(conditions, choices, default='Unknown')
    return df

def scan_fresh_gtf_zones(df, is_bullish):
    if len(df) < 15: return None
    
    df = analyze_gtf_candles(df)
    current_candle = df.iloc[-1]
    current_price = current_candle['Close']
    
    search_df = df.tail(60) 
    
    for i in range(len(search_df) - 3, 0, -1):
        leg_in = search_df.iloc[i-1]
        
        # STRICT GTF RULE: Max 1 to 2 Base Candles
        for base_len in range(1, 3):
            if i + base_len >= len(search_df): continue
            
            base_candles = search_df.iloc[i : i + base_len]
            leg_out = search_df.iloc[i + base_len]
            
            if not all(base_candles['GTF_Type'] == 'Base'): continue
            
            # --- DEMAND LOGIC ---
            if is_bullish and leg_out['GTF_Type'] == 'Green Exciting':
                if leg_out['Close'] <= leg_in['High']: continue 
                
                proximal = max(base_candles['Open'].max(), base_candles['Close'].max())
                distal = base_candles['Low'].min()
                
                rally_pct = ((leg_out['Close'] - proximal) / proximal) * 100
                if rally_pct < 8.0 or rally_pct > 20.0: continue
                
                pattern = 'DBR' if leg_in['GTF_Type'] == 'Red Exciting' else ('RBR' if leg_in['GTF_Type'] == 'Green Exciting' else None)
                
            # --- SUPPLY LOGIC ---
            elif not is_bullish and leg_out['GTF_Type'] == 'Red Exciting':
                if leg_out['Close'] >= leg_in['Low']: continue 
                
                proximal = min(base_candles['Open'].min(), base_candles['Close'].min())
                distal = base_candles['High'].max()
                
                rally_pct = ((proximal - leg_out['Close']) / proximal) * 100
                if rally_pct < 8.0 or rally_pct > 20.0: continue
                
                pattern = 'RBD' if leg_in['GTF_Type'] == 'Green Exciting' else ('DBD' if leg_in['GTF_Type'] == 'Red Exciting' else None)
                
            else:
                continue
                
            if not pattern: continue
            
            # --- "FRESHNESS" & BROKEN VALIDATION ---
            # Extract all candles AFTER the leg-out, but BEFORE today's live candle
            future_data = search_df.iloc[i + base_len + 1 : -1]
            is_tested = False
            is_broken = False
            
            if not future_data.empty:
                for _, past_candle in future_data.iterrows():
                    if is_bullish:
                        # If a past candle dipped into the zone, it is NOT fresh. Trash it.
                        if past_candle['Low'] <= proximal: is_tested = True
                        if past_candle['Close'] < distal: is_broken = True
                    else:
                        # If a past candle spiked into the zone, it is NOT fresh. Trash it.
                        if past_candle['High'] >= proximal: is_tested = True
                        if past_candle['Close'] > distal: is_broken = True
                        
            if is_broken or is_tested: continue
            
            # --- ACTIVE LIVE RETEST (MEETING FRESHLY) ---
            trading_at_zone = False
            
            if is_bullish:
                # Today's price is dipping into the zone and hasn't closed below it
                if current_price <= (proximal * 1.02) and current_candle['Close'] >= distal: 
                    trading_at_zone = True
            else:
                # Today's price is spiking into the zone and hasn't closed above it
                if current_price >= (proximal * 0.98) and current_candle['Close'] <= distal:
                    trading_at_zone = True
            
            if trading_at_zone:
                return {
                    "GTF Setup": f"🟢 {pattern}" if is_bullish else f"🔴 {pattern}",
                    "Structure": f"{base_len} Base (Fresh)",
                    "Momentum": f"{round(rally_pct, 2)}% Leg-Out",
                    "Live Price": round(current_price, 2),
                    "Entry (Prox)": round(proximal, 2),
                    "SL (Distal)": round(distal, 2),
                    "Status": "🔥 1st TIME TEST"
                }
    return None

# ==========================================
# 5. EXECUTION & DYNAMIC PROGRESS
# ==========================================
if st.button("🔥 RUN GTF FRESH ZONE SCAN", type="primary"):
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
        
        progress_text.markdown("#### ⏳ Fetching Historical Institutional Data...")
        
        # Mapping timeframe requests to yfinance logic
        if timeframe in ["6mo", "3mo", "1mo"]:
            interval_val = "1mo"
            period_val = "max"
        elif timeframe == "1wk":
            interval_val = "1wk"
            period_val = "5y"
        else: # 1d
            interval_val = "1d"
            period_val = "2y"
        
        market_data = yf.download(" ".join(ticker_list), period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        results = []
        
        for i, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Analyzing {i + 1} out of {total_stocks} ({ticker.replace('.NS', '')})")
            progress_bar.progress((i + 1) / total_stocks)
            
            try:
                df = market_data[ticker].dropna() if total_stocks > 1 else market_data.dropna()
                
                if not df.empty:
                    # Execute custom resampling for 3M and 6M
                    if timeframe == '6mo': 
                        df = resample_custom_months(df, 6)
                    elif timeframe == '3mo':
                        df = resample_custom_months(df, 3)
                        
                    setup = scan_fresh_gtf_zones(df, is_bull)
                    
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except:
                pass
                
        progress_text.empty()
        progress_bar.empty()
        st.divider()
        
        if results:
            st.success(f"Successfully isolated {len(results)} assets testing a VERIFIED FRESH GTF Zone.")
            
            final_df = pd.DataFrame(results)[['Asset', 'GTF Setup', 'Structure', 'Momentum', 'Live Price', 'Entry (Prox)', 'SL (Distal)', 'Status']]
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else ('color: #FF0000; font-weight: 800;' if '🔴' in str(v) else ''), subset=['GTF Setup'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Momentum'])\
              .map(lambda v: 'color: #00F2FE; font-weight: 900;', subset=['Status'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. The GTF rules have filtered all noise. No fresh, untested zones are currently being tapped in this sector on this timeframe.")
