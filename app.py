import streamlit as st
import yfinance as yf
import pandas as pd
import time

# --- PAGE SETUP ---
st.set_page_config(page_title="HTF 50 EMA Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 38px; font-weight: 800; color: #FF3D00; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #455A64; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 HTF 50 EMA Proximity Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Ultra-lightweight engine. Scans strictly for price approaching the Macro 50 EMA.</p>', unsafe_allow_html=True)

# --- MARKET SYMBOLS ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[category])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]

# --- UI DASHBOARD ---
with st.sidebar:
    st.header("1. Target Universe")
    selected_sector = st.selectbox("Market Index", ["Test Scan (5 Stocks)", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Setup Parameters")
    target_tf = st.selectbox("Select Target Timeframe:", ["1 Day", "1 Week", "1 Month"])
    
    st.markdown("**How close must the price be to the 50 EMA?**")
    proximity_tolerance = st.slider("Approach Tolerance (± %)", 0.1, 5.0, 1.5, step=0.1, help="If set to 1.5%, the scanner finds stocks sitting anywhere between 1.5% above and 1.5% below the 50 EMA.")
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE HTF SCAN", type="primary", use_container_width=True)

target_symbols = load_symbols("NIFTY 50")[:5] if "Test" in selected_sector else load_symbols(selected_sector)

# --- LIGHTWEIGHT PROCESSING ENGINE ---
if run_scan:
    scanned_opportunities = []
    
    st.info(f"🔄 Scanning for exact touches on the {target_tf} 50 EMA...")
    execution_progress = st.progress(0, text="Igniting engine...")
    
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        clean_ticker = ticker.replace('.NS', '')
        execution_progress.progress((idx + 1) / total_symbols, text=f"Analyzing {clean_ticker}...")
        
        try:
            # Gentle throttle to prevent API bans
            time.sleep(0.2) 
            
            # Fetch 10 years of Daily data (highly stable)
            stock = yf.Ticker(ticker)
            df = stock.history(period="10y", interval="1d")
            
            if df.empty:
                continue
                
            # Clean timezone data
            if df.index.tz is not None: 
                df.index = df.index.tz_localize(None)
                
            df = df.ffill().dropna(subset=['Close'])
            
            # Resample to requested HTF
            if target_tf == '1 Week':
                df = df.resample('1W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
            elif target_tf == '1 Month':
                df = df.resample('1ME').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
                
            # Ensure enough data exists for a valid 50 EMA
            if len(df) < 50:
                continue
                
            # Calculate 50 EMA
            ema_50 = df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
            latest_close = df['Close'].iloc[-1]
            
            # Calculate Distance
            dist_pct = ((latest_close - ema_50) / ema_50) * 100
            
            # Check if it is within the tolerance band
            if abs(dist_pct) <= proximity_tolerance:
                
                # Format visual output
                if dist_pct >= 0:
                    status = f"🟢 +{round(dist_pct, 2)}% (Above)"
                else:
                    status = f"🔴 {round(dist_pct, 2)}% (Below)"
                    
                scanned_opportunities.append({
                    "Ticker": clean_ticker,
                    "Timeframe": target_tf,
                    "Live Price": f"₹{round(latest_close, 2)}",
                    "50 EMA Value": f"₹{round(ema_50, 2)}",
                    "Distance to EMA": status
                })
                
        except Exception:
            # Skip broken stocks silently
            pass
            
    execution_progress.empty()
    
    if scanned_opportunities:
        display_dataframe = pd.DataFrame(scanned_opportunities)
        st.success(f"🎯 Scan Complete! Found **{len(display_dataframe)}** stocks right on the {target_tf} 50 EMA.")
        st.dataframe(display_dataframe, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks are within {proximity_tolerance}% of their {target_tf} 50 EMA right now.")
