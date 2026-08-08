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
st.set_page_config(page_title="High-Speed Role Reversal Scanner", layout="wide")
st.title("⚡ Ultra-Speed Role Reversal (BOS Retest) Scanner")
st.markdown("Scans strictly for old S&R zones that were broken with massive momentum and are now being retested from the other side.")

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
    help="Uncheck if using 3M/6M HTF to bypass the 200 EMA data limit."
)

ltf_ema_filter = st.sidebar.radio(
    "Require LTF EMA Confluence at Zone?",
    ("None (Pure Price Action)", "Near 44 EMA", "Near 200 EMA")
)

st.sidebar.header("🎯 Setup Direction")
direction = st.sidebar.radio("Trade Direction", ("🟢 Bullish (Buy at Flipped Resistance)", "🔴 Bearish (Sell at Flipped Support)"))

st.sidebar.header("📍 Proximity Filter")
proximity_filter = st.sidebar.radio(
    "Live Price Status",
    (
        "Show Both (Tapped & Approaching)",
        "🎯 Freshly Tapped Only",
        "⏳ Approaching Only"
    )
)

st.sidebar.header("📐 Strictness Settings")
max_base_candles = st.sidebar.slider("Max Old Base Candles", min_value=1, max_value=4, value=3)
base_body_pct = st.sidebar.slider("Max Old Base Body %", min_value=10, max_value=60, value=50)
breakout_body_pct = st.sidebar.slider("Min BOS Breakout Body %", min_value=60, max_value=95, value=75, help="Forces the breakout to be a true Marubozu/Institutional candle.")
atr_multiplier = st.sidebar.slider("ATR Pullback Hit-Box", min_value=0.1, max_value=2.0, value=0.5, step=0.1)

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
# 3. CORE LOGIC ENGINE & RESAMPLERS
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
    if is_bullish: return (curr['Close'] > curr['EMA_44']) and (curr['EMA_44'] > curr['EMA_200'])
    else: return (curr['Close'] < curr['EMA_44']) and (curr['EMA_44'] < curr['EMA_200'])

def check_role_reversal(df, is_bullish, max_bases, base_pct, breakout_pct, atr_mult, prox_filter, ltf_ema_choice):
    if len(df) < 100: return None
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['ATR'] = calculate_atr(df)
    
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    current = df.iloc[-1]
    current_atr = current['ATR'] if not pd.isna(current['ATR']) else current['Range']
    
    flipped_zones = []
    
    # SCAN FOR OLD ZONES THAT GOT SHATTERED
    for i in range(10, len(df) - 10):
        for bases in range(1, max_bases + 1):
            base_slice = df.iloc[i : i + bases]
            
            # Verify it was a tight, valid base
            base_valid = True
            for _, candle in base_slice.iterrows():
                if candle['Range'] == 0 or ((candle['Body'] / candle['Range']) * 100 > base_pct):
                    base_valid = False
                    break
            if not base_valid: continue
                
            base_high = base_slice['High'].max()
            base_low = base_slice['Low'].min()
            
            # Find the breakout event (BOS) in the future data
            future_data = df.iloc[i + bases : -1]
            if future_data.empty: continue
                
            if is_bullish:
                # Looking for old SUPPLY that was broken UPWARDS
                breakouts = future_data[future_data['Close'] > base_high]
                if not breakouts.empty:
                    bos_idx = breakouts.index[0]
                    bos_candle = breakouts.loc[bos_idx]
                    
                    # Verify breakout was massive (Marubozu style)
                    if bos_candle['Range'] > 0 and ((bos_candle['Body'] / bos_candle['Range']) * 100 >= breakout_pct):
                        
                        # Verify the zone hasn't been completely destroyed on the downside since the breakout
                        post_bos = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
                        if post_bos.empty or not (post_bos['Close'] < base_low).any():
                            # The old Supply High becomes new Demand Entry (Proximal)
                            # The old Supply Low becomes new Demand SL (Distal)
                            flipped_zones.append({
                                'type': 'Flipped to Demand', 'proximal': base_high, 'distal': base_low
                            })
            else:
                # Looking for old DEMAND that was broken DOWNWARDS
                breakdowns = future_data[future_data['Close'] < base_low]
                if not breakdowns.empty:
                    bos_idx = breakdowns.index[0]
                    bos_candle = breakdowns.loc[bos_idx]
                    
                    if bos_candle['Range'] > 0 and ((bos_candle['Body'] / bos_candle['Range']) * 100 >= breakout_pct):
                        
                        post_bos = df.loc[bos_idx+1 : current.name - pd.Timedelta(days=1)]
                        if post_bos.empty or not (post_bos['Close'] > base_high).any():
                            flipped_zones.append({
                                'type': 'Flipped to Supply', 'proximal': base_low, 'distal': base_high
                            })

    if not flipped_zones: return None
    
    atr_allowance = current_atr * atr_mult
    
    # REVERSE TO CHECK THE MOST RECENT ZONES FIRST
    for z in reversed(flipped_zones):
        ema_passed = True
        ema_val = None
        
        if "44" in ltf_ema_choice: ema_val = current['EMA_44']
        elif "200" in ltf_ema_choice: ema_val = current['EMA_200']
            
        if ema_val is not None:
            if is_bullish:
                if not (ema_val >= z['distal'] and ema_val <= (z['proximal'] + atr_allowance)): ema_passed = False
            else:
                if not (ema_val <= z['distal'] and ema_val >= (z['proximal'] - atr_allowance)): ema_passed = False
                    
        if not ema_passed: continue
        
        is_tapped = False
        is_approaching = False
        
        if is_bullish:
            if current['Low'] <= z['proximal'] and current['Close'] >= z['distal']: is_tapped = True
            elif current['Low'] > z['proximal'] and current['Low'] <= (z['proximal'] + atr_allowance): is_approaching = True
        else:
            if current['High'] >= z['proximal'] and current['Close'] <= z['distal']: is_tapped = True
            elif current['High'] < z['proximal'] and current['High'] >= (z['proximal'] - atr_allowance): is_approaching = True

        if "Tapped Only" in prox_filter and not is_tapped: continue
        if "Approaching Only" in prox_filter and not is_approaching: continue
        if not (is_tapped or is_approaching): continue 

        risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
        status_msg = "🎯 Freshly Tapped" if is_tapped else "⏳ Approaching"
        
        ema_str = "N/A"
        if "44" in ltf_ema_choice: ema_str = f"44 EMA: {current['EMA_44']:.2f}"
        if "200" in ltf_ema_choice: ema_str = f"200 EMA: {current['EMA_200']:.2f}"
        
        return {
            "Zone Type": f"{z['type']} (BOS Retest)",
            "Live Price": round(current['Close'], 2),
            "Zone Range": f"₹{round(z['proximal'], 2)} - ₹{round(z['distal'], 2)}",
            "Entry (Proximal)": round(z['proximal'], 2),
            "SL (Distal)": round(z['distal'], 2),
            "Risk %": f"{risk_pct:.2f}%",
            "LTF EMA": ema_str,
            "Status": status_msg
        }
            
    return None

# ==========================================
# 4. BATCH DOWNLOADING ENGINE (THE SPEED FIX)
# ==========================================
if st.sidebar.button("⚡ Launch Batch Scanner", type="primary"):
    is_bull_setup = "Bullish" in direction
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Phase 1: Initiating Mass Batch Download...")
        
        htf_period_val = "max" if htf in ['3mo', '6mo'] else "10y"
        htf_interval_val = "1mo" if htf in ['3mo', '6mo'] else htf
        
        ltf_period_val = {"1mo": "15y", "1wk": "10y", "1d": "5y", "75m": "60d"}.get(ltf, "5y")
        ltf_interval_val = "15m" if ltf == "75m" else ltf
        
        tickers_str = " ".join(ticker_list)
        
        progress_bar = st.progress(10)
        status_text = st.empty()
        
        htf_data = None
        if require_htf_ema:
            status_text.text("📥 Payload 1/2: Downloading Higher Timeframe Market Data...")
            htf_data = yf.download(tickers_str, period=htf_period_val, interval=htf_interval_val, group_by='ticker', threads=True, show_errors=False)
            
        progress_bar.progress(50)
        status_text.text("📥 Payload 2/2: Downloading Lower Timeframe Market Data...")
        ltf_data = yf.download(tickers_str, period=ltf_period_val, interval=ltf_interval_val, group_by='ticker', threads=True, show_errors=False)
        
        progress_bar.progress(85)
        status_text.text("🧠 Phase 2: Processing S&R Flip Logic locally...")
        
        results = []
        
        for ticker in ticker_list:
            try:
                htf_passed = True
                
                if require_htf_ema and htf_data is not None:
                    htf_passed = False
                    df_htf = htf_data if len(ticker_list) == 1 else htf_data[ticker]
                    df_htf = df_htf.dropna()
                    
                    if not df_htf.empty:
                        if htf == '3mo': df_htf = resample_macro(df_htf, '3ME')
                        if htf == '6mo': df_htf = resample_macro(df_htf, '6ME')
                        if len(df_htf) > 200:
                            htf_passed = check_htf_trend(df_htf, is_bull_setup)
                
                if htf_passed:
                    df_ltf = ltf_data if len(ticker_list) == 1 else ltf_data[ticker]
                    df_ltf = df_ltf.dropna()
                    
                    if not df_ltf.empty:
                        if ltf == '75m': df_ltf = resample_to_75m(df_ltf)
                        
                        setup = check_role_reversal(df_ltf, is_bull_setup, max_base_candles, base_body_pct, breakout_body_pct, atr_multiplier, proximity_filter, ltf_ema_filter)
                        if setup:
                            setup['Ticker'] = ticker.replace(".NS", "")
                            results.append(setup)
                            
            except Exception:
                pass
                
        progress_bar.progress(100)
        status_text.empty()
        progress_bar.empty()
        
        st.subheader(f"📊 {direction[:2]} Strict Role Reversal Results")
        if results:
            final_df = pd.DataFrame(results)[['Ticker', 'Zone Type', 'Live Price', 'Zone Range', 'Entry (Proximal)', 'SL (Distal)', 'Risk %', 'LTF EMA', 'Status']]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Lightning Batch Scan Complete. Support/Resistance Flips isolated.")
        else:
            st.warning("0 matches. The stringent Break of Structure (BOS) rule and proximity limits successfully filtered out the noise.")
