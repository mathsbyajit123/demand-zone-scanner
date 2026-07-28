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
st.set_page_config(page_title="Pure Demand Zone Scanner", layout="wide")
st.title("🎯 Pure Demand Zone & Volume Scanner")
st.markdown("Scans for pullbacks into strict 1-2 boring candle demand zones where the retracement volume is lower than the breakout volume.")

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

# ==========================================
# 2. DATA FETCHER (FIREWALL-PROOF GITHUB MIRRORS)
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
        f"https://raw.githubusercontent.com/rohanmadhale/Python-Portfolio-Optimisation/main/{csv_file}",
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
            
    st.sidebar.error("⚠️ Critical Error: Unable to fetch ticker list from any GitHub mirror.")
    return []

# ==========================================
# 3. CORE LOGIC: PURE ZONES & VOLUME
# ==========================================
def check_setup(df):
    df = df.dropna()
    if len(df) > 0: df = df.iloc[:-1] 
    if len(df) < 50: return None
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    # Defining a "Boring Candle": Body is <= 50% of the total range
    df['Is_Boring'] = df['Body'] <= (0.5 * df['Range'])
    
    # Defining a "Healthy Leg-Out": Green, large body, bigger than recent average
    avg_body = df['Body'].rolling(10).mean()
    df['Is_Strong_Green'] = (df['Close'] > df['Open']) & (df['Body'] > (0.6 * df['Range'])) & (df['Body'] > avg_body)

    zones = []
    
    for i in range(15, len(df) - 2):
        
        # PATTERN 1: Exactly 1 Boring Candle Base
        if df['Is_Boring'].iloc[i] and df['Is_Strong_Green'].iloc[i+1]:
            if df['Close'].iloc[i+1] > df['High'].iloc[i]: 
                zones.append({
                    'type': '1-Base Demand',
                    'proximal': df['High'].iloc[i], 
                    'distal': df['Low'].iloc[i],    
                    'breakout_vol': df['Volume'].iloc[i+1],
                    'index': i
                })
                
        # PATTERN 2: Exactly 2 Boring Candles Base
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

    # Validate: Filter out zones that have been broken by a daily close below the distal line
    valid_zones = []
    for z in zones:
        future_data = df.iloc[z['index']+2 : ]
        if not (future_data['Close'] < z['distal']).any():
            valid_zones.append(z)

    if not valid_zones: return None
    
    # Check the most recent valid zone against the current price
    latest_zone = valid_zones[-1] 
    current = df.iloc[-1]
    
    # Rule 1: Price has retraced into or very near the zone (within 1.5% of proximal line)
    near_zone = current['Low'] <= (latest_zone['proximal'] * 1.015)
    
    # Rule 2: Price has not closed below the distal stop-loss line
    holding_zone = current['Close'] >= latest_zone['distal']
    
    # Rule 3: Retracement volume is strictly less than the leg-out breakout volume
    volume_is_less = current['Volume'] < latest_zone['breakout_vol']

    if near_zone and holding_zone and volume_is_less:
        # Calculate Risk percentage (Distance from Entry to Stop Loss)
        risk_pct = ((latest_zone['proximal'] - latest_zone['distal']) / latest_zone['proximal']) * 100
        
        return {
            "Zone Type": latest_zone['type'],
            "Current Price": round(current['Close'], 2),
            "Proximal (Entry)": round(latest_zone['proximal'], 2),
            "Distal (SL)": round(latest_zone['distal'], 2),
            "Zone Risk": f"{risk_pct:.2f}%",
            "Vol Dry-Up": "✅ Yes"
        }
        
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan {selected_sector}", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list from secure mirrors..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Successfully loaded {len(ticker_list)} stocks. Hunting for Pure Demand Zones...")
        
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
                    setup = check_setup(df)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append({
                            "Ticker": setup['Ticker'],
                            "Zone Type": setup['Zone Type'],
                            "Price": setup['Current Price'],
                            "Entry Level": setup['Proximal (Entry)'],
                            "Stop Loss": setup['Distal (SL)'],
                            "Risk %": setup['Zone Risk'],
                            "Volume Check": setup['Vol Dry-Up']
                        })
            except:
                pass
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 {selected_sector} S&D Results ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Target acquired. Stocks listed have retraced to a validated Boring Candle Base on lower volume.")
        else:
            st.warning(f"No stocks found. None are currently pulling back to a valid 1-2 candle base zone on low volume.")
