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
st.set_page_config(page_title="Dry Pullback Scanner", layout="wide")
st.title("🚀 Uptrend Dry Pullback Scanner")
st.markdown("Scans for stocks in a confirmed uptrend (20 EMA > 50 EMA) that are pulling back to touch the 20 EMA on low volume.")

st.sidebar.header("⚙️ Scanner Settings")

# Dynamic Index Selector
selected_index = st.sidebar.selectbox(
    "Select Index to Scan", 
    ["Nifty 50", "Nifty Midcap 100", "Nifty Smallcap 250", "Nifty 500"]
)

# Flexible Timeframe
st.sidebar.subheader("Chart Settings")
timeframe = st.sidebar.selectbox("Timeframe", ["1d", "1wk"], index=0, help="1d = Daily, 1wk = Weekly")

# ==========================================
# 2. NSE INDEX DATA FETCHER
# ==========================================
def get_index_tickers(index_name):
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
        tickers = [str(symbol).strip() + ".NS" for symbol in df['Symbol']]
        return tickers
    except Exception as e:
        st.sidebar.error(f"Failed to fetch index list: {e}")
        return []

# ==========================================
# 3. CORE LOGIC & MATHEMATICS
# ==========================================
def fetch_metadata(ticker):
    try:
        info = yf.Ticker(ticker).info
        sector = info.get('sector', 'N/A')
        return sector
    except:
        return "N/A"

def check_setup(ticker, df):
    # Drop missing data and ignore unclosed current candle
    df = df.dropna()
    if len(df) > 0:
        df = df.iloc[:-1] 

    if len(df) < 50: return None
        
    # Calculate 20 EMA, 50 EMA, and Volume Average
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Vol_SMA'] = df['Volume'].rolling(window=20).mean()
    
    latest = df.iloc[-1]
    
    # --- SCANNER RULES ---
    
    # Rule 1: Uptrend Confirmed (20 EMA is strictly above 50 EMA)
    is_uptrend = latest['EMA_20'] > latest['EMA_50']
    
    # Rule 2: Pullback to 20 EMA (The Low touches or drops slightly below 20 EMA, but Close stays above 50 EMA)
    touched_20_ema = latest['Low'] <= latest['EMA_20']
    held_trend = latest['Close'] > latest['EMA_50']
    
    # Rule 3: Dry Volume (Volume must be less than the 20-period average)
    dry_volume = latest['Volume'] < latest['Vol_SMA']
    
    # If ALL conditions are met, trigger the setup
    if is_uptrend and touched_20_ema and held_trend and dry_volume:
        return latest['Close'], latest['EMA_20'], latest['EMA_50']
        
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Scan {selected_index}", type="primary"):
    
    with st.spinner(f"Downloading official {selected_index} list from NSE..."):
        ticker_list = get_index_tickers(selected_index)
        
    if not ticker_list:
        st.error("Failed to load ticker list. Please try again.")
    else:
        st.info(f"Loaded {len(ticker_list)} stocks. Running Dry Pullback Scan...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                stock = yf.Ticker(ticker)
                # 6 months of data is enough to calculate EMAs accurately
                df = stock.history(period="6mo", interval=timeframe) 
                
                if not df.empty:
                    setup_data = check_setup(ticker, df)
                    
                    if setup_data:
                        latest_c, ema_20, ema_50 = setup_data
                        sector = fetch_metadata(ticker)
                        
                        results.append({
                            "Ticker": ticker.replace(".NS", ""),
                            "Sector": sector,
                            "Status": "📉 Dry Pullback to 20 EMA",
                            "Current Price": round(float(latest_c), 2),
                            "20 EMA": round(float(ema_20), 2),
                            "50 EMA": round(float(ema_50), 2)
                        })
            except Exception:
                pass 
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 Scan Results: {selected_index} ({timeframe.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"Scan complete. No stocks in the {selected_index} are currently pulling back to the 20 EMA on low volume.")
