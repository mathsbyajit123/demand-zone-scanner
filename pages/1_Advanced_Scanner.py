import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

st.set_page_config(page_title="Advanced S&R Scanner", layout="wide")
st.title("Automated Multi-Timeframe S&R Scanner")
st.markdown("Scans Nifty 500 for Support/Resistance Zones (minimum 3 touches) and Rejection/Breakout patterns.")

# --- 1. FETCH NIFTY 500 TICKERS AUTOMATICALLY ---
@st.cache_data(ttl=86400) # Caches the list for 24 hours
def get_nifty_500():
    try:
        # Pulls live Nifty 500 list from a public GitHub CSV
        url = "https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/ind_nifty500list.csv"
        df = pd.read_csv(url)
        return [str(symbol) + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception as e:
        st.error("Could not load Nifty 500 list. Using backup top 10 stocks.")
        return ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'L&T.NS', 'BAJFINANCE.NS']

# --- 2. CORE LOGIC ---
@st.cache_data(show_spinner=False)
def fetch_data(tickers, period="3y"):
    # Downloads data for all stocks at once
    data = yf.download(tickers, period=period, group_by='ticker', threads=True, progress=False)
    return data

def resample_data(df, timeframe):
    resample_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
    if timeframe == '1D': return df
    elif timeframe == '1W': return df.resample('W').agg(resample_dict).dropna()
    elif timeframe == '1M': return df.resample('ME').agg(resample_dict).dropna()
    elif timeframe == '3M': return df.resample('3ME').agg(resample_dict).dropna()
    elif timeframe == '6M': return df.resample('6ME').agg(resample_dict).dropna()
    elif timeframe == '12M': return df.resample('YE').agg(resample_dict).dropna()
    return df

def find_zones(df, zone_type='support', window=10, zone_width_pct=0.02, min_touches=3):
    if len(df) < window * 2: return []
    
    if zone_type == 'support':
        pivots = df.iloc[argrelextrema(df['Low'].values, np.less_equal, order=window)[0]]['Low']
    else:
        pivots = df.iloc[argrelextrema(df['High'].values, np.greater_equal, order=window)[0]]['High']
        
    zones = []
    for price in pivots:
        matched = False
        for zone in zones:
            if abs(price - zone['center']) / zone['center'] <= zone_width_pct:
                zone['touches'] += 1
                zone['max'] = max(zone['max'], price)
                zone['min'] = min(zone['min'], price)
                matched = True
                break
        if not matched:
            zones.append({'center': price, 'max': price, 'min': price, 'touches': 1})
            
    return [z for z in zones if z['touches'] >= min_touches]

def check_rejection_candles(df, zone_type):
    if len(df) < 2: return False, "None"
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    body = abs(latest['Close'] - latest['Open'])
    lower_shadow = min(latest['Open'], latest['Close']) - latest['Low']
    upper_shadow = latest['High'] - max(latest['Open'], latest['Close'])
    
    if zone_type == 'support':
        is_hammer = (lower_shadow > (2 * body)) and (upper_shadow < (0.5 * body))
        prev_red = prev['Close'] < prev['Open']
        curr_green = latest['Close'] > latest['Open']
        engulfing = prev_red and curr_green and (latest['Close'] > prev['Open']) and (latest['Open'] < prev['Close'])
        
        if is_hammer: return True, "Hammer"
        if engulfing: return True, "Bullish Engulfing"
        
    elif zone_type == 'resistance':
        is_shooting_star = (upper_shadow > (2 * body)) and (lower_shadow < (0.5 * body))
        prev_green = prev['Close'] > prev['Open']
        curr_red = latest['Close'] < latest['Open']
        engulfing = prev_green and curr_red and (latest['Close'] < prev['Open']) and (latest['Open'] > prev['Close'])
        
        if is_shooting_star: return True, "Shooting Star"
        if engulfing: return True, "Bearish Engulfing"
        
    return False, "None"

# --- 3. USER INTERFACE ---
col1, col2 = st.columns(2)
with col1:
    timeframe = st.selectbox("Select Timeframe", ["1D", "1W", "1M", "3M", "6M", "12M"])
with col2:
    scan_type = st.radio("Scan Type", ["Support Rejection (Bullish)", "Resistance Rejection (Bearish)", "Support Breakdown", "Resistance Breakout"])

nifty_tickers = get_nifty_500()
st.write(f"Loaded {len(nifty_tickers)} Nifty 500 stocks ready for scanning.")

if st.button("RUN AUTO-SCAN"):
    # Create an empty container to show progress
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    with st.spinner("Connecting to Yahoo Finance and downloading 3 years of data... (This takes about 1-2 minutes)"):
        raw_data = fetch_data(nifty_tickers, period="3y") 
        
        results = []
        total_stocks = len(nifty_tickers)
        
        for i, ticker in enumerate(nifty_tickers):
            # Update progress bar
            progress_bar.progress((i + 1) / total_stocks)
            
            try:
                # Yahoo Finance multi-ticker download structure handling
                if total_stocks > 1:
                    df = raw_data[ticker].dropna()
                else:
                    df = raw_data.dropna()
                    
                if df.empty or len(df) < 50: continue # Skip if not enough data
                
                tf_df = resample_data(df, timeframe)
                latest_close = tf_df.iloc[-1]['Close']
                
                z_type = 'support' if 'Support' in scan_type else 'resistance'
                zones = find_zones(tf_df, zone_type=z_type, min_touches=3)
                
                for zone in zones:
                    # Is current price inside the zone? (within 2%)
                    is_in_zone = abs(latest_close - zone['center']) / zone['center'] <= 0.02
                    
                    if is_in_zone:
                        if 'Rejection' in scan_type:
                            has_signal, pattern = check_rejection_candles(tf_df, z_type)
                            if has_signal:
                                results.append({"Ticker": ticker.replace('.NS', ''), "Zone Price": round(zone['center'], 2), "Pattern": pattern, "Times Tested": zone['touches']})
                                
                        elif scan_type == "Support Breakdown" and latest_close < zone['min']:
                            results.append({"Ticker": ticker.replace('.NS', ''), "Zone Price": round(zone['center'], 2), "Pattern": "Breakdown", "Times Tested": zone['touches']})
                            
                        elif scan_type == "Resistance Breakout" and latest_close > zone['max']:
                            results.append({"Ticker": ticker.replace('.NS', ''), "Zone Price": round(zone['center'], 2), "Pattern": "Breakout", "Times Tested": zone['touches']})
            except Exception as e:
                pass # Skip stock silently if there is a calculation error
                
        # Clear progress bar
        progress_bar.empty()
        
        if results:
            st.success(f"Scan complete! Found {len(results)} stocks matching your criteria.")
            st.dataframe(pd.DataFrame(results))
        else:
            st.warning("Scan complete. No stocks matched your criteria right now.")
