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
st.set_page_config(page_title="Apex Flip Zone Scanner", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #090B10; color: #E2E8F0; }
    .gradient-text {
        font-weight: 900; font-size: 40px; letter-spacing: -1px;
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
    .metric-box h2 { color: #F8FAFC; margin: 0; padding-top: 5px; font-size: 28px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">ROLE REVERSAL (FLIP ZONE) ENGINE</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Scans for Broken Demand turned Supply & Broken Supply turned Demand</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    
    sector_options = ["F&O Stocks (~225)", "Nifty 50", "Nifty 500"]
    selected_sector = st.selectbox("Market Universe", sector_options, index=0)
    
    tf_options = {
        "1 Day": "1d", 
        "1 Week": "1wk",
        "1 Month": "1mo"
    }
    tf_label = st.selectbox("Resolution (Timeframe)", list(tf_options.keys()), index=2)
    timeframe = tf_options[tf_label]
    
    st.divider()
    direction = st.radio("Target Flip Setup", (
        "🔴 Demand turned Supply (Short Pullbacks)", 
        "🟢 Supply turned Demand (Long Pullbacks)"
    ))

# ==========================================
# 3. DATA ROUTING 
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
# 4. STRICT FLIP ZONE (ROLE REVERSAL) ENGINE
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

def scan_flip_zones(df, target_setup):
    """
    Hunts for original zones, waits for them to be broken by a closing candle, 
    and alerts when the price pulls back into the newly created Flip Zone.
    """
    if len(df) < 30: return None
    
    df = analyze_gtf_candles(df)
    current_price = df.iloc[-1]['Close']
    
    # We must scan deeper into the past (120 bars) because old zones take time to break and flip
    search_df = df.tail(120) 
    
    for i in range(len(search_df) - 5):
        leg_in = search_df.iloc[i]
        
        for base_len in range(1, 4): # Max 3 Base Candles
            if i + base_len >= len(search_df): continue
            
            base_candles = search_df.iloc[i+1 : i+1+base_len]
            leg_out = search_df.iloc[i+1+base_len]
            
            if not all(base_candles['GTF_Type'] == 'Base'): continue
            
            # ==========================================================
            # SETUP 1: DEMAND TURNED SUPPLY (Like your DLF Chart)
            # ==========================================================
            if "Demand turned Supply" in target_setup:
                # Identify original Demand Zone
                if leg_out['GTF_Type'] == 'Green Exciting' and leg_out['Close'] > leg_in['High']:
                    old_proximal = max(base_candles['Open'].max(), base_candles['Close'].max())
                    old_distal = base_candles['Low'].min()
                    
                    future_data = search_df.iloc[i+1+base_len+1 : -1]
                    is_broken = False
                    is_destroyed = False
                    
                    for _, past_candle in future_data.iterrows():
                        if not is_broken:
                            # Break Phase: Candle MUST close below the Demand Zone to flip it
                            if past_candle['Close'] < old_distal:
                                is_broken = True 
                        else:
                            # Destroy Phase: If it breaks above the old proximal, the new supply is dead
                            if past_candle['Close'] > old_proximal:
                                is_destroyed = True
                                break
                                
                    if is_broken and not is_destroyed:
                        # New Entry is at the Old Distal (Bottom of the broken box)
                        new_entry = old_distal
                        new_sl = old_proximal
                        
                        # Trigger if price pulls up into the bottom of the flipped zone
                        if current_price >= (new_entry * 0.98) and current_price <= new_sl:
                            return {
                                "Zone Type": "🔴 Dem turned Supply",
                                "History": "DZ Broken Down",
                                "Live Price": round(current_price, 2),
                                "New Entry": round(new_entry, 2),
                                "New SL": round(new_sl, 2),
                                "Action": "🎯 SELL THE FLIP"
                            }
                            
            # ==========================================================
            # SETUP 2: SUPPLY TURNED DEMAND 
            # ==========================================================
            elif "Supply turned Demand" in target_setup:
                # Identify original Supply Zone
                if leg_out['GTF_Type'] == 'Red Exciting' and leg_out['Close'] < leg_in['Low']:
                    old_proximal = min(base_candles['Open'].min(), base_candles['Close'].min())
                    old_distal = base_candles['High'].max()
                    
                    future_data = search_df.iloc[i+1+base_len+1 : -1]
                    is_broken = False
                    is_destroyed = False
                    
                    for _, past_candle in future_data.iterrows():
                        if not is_broken:
                            # Break Phase: Candle MUST close above the Supply Zone to flip it
                            if past_candle['Close'] > old_distal:
                                is_broken = True 
                        else:
                            # Destroy Phase: If it breaks below the old proximal, the new demand is dead
                            if past_candle['Close'] < old_proximal:
                                is_destroyed = True
                                break
                                
                    if is_broken and not is_destroyed:
                        # New Entry is at the Old Distal (Top of the broken box)
                        new_entry = old_distal
                        new_sl = old_proximal
                        
                        # Trigger if price pulls down into the top of the flipped zone
                        if current_price <= (new_entry * 1.02) and current_price >= new_sl:
                            return {
                                "Zone Type": "🟢 Sup turned Demand",
                                "History": "SZ Broken Up",
                                "Live Price": round(current_price, 2),
                                "New Entry": round(new_entry, 2),
                                "New SL": round(new_sl, 2),
                                "Action": "🎯 BUY THE FLIP"
                            }
    return None

# ==========================================
# 5. EXECUTION & DYNAMIC PROGRESS
# ==========================================
if st.button("🔥 RUN FLIP ZONE SCANNER", type="primary"):
    ticker_list = get_index_tickers(selected_sector)
    total_stocks = len(ticker_list)
    
    if ticker_list:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1: st.markdown(f"<div class='metric-box'><span>TRACKING</span><h2>{total_stocks} ASSETS</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-box'><span>RESOLUTION</span><h2>{tf_label}</h2></div>", unsafe_allow_html=True)
        with col3: st.markdown(f"<div class='metric-box'><span>VECTOR</span><h2>{'SHORT' if 'Supply' in direction else 'LONG'}</h2></div>", unsafe_allow_html=True)

        st.write("")
        
        progress_text = st.empty()
        progress_bar = st.progress(0)
        progress_text.markdown("#### ⏳ Mapping Historical Zones & Tracking Violations...")
        
        # Deep historical pull to allow time for zones to form, break, and retest
        interval_val = "1mo" if timeframe == "1mo" else ("1wk" if timeframe == "1wk" else "1d")
        period_val = "max" if timeframe == "1mo" else ("5y" if timeframe == "1wk" else "2y")
        
        market_data = yf.download(" ".join(ticker_list), period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        results = []
        
        for i, ticker in enumerate(ticker_list):
            progress_text.markdown(f"#### 🔍 Analyzing {i + 1} out of {total_stocks} ({ticker.replace('.NS', '')})")
            progress_bar.progress((i + 1) / total_stocks)
            
            try:
                df = market_data[ticker].dropna() if total_stocks > 1 else market_data.dropna()
                if not df.empty:
                    setup = scan_flip_zones(df, direction)
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except:
                pass
                
        progress_text.empty()
        progress_bar.empty()
        st.divider()
        
        if results:
            st.success(f"Successfully isolated {len(results)} assets actively testing a verified Flip Zone.")
            
            final_df = pd.DataFrame(results)[['Asset', 'Zone Type', 'History', 'Live Price', 'New Entry', 'New SL', 'Action']]
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else ('color: #FF0000; font-weight: 800;' if '🔴' in str(v) else ''), subset=['Zone Type'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['History'])\
              .map(lambda v: 'color: #00F2FE; font-weight: 900;', subset=['Action'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. No assets are currently pulling back to retest a broken Flip Zone right now.")
