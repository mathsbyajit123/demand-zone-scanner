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
st.set_page_config(page_title="Momentum Scanner", layout="wide")
st.title("🚀 Momentum & EMA Extension Scanner")
st.markdown("Scans for stocks in a confirmed uptrend (21 > 44 EMA) where the current price is stretched 5% to 10% above the 21 EMA.")

st.sidebar.header("⚙️ Scanner Settings")

# Dynamic Index Selector
selected_index = st.sidebar.selectbox(
    "Select Index to Scan", 
    ["Nifty 50", "Nifty Midcap 100", "Nifty Smallcap 250", "Nifty 500"]
)

# Extension Settings
st.sidebar.subheader("Distance from Fast EMA")
min_pct_above = st.sidebar.number_input("Minimum % Above EMA", min_value=1.0, max_value=20.0, value=5.0, step=0.5)
max_pct_above = st.sidebar.number_input("Maximum % Above EMA", min_value=2.0, max_value=50.0, value=10.0, step=0.5)

# Flexible Timeframe & EMAs
st.sidebar.subheader("Chart Settings")
timeframe = st.sidebar.selectbox("Timeframe", ["1d", "1wk"], index=0)
fast_ema_len = st.sidebar.number_input("Fast EMA Length", min_value=5, max_value=100, value=21)
slow_ema_len = st.sidebar.number_input("Slow EMA Length", min_value=10, max_value=200, value=44)


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
    # Safety: Drop missing data and ignore unclosed current candle
    df = df.dropna()
    if len(df) > 0:
        df = df.iloc[:-1] 

    if len(df) < 50: return None
        
    df['EMA_Fast'] = df['Close'].ewm(span=fast_ema_len, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=slow_ema_len, adjust=False).mean()
    
    # Evaluate only the latest completed candle
    latest = df.iloc[-1]
    
    close_price = latest['Close']
    fast_ema = latest['EMA_Fast']
    slow_ema = latest['EMA_Slow']
    
    # Rule 1: Fast EMA must be strictly above Slow EMA (Confirmed Uptrend)
    if fast_ema <= slow_ema:
        return None
        
    # Rule 2: Calculate the exact percentage the price is above the Fast EMA
    pct_above_ema = ((close_price - fast_ema) / fast_ema) * 100
    
    # Rule 3: Check if it falls within the 5% to 10% range
    if min_pct_above <= pct_above_ema <= max_pct_above:
        return pct_above_ema, close_price, fast_ema
        
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
        st.info(f"Loaded {len(ticker_list)} stocks. Running Momentum Scan...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="6mo", interval=timeframe) # Only need 6mo for EMA 44
                
                if not df.empty:
                    setup_data = check_setup(ticker, df)
                    
                    if setup_data:
                        pct_extension, latest_c, fast_ema_val = setup_data
                        sector, mcap = fetch_metadata(ticker)
                        
                        results.append({
                            "Ticker": ticker.replace(".NS", ""),
                            "Sector": sector,
                            "Market Cap": mcap,
                            "Current Price": round(float(latest_c), 2),
                            "21 EMA Level": round(float(fast_ema_val), 2),
                            "% Above EMA": f"+{pct_extension:.2f}%"
                        })
            except Exception:
                pass 
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 Scan Results: {selected_index}")
        
        if results:
            final_df = pd.DataFrame(results)
            # Sort by highest extension percentage by default
            final_df = final_df.sort_values(by="% Above EMA", ascending=False)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"Scan complete. No stocks in the {selected_index} are currently stretched {min_pct_above}% to {max_pct_above}% above the {fast_ema_len} EMA.")
