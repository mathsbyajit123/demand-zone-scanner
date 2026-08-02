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
st.set_page_config(page_title="200 EMA Scanner", layout="wide")
st.title("🎯 200 EMA Support Scanner")
st.markdown("A clean, focused scanner that finds stocks currently touching or sitting right at the 200 EMA support line.")

st.sidebar.header("⚙️ Market Settings")

sector_options = [
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Auto"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options)

timeframe_options = {
    "1 Day": "1d",
    "1 Week": "1wk",
    "1 Month": "1mo"
}
selected_tf_label = st.sidebar.selectbox("Timeframe", list(timeframe_options.keys()))
timeframe = timeframe_options[selected_tf_label]

proximity_pct = st.sidebar.slider("Proximity to 200 EMA (%)", min_value=1.0, max_value=5.0, value=2.0, step=0.5,
                                  help="How close the current price needs to be to the 200 EMA to be considered 'at support'.")

# ==========================================
# 2. DATA FETCHER (FIREWALL-PROOF)
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
            
    st.sidebar.error("⚠️ Critical Error: Unable to fetch ticker list.")
    return []

# ==========================================
# 3. CORE LOGIC: 200 EMA SUPPORT
# ==========================================
def check_200_ema(df, buffer_pct):
    df = df.dropna()
    
    # We need at least 200 periods to calculate a 200 EMA accurately
    if len(df) < 200: 
        return None 
        
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    current = df.iloc[-1]
    ema_200 = current['EMA_200']
    
    # Calculate upper and lower bounds based on your slider
    upper_bound = ema_200 * (1 + (buffer_pct / 100))
    lower_bound = ema_200 * (1 - (buffer_pct / 100))
    
    # Logic: The price is considered "at support" if it is currently trading inside this buffer zone
    # OR if the low of the candle tapped the EMA and the close held above it.
    tapped_support = current['Low'] <= upper_bound and current['Close'] >= lower_bound
    
    if tapped_support:
        distance_pct = ((current['Close'] - ema_200) / ema_200) * 100
        return {
            "Live Price": round(current['Close'], 2),
            "200 EMA": round(ema_200, 2),
            "Distance to EMA": f"{distance_pct:+.2f}%"
        }
        
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan for 200 EMA Support", type="primary"):
    
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for 200 EMA Support on {selected_tf_label} timeframe...")
        
        # Ensure we fetch enough data history to calculate the 200 EMA for the selected timeframe
        if timeframe == '1d':
            fetch_period = "2y"   # ~500 trading days
        elif timeframe == '1wk':
            fetch_period = "5y"   # ~260 weeks
        else:
            fetch_period = "20y"  # 240 months
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=timeframe)
                if not df.empty:
                    setup = check_200_ema(df, proximity_pct)
                    if setup:
                        results.append({
                            "Ticker": ticker.replace(".NS", ""),
                            "Live Price": setup['Live Price'],
                            "200 EMA": setup['200 EMA'],
                            "Distance to EMA": setup['Distance to EMA']
                        })
            except:
                pass
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 200 EMA Support Results ({selected_tf_label})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Scan complete. Found {len(results)} stocks currently sitting at 200 EMA support.")
        else:
            st.warning(f"No stocks found near the 200 EMA on the {selected_tf_label} timeframe right now.")
