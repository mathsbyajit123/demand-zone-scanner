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
st.set_page_config(page_title="GTF Rated S&D Scanner", layout="wide")

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

st.markdown('<p class="gradient-text">GTF RATED ZONE TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Deep History Scan | Gap Theory | 7-Point Institutional Score</p>', unsafe_allow_html=True)

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
# 4. GTF ENGINE & SCORING MATHEMATICS
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

def calculate_gtf_score(base_len, rally_pct, is_gap):
    # GTF Rule: 1-2 bases are superior. 3 bases is acceptable but lower probability.
    base_score = 2 if base_len <= 2 else 1
    
    # GTF Rule: Massive momentum (>10%) or Gaps score maximum strength.
    momentum_score = 2 if (is_gap or rally_pct >= 10.0) else 1
    
    # GTF Rule: The scanner inherently filters tested zones, so freshness is always maximum.
    fresh_score = 3
    
    total = base_score + momentum_score + fresh_score
    
    if total == 7: return "⭐⭐⭐⭐⭐ (7/7)"
    elif total == 6: return "⭐⭐⭐⭐ (6/7)"
    else: return "⭐⭐⭐ (5/7)"

def scan_fresh_gtf_zones(df, is_bullish):
    if len(df) < 20: return None
    
    df = analyze_gtf_candles(df)
    
    # Extract deep history (up to ~1 year of daily bars)
    search_df = df.tail(300) 
    last_idx = len(search_df) - 1
    today_candle = search_df.iloc[last_idx]
    live_price = today_candle['Close']
    
    for i in range(1, last_idx - 3):
        leg_in = search_df.iloc[i-1]
        
        # Allows up to 3 Base Candles now
        for base_len in range(1, 4):
            leg_out_idx = i + base_len
            if leg_out_idx >= last_idx: continue # Zone must have formed before today
            
            base_candles = search_df.iloc[i : leg_out_idx]
            leg_out = search_df.iloc[leg_out_idx]
            
            if not all(base_candles['GTF_Type'] == 'Base'): continue
            
            pattern = None
            is_gap = False
            
            # --- DEMAND & GAP DEMAND LOGIC ---
            if is_bullish:
                is_standard_leg = (leg_out['GTF_Type'] == 'Green Exciting' and leg_out['Close'] > leg_in['High'])
                # Gap Up logic: Opened above the highest point of the base and formed a green/neutral body
                is_gap_up = (leg_out['Open'] > base_candles['High'].max()) and (leg_out['Close'] >= leg_out['Open'])
                
                if is_standard_leg or is_gap_up:
                    proximal = max(base_candles['Open'].max(), base_candles['Close'].max())
                    distal = base_candles['Low'].min()
                    rally_pct = ((leg_out['Close'] - proximal) / proximal) * 100
                    
                    if is_gap_up:
                        pattern = 'DBR (GAP)' if leg_in['GTF_Type'] == 'Red Exciting' else 'RBR (GAP)'
                        is_gap = True
                    else:
                        pattern = 'DBR' if leg_in['GTF_Type'] == 'Red Exciting' else 'RBR'
                        
                    # Expanded Momentum Rule: 5% to 30% (Catch large cap moves)
                    if not is_gap and (rally_pct < 5.0 or rally_pct > 30.0): continue

            # --- SUPPLY & GAP SUPPLY LOGIC ---
            elif not is_bullish:
                is_standard_leg = (leg_out['GTF_Type'] == 'Red Exciting' and leg_out['Close'] < leg_in['Low'])
                # Gap Down logic: Opened below the lowest point of the base and formed a red/neutral body
                is_gap_down = (leg_out['Open'] < base_candles['Low'].min()) and (leg_out['Close'] <= leg_out['Open'])
                
                if is_standard_leg or is_gap_down:
                    proximal = min(base_candles['Open'].min(), base_candles['Close'].min())
                    distal = base_candles['High'].max()
                    rally_pct = ((proximal - leg_out['Close']) / proximal) * 100
                    
                    if is_gap_down:
                        pattern = 'RBD (GAP)' if leg_in['GTF_Type'] == 'Green Exciting' else 'DBD (GAP)'
                        is_gap = True
                    else:
                        pattern = 'RBD' if leg_in['GTF_Type'] == 'Green Exciting' else 'DBD'
                        
                    if not is_gap and (rally_pct < 5.0 or rally_pct > 30.0): continue
                
            if not pattern: continue
            
            # --- "FRESHNESS" & BROKEN VALIDATION ---
            # Look at all days between the Leg-Out and Yesterday
            future_data = search_df.iloc[leg_out_idx + 1 : last_idx]
            is_tested = False
            is_broken = False
            
            if not future_data.empty:
                for _, past_candle in future_data.iterrows():
                    if is_bullish:
                        if past_candle['Low'] <= proximal: is_tested = True
                        if past_candle['Close'] < distal: is_broken = True
                    else:
                        if past_candle['High'] >= proximal: is_tested = True
                        if past_candle['Close'] > distal: is_broken = True
                        
            if is_broken or is_tested: continue
            
            # --- DYNAMIC ACTIVE TOUCH (TODAY'S ACTION) ---
            trading_at_zone = False
            
            if is_bullish:
                # If TODAY'S LOW pierced the proximal line (or came within 2.5% of it) AND hasn't hit stop loss
                if today_candle['Low'] <= (proximal * 1.025) and live_price >= distal: 
                    trading_at_zone = True
            else:
                # If TODAY'S HIGH pierced the proximal line (or came within 2.5% of it) AND hasn't hit stop loss
                if today_candle['High'] >= (proximal * 0.975) and live_price <= distal:
                    trading_at_zone = True
            
            if trading_at_zone:
                gtf_rating = calculate_gtf_score(base_len, rally_pct, is_gap)
                
                return {
                    "GTF Setup": f"🟢 {pattern}" if is_bullish else f"🔴 {pattern}",
                    "Structure": f"{base_len} Base",
                    "GTF Score": gtf_rating,
                    "Live Price": round(live_price, 2),
                    "Entry (Prox)": round(proximal, 2),
                    "SL (Distal)": round(distal, 2),
                    "Action": "🎯 FRESH TAP TODAY"
                }
    return None

# ==========================================
# 5. EXECUTION & DYNAMIC PROGRESS
# ==========================================
if st.button("🔥 RUN GTF SCORED SCAN", type="primary"):
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
        
        progress_text.markdown("#### ⏳ Retrieving 1 Year Deep History & Scanning...")
        
        if timeframe in ["6mo", "3mo", "1mo"]:
            interval_val = "1mo"
            period_val = "max"
        elif timeframe == "1wk":
            interval_val = "1wk"
            period_val = "5y"
        else: # 1d
            interval_val = "1d"
            period_val = "3y" # Deepened to catch older, massive daily zones
        
        market_data = yf.download(" ".join(ticker_list), period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        results = []
        
        for i, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Analyzing & Grading {i + 1} out of {total_stocks} ({ticker.replace('.NS', '')})")
            progress_bar.progress((i + 1) / total_stocks)
            
            try:
                df = market_data[ticker].dropna() if total_stocks > 1 else market_data.dropna()
                
                if not df.empty:
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
            st.success(f"Successfully isolated {len(results)} assets tapping a VERIFIED FRESH GTF Zone today.")
            
            final_df = pd.DataFrame(results)[['Asset', 'GTF Setup', 'Structure', 'GTF Score', 'Live Price', 'Entry (Prox)', 'SL (Distal)', 'Action']]
            final_df = final_df.sort_values(by="GTF Score", ascending=False)
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else ('color: #FF0000; font-weight: 800;' if '🔴' in str(v) else ''), subset=['GTF Setup'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800; font-size: 16px;', subset=['GTF Score'])\
              .map(lambda v: 'color: #00F2FE; font-weight: 900;', subset=['Action'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. The GTF algorithm scanned 1 year of history, but no stocks touched an untested zone today.")
