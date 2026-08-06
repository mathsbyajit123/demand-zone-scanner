import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SETTINGS
# ==========================================
st.set_page_config(page_title="EMA Proximity Scanner", layout="wide")
st.title("🎯 Pure EMA Proximity & Bounce Scanner")
st.markdown("Scans for stocks interacting with the 44 EMA or 200 EMA. Tolerates wicks and slight crosses based on your exact settings.")

st.sidebar.header("⚙️ Market Settings")
sector_options = [
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Auto"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options, index=1)

timeframe_options = {
    "1 Day": "1d",
    "75 Minutes (Intraday)": "75m",
    "1 Week": "1wk",
    "1 Month": "1mo"
}
selected_tf_label = st.sidebar.selectbox("Timeframe", list(timeframe_options.keys()))
timeframe = timeframe_options[selected_tf_label]

st.sidebar.header("🎯 Trade Setup")
direction = st.sidebar.radio(
    "Select Setup Direction",
    ("🟢 Bullish (Support / Bounce)", "🔴 Bearish (Resistance / Rejection)")
)

st.sidebar.header("📈 Target EMA")
ema_target = st.sidebar.radio(
    "Which EMA are you tracking?",
    ("44 EMA", "200 EMA", "Both (Must tap either)")
)

st.sidebar.header("🧲 Tolerance & Wicks")
approach_buffer = st.sidebar.slider(
    "Approach Buffer (%)", 
    min_value=0.0, max_value=5.0, value=2.0, step=0.5,
    help="How close the wick (High/Low) must get to the EMA to count as a touch."
)

cross_allowance = st.sidebar.slider(
    "Max Penetration / Cross Allowance (%)", 
    min_value=0.0, max_value=5.0, value=1.0, step=0.5,
    help="How far the closing price is allowed to cross past the EMA before the setup is considered broken/invalid."
)

# ==========================================
# 2. DATA FETCHER
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    csv_file = {
        "Nifty 50": "ind_nifty50list.csv",
        "Nifty 500": "ind_nifty500list.csv",
        "Nifty Midcap 100": "ind_niftymidcap100list.csv",
        "Nifty Bank": "ind_niftybanklist.csv",
        "Nifty IT": "ind_niftyitlist.csv",
        "Nifty Auto": "ind_niftyautolist.csv"
    }.get(sector_name, "ind_nifty500list.csv")
    
    mirrors = [
        f"https://raw.githubusercontent.com/althk/zerobha/main/{csv_file}",
        f"https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/{csv_file}",
        f"https://raw.githubusercontent.com/faizanahemad/data-science-utils/master/data_science_utils/financial/{csv_file}"
    ]
    
    for url in mirrors:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                symbol_col = next((col for col in df.columns if 'Symbol' in col or 'SYMBOL' in col), None)
                if symbol_col:
                    return [str(s).strip() + ".NS" for s in df[symbol_col]]
        except Exception:
            continue
            
    st.sidebar.error("⚠️ Unable to fetch ticker list.")
    return []

# ==========================================
# 3. CORE LOGIC: EMA PROXIMITY
# ==========================================
def resample_to_75m(df):
    resampled = df.resample('75min', offset='15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    return resampled

def check_ema_setup(df, dir_choice, ema_choice, approach_pct, cross_pct):
    df = df[['Open', 'High', 'Low', 'Close']].dropna()
    if len(df) < 200: return None 
        
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    is_bullish = "Bullish" in dir_choice
    current = df.iloc[-1]
    
    app_mult_bull = 1 + (approach_pct / 100)
    app_mult_bear = 1 - (approach_pct / 100)
    
    cross_mult_bull = 1 - (cross_pct / 100)
    cross_mult_bear = 1 + (cross_pct / 100)
    
    targets = []
    if "44" in ema_choice or "Both" in ema_choice: targets.append(("44 EMA", current['EMA_44']))
    if "200" in ema_choice or "Both" in ema_choice: targets.append(("200 EMA", current['EMA_200']))
    
    matched_emas = []
    
    for ema_name, ema_val in targets:
        if is_bullish:
            # 1. Did the Low tap the EMA (or come within the approach buffer)?
            tapped_ema = current['Low'] <= (ema_val * app_mult_bull)
            
            # 2. Did the Close respect the Cross Allowance? (Not crashing straight through)
            held_ema = current['Close'] >= (ema_val * cross_mult_bull)
            
            if tapped_ema and held_ema:
                dist_pct = ((current['Close'] - ema_val) / ema_val) * 100
                matched_emas.append({
                    "Target": ema_name,
                    "EMA Value": round(ema_val, 2),
                    "Distance": f"{dist_pct:+.2f}%"
                })
        else:
            # 1. Did the High tap the EMA (or come within the approach buffer)?
            tapped_ema = current['High'] >= (ema_val * app_mult_bear)
            
            # 2. Did the Close respect the Cross Allowance? (Not breaking straight through upside)
            held_ema = current['Close'] <= (ema_val * cross_mult_bear)
            
            if tapped_ema and held_ema:
                dist_pct = ((current['Close'] - ema_val) / ema_val) * 100
                matched_emas.append({
                    "Target": ema_name,
                    "EMA Value": round(ema_val, 2),
                    "Distance": f"{dist_pct:+.2f}%"
                })

    if not matched_emas:
        return None
        
    # If multiple EMAs match, just take the first one (or format a string for both)
    primary_match = matched_emas[0]
    
    # Determine visual status based on close price vs EMA
    status = "N/A"
    if is_bullish:
        if current['Close'] < primary_match['EMA Value']:
            status = "⚠️ Slight Cross Down"
        elif current['Close'] > current['Open']:
            status = "✅ Bouncing (Green)"
        else:
            status = "⏳ Resting on EMA"
    else:
        if current['Close'] > primary_match['EMA Value']:
            status = "⚠️ Slight Cross Up"
        elif current['Close'] < current['Open']:
            status = "✅ Rejecting (Red)"
        else:
            status = "⏳ Resting on EMA"

    return {
        "Live Price": round(current['Close'], 2),
        "EMA Target": primary_match['Target'],
        "EMA Value": primary_match['EMA Value'],
        "Close vs EMA": primary_match['Distance'],
        "Action Status": status
    }

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Launch EMA Scanner", type="primary"):
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Scanning for {direction[:2]} EMA interactions...")
        
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
                    
                    setup = check_ema_setup(df, direction, ema_target, approach_buffer, cross_allowance)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append(setup)
            except: pass
            progress_bar.progress((i + 1) / len(ticker_list))
            
        progress_bar.empty()
        
        st.subheader(f"📊 Scan Results ({selected_tf_label})")
        if results:
            final_df = pd.DataFrame(results)[['Ticker', 'Live Price', 'EMA Target', 'EMA Value', 'Close vs EMA', 'Action Status']]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Results acquired. These stocks are interacting with the specified EMA.")
        else:
            st.warning(f"0 matches found. The market is not presenting this EMA setup right now. Adjust your Tolerance sliders.")
