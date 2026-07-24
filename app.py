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
st.set_page_config(page_title="MTF Zone & CHoCH Scanner", layout="wide")
st.title("🎯 MTF Support Zone & LTF CHoCH Scanner")
st.markdown("Identifies stocks touching a major HTF Support Zone that have just confirmed a Market Structure Shift (CHoCH / Higher High) on the LTF.")

st.sidebar.header("⚙️ Scanner Settings")

selected_index = st.sidebar.selectbox(
    "Select Index to Scan", 
    ["Nifty 50", "Nifty Midcap 100", "Nifty Smallcap 250", "Nifty 500"]
)

st.sidebar.subheader("Timeframe Settings")
htf_selection = st.sidebar.selectbox("Higher Timeframe (HTF)", ["1d", "1wk"], index=0)

# Automatically set LTF based on HTF selection
if htf_selection == "1d":
    ltf_selection = "15m"
    htf_period = "1y"
    ltf_period = "60d" # yfinance limit for 15m is 60 days
else:
    ltf_selection = "1h"
    htf_period = "2y"
    ltf_period = "730d" # yfinance limit for 1h is 730 days

st.sidebar.info(f"**Current Setup:**\nHTF: {htf_selection.upper()}\nLTF: {ltf_selection.upper()}")

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
# 3. CORE LOGIC: HTF ZONES & LTF CHoCH
# ==========================================
def fetch_metadata(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info.get('sector', 'N/A')
    except:
        return "N/A"

def check_htf_support(df_htf):
    """Scans HTF to find major support zones and checks if price is currently at one."""
    df_htf = df_htf.dropna()
    if len(df_htf) < 50: return None
    
    latest_close = df_htf.iloc[-1]['Close']
    latest_low = df_htf.iloc[-1]['Low']
    prev_low = df_htf.iloc[-2]['Low']
    
    # 1. Map Historical Pivot Points
    window = 10
    highs = df_htf['High'].values
    lows = df_htf['Low'].values
    raw_levels = []

    for i in range(window, len(df_htf) - window):
        if max(highs[i-window:i+window+1]) == highs[i]: raw_levels.append(highs[i])
        if min(lows[i-window:i+window+1]) == lows[i]: raw_levels.append(lows[i])

    if not raw_levels: return None

    # 2. Cluster into 2% Zones
    raw_levels = sorted(list(set(raw_levels)))
    zones = []
    current_cluster = [raw_levels[0]]

    for level in raw_levels[1:]:
        if level <= current_cluster[0] * 1.02: 
            current_cluster.append(level)
        else:
            zones.append(np.median(current_cluster))
            current_cluster = [level]
    zones.append(np.median(current_cluster))

    # 3. Identify closest Support below current price
    supports = [z for z in zones if z < latest_close]
    if not supports: return None
    s1 = max(supports)

    # 4. Check if recent price touched or is hovering in the 2% support zone
    # Condition: Current or previous low dipped into the zone, but price is closing above it.
    in_zone = (latest_low <= s1 * 1.02 or prev_low <= s1 * 1.02) and (latest_close >= s1 * 0.98)
    
    if in_zone:
        return s1
    return None

def check_ltf_choch(df_ltf):
    """Scans LTF to verify if Market Structure Shift (CHoCH) occurred after HTF touch."""
    df_ltf = df_ltf.dropna()
    if len(df_ltf) < 30: return None
    
    # Focus on the recent LTF price action (last 100 LTF candles)
    recent_df = df_ltf.tail(100).copy()
    latest_close = recent_df.iloc[-1]['Close']
    
    # 1. Find LTF Swing Highs and Lows
    window = 5
    recent_df['Swing_High'] = False
    recent_df['Swing_Low'] = False
    
    highs = recent_df['High'].values
    lows = recent_df['Low'].values
    
    for i in range(window, len(recent_df) - window):
        if max(highs[i-window:i+window+1]) == highs[i]:
            recent_df.iloc[i, recent_df.columns.get_loc('Swing_High')] = True
        if min(lows[i-window:i+window+1]) == lows[i]:
            recent_df.iloc[i, recent_df.columns.get_loc('Swing_Low')] = True

    # 2. Identify the absolute lowest point recently (The HTF Touch)
    if not recent_df['Swing_Low'].any(): return None
    
    # Find the index of the absolute lowest price in this recent window
    lowest_idx = recent_df['Low'].idxmin()
    
    # 3. Find the last Swing High that occurred strictly BEFORE the absolute low
    prior_action = recent_df.loc[:lowest_idx]
    swing_highs_before_low = prior_action[prior_action['Swing_High'] == True]
    
    if swing_highs_before_low.empty: return None
    
    # The crucial Lower High (Supply) that caused the drop into HTF support
    last_supply_high = swing_highs_before_low.iloc[-1]['High']
    
    # 4. The CHoCH Trigger: Has the LTF price crossed above that supply high?
    # Ensure it actually broke out and didn't just wick it
    choch_confirmed = latest_close > last_supply_high
    
    if choch_confirmed:
        return last_supply_high, latest_close
        
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
        st.info(f"Loaded {len(ticker_list)} stocks. Running MTFA Scanner...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        for i, ticker in enumerate(ticker_list):
            status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker} (HTF...)")
            
            try:
                stock = yf.Ticker(ticker)
                
                # --- STEP 1: Evaluate Higher Timeframe (HTF) ---
                df_htf = stock.history(period=htf_period, interval=htf_selection)
                
                if not df_htf.empty:
                    htf_support = check_htf_support(df_htf)
                    
                    # --- STEP 2: Evaluate Lower Timeframe (LTF) if HTF passes ---
                    if htf_support:
                        status_text.text(f"Scanning {i+1}/{len(ticker_list)}: {ticker} (Checking LTF CHoCH...)")
                        
                        df_ltf = stock.history(period=ltf_period, interval=ltf_selection)
                        
                        if not df_ltf.empty:
                            ltf_data = check_ltf_choch(df_ltf)
                            
                            if ltf_data:
                                ltf_breakout_lvl, latest_c = ltf_data
                                sector = fetch_metadata(ticker)
                                
                                results.append({
                                    "Ticker": ticker.replace(".NS", ""),
                                    "Sector": sector,
                                    "Status": f"🔥 {ltf_selection.upper()} CHoCH Confirmed",
                                    "Current Price": round(float(latest_c), 2),
                                    "HTF Support Zone": round(float(htf_support), 2),
                                    "LTF Breakout Lvl": round(float(ltf_breakout_lvl), 2)
                                })
            except Exception:
                pass 
                
            progress_bar.progress((i + 1) / len(ticker_list))
            
        status_text.empty()
        progress_bar.empty()
        
        # ==========================================
        # 5. RESULTS DISPLAY
        # ==========================================
        st.subheader(f"📊 {selected_index} Scan Results (HTF: {htf_selection.upper()} | LTF: {ltf_selection.upper()})")
        
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success("Scanner completed successfully. Stocks listed above have touched a major HTF support and confirmed a trend reversal on the LTF.")
        else:
            st.warning(f"Scan complete. No stocks in the {selected_index} currently show an HTF Support Touch combined with an LTF Market Structure Shift.")
