import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import warnings
import concurrent.futures

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SETTINGS
# ==========================================
st.set_page_config(page_title="High-Speed MTF S&D Scanner", layout="wide")
st.title("⚡ High-Speed MTF S&D Scanner")
st.markdown("Features 3M/6M Macro tracking, HTF trend filtering, strict LTF Marubozu breakouts, and multithreaded execution for rapid scanning.")

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
htf_options = {"6 Months": "6mo", "3 Months": "3mo", "1 Month": "1mo", "1 Week": "1wk", "1 Day": "1d"}
ltf_options = {"1 Month": "1mo", "1 Week": "1wk", "1 Day": "1d", "75 Minutes (Intraday)": "75m"}

htf_label = st.sidebar.selectbox("Higher Timeframe (HTF)", list(htf_options.keys()), index=2)
ltf_label = st.sidebar.selectbox("Lower Timeframe (LTF)", list(ltf_options.keys()), index=2)

htf = htf_options[htf_label]
ltf = ltf_options[ltf_label]

st.sidebar.header("📈 EMA Settings")
require_htf_ema = st.sidebar.checkbox(
    "✅ Require HTF Trend (44 > 200 EMA)", 
    value=False, 
    help="Uncheck if using 3M or 6M HTF, as 200 EMAs require 50-100 years of data."
)

ltf_ema_filter = st.sidebar.radio(
    "Require LTF EMA Confluence at Zone?",
    ("None (Pure Price Action)", "Near 44 EMA", "Near 200 EMA"),
    help="Forces the selected EMA to physically pass through or sit right next to the LTF Demand/Supply zone."
)

st.sidebar.header("🎯 Setup Direction")
direction = st.sidebar.radio("Direction", ("🟢 Bullish (Long)", "🔴 Bearish (Short)"))

st.sidebar.header("📍 Current Zone Status")
proximity_filter = st.sidebar.radio(
    "Where is the LTF Live Price?",
    (
        "Show Both (Tapped & Approaching)",
        "🎯 Freshly Tapped Only",
        "⏳ Approaching Only"
    )
)

st.sidebar.header("📐 Base & Breakout Strictness")
max_base_candles = st.sidebar.slider("Max Base Candles (Squeeze)", min_value=1, max_value=3, value=3)
base_body_pct = st.sidebar.slider("Max Base Body % (Shrink Type)", min_value=10, max_value=50, value=45)
legout_body_pct = st.sidebar.slider("Min Leg-Out Body % (Marubozu)", min_value=60, max_value=95, value=80)

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
# 3. CORE LOGIC ENGINE & MACRO RESAMPLERS
# ==========================================
def resample_to_75m(df):
    return df.resample('75min', offset='15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

def resample_macro(df, period):
    return df.resample(period).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return np.max(ranges, axis=1).rolling(window=period).mean()

def check_htf_trend(df, is_bullish):
    if len(df) < 200: return False
    
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    curr = df.iloc[-1]
    
    if is_bullish:
        return (curr['Close'] > curr['EMA_44']) and (curr['EMA_44'] > curr['EMA_200'])
    else:
        return (curr['Close'] < curr['EMA_44']) and (curr['EMA_44'] < curr['EMA_200'])

def check_ltf_setup(df, is_bullish, max_bases, base_pct, legout_pct, atr_mult, prox_filter, ltf_ema_choice):
    if len(df) < 200: return None
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['ATR'] = calculate_atr(df)
    
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    current = df.iloc[-1]
    current_atr = current['ATR'] if not pd.isna(current['ATR']) else current['Range']
    
    valid_zones = []
    
    for i in range(10, len(df) - 3):
        for bases in range(1, max_bases + 1):
            base_slice = df.iloc[i : i + bases]
            leg1_idx = i + bases
            leg2_idx = i + bases + 1
            
            if leg2_idx >= len(df) - 1: break
                
            base_valid = True
            for _, candle in base_slice.iterrows():
                if candle['Range'] == 0 or ((candle['Body'] / candle['Range']) * 100 > base_pct):
                    base_valid = False
                    break
            if not base_valid: continue
                
            base_high = base_slice['High'].max()
            base_low = base_slice['Low'].min()
            
            leg1 = df.iloc[leg1_idx]
            leg2 = df.iloc[leg2_idx]
            
            if leg1['Range'] == 0 or leg2['Range'] == 0: continue
                
            leg1_body_pct = (leg1['Body'] / leg1['Range']) * 100
            leg2_body_pct = (leg2['Body'] / leg2['Range']) * 100
            
            if leg1_body_pct < legout_pct or leg2_body_pct < legout_pct: continue
                
            leg1_green = leg1['Close'] > leg1['Open']
            leg2_green = leg2['Close'] > leg2['Open']
            
            if is_bullish:
                if leg1_green and leg2_green and (leg1['Close'] > base_high) and (leg2['Close'] > leg1['Close']):
                    valid_zones.append({
                        'type': 'Demand', 'proximal': base_high, 'distal': base_low, 'index': leg2_idx
                    })
            else:
                if not leg1_green and not leg2_green and (leg1['Close'] < base_low) and (leg2['Close'] < leg1['Close']):
                    valid_zones.append({
                        'type': 'Supply', 'proximal': base_low, 'distal': base_high, 'index': leg2_idx
                    })

    if not valid_zones: return None
    
    active_zones = []
    for z in valid_zones:
        future_data = df.iloc[z['index']+1 : -1] 
        if is_bullish:
            if not (future_data['Close'] < z['distal']).any(): active_zones.append(z)
        else:
            if not (future_data['Close'] > z['distal']).any(): active_zones.append(z)

    if not active_zones: return None
    
    atr_allowance = current_atr * atr_mult
    
    for z in reversed(active_zones):
        ema_passed = True
        ema_val = None
        
        if "44" in ltf_ema_choice:
            ema_val = current['EMA_44']
        elif "200" in ltf_ema_choice:
            ema_val = current['EMA_200']
            
        if ema_val is not None:
            if is_bullish:
                if not (ema_val >= z['distal'] and ema_val <= (z['proximal'] + atr_allowance)):
                    ema_passed = False
            else:
                if not (ema_val <= z['distal'] and ema_val >= (z['proximal'] - atr_allowance)):
                    ema_passed = False
                    
        if not ema_passed: continue
        
        is_tapped = False
        is_approaching = False
        
        if is_bullish:
            if current['Low'] <= z['proximal'] and current['Close'] >= z['distal']:
                is_tapped = True
            elif current['Low'] > z['proximal'] and current['Low'] <= (z['proximal'] + atr_allowance):
                is_approaching = True
        else:
            if current['High'] >= z['proximal'] and current['Close'] <= z['distal']:
                is_tapped = True
            elif current['High'] < z['proximal'] and current['High'] >= (z['proximal'] - atr_allowance):
                is_approaching = True

        if "Tapped Only" in prox_filter and not is_tapped: continue
        if "Approaching Only" in prox_filter and not is_approaching: continue
        if not (is_tapped or is_approaching): continue 

        risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
        status_msg = "🎯 Freshly Tapped" if is_tapped else "⏳ Approaching"
        
        ema_str = "N/A"
        if "44" in ltf_ema_choice: ema_str = f"44 EMA: {current['EMA_44']:.2f}"
        if "200" in ltf_ema_choice: ema_str = f"200 EMA: {current['EMA_200']:.2f}"
        
        return {
            "Zone Type": f"{z['type']} (2-Leg)",
            "Live Price": round(current['Close'], 2),
            "Entry (Proximal)": round(z['proximal'], 2),
            "SL (Distal)": round(z['distal'], 2),
            "Risk %": f"{risk_pct:.2f}%",
            "LTF EMA": ema_str,
            "Status": status_msg
        }
            
    return None

# ==========================================
# 4. HIGH-SPEED MULTITHREADED EXECUTION ENGINE
# ==========================================
def scan_single_stock(ticker, is_bull_setup, htf, ltf, req_htf_ema, ltf_ema_choice, max_base, base_pct, legout_pct, atr_mult, prox_filter):
    try:
        htf_passed = True
        
        # Determine Fetch Periods dynamically
        ltf_period = {"1mo": "15y", "1wk": "10y", "1d": "5y", "75m": "60d"}.get(ltf, "5y")
        ltf_interval = "15m" if ltf == "75m" else ltf

        # STEP 1: Fetch HTF & Check Trend if requested
        if req_htf_ema:
            htf_passed = False
            if htf in ['3mo', '6mo']:
                df_htf = yf.Ticker(ticker).history(period="max", interval="1mo")
                if not df_htf.empty:
                    if htf == '3mo': df_htf = resample_macro(df_htf, '3ME')
                    if htf == '6mo': df_htf = resample_macro(df_htf, '6ME')
            else:
                df_htf = yf.Ticker(ticker).history(period="max", interval=htf)
                
            if not df_htf.empty and len(df_htf) > 200:
                htf_passed = check_htf_trend(df_htf, is_bull_setup)
        
        # STEP 2: Fetch LTF & Validate Setup 
        if htf_passed:
            df_ltf = yf.Ticker(ticker).history(period=ltf_period, interval=ltf_interval)
            if not df_ltf.empty:
                if ltf == '75m': df_ltf = resample_to_75m(df_ltf)
                
                setup = check_ltf_setup(df_ltf, is_bull_setup, max_base, base_pct, legout_pct, atr_mult, prox_filter, ltf_ema_choice)
                if setup:
                    setup['Ticker'] = ticker.replace(".NS", "")
                    return setup
    except Exception:
        pass
    return None

if st.sidebar.button("⚡ Launch High-Speed Scanner", type="primary"):
    is_bull_setup = "Bullish" in direction
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        htf_ema_status = "ON" if require_htf_ema else "OFF"
        ltf_ema_status = ltf_ema_filter.split(' ')[0]
        st.info(f"Loaded {len(ticker_list)} stocks. Running Multithreaded Scan. HTF: {htf_ema_status} ➔ LTF EMA: {ltf_ema_status}")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        # Set max_workers to 15 for optimal speed without triggering Yahoo Finance anti-bot bans
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            future_to_ticker = {
                executor.submit(scan_single_stock, ticker, is_bull_setup, htf, ltf, require_htf_ema, 
                                ltf_ema_filter, max_base_candles, base_body_pct, legout_body_pct, 
                                atr_multiplier, proximity_filter): ticker 
                for ticker in ticker_list
            }
            
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_ticker):
                completed_count += 1
                progress_bar.progress(completed_count / len(ticker_list))
                status_text.text(f"Processed {completed_count}/{len(ticker_list)} stocks...")
                
                res = future.result()
                if res:
                    results.append(res)
                    
        status_text.empty()
        progress_bar.empty()
        
        st.subheader(f"📊 {direction[:2]} Strict 2-Leg Results")
        if results:
            final_df = pd.DataFrame(results)[['Ticker', 'Zone Type', 'Live Price', 'Status', 'Entry (Proximal)', 'SL (Distal)', 'Risk %', 'LTF EMA']]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Lightning scan complete. Target acquired.")
        else:
            st.warning("0 matches found based on the current strict conditions.")
