import streamlit as st
import yfinance as yf
import pandas as pd
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SIDEBAR SETTINGS
# ==========================================
st.set_page_config(page_title="Advanced Setup Scanner", layout="wide")
st.title("🚀 Advanced Market Structure Scanner")
st.markdown("Scans for EMA crossovers followed by dry volume pullbacks and CHoCH/HH breakouts.")

st.sidebar.header("⚙️ Scanner Settings")

# Default Tickers
default_tickers = "REDINGTON.NS, RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, TATASTEEL.NS, SBIN.NS, ZOMATO.NS, AAPL, MSFT"
tickers_input = st.sidebar.text_area("Tickers (Comma separated)", default_tickers)

# Flexible Timeframe
timeframe = st.sidebar.selectbox("Timeframe", ["1d", "1wk"], index=0, help="1d = Daily, 1wk = Weekly")

# Flexible EMAs & Volume
fast_ema_len = st.sidebar.number_input("Fast EMA Length", min_value=5, max_value=200, value=21)
slow_ema_len = st.sidebar.number_input("Slow EMA Length", min_value=10, max_value=200, value=44)
vol_sma_len = st.sidebar.number_input("Volume Average Length", min_value=5, max_value=100, value=20)

# ==========================================
# 2. CORE LOGIC & MATHEMATICS
# ==========================================
def get_market_cap_category(mcap_cr):
    """Categorizes Market Cap into readable tiers."""
    if mcap_cr == 0: return "Unknown"
    elif mcap_cr < 100: return "Under 100 Cr"
    elif 100 <= mcap_cr < 500: return "100 - 500 Cr"
    elif 500 <= mcap_cr < 1000: return "500 - 1000 Cr"
    elif 1000 <= mcap_cr < 10000: return "1000 - 10000 Cr"
    elif 10000 <= mcap_cr < 100000: return "10000 - 1 Lakh Cr"
    else: return "Over 1 Lakh Cr"

def fetch_metadata(ticker):
    """Fetches Sector and Market Cap only for stocks that pass the scan."""
    try:
        info = yf.Ticker(ticker).info
        sector = info.get('sector', 'N/A')
        # Convert raw market cap to Crores (approximate for INR, just raw formatting for USD)
        mcap_raw = info.get('marketCap', 0)
        mcap_cr = mcap_raw / 10_000_000 if ".NS" in ticker else mcap_raw / 1_000_000 # Millions for US
        
        mcap_cat = get_market_cap_category(mcap_cr) if ".NS" in ticker else f"${mcap_cr:,.0f}M"
        return sector, mcap_cat
    except:
        return "N/A", "Unknown"

def check_setup(ticker, df):
    # LIVE MARKET SAFETY: Drop corrupted rows
    df = df.dropna()
    
    # IGNORE TODAY'S INCOMPLETE CANDLE
    if len(df) > 0:
        df = df.iloc[:-1]

    if len(df) < 50:
        return None
        
    # Calculate Custom Indicators
    df['EMA_Fast'] = df['Close'].ewm(span=fast_ema_len, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=slow_ema_len, adjust=False).mean()
    df['Vol_SMA'] = df['Volume'].rolling(window=vol_sma_len).mean()
    
    # 1. The Cross
    cross_ups = (df['EMA_Fast'] > df['EMA_Slow']) & (df['EMA_Fast'].shift(1) <= df['EMA_Slow'].shift(1))
    if not cross_ups.any(): return None 
        
    last_cross_idx = cross_ups[::-1].idxmax()
    post_cross = df.loc[last_cross_idx:]
    if len(post_cross) < 3: return None

    # 2. Track the Swing High (Prior to today)
    prior_candles = post_cross.iloc[:-1]
    if prior_candles.empty: return None
    swing_high = prior_candles['High'].max()
    
    # 3. The Retracement & Dry Volume Condition
    # Rule: Low touches Fast EMA, Close stays above Slow EMA, Volume is DRY (< SMA)
    pullback_days = prior_candles[
        (prior_candles['Low'] <= prior_candles['EMA_Fast']) & 
        (prior_candles['Close'] >= prior_candles['EMA_Slow']) & 
        (prior_candles['Volume'] < prior_candles['Vol_SMA'])
    ]
    if pullback_days.empty: return None 
        
    # 4. Check Current Status
    latest = post_cross.iloc[-1]
    
    in_accumulation_zone = (
        (latest['Low'] <= latest['EMA_Fast']) and 
        (latest['Close'] >= latest['EMA_Slow']) and 
        (latest['Volume'] < latest['Vol_SMA']) # DRY VOLUME CONFIRMED
    )
    hh_confirmed = latest['Close'] > swing_high
    
    # Return basic setup info if found
    if hh_confirmed:
        return "🔥 Breakout Confirmed (HH)", swing_high, latest['Close']
    elif in_accumulation_zone:
        return "📉 Dry Pullback Zone (HL)", swing_high, latest['Close']
        
    return None

# ==========================================
# 3. EXECUTION ENGINE
# ==========================================
if st.sidebar.button("Run Scanner", type="primary"):
    ticker_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    
    for i, ticker in enumerate(ticker_list):
        status_text.text(f"Scanning {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y", interval=timeframe)
            
            if not df.empty:
                setup_data = check_setup(ticker, df)
                
                # If setup is found, THEN fetch the heavy sector/market cap data
                if setup_data:
                    status, swing_h, latest_c = setup_data
                    sector, mcap = fetch_metadata(ticker)
                    
                    results.append({
                        "Ticker": ticker,
                        "Sector": sector,
                        "Market Cap": mcap,
                        "Status": status,
                        "Swing High": round(float(swing_h), 2),
                        "Current Price": round(float(latest_c), 2)
                    })
        except Exception:
            pass # Skip broken tickers
            
        progress_bar.progress((i + 1) / len(ticker_list))
        
    status_text.empty()
    progress_bar.empty()
    
    # ==========================================
    # 4. RESULTS DISPLAY
    # ==========================================
    st.subheader(f"📊 Scan Results ({timeframe.upper()})")
    
    if results:
        final_df = pd.DataFrame(results)
        st.dataframe(final_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks met the criteria (Dry Volume Pullback / Breakout) right now.")
