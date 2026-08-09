import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import io, requests

warnings.filterwarnings('ignore')

# ==========================================
# 1. APEX TERMINAL UI
# ==========================================
st.set_page_config(page_title="Apex Rapid S&D Scanner", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #090B10; color: #E2E8F0; }
    .gradient-text {
        font-weight: 900; font-size: 42px; letter-spacing: -1px;
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
    .css-1d391kg { background-color: #11151C; border-right: 1px solid #1E293B; }
    div[data-testid="metric-container"] {
        background-color: #11151C; border-radius: 8px; padding: 20px;
        border: 1px solid #1E293B; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }
    div[data-testid="metric-container"] label { color: #4FACFE !important; font-weight: 600; letter-spacing: 1px; }
    div[data-testid="metric-container"] div { color: #F8FAFC !important; }
    </style>
""", unsafe_allow_html=True)

def render_hud(progress, status):
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; margin: 30px 0px;">
        <div style="width: 120px; height: 120px; border-radius: 50%; background: conic-gradient(#00C6FF {progress}%, #1E293B 0); display: flex; justify-content: center; align-items: center; box-shadow: 0 0 20px rgba(0, 198, 255, 0.2);">
            <div style="width: 105px; height: 105px; border-radius: 50%; background-color: #090B10; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: 900; color: #F8FAFC;">
                {int(progress)}<span style="font-size: 12px; color: #64748B;">%</span>
            </div>
        </div>
        <p style="color: #4FACFE; font-size: 14px; margin-top: 15px; font-weight: 600; letter-spacing: 1px;">{status}</p>
    </div>
    """

st.markdown('<p class="gradient-text">APEX RAPID SCANNER</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Active Zone Penetration & Proximity Alert</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    sector_options = ["F&O Stocks (~223+)", "Nifty 50", "Nifty 500"]
    selected_sector = st.selectbox("Market Universe", sector_options, index=0)
    
    tf_options = {
        "75 Min": "75m", 
        "1 Day": "1d", 
        "1 Week": "1wk", 
        "1 Month": "1mo", 
        "3 Month": "3mo"
    }
    tf_label = st.selectbox("Resolution", list(tf_options.keys()), index=0)
    timeframe = tf_options[tf_label]
    
    direction = st.radio("Target Vector", ("🟢 Active Demand (Buy)", "🔴 Active Supply (Sell)"))
    
    st.divider()
    st.markdown("### 📐 **GEOMETRY OVERRIDE**")
    st.caption("Loosen these if valid setups are being missed.")
    max_base_body = st.slider("Max Base Body %", 20, 80, 50)
    min_leg_body = st.slider("Min Leg-Out Body %", 40, 100, 60)
    leg_mult = st.slider("Leg Momentum Multiplier", 1.0, 3.0, 1.2, step=0.1)

# ==========================================
# 3. UNIVERSE ROUTING
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
    
    csv_file = "ind_nifty50list.csv" if "50" in sector_name and "500" not in sector_name else "ind_nifty500list.csv"
    try:
        response = requests.get(f"https://raw.githubusercontent.com/althk/zerobha/main/{csv_file}", timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        return [f"{s.strip()}.NS" for s in df['Symbol']]
    except:
        return [f"{t}.NS" for t in fo_stocks_list]

# ==========================================
# 4. STRICT PENETRATION & PROXIMITY ENGINE
# ==========================================
def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

def get_active_zone(df, is_bullish, tf_label, max_b_body, min_l_body, l_mult):
    df = df.tail(100) # Give it 100 bars of history to ensure we don't cut off zones forming slightly earlier
    if len(df) < 5: return None
    
    current_price = df.iloc[-1]['Close']
    current_low = df.iloc[-1]['Low']
    current_high = df.iloc[-1]['High']
    
    # Map timeframe to dynamic proximity threshold (%)
    if "Month" in tf_label: max_dist_pct = 3.0
    elif "Week" in tf_label: max_dist_pct = 1.0
    else: max_dist_pct = 1.5

    MAX_BASE_CANDLES = 2
    
    for i in range(len(df) - 3, 0, -1):
        for b_len in range(1, MAX_BASE_CANDLES + 1):
            
            if i + b_len >= len(df): continue
            
            base_slice = df.iloc[i : i + b_len]
            leg_idx = i + b_len
            leg_candle = df.iloc[leg_idx]
            
            # --- 1. VERIFY BASE STRICTNESS ---
            valid_base = True
            total_base_rng = 0.0
            
            for _, candle in base_slice.iterrows():
                rng = candle['High'] - candle['Low']
                body = abs(candle['Close'] - candle['Open'])
                body_pct = (body / rng * 100) if rng > 0 else 0
                if body_pct > max_b_body:
                    valid_base = False
                    break
                total_base_rng += rng
                
            if not valid_base: continue
            avg_base_rng = total_base_rng / b_len
            if avg_base_rng == 0: continue
            
            # --- 2. VERIFY LEG-OUT MOMENTUM ---
            leg_rng = leg_candle['High'] - leg_candle['Low']
            leg_body = abs(leg_candle['Close'] - leg_candle['Open'])
            leg_body_pct = (leg_body / leg_rng * 100) if leg_rng > 0 else 0
            
            if leg_body_pct < min_l_body or leg_rng < (avg_base_rng * l_mult):
                continue
                
            if is_bullish and leg_candle['Close'] <= leg_candle['Open']: continue
            if not is_bullish and leg_candle['Close'] >= leg_candle['Open']: continue
                
            # --- 3. ZONE BOUNDARIES (FIXED OVERLAP BUG) ---
            if is_bullish:
                proximal = max(base_slice['Open'].max(), base_slice['Close'].max())
                distal = base_slice['Low'].min()
                # FIX: Leg-out only needs to clear the bodies (proximal line), not the extreme wick
                if leg_candle['Close'] <= proximal: continue 
            else:
                proximal = min(base_slice['Open'].min(), base_slice['Close'].min())
                distal = base_slice['High'].max()
                # FIX: Leg-out only needs to clear the bodies
                if leg_candle['Close'] >= proximal: continue
                
            # --- 4. VERIFY IT IS NOT A BROKEN ZONE ---
            future_data = df.iloc[leg_idx + 1 : -1]
            is_broken = False
            touch_count = 0
            
            if not future_data.empty:
                for _, past_candle in future_data.iterrows():
                    if is_bullish:
                        # FIX: It only dies if a candle closed below the distal line
                        if past_candle['Close'] < distal: is_broken = True
                        elif past_candle['Low'] <= proximal: touch_count += 1
                    else:
                        # FIX: It only dies if a candle closed above the distal line
                        if past_candle['Close'] > distal: is_broken = True
                        elif past_candle['High'] >= proximal: touch_count += 1
            
            if is_broken: continue
            
            # --- 5. EXECUTION & PROXIMITY TRIGGER ---
            in_zone = False
            approaching = False
            
            if is_bullish:
                if current_low <= proximal and current_price >= distal:
                    in_zone = True
                elif proximal < current_price <= proximal * (1 + (max_dist_pct / 100)):
                    approaching = True
            else:
                if current_high >= proximal and current_price <= distal:
                    in_zone = True
                elif proximal * (1 - (max_dist_pct / 100)) <= current_price < proximal:
                    approaching = True
            
            if in_zone or approaching:
                status_msg = "🎯 IN ZONE" if in_zone else f"⚠️ APPROACHING (<{max_dist_pct}%)"
                zone_type = f"🟢 Demand (Tested {touch_count}x)" if is_bullish else f"🔴 Supply (Tested {touch_count}x)"
                
                return {
                    "Zone Type": zone_type,
                    "Live Price": round(current_price, 2),
                    "Entry": round(proximal, 2),
                    "SL": round(distal, 2),
                    "Action": status_msg
                }
    return None

# ==========================================
# 5. HIGH-SPEED SCANNER
# ==========================================
col1, col2, col3 = st.columns([1, 1, 1])

if st.button("⚡ SCAN FOR LIVE EXECUTIONS", type="primary"):
    is_bull = "Demand" in direction
    ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        with col1: st.metric("TRACKING", f"{len(ticker_list)} ASSETS")
        with col2: st.metric("RESOLUTION", f"{tf_label}")
        with col3: st.metric("VECTOR", "LONG" if is_bull else "SHORT")

        if timeframe == "3mo": period_val = "max"
        elif timeframe == "1mo": period_val = "10y"
        elif timeframe == "1wk": period_val = "5y"
        elif timeframe == "1d": period_val = "2y"
        else: period_val = "60d"

        interval_val = "15m" if timeframe == "75m" else timeframe
        
        tickers_str = " ".join(ticker_list)
        progress_ui = st.empty()
        progress_ui.markdown(render_hud(10, "FETCHING MARKET DATA..."), unsafe_allow_html=True)
        
        market_data = yf.download(tickers_str, period=period_val, interval=interval_val, group_by='ticker', threads=True)
        progress_ui.markdown(render_hud(60, "HUNTING PROXIMITY & PENETRATIONS..."), unsafe_allow_html=True)
        
        results = []
        total = len(ticker_list)
        
        for i, ticker in enumerate(ticker_list):
            try:
                df = market_data if len(ticker_list) == 1 else market_data[ticker]
                df = df.dropna()
                
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    
                    setup = get_active_zone(df, is_bull, tf_label, max_base_body, min_leg_body, leg_mult)
                    
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except Exception:
                pass
            
            if i % 25 == 0 or i == total - 1:
                progress_ui.markdown(render_hud(60 + (i/total)*40, f"ANALYZING {ticker.replace('.NS', '')}"), unsafe_allow_html=True)
                
        progress_ui.empty()
        st.divider()
        st.markdown(f"### 🎯 IMMEDIATE TARGETS")
        
        if results:
            final_df = pd.DataFrame(results)[['Asset', 'Zone Type', 'Live Price', 'Entry', 'SL', 'Action']]
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B'
            }).map(lambda v: 'color: #00F2FE; font-weight: 900;' if 'IN ZONE' in str(v) else ('color: #F6D365; font-weight: 800;' if 'APPROACHING' in str(v) else 'color: #64748B;'), subset=['Action'])\
              .map(lambda v: 'color: #00FF00; font-weight: 800;' if 'Demand' in str(v) else 'color: #FF0000; font-weight: 800;', subset=['Zone Type'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. You may need to loosen the Geometry Override sliders in the sidebar to catch setups with wider bases or weaker breakouts.")
