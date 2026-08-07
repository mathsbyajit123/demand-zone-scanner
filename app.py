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
st.set_page_config(page_title="Pro S&D ATR Scanner", layout="wide")
st.title("🎯 Pro S&D Scanner (ATR & Marubozu Engine)")
st.markdown("Utilizes Average True Range (ATR) for dynamic hit-boxes and enforces strict Marubozu-style leg-out candles to filter out false breakouts.")

st.sidebar.header("⚙️ Market Settings")
sector_options = [
    "F&O Stocks (~223+)",
    "Non-F&O Stocks (Nifty 500 base)",
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Auto"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options, index=0)

timeframe_options = {
    "1 Day": "1d",
    "1 Week": "1wk",
    "1 Month": "1mo",
    "75 Minutes (Intraday)": "75m"
}
selected_tf_label = st.sidebar.selectbox("Timeframe", list(timeframe_options.keys()))
timeframe = timeframe_options[selected_tf_label]

st.sidebar.header("🎯 Trade Strategy")
direction = st.sidebar.radio(
    "Select Setup Direction",
    ("🟢 Bullish (Buy Setups)", "🔴 Bearish (Sell Setups)")
)

zone_strategy = st.sidebar.radio(
    "Select Zone Strategy",
    (
        "Standard (Pure S&D Zones)", 
        "Flipped / BOS Retest (Role Reversal)",
        "Show Me Both"
    )
)

st.sidebar.header("📐 Candle strictness")
base_body_pct = st.sidebar.slider("Max Base Candle Body % (The Wide Net)", min_value=20, max_value=80, value=55, 
                                  help="Keep this slightly loose (50-60%) so the computer doesn't reject good setups over a 0.1% difference.")
legout_body_pct = st.sidebar.slider("Min Leg-Out Body % (Marubozu Filter)", min_value=50, max_value=95, value=75, 
                                    help="Set high (70-85%) to ensure the breakout candle has very small wicks and massive momentum.")

st.sidebar.header("🧲 ATR Dynamic Hit-Box")
atr_multiplier = st.sidebar.slider("ATR Approach Multiplier", min_value=0.1, max_value=2.0, value=0.5, step=0.1,
                                   help="0.5x ATR means the stock is allowed to be half its average daily range away from the zone and still trigger.")

# ==========================================
# 2. DATA FETCHER & F&O FILTER
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
    
    if "F&O Stocks" in sector_name:
        return [f"{ticker}.NS" for ticker in fo_stocks_list]
        
    csv_file = {
        "Nifty 50": "ind_nifty50list.csv",
        "Nifty 500": "ind_nifty500list.csv",
        "Non-F&O Stocks (Nifty 500 base)": "ind_nifty500list.csv",
        "Nifty Midcap 100": "ind_niftymidcap100list.csv",
        "Nifty Bank": "ind_niftybanklist.csv",
        "Nifty IT": "ind_niftyitlist.csv",
        "Nifty Auto": "ind_niftyautolist.csv"
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
        except Exception:
            continue
            
    if not fetched_list:
        return []
        
    if "Non-F&O" in sector_name:
        non_fo_list = [ticker for ticker in fetched_list if ticker not in fo_stocks_list]
        return [f"{ticker}.NS" for ticker in non_fo_list]
        
    return [f"{ticker}.NS" for ticker in fetched_list]

# ==========================================
# 3. CORE LOGIC (ATR + MARUBOZU)
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
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(window=period).mean()

def check_setup(df, dir_choice, strategy_choice, base_pct, legout_pct, atr_mult):
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    if len(df) < 30: return None 
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['ATR'] = calculate_atr(df)
    
    is_bullish = "Bullish" in dir_choice
    current = df.iloc[-1]
    current_atr = current['ATR'] if not pd.isna(current['ATR']) else current['Range']
    
    target_zones = []
    
    # 1. STRICT 1-BASE & MARUBOZU LEG-OUT SCAN
    for i in range(1, len(df) - 2):
        leg_in_idx = i - 1
        base_idx = i
        leg_out_idx = i + 1
        
        # Base Evaluation
        base_range = df['Range'].iloc[base_idx]
        if base_range == 0: continue
        
        if (df['Body'].iloc[base_idx] / base_range) * 100 > base_pct: continue
            
        base_high = df['High'].iloc[base_idx]
        base_low = df['Low'].iloc[base_idx]
        
        # Leg-Out Evaluation (Strict Marubozu Filter)
        leg_out_range = df['Range'].iloc[leg_out_idx]
        if leg_out_range == 0: continue
            
        leg_out_body_pct = (df['Body'].iloc[leg_out_idx] / leg_out_range) * 100
        if leg_out_body_pct < legout_pct: continue # Rejects wicky breakouts
            
        leg_out_green = df['Close'].iloc[leg_out_idx] > df['Open'].iloc[leg_out_idx]
        leg_in_green = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
        leg_in_type = "R" if leg_in_green else "D"
        
        if leg_out_green and df['Close'].iloc[leg_out_idx] > base_high:
            target_zones.append({
                'raw_type': 'Demand', 'pattern': f"{leg_in_type}BR",
                'proximal': base_high, 'distal': base_low, 'index': leg_out_idx
            })
        elif not leg_out_green and df['Close'].iloc[leg_out_idx] < base_low:
            target_zones.append({
                'raw_type': 'Supply', 'pattern': f"{leg_in_type}BD",
                'proximal': base_low, 'distal': base_high, 'index': leg_out_idx
            })

    # 2. FILTER & PROCESS BOS / ROLE REVERSALS
    final_zones = []
    want_standard = "Standard" in strategy_choice or "Both" in strategy_choice
    want_flipped = "Flipped" in strategy_choice or "Both" in strategy_choice
    
    for z in target_zones:
        future_data = df.iloc[z['index']+1 : -1] 
        
        if want_standard:
            if len(future_data) == 0:
                if (is_bullish and z['raw_type'] == 'Demand') or (not is_bullish and z['raw_type'] == 'Supply'):
                    final_zones.append(z)
            else:
                if is_bullish and z['raw_type'] == 'Demand':
                    if not (future_data['Close'] < z['distal']).any(): final_zones.append(z)
                elif not is_bullish and z['raw_type'] == 'Supply':
                    if not (future_data['Close'] > z['distal']).any(): final_zones.append(z)
                    
        if want_flipped and len(future_data) > 0:
            if is_bullish and z['raw_type'] == 'Supply':
                breakouts = future_data[future_data['Close'] > z['distal']]
                if not breakouts.empty:
                    bos_idx = breakouts.index[0]
                    post_bos = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
                    if post_bos.empty or not (post_bos['Close'] < z['proximal']).any():
                        final_zones.append({
                            'pattern': f"Flipped {z['pattern']} (BOS)",
                            'proximal': z['distal'], 'distal': z['proximal'], 'index': bos_idx
                        })
            elif not is_bullish and z['raw_type'] == 'Demand':
                breakdowns = future_data[future_data['Close'] < z['distal']]
                if not breakdowns.empty:
                    bos_idx = breakdowns.index[0]
                    post_bos = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
                    if post_bos.empty or not (post_bos['Close'] > z['proximal']).any():
                        final_zones.append({
                            'pattern': f"Flipped {z['pattern']} (BOS)",
                            'proximal': z['distal'], 'distal': z['proximal'], 'index': bos_idx
                        })

    if not final_zones: return None
    
    # 3. DYNAMIC ATR PROXIMITY CHECK
    atr_allowance = current_atr * atr_mult
    
    for z in reversed(final_zones): 
        is_valid = False
        
        if is_bullish:
            # Low comes within ATR allowance of proximal line, Close stays above Stop Loss
            if current['Low'] <= (z['proximal'] + atr_allowance) and current['Close'] >= z['distal']:
                is_valid = True
        else:
            if current['High'] >= (z['proximal'] - atr_allowance) and current['Close'] <= z['distal']:
                is_valid = True

        if is_valid:
            risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
            
            if is_bullish:
                status = "✅ IN ZONE" if current['Close'] <= z['proximal'] else f"⏳ NEAR ZONE (+{atr_mult} ATR)"
            else:
                status = "✅ IN ZONE" if current['Close'] >= z['proximal'] else f"⏳ NEAR ZONE (-{atr_mult} ATR)"
                
            return {
                "Pattern": z['pattern'],
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "Risk %": f"{risk_pct:.2f}%",
                "Status": status
            }
            
    return None

# ==========================================
# 4. EXECUTION
# ==========================================
if st.sidebar.button(f"Launch Scanner", type="primary"):
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for ATR-calibrated setups...")
        
        if timeframe == '75m': fetch_period, fetch_interval = "60d", "15m"
        elif timeframe == '1d': fetch_period, fetch_interval = "2y", "1d"
        elif timeframe == '1wk': fetch_period, fetch_interval = "5y", "1wk"
        else: fetch_period, fetch_interval = "10y", "1mo"
        
        progress_bar = st.progress(0)
        results = []
        
        for i, ticker in enumerate(ticker_list):
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=fetch_interval)
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    setup = check_setup(df, direction, zone_strategy, base_body_pct, legout_body_pct, atr_multiplier)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append(setup)
            except: pass
            progress_bar.progress((i + 1) / len(ticker_list))
            
        progress_bar.empty()
        
        st.subheader(f"📊 Scan Results ({selected_tf_label})")
        if results:
            final_df = pd.DataFrame(results)[['Ticker', 'Pattern', 'Live Price', 'Zone Entry', 'Stop Loss', 'Risk %', 'Status']]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Target setups acquired. Verify these on Upstox, Zerodha, or TradingView to confirm alignment.")
        else:
            st.warning(f"0 matches. The Marubozu strictness successfully filtered out weak setups.")
