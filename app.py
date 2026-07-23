import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SIDEBAR SETTINGS
# ==========================================
st.set_page_config(page_title="Index Setup Scanner", layout="wide")
st.title("🚀 Nifty Index Structure Scanner")
st.markdown("Scans entire NSE indices for EMA crossovers, dry volume pullbacks, and CHoCH/HH breakouts.")

st.sidebar.header("⚙️ Scanner Settings")

# Dynamic Index Selector
selected_index = st.sidebar.selectbox(
    "Select Index to Scan", 
    ["Nifty 50", "Nifty Midcap 100", "Nifty Smallcap 250", "Nifty 500"]
)

# Flexible Timeframe & EMAs
timeframe = st.sidebar.selectbox("Timeframe", ["1d", "1wk"], index=0)
fast_ema_len = st.sidebar.number_input("Fast EMA Length", min_value=5, max_value=200, value=21)
slow_ema_len = st.sidebar.number_input("Slow EMA Length", min_value=10, max_value=200, value=44)
vol_sma_len = st.sidebar.number_input("Volume Average Length", min_value=5, max_value=100, value=20)

# ==========================================
# 2. NSE INDEX DATA FETCHER
# ==========================================
def get_index_tickers(index_name):
    """Bypasses NSE firewall to download the live index CSVs and extract symbols."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    urls = {
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "Nifty Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "Nifty Smallcap 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    
    url = urls.get(index_name)
    try:
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        # Extract symbols and append .NS for Yahoo Finance compatibility
        tickers = [str(symbol).strip() + ".NS" for symbol in df['Symbol']]
        return tickers
    except Exception as e:
        st.sidebar.error(f"Failed to fetch index list: {e}")
        return []

# ==========================================
# 3. CORE LOGIC & MATHEMATICS
# ==========================================
def get_market_cap_category(mcap_cr):
    if mcap_cr == 0: return "Unknown"
    elif mcap_cr < 100: return "Under 100 Cr"
    elif 100 <= mcap_cr < 500: return "100 - 500 Cr"
    elif 500 <= mcap_cr < 1000: return "500 - 1000 Cr"
    elif 1000 <= mcap_cr < 10000: return "1000 - 10000 Cr"
    elif 10000 <= mcap_cr < 100000: return "10000 - 1 Lakh Cr"
    else: return "Over 1 Lakh Cr"

def fetch_metadata(ticker):
    try:
        info = yf.Ticker(ticker).info
        sector = info.get('sector', 'N/A')
        mcap_raw = info.get('marketCap', 0)
        mcap_cr = mcap_raw / 10_000_000 
        return sector, get_market_cap_category(mcap_cr)
    except:
        return "N/A", "Unknown"

def check_setup(ticker, df):
    df = df.dropna()
    if len(df) > 0:
        df = df.iloc[:-1] # Ignore incomplete live candle

    if len(df) < 50: return None
        
    df['EMA_Fast'] = df['Close'].ewm(span=fast_ema_len, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=slow_ema_len, adjust=False).mean()
    df['Vol_SMA'] = df['Volume'].rolling(window=vol_sma_len).mean()
    
    cross_ups = (df['EMA_Fast'] > df['EMA_Slow']) & (df['EMA_Fast'].shift(1) <= df['EMA_Slow'].shift(1))
    if not cross_ups.any(): return None 
        
    last_cross_idx = cross_ups[::-1].idxmax()
    post_cross = df.loc[last_cross_idx:]
    if len(post_cross) < 3: return None

    prior_candles = post_cross.iloc[:-1]
    if prior_candles.empty: return None
    swing_high = prior_candles['High'].max()
    
    pullback_days = prior_candles[
        (prior_candles['Low'] <= prior_candles['EMA_Fast']) & 
        (prior_candles['Close'] >= prior_candles['EMA_Slow']) & 
        (prior_candles['Volume'] < prior_candles['Vol_SMA'])
    ]
    if pullback_days.empty: return None 
        
    latest = post_cross.iloc[-1]
    
    in_accumulation_zone = (
        (latest['Low'] <= latest['EMA_Fast']) and 
        (latest['Close'] >= latest['EMA_Slow']) and 
        (latest['Volume'] < latest['Vol_SMA'])
    )
    hh_confirmed = latest['Close'] > swing_high
    
    if hh_confirmed:
        return "🔥 Breakout Confirmed (HH)", swing_high, latest['Close']
    elif in_accumulation_zone:
        return "📉 Dry Pullback Zone (HL)", swing_high, latest['Close']
        
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan {selected_index}", type="primary"):
    
    with st.spinner(f"Downloading official {selected_index} list from NSE..."):
        ticker_list = get_index_tickers(selected_index)
        
    if not ticker_list:
        st.error("Failed to load ticker list. NSE servers might be blocking the request.")
    else:
        st.info(f"Loaded {len(ticker_list)} stocks from {selected_index}. Starting technical scan...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="1y", interval=timeframe)
                
                if not df.empty:
                    setup_data = check_setup(ticker, df)
                    
                    if setup_data:
                        status, swing_h, latest_c = setup_data
                        sector, mcap = fetch_metadata(ticker)
                        
                        results.append({
                            "Ticker": ticker.replace(".NS", ""), # Clean up the display name
                            "Sector": sector,
                            "Market Cap": mcap,
                            "Status": status,
                            "Swing High": round(float(swing_h), 2),
                            "Current Price": round(float(latest_c), 2)
                        })
            except Exception:
                pass 
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 {selected_index} Results ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"Scan complete. None of the {len(ticker_list)} stocks met the strict setup criteria today.")
