import streamlit as st
import yfinance as yf
import pandas as pd
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')

# --- 1. STREAMLIT WEB SETUP ---
st.set_page_config(page_title="Market Scanner", layout="wide")
st.title("🚀 Live Market Structure Scanner")
st.markdown("This scanner is built to run safely on cloud servers during live market hours.")

TICKERS = [
    "REDINGTON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", 
    "INFY.NS", "TATASTEEL.NS", "SBIN.NS", "AAPL", "MSFT"
]
TIMEFRAME = "1d"

def calculate_indicators(df):
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    return df

def check_setup(ticker, df):
    # LIVE MARKET SAFETY: Drop corrupted rows instantly
    df = df.dropna()
    
    # IGNORE TODAY'S INCOMPLETE CANDLE
    if len(df) > 0:
        df = df.iloc[:-1]

    if len(df) < 50:
        return None
        
    df = calculate_indicators(df)
    
    cross_ups = (df['EMA_21'] > df['EMA_44']) & (df['EMA_21'].shift(1) <= df['EMA_44'].shift(1))
    if not cross_ups.any(): return None 
        
    last_cross_idx = cross_ups[::-1].idxmax()
    post_cross = df.loc[last_cross_idx:]
    if len(post_cross) < 3: return None

    prior_candles = post_cross.iloc[:-1]
    if prior_candles.empty: return None
        
    swing_high = prior_candles['High'].max()
    
    pullback_days = prior_candles[
        (prior_candles['Low'] <= prior_candles['EMA_21']) & 
        (prior_candles['Close'] >= prior_candles['EMA_44']) & 
        (prior_candles['Volume'] < prior_candles['Vol_SMA_20'])
    ]
    if pullback_days.empty: return None 
        
    latest = post_cross.iloc[-1]
    
    in_accumulation_zone = (
        (latest['Low'] <= latest['EMA_21']) and 
        (latest['Close'] >= latest['EMA_44']) and 
        (latest['Volume'] < latest['Vol_SMA_20'])
    )
    hh_confirmed = latest['Close'] > swing_high
    
    if hh_confirmed:
        return {"Ticker": ticker, "Status": "🔥 Breakout Confirmed (HH)", "Swing High": round(float(swing_high), 2), "Latest": round(float(latest['Close']), 2)}
    elif in_accumulation_zone:
        return {"Ticker": ticker, "Status": "📉 In Pullback Zone (HL)", "Swing High": round(float(swing_high), 2), "Latest": round(float(latest['Close']), 2)}
    return None

# --- 2. RUN THE SCAN BUTTON ---
if st.button("Run Scanner Now", type="primary"):
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    
    for i, ticker in enumerate(TICKERS):
        # Update Streamlit UI text directly
        status_text.text(f"Fetching live data for {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y", interval=TIMEFRAME)
            
            if not df.empty:
                result = check_setup(ticker, df)
                if result:
                    results.append(result)
                    
        except Exception as e:
            # If a stock fails, tell the web page but keep scanning the rest
            st.toast(f"Skipped {ticker} due to data error.")
            
        progress_bar.progress((i + 1) / len(TICKERS))
        
    # Clear the loading indicators
    status_text.empty()
    progress_bar.empty()
    
    # --- 3. RENDER RESULTS TO WEB BROWSER ---
    st.subheader("📊 Scan Results")
    if results:
        final_df = pd.DataFrame(results)
        st.dataframe(final_df, use_container_width=True, hide_index=True)
    else:
        st.info("No stocks met the setup criteria today.")
