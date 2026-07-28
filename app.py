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
st.set_page_config(page_title="Advanced S/D & Volume Scanner", layout="wide")
st.title("🎯 Advanced Demand Zone & Volume Scanner")
st.markdown("Scans for pullbacks into 1-2 candle base zones where retracement volume is strictly lower than the breakout volume.")

st.sidebar.header("⚙️ Scanner Settings")

sector_options = [
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Auto"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options)

timeframe = st.sidebar.selectbox("Timeframe", ["1d", "1wk", "1mo"], index=0)

ema_target = st.sidebar.radio(
    "Target EMA Confluence",
    ("Near 44 EMA", "Near 50 EMA", "Either (44 or 50)")
)

# ==========================================
# 2. DATA FETCHER (FIREWALL-PROOF GITHUB MIRRORS)
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    # Match the exact CSV file names used by the NSE
    csv_file = {
        "Nifty 50": "ind_nifty50list.csv",
        "Nifty 500": "ind_nifty500list.csv",
        "Nifty Midcap 100": "ind_niftymidcap100list.csv",
        "Nifty Bank": "ind_niftybanklist.csv",
        "Nifty IT": "ind_niftyitlist.csv",
        "Nifty Auto": "ind_niftyautolist.csv"
    }.get(sector_name, "ind_nifty500list.csv")
    
    # We pull the data from 4 different public developer repositories on GitHub.
    # GitHub never blocks Cloud Servers. This completely bypasses the NSE.
    mirrors = [
        f"https://raw.githubusercontent.com/althk/zerobha/main/{csv_file}",
        f"https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/{csv_file}",
        f"https://raw.githubusercontent.com/rohanmadhale/Python-Portfolio-Optimisation/main/{csv_file}",
        f"https://raw.githubusercontent.com/faizanahemad/data-science-utils/master/data_science_utils/financial/{csv_file}"
    ]
    
    for url in mirrors:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                # Dynamically find the symbol column regardless of formatting
                symbol_col = next((col for col in df.columns if 'Symbol' in col or 'SYMBOL' in col), None)
                if symbol_col:
                    return [str(s).strip() + ".NS" for s in df[symbol_col]]
        except Exception:
            continue # If one mirror is down, try the next one instantly
            
    st.sidebar.error("⚠️ Critical Error: Unable to fetch ticker list from any GitHub mirror.")
    return []

# ==========================================
# 3. CORE LOGIC: ZONES, VOLUME & EMA
# ==========================================
def check_setup(df, ema_choice):
    df = df.dropna()
    if len(df) > 0: df = df.iloc[:-1] 
    if len(df) < 100: return None
        
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    df['Is_Boring'] = df['Body'] <= (0.5 * df['Range'])
    
    avg_body = df['Body'].rolling(10).mean()
    df['Is_Strong_Green'] = (df['Close'] > df['Open']) & (df['Body'] > (0.6 * df['Range'])) & (df['Body'] > avg_body)

    zones = []
    
    for i in range(20, len(df) - 2):
        
        # PATTERN 1: 1-Candle Base 
        if df['Is_Boring'].iloc[i] and df['Is_Strong_Green'].iloc[i+1]:
            if df['Close'].iloc[i+1] > df['High'].iloc[i]: 
                zones.append({
                    'type': '1-Base Demand',
                    'proximal': df['High'].iloc[i], 
                    'distal': df['Low'].iloc[i],    
                    'breakout_vol': df['Volume'].iloc[i+1],
                    'index': i
                })
                
        # PATTERN 2: 2-Candle Base 
        elif df['Is_Boring'].iloc[i-1] and df['Is_Boring'].iloc[i] and df['Is_Strong_Green'].iloc[i+1]:
            highest_base = max(df['High'].iloc[i], df['High'].iloc[i-1])
            lowest_base = min(df['Low'].iloc[i], df['Low'].iloc[i-1])
            
            if df['Close'].iloc[i+1] > highest_base:
                zones.append({
                    'type': '2-Base Demand',
                    'proximal': highest_base,
                    'distal': lowest_base,
                    'breakout_vol': df['Volume'].iloc[i+1], 
                    'index': i
                })
                
        # PATTERN 3: Resistance Flipped to Support 
        is_swing_high = max(df['High'].iloc[i-5:i+6]) == df['High'].iloc[i]
        if is_swing_high:
            for j in range(i+1, min(i+15, len(df)-2)):
                if df['Is_Strong_Green'].iloc[j] and df['Close'].iloc[j] > df['High'].iloc[i]:
                    zones.append({
                        'type': 'Supply Flipped to Demand',
                        'proximal': df['High'].iloc[i],
                        'distal': df['Low'].iloc[i] if df['Low'].iloc[i] < df['High'].iloc[i] * 0.98 else df['High'].iloc[i] * 0.98,
                        'breakout_vol': df['Volume'].iloc[j],
                        'index': j
                    })
                    break

    valid_zones = []
    for z in zones:
        future_data = df.iloc[z['index']+2 : ]
        if not (future_data['Close'] < z['distal']).any():
            valid_zones.append(z)

    if not valid_zones: return None
    
    latest_zone = valid_zones[-1] 
    current = df.iloc[-1]
    
    near_zone = current['Low'] <= (latest_zone['proximal'] * 1.015)
    holding_zone = current['Close'] >= latest_zone['distal']
    
    volume_is_less = current['Volume'] < latest_zone['breakout_vol']
    
    ema44 = current['EMA_44']
    ema50 = current['EMA_50']
    
    touching_44 = current['Low'] <= (ema44 * 1.02) and current['Close'] >= (ema44 * 0.98)
    touching_50 = current['Low'] <= (ema50 * 1.02) and current['Close'] >= (ema50 * 0.98)
    
    ema_valid = False
    active_ema = "None"
    
    if ema_choice == "Near 44 EMA" and touching_44:
        ema_valid = True
        active_ema = "44 EMA"
    elif ema_choice == "Near 50 EMA" and touching_50:
        ema_valid = True
        active_ema = "50 EMA"
    elif ema_choice == "Either (44 or 50)":
        if touching_44:
            ema_valid = True
            active_ema = "44 EMA"
        elif touching_50:
            ema_valid = True
            active_ema = "50 EMA"

    if near_zone and holding_zone and volume_is_less and ema_valid:
        return {
            "Zone Type": latest_zone['type'],
            "Price": round(current['Close'], 2),
            "Zone Entry": round(latest_zone['proximal'], 2),
            "Zone SL": round(latest_zone['distal'], 2),
            "Vol Dry-Up": "✅ Yes",
            "EMA Support": active_ema,
        }
        
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan {selected_sector}", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list from secure mirrors..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Successfully loaded {len(ticker_list)} stocks. Hunting for Demand Zones & EMA Confluence...")
        
        period_map = {"1d": "2y", "1wk": "5y", "1mo": "10y"}
        fetch_period = period_map.get(timeframe, "2y")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=timeframe)
                if not df.empty:
                    setup = check_setup(df, ema_target)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append({
                            "Ticker": setup['Ticker'],
                            "Setup Type": setup['Zone Type'],
                            "Price": setup['Price'],
                            "Zone Entry": setup['Zone Entry'],
                            "Invalidation (SL)": setup['Zone SL'],
                            "Vol Dry-Up": setup['Vol Dry-Up'],
                            "EMA Support": setup['EMA Support']
                        })
            except:
                pass
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 {selected_sector} Scan Results ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Target acquired. Stocks listed have retraced to a Demand Zone on lower volume, aligning with your EMA target.")
        else:
            st.warning(f"No stocks found. None are currently pulling back to a valid base zone on low volume with {ema_target} support.")
