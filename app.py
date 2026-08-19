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
st.set_page_config(page_title="Apex Target-Locked Scanner", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #090B10; color: #E2E8F0; }
    .gradient-text {
        font-weight: 900; font-size: 34px; letter-spacing: -1px;
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

st.markdown('<p class="gradient-text">TARGET-LOCKED GTF TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Single Base Entry | 2-Candle Breakout Allowance | Pullback Target Mapper</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    
    sector_options = ["F&O Stocks (~242)", "Nifty 50", "Nifty 500", "Nifty Smallcap 250"]
    selected_sector = st.selectbox("Market Universe", sector_options, index=0)
    
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
    direction = st.radio("Target Zone Vector", ("🟢 Demand (Buy Fresh Pullbacks)", "🔴 Supply (Sell Fresh Pullbacks)"))

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
# 4. TARGET-LOCKED GTF ENGINE
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

def scan_target_locked_zones(df, is_bullish):
    if len(df) < 30: return None
    
    df = analyze_gtf_candles(df)
    
    search_df = df.tail(300) 
    last_idx = len(search_df) - 1
    today_candle = search_df.iloc[last_idx]
    live_price = today_candle['Close']
    
    for i in range(1, last_idx - 3):
        leg_in = search_df.iloc[i-1]
        
        # STRICT RULE: Single Base Candle Only
        base_candle = search_df.iloc[i]
        if base_candle['GTF_Type'] != 'Base': continue 
        
        leg_out_1 = search_df.iloc[i+1]
        leg_out_2 = search_df.iloc[i+2]
        
        valid_leg_out_idx = None
        pattern = None
        
        # ==========================================
        # STEP 1: ENTRY ZONE VALIDATION (1 or 2 Candles)
        # ==========================================
        if is_bullish:
            # Check 1st Leg Out
            if leg_out_1['GTF_Type'] == 'Green Exciting' and leg_out_1['Close'] > leg_in['High']:
                valid_leg_out_idx = i + 1
            # Check 2nd Leg Out if 1st fails
            elif leg_out_2['GTF_Type'] == 'Green Exciting' and leg_out_2['Close'] > leg_in['High']:
                valid_leg_out_idx = i + 2
                
            if valid_leg_out_idx:
                proximal = max(base_candle['Open'], base_candle['Close'])
                distal = base_candle['Low']
                pattern = 'DBR' if leg_in['GTF_Type'] == 'Red Exciting' else 'RBR'

        elif not is_bullish:
            # Check 1st Leg Out
            if leg_out_1['GTF_Type'] == 'Red Exciting' and leg_out_1['Close'] < leg_in['Low']:
                valid_leg_out_idx = i + 1
            # Check 2nd Leg Out if 1st fails
            elif leg_out_2['GTF_Type'] == 'Red Exciting' and leg_out_2['Close'] < leg_in['Low']:
                valid_leg_out_idx = i + 2
                
            if valid_leg_out_idx:
                proximal = min(base_candle['Open'], base_candle['Close'])
                distal = base_candle['High']
                pattern = 'RBD' if leg_in['GTF_Type'] == 'Green Exciting' else 'DBD'
                
        if not valid_leg_out_idx: continue
        
        # ==========================================
        # STEP 2: STRICT FRESHNESS & ACTIVE TOUCH
        # ==========================================
        future_data = search_df.iloc[valid_leg_out_idx + 1 : last_idx]
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
        
        trading_at_zone = False
        if is_bullish:
            if today_candle['Low'] <= (proximal * 1.025) and live_price >= distal: 
                trading_at_zone = True
        else:
            if today_candle['High'] >= (proximal * 0.975) and live_price <= distal:
                trading_at_zone = True
                
        if not trading_at_zone: continue
        
        # ==========================================
        # STEP 3: THE PULLBACK TARGET MAPPER
        # ==========================================
        fixed_target = None
        
        if not future_data.empty:
            if is_bullish:
                # Find the Peak of the rally (The start of the pullback leg)
                peak_idx = future_data['High'].idxmax()
                # Isolate the downward pullback leg
                pullback_leg = search_df.loc[peak_idx : last_idx.name]
                
                # Scan inside the pullback leg for a Supply Zone (Target)
                for t_i in range(1, len(pullback_leg) - 2):
                    t_leg_in = pullback_leg.iloc[t_i-1]
                    if t_leg_in['GTF_Type'] == 'Base': continue
                    
                    for t_b in range(1, 4): # Target can be 1-3 bases
                        if t_i + t_b >= len(pullback_leg): continue
                        t_bases = pullback_leg.iloc[t_i : t_i+t_b]
                        t_leg_out = pullback_leg.iloc[t_i+t_b]
                        
                        if not all(t_bases['GTF_Type'] == 'Base'): continue
                        
                        if t_leg_out['GTF_Type'] == 'Red Exciting' and t_leg_out['Close'] < t_leg_in['Low']:
                            t_proximal = min(t_bases['Open'].min(), t_bases['Close'].min())
                            if t_proximal > proximal: # Target MUST be physically above Entry
                                fixed_target = t_proximal
                                break
                    if fixed_target: break

            else: # Bearish Setup
                # Find the Bottom of the crash (The start of the upward pullback leg)
                trough_idx = future_data['Low'].idxmin()
                # Isolate the upward pullback leg
                pullback_leg = search_df.loc[trough_idx : last_idx.name]
                
                # Scan inside the pullback leg for a Demand Zone (Target)
                for t_i in range(1, len(pullback_leg) - 2):
                    t_leg_in = pullback_leg.iloc[t_i-1]
                    if t_leg_in['GTF_Type'] == 'Base': continue
                    
                    for t_b in range(1, 4): 
                        if t_i + t_b >= len(pullback_leg): continue
                        t_bases = pullback_leg.iloc[t_i : t_i+t_b]
                        t_leg_out = pullback_leg.iloc[t_i+t_b]
                        
                        if not all(t_bases['GTF_Type'] == 'Base'): continue
                        
                        if t_leg_out['GTF_Type'] == 'Green Exciting' and t_leg_out['Close'] > t_leg_in['High']:
                            t_proximal = max(t_bases['Open'].max(), t_bases['Close'].max())
                            if t_proximal < proximal: # Target MUST be physically below Entry
                                fixed_target = t_proximal
                                break
                    if fixed_target: break

        # Throw away the setup if no fixed institutional target was formed in the pullback
        if not fixed_target: continue 
        
        # Calculate Risk to Reward
        risk = abs(proximal - distal)
        reward = abs(fixed_target - proximal)
        rr_ratio = round(reward / risk, 1) if risk > 0 else 0
        
        return {
            "GTF Setup": f"🟢 {pattern}" if is_bullish else f"🔴 {pattern}",
            "Entry (Prox)": round(proximal, 2),
            "SL (Distal)": round(distal, 2),
            "Target (Opposing)": f"🎯 {round(fixed_target, 2)}",
            "R:R Ratio": f"1 : {rr_ratio}",
            "Live Price": round(live_price, 2)
        }
        
    return None

# ==========================================
# 5. EXECUTION & DYNAMIC PROGRESS
# ==========================================
if st.button("🔥 RUN TARGET-LOCKED SCAN", type="primary"):
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
        
        progress_text.markdown("#### ⏳ Scanning Single Base Structures & Mapping Pullback Targets...")
        
        if timeframe == "1mo":
            interval_val = "1mo"
            period_val = "max"
        elif timeframe == "1wk":
            interval_val = "1wk"
            period_val = "10y" 
        elif timeframe == "1d":
            interval_val = "1d"
            period_val = "3y" 
        else: 
            interval_val = "15m"
            period_val = "60d"
        
        market_data = yf.download(" ".join(ticker_list), period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        results = []
        
        for i, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Analyzing Trade Plans {i + 1} out of {total_stocks} ({ticker.replace('.NS', '')})")
            progress_bar.progress((i + 1) / total_stocks)
            
            try:
                df = market_data[ticker].dropna() if total_stocks > 1 else market_data.dropna()
                
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    
                    setup = scan_target_locked_zones(df, is_bull)
                    
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except:
                pass
                
        progress_text.empty()
        progress_bar.empty()
        st.divider()
        
        if results:
            st.success(f"Successfully isolated {len(results)} assets with a PERFECT SINGLE-BASE ENTRY and a MAPPED INSTITUTIONAL TARGET.")
            
            final_df = pd.DataFrame(results)[['Asset', 'GTF Setup', 'Entry (Prox)', 'SL (Distal)', 'Target (Opposing)', 'R:R Ratio', 'Live Price']]
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else ('color: #FF0000; font-weight: 800;' if '🔴' in str(v) else ''), subset=['GTF Setup'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800; font-size: 16px;', subset=['Target (Opposing)'])\
              .map(lambda v: 'color: #00F2FE; font-weight: 900;', subset=['R:R Ratio'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. The dual-engine filter is incredibly strict. No stocks formed a 1-Base Entry with a verified Opposing Zone in the pullback leg today.")
