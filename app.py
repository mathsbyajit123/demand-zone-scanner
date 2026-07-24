import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SIDEBAR SETTINGS
# ==========================================
st.set_page_config(page_title="S&R Zone Scanner", layout="wide")
st.title("🎯 Support & Resistance Zone Scanner")
st.markdown("Scans for stocks bouncing off a 2% Support Zone (or retracing to a broken resistance) with a clear Resistance Target above.")

st.sidebar.header("⚙️ Scanner Settings")

# Dynamic Index Selector
selected_index = st.sidebar.selectbox(
    "Select Index to Scan", 
    ["Nifty 50", "Nifty Midcap 100", "Nifty Smallcap 250", "Nifty 500"]
)

st.sidebar.subheader("Zone & Target Rules")
# The minimum distance to the next resistance to ensure a good Risk/Reward
min_target_pct = st.sidebar.number_input("Minimum Target Distance (%)", min_value=1.0, max_value=30.0, value=5.0, step=1.0)

st.sidebar.subheader("Chart Settings")
timeframe = st.sidebar.selectbox("Timeframe", ["1d", "1wk"], index=0)

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
    # Safety: Drop missing data and ignore unclosed current candle
    df = df.dropna()
    if len(df) > 0:
        df = df.iloc[:-1] 

    if len(df) < 50: return None
        
    latest_close = df.iloc[-1]['Close']
    
    # --- STEP 1: Find Pivot Highs & Lows (Swing Points) ---
    window = 10 # Looks 10 candles to the left and right to confirm a major swing
    highs = df['High'].values
    lows = df['Low'].values
    raw_levels = []

    for i in range(window, len(df) - window):
        # If it's a fractal high
        if max(highs[i-window:i+window+1]) == highs[i]:
            raw_levels.append(highs[i])
        # If it's a fractal low
        if min(lows[i-window:i+window+1]) == lows[i]:
            raw_levels.append(lows[i])

    if not raw_levels: return None

    # --- STEP 2: Cluster Pivots into <2% Zones ---
    raw_levels = sorted(list(set(raw_levels)))
    zones = []
    current_cluster = [raw_levels[0]]

    for level in raw_levels[1:]:
        # If the level is within 2% of the base of the current cluster, merge them
        if level <= current_cluster[0] * 1.02: 
            current_cluster.append(level)
        else:
            # Calculate the median of the zone and save it, then start a new zone
            zones.append(np.median(current_cluster))
            current_cluster = [level]
            
    zones.append(np.median(current_cluster))

    if len(zones) < 2: return None

    # --- STEP 3: Identify Immediate Support and Resistance ---
    # Any zone below current price is acting as Support (Even if it used to be Resistance)
    supports = [z for z in zones if z <= latest_close]
    # Any zone above current price is acting as Resistance Target
    resistances = [z for z in zones if z > latest_close]

    if not supports or not resistances: return None

    # The closest support below
    s1 = max(supports) 
    # The closest resistance above
    r1 = min(resistances) 

    # --- STEP 4: Apply Scanner Rules ---
    
    # Rule 1: Entry Condition - Price must be sitting near the S1 zone (Max 2% above it)
    near_support = latest_close <= (s1 * 1.02)
    
    # Rule 2: Target Condition - The R1 zone must be far enough away to be profitable
    target_distance_pct = ((r1 - latest_close) / latest_close) * 100
    valid_target = target_distance_pct >= min_target_pct

    if near_support and valid_target:
        return s1, r1, target_distance_pct, latest_close
        
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
        st.info(f"Loaded {len(ticker_list)} stocks. Mapping S&R Zones...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker}...")
            
            try:
                stock = yf.Ticker(ticker)
                # Need at least 1 year to map major support/resistance zones accurately
                df = stock.history(period="1y", interval=timeframe) 
                
                if not df.empty:
                    setup_data = check_setup(ticker, df)
                    
                    if setup_data:
                        s1_val, r1_val, tgt_pct, latest_c = setup_data
                        sector = fetch_metadata(ticker)
                        
                        results.append({
                            "Ticker": ticker.replace(".NS", ""),
                            "Sector": sector,
                            "Status": "✅ In Support Zone",
                            "Current Price": round(float(latest_c), 2),
                            "Support Base": round(float(s1_val), 2),
                            "Resistance Target": round(float(r1_val), 2),
                            "Target Distance": f"+{tgt_pct:.2f}%"
                        })
            except Exception:
                pass 
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 Zone Scan Results: {selected_index}")
        
        if results:
            final_df = pd.DataFrame(results)
            # Sort by the highest available target percentage
            final_df['Sort_Tgt'] = final_df['Target Distance'].str.replace('%', '').str.replace('+', '').astype(float)
            final_df = final_df.sort_values(by="Sort_Tgt", ascending=False).drop(columns=['Sort_Tgt'])
            
            st.dataframe(final_df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"Scan complete. No stocks are currently bouncing in a 2% support zone with a {min_target_pct}%+ resistance target above.")
