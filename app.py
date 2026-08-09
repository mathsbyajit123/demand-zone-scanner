import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. UI & STYLING
# ==========================================
st.set_page_config(page_title="Momentum & Reversion Scanner", layout="wide", initial_sidebar_state="expanded")

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
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">PURE MOMENTUM SCANNER</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">20 EMA Wick Fills & BTST Volume Explosions</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    
    strategy = st.radio("Select Execution Strategy", (
        "⚡ BTST Power Close (Run @ 3:15 PM)", 
        "📉 20 EMA Pullback (Run Post-Market)"
    ))
    
    st.divider()
    st.caption("Scanning NSE F&O Universe (~225 Highly Liquid Stocks)")

# F&O Universe List
def get_fo_tickers():
    return [
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

# ==========================================
# 3. ALGORITHMIC ENGINES
# ==========================================
def scan_btst(df):
    """Hunts for end-of-day volume spikes closing near HOD in an uptrend."""
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Avg_Vol_20'] = df['Volume'].rolling(window=20).mean().shift(1)
    
    c = df.iloc[-1] # Current Day
    
    # Rule 1: Uptrend Check
    if c['Close'] < c['EMA_50']: return None
    
    # Rule 2: Closing within 1% of High of the Day (No upper wick trap)
    if c['Close'] < (c['High'] * 0.99): return None
    
    # Rule 3: Must be a Green Candle
    if c['Close'] <= c['Open']: return None
    
    # Rule 4: Volume Explosion (1.5x greater than average)
    if c['Volume'] < (1.5 * c['Avg_Vol_20']): return None
    
    return {
        "Setup": "⚡ BTST Momentum",
        "Live Price": round(c['Close'], 2),
        "Vol Spike": f"{round((c['Volume'] / c['Avg_Vol_20']), 1)}x Avg",
        "Action": "🎯 BUY @ 3:20 PM"
    }

def scan_20_ema(df):
    """Hunts for pullbacks to the 20 EMA with absorption logic and calculates Wick Fill limits."""
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    c = df.iloc[-1]
    
    # Rule 1: Strict Uptrend (20 EMA > 50 EMA)
    if c['EMA_20'] <= c['EMA_50']: return None
    
    # Rule 2: The Pullback Tap (Low of candle must pierce or touch the 20 EMA zone)
    if c['Low'] > (c['EMA_20'] * 1.015): return None # Too far above
    if c['High'] < (c['EMA_20'] * 0.985): return None # Too far below
    
    body = abs(c['Close'] - c['Open'])
    lower_wick = min(c['Open'], c['Close']) - c['Low']
    upper_wick = c['High'] - max(c['Open'], c['Close'])
    
    # Rule 3: The Proof of Life (Must be a Hammer OR a solid green candle bouncing off the line)
    is_hammer = (lower_wick > (1.5 * body)) and (upper_wick < body)
    is_green_bounce = (c['Close'] > c['Open']) and (c['Low'] <= c['EMA_20'])
    
    if not (is_hammer or is_green_bounce): return None
    
    # --- WICK FILL MATH & SL CALCULATION ---
    # If the wick is large, it calculates the 50% midpoint limit order. Otherwise, it uses the High break.
    if lower_wick > (c['Close'] * 0.01): 
        entry_price = c['Low'] + (lower_wick / 2)
        entry_type = "50% Wick Limit"
    else:
        entry_price = c['High'] * 1.002
        entry_type = "Break of High Limit"
        
    hard_sl = c['Low'] * 0.99
    risk_rupees = entry_price - hard_sl
    target = entry_price + (risk_rupees * 2) # Strict 1:2 R:R
    
    return {
        "Setup": "📉 20 EMA Reversal",
        "Live Price": round(c['Close'], 2),
        "Limit Entry": f"₹{round(entry_price, 2)} ({entry_type})",
        "Hard SL (1% Buf)": round(hard_sl, 2),
        "1:2 Target": round(target, 2)
    }

# ==========================================
# 4. EXECUTION
# ==========================================
if st.button("🔥 INITIATE RAW MARKET SCAN", type="primary"):
    ticker_list = [f"{t}.NS" for t in get_fo_tickers()]
    
    st.markdown(f"#### Analyzing **{len(ticker_list)}** F&O Stocks...")
    progress_bar = st.progress(0)
    
    # Pull Daily Data. 100 days is enough to cleanly calculate a 50 EMA and 20-Day Vol Avg.
    market_data = yf.download(" ".join(ticker_list), period="100d", interval="1d", group_by='ticker', threads=True)
    
    results = []
    total = len(ticker_list)
    
    for i, ticker in enumerate(ticker_list):
        try:
            df = market_data[ticker].dropna() if len(ticker_list) > 1 else market_data.dropna()
            if df.empty or len(df) < 55:
                continue
            
            if "BTST" in strategy:
                setup = scan_btst(df)
            else:
                setup = scan_20_ema(df)
                
            if setup:
                setup['Asset'] = ticker.replace(".NS", "")
                results.append(setup)
        except:
            pass
            
        progress_bar.progress((i + 1) / total)
        
    progress_bar.empty()
    st.divider()
    
    if results:
        st.success(f"Successfully isolated {len(results)} high-probability institutional setups.")
        
        # Display Ordering Based on Strategy
        if "BTST" in strategy:
            final_df = pd.DataFrame(results)[['Asset', 'Setup', 'Live Price', 'Vol Spike', 'Action']]
        else:
            final_df = pd.DataFrame(results)[['Asset', 'Setup', 'Live Price', 'Limit Entry', 'Hard SL (1% Buf)', '1:2 Target']]
        
        styled = final_df.style.set_properties(**{
            'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B'
        }).map(lambda v: 'color: #00F2FE; font-weight: 900;' if 'BUY' in str(v) else 'color: #F8FAFC;', subset=['Action'] if "BTST" in strategy else [])
        
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.error("0 MATCHES. The algorithm filtered out the noise. No stocks meet the strict mathematical criteria right now. Protect your capital and wait for the next session.")
