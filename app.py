import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SETTINGS
# ==========================================
st.set_page_config(page_title="Strict MTF Confluence Scanner", layout="wide")
st.title("🎯 MTF Strict Confluence Scanner")
st.markdown("Executes a strict Dual-Timeframe approach: HTF Trend Filtering + LTF Zone Creation, explicitly tracking Fresh Taps vs Approaching setups.")

st.sidebar.header("⚙️ Market Settings")
sector_options = [
    "F&O Stocks (~223+)",
    "Non-F&O Stocks (Nifty 500 base)",
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options, index=0)

st.sidebar.header("⏱️ Timeframe Alignment")
htf_options = {"1 Month": "1mo", "1 Week": "1wk", "1 Day": "1d"}
ltf_options = {"1 Day": "1d", "75 Minutes (Intraday)": "75m"}

htf_label = st.sidebar.selectbox("Higher Timeframe (HTF)", list(htf_options.keys()), index=1)
ltf_label = st.sidebar.selectbox("Lower Timeframe (LTF)", list(ltf_options.keys()), index=0)

htf = htf_options[htf_label]
ltf = ltf_options[ltf_label]

st.sidebar.header("🎯 Setup Direction")
direction = st.sidebar.radio("Direction", ("🟢 Bullish (Long)", "🔴 Bearish (Short)"))

st.sidebar.header("📍 Pullback Proximity")
proximity_filter = st.sidebar.radio(
    "Where is the LTF Live Price?",
    (
        "Show Both (Tapped & Approaching)",
        "🎯 Freshly Tapped Only",
        "⏳ Approaching Only"
    )
)

st.sidebar.header("📐 Base & Breakout Strictness")
max_base_candles = st.sidebar.slider("Max Base Candles (1 to X)", min_value=1, max_value=4, value=4)
base_body_pct = st.sidebar.slider("Max Base Body % (Tightness)", min_value=20, max_value=80, value=50)
legout_body_pct = st.sidebar.slider("Min Leg-Out Body % (Impulsive)", min_value=50, max_value=90, value=70)

st.sidebar.header("🧲 Execution Hit-Box")
atr_multiplier = st.sidebar.slider("ATR Pullback Allowance", min_value=0.1, max_value=2.0, value=0.5, step=0.1)

# ==========================================
# 2. DATA FETCHER 
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
    if "F&O Stocks" in sector_name: return [f"{ticker}.NS" for ticker in fo_stocks_list]
        
    csv_file = {
        "Nifty 50": "ind_nifty50list.csv", "Nifty 500": "ind_nifty500list.csv",
        "Non-F&O Stocks (Nifty 500 base)": "ind_nifty500list.csv", "Nifty Midcap 100": "ind_niftymidcap100list.csv",
        "Nifty Bank": "ind_niftybanklist.csv"
    }.get(sector_name, "ind_nifty500list.csv")
    
    mirrors = [
        f"https://raw.githubusercontent.com/althk/zerobha/main/{csv_file}",
        f"https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/{csv_file}"
    ]
    
    fetched_list = []
    for url in mirrors:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                symbol_col = next((col for col in df.columns if 'Symbol' in col or 'SYMBOL' in col), None)
                if symbol_col:
                    fetched_list = [str(s).strip() for s in df[symbol_col]]
                    break 
        except Exception: continue
            
    if not fetched_list: return []
    if "Non-F&O" in sector_name:
        return [f"{ticker}.NS" for ticker in fetched_list if ticker not in fo_stocks_list]
    return [f"{ticker}.NS" for ticker in fetched_list]

# ==========================================
# 3. CORE LOGIC ENGINE
# ==========================================
def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return np.max(ranges, axis=1).rolling(window=period).mean()

def check_htf_trend(df, is_bullish):
    """Condition A: HTF Trend Gatekeeper"""
    if len(df) < 50: return False
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    if is_bullish:
        return (curr['Close'] > curr['EMA_44']) and (curr['EMA_44'] > prev['EMA_44'])
    else:
        return (curr['Close'] < curr['EMA_44']) and (curr['EMA_44'] < prev['EMA_44'])

def check_ltf_setup(df, is_bullish, max_bases, base_pct, legout_pct, atr_mult, prox_filter):
    """Condition B & C: LTF Zone Creation + Confluence Pullback"""
    if len(df) < 50: return None
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['ATR'] = calculate_atr(df)
    
    current = df.iloc[-1]
    current_atr = current['ATR'] if not pd.isna(current['ATR']) else current['Range']
    
    valid_zones = []
    
    # 1. SCAN FOR TIGHT BASES + IMPULSIVE BREAKOUT (BOS)
    for i in range(10, len(df) - 2):
        for bases in range(1, max_bases + 1):
            leg_in_idx = i - 1
            base_slice = df.iloc[i : i + bases]
            leg_out_idx = i + bases
            
            if leg_out_idx >= len(df) - 1: break
                
            base_valid = True
            for _, candle in base_slice.iterrows():
                if candle['Range'] == 0 or ((candle['Body'] / candle['Range']) * 100 > base_pct):
                    base_valid = False
                    break
            if not base_valid: continue
                
            base_high = base_slice['High'].max()
            base_low = base_slice['Low'].min()
            
            leg_out = df.iloc[leg_out_idx]
            if leg_out['Range'] == 0: continue
            if (leg_out['Body'] / leg_out['Range']) * 100 < legout_pct: continue
                
            leg_out_green = leg_out['Close'] > leg_out['Open']
            
            past_10_high = df['High'].iloc[i-10 : i].max()
            past_10_low = df['Low'].iloc[i-10 : i].min()
            
            if is_bullish and leg_out_green and (leg_out['Close'] > base_high):
                if leg_out['Close'] > past_10_high:
                    valid_zones.append({
                        'type': 'Demand', 'proximal': base_high, 'distal': base_low, 'index': leg_out_idx
                    })
            elif not is_bullish and not leg_out_green and (leg_out['Close'] < base_low):
                if leg_out['Close'] < past_10_low:
                    valid_zones.append({
                        'type': 'Supply', 'proximal': base_low, 'distal': base_high, 'index': leg_out_idx
                    })

    if not valid_zones: return None
    
    # 2. FILTER UNBROKEN ZONES
    active_zones = []
    for z in valid_zones:
        future_data = df.iloc[z['index']+1 : -1] 
        if is_bullish:
            if not (future_data['Close'] < z['distal']).any(): active_zones.append(z)
        else:
            if not (future_data['Close'] > z['distal']).any(): active_zones.append(z)

    if not active_zones: return None
    
    # 3. CONDITION C: CONFLUENCE PULLBACK & FRESH TAP VERIFICATION
    atr_allowance = current_atr * atr_mult
    
    for z in reversed(active_zones):
        confluence_ema = False
        ltf_ema = current['EMA_44']
        
        is_tapped = False
        is_approaching = False
        
        if is_bullish:
            if ltf_ema >= z['distal'] and ltf_ema <= (z['proximal'] + atr_allowance): confluence_ema = True
            
            # Tapped: Low breached proximal, hasn't broken distal SL
            if current['Low'] <= z['proximal'] and current['Close'] >= z['distal']:
                is_tapped = True
            # Approaching: Low is within ATR allowance, but hasn't touched proximal
            elif current['Low'] > z['proximal'] and current['Low'] <= (z['proximal'] + atr_allowance):
                is_approaching = True
        else:
            if ltf_ema <= z['distal'] and ltf_ema >= (z['proximal'] - atr_allowance): confluence_ema = True
                
            # Tapped: High breached proximal, hasn't broken distal SL
            if current['High'] >= z['proximal'] and current['Close'] <= z['distal']:
                is_tapped = True
            # Approaching: High is within ATR allowance, but hasn't touched proximal
            elif current['High'] < z['proximal'] and current['High'] >= (z['proximal'] - atr_allowance):
                is_approaching = True

        # Apply user proximity filter
        if "Tapped Only" in prox_filter and not is_tapped: continue
        if "Approaching Only" in prox_filter and not is_approaching: continue
        if not (is_tapped or is_approaching): continue # Safety catch

        if confluence_ema:
            risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
            status_msg = "🎯 Freshly Tapped" if is_tapped else "⏳ Approaching"
            
            return {
                "Zone Base": f"{z['type']} (BOS)",
                "Live Price": round(current['Close'], 2),
                "Entry (Proximal)": round(z['proximal'], 2),
                "SL (Distal)": round(z['distal'], 2),
                "Risk %": f"{risk_pct:.2f}%",
                "Pullback Status": status_msg,
                "LTF 44 EMA": round(ltf_ema, 2)
            }
            
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button("Launch MTF Scanner", type="primary"):
    is_bull_setup = "Bullish" in direction
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Running MTF Pipeline: HTF ({htf_label}) ➔ LTF ({ltf_label})")
        
        htf_period = {"1mo": "10y", "1wk": "5y", "1d": "2y"}.get(htf, "5y")
        htf_interval = htf
        
        ltf_period = {"1d": "2y", "75m": "60d"}.get(ltf, "1y")
        ltf_interval = "15m" if ltf == "75m" else "1d"
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {ticker}... ({i+1}/{len(ticker_list)})")
            try:
                # STEP 1: Fetch HTF & Filter
                df_htf = yf.Ticker(ticker).history(period=htf_period, interval=htf_interval)
                if not df_htf.empty and check_htf_trend(df_htf, is_bull_setup):
                    
                    # STEP 2: Fetch LTF & Validate Setup
                    df_ltf = yf.Ticker(ticker).history(period=ltf_period, interval=ltf_interval)
                    if not df_ltf.empty:
                        if ltf == '75m': df_ltf = resample_to_75m(df_ltf)
                        
                        setup = check_ltf_setup(df_ltf, is_bull_setup, max_base_candles, base_body_pct, legout_body_pct, atr_multiplier, proximity_filter)
                        if setup:
                            setup['Ticker'] = ticker.replace(".NS", "")
                            results.append(setup)
            except: pass
            
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        st.subheader(f"📊 {direction[:2]} Strict MTF Results")
        if results:
            final_df = pd.DataFrame(results)[['Ticker', 'Zone Base', 'Live Price', 'Pullback Status', 'Entry (Proximal)', 'SL (Distal)', 'Risk %', 'LTF 44 EMA']]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Target acquired. These strictly match your 3-Condition MTF Checklist.")
        else:
            st.warning("0 matches. The market is not presenting this exact 3-layer confluence setup across both timeframes right now.")
