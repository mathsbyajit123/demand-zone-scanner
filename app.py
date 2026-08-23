import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import io
import requests

warnings.filterwarnings('ignore')

# ==========================================
# 1. UI CONFIGURATION
# ==========================================
st.set_page_config(page_title="RSI Divergence Terminal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #090B10; color: #E2E8F0; }
    .gradient-text {
        font-weight: 900; font-size: 34px; letter-spacing: -1px;
        background: -webkit-linear-gradient(45deg, #00F2FE, #4FACFE, #F6D365);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px; padding-bottom: 0px; text-transform: uppercase;
    }
    .sub-text { font-size: 14px; color: #64748B; margin-top: -5px; margin-bottom: 25px; font-weight: 600;}
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #00C6FF 0%, #0072FF 100%);
        color: white; border: none; border-radius: 6px;
        padding: 12px 24px; font-size: 16px; font-weight: 700; letter-spacing: 1px;
        box-shadow: 0 4px 20px rgba(0, 198, 255, 0.4); width: 100%; text-transform: uppercase;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">RSI DIVERGENCE TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Regular & Hidden Divergence | Multi-Timeframe | Broad Market Scanning</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER (SIDEBAR)
# ==========================================
with st.sidebar:
    st.markdown("### **1. MARKET UNIVERSE**")
    universe_choice = st.selectbox(
        "Choose Stock Source:",
        [
            "Nifty 500 (Broad Market)", 
            "Nifty MidSmallcap 400", 
            "Nifty Smallcap 250",
            "Nifty Midcap 150",
            "Nifty 50",
            "F&O Universe (~242)",
            "Custom Tickers"
        ]
    )
    
    custom_pasted = ""
    if universe_choice == "Custom Tickers":
        custom_pasted = st.text_area("Paste Symbols (comma-separated):", "RELIANCE, TCS, HDFCBANK")
        
    st.divider()
    st.markdown("### **2. TIMEFRAME & VECTOR**")
    tf_options = {
        "15 Min": "15m",
        "75 Min": "75m",
        "1 Day": "1d", 
        "1 Week": "1wk", 
        "1 Month": "1mo"
    }
    tf_label = st.selectbox("Resolution:", list(tf_options.keys()), index=2)
    timeframe = tf_options[tf_label]
    
    direction = st.radio("Trend Bias:", ("🟢 Bullish (Long Setups)", "🔴 Bearish (Short Setups)"))
    is_bullish = "Bullish" in direction

# ==========================================
# 3. FAST UNIVERSE PARSER
# ==========================================
@st.cache_data(ttl=3600)
def load_nse_list(index_name):
    urls = {
        "Nifty 500 (Broad Market)": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "Nifty MidSmallcap 400": "https://archives.nseindia.com/content/indices/ind_niftymidsmallcap400list.csv",
        "Nifty Smallcap 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "Nifty Midcap 150": "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
    }
    
    url = urls.get(index_name)
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    if url:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                df = pd.read_csv(io.StringIO(res.text))
                return [f"{s.strip()}.NS" for s in df['Symbol']]
        except Exception:
            pass
            
    # Fallback to standard highly liquid F&O list if NSE site fails
    return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "TATAMOTORS.NS"]

def get_target_tickers():
    if universe_choice == "Custom Tickers":
        return [f"{t.strip().upper()}.NS" if not t.strip().upper().endswith(".NS") else t.strip().upper() for t in custom_pasted.split(",") if t.strip()]
    elif universe_choice == "F&O Universe (~242)":
        return ["AARTIIND.NS", "ABB.NS", "ABBOTINDIA.NS", "ABCAPITAL.NS", "ACC.NS", "ADANIENT.NS", "ADANIPORTS.NS", "ASHOKLEY.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BHEL.NS", "BIOCON.NS", "BPCL.NS", "BRITANNIA.NS", "CANBK.NS", "CHOLAFIN.NS", "CIPLA.NS", "COALINDIA.NS", "DABUR.NS", "DIVISLAB.NS", "DLF.NS", "DRREDDY.NS", "EICHERMOT.NS", "FEDERALBNK.NS", "GAIL.NS", "GODREJCP.NS", "GRASIM.NS", "HAL.NS", "HAVELLS.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "IGL.NS", "INDIGO.NS", "INDUSINDBK.NS", "JSWSTEEL.NS", "M&M.NS", "MUTHOOTFIN.NS", "NMDC.NS", "PFC.NS", "PNB.NS", "POWERGRID.NS", "RECLTD.NS", "SAIL.NS", "SIEMENS.NS", "TATAPOWER.NS", "TITAN.NS", "TVSMOTOR.NS", "ULTRACEMCO.NS", "VEDL.NS", "WIPRO.NS", "ZOMATO.NS"]
    else:
        return load_nse_list(universe_choice)

# ==========================================
# 4. MATHEMATICS & RSI ENGINE
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_rsi_divergence(df, is_bull):
    if len(df) < 45: return None
    
    df['RSI'] = calculate_rsi(df['Close'], 14)
    live_price = float(df['Close'].iloc[-1])
    
    # Analyze recent 15 bars vs prior 15 bars for swing points
    recent_p_low = df['Low'].iloc[-15:].min()
    prior_p_low = df['Low'].iloc[-30:-15].min()
    
    recent_rsi_low = df['RSI'].iloc[-15:].min()
    prior_rsi_low = df['RSI'].iloc[-30:-15].min()
    
    recent_p_high = df['High'].iloc[-15:].max()
    prior_p_high = df['High'].iloc[-30:-15].max()
    
    recent_rsi_high = df['RSI'].iloc[-15:].max()
    prior_rsi_high = df['RSI'].iloc[-30:-15].max()
    
    if is_bull:
        # REGULAR BULLISH (Reversal): Price Lower Low, RSI Higher Low
        if recent_p_low < prior_p_low and recent_rsi_low > prior_rsi_low:
            return {
                "Setup": "🟢 Regular Bullish DVG",
                "Indication": "Trend Reversal Up",
                "Live Price": round(live_price, 2),
                "Price Swing": f"₹{round(prior_p_low, 1)} ↘ ₹{round(recent_p_low, 1)}",
                "RSI Swing": f"{round(prior_rsi_low, 1)} ↗ {round(recent_rsi_low, 1)}"
            }
        # HIDDEN BULLISH (Continuation): Price Higher Low, RSI Lower Low
        elif recent_p_low > prior_p_low and recent_rsi_low < prior_rsi_low:
            return {
                "Setup": "🟢 Hidden Bullish DVG",
                "Indication": "Pullback Exhausted (Continuation)",
                "Live Price": round(live_price, 2),
                "Price Swing": f"₹{round(prior_p_low, 1)} ↗ ₹{round(recent_p_low, 1)}",
                "RSI Swing": f"{round(prior_rsi_low, 1)} ↘ {round(recent_rsi_low, 1)}"
            }
    else:
        # REGULAR BEARISH (Reversal): Price Higher High, RSI Lower High
        if recent_p_high > prior_p_high and recent_rsi_high < prior_rsi_high:
            return {
                "Setup": "🔴 Regular Bearish DVG",
                "Indication": "Trend Reversal Down",
                "Live Price": round(live_price, 2),
                "Price Swing": f"₹{round(prior_p_high, 1)} ↗ ₹{round(recent_p_high, 1)}",
                "RSI Swing": f"{round(prior_rsi_high, 1)} ↘ {round(recent_rsi_high, 1)}"
            }
        # HIDDEN BEARISH (Continuation): Price Lower High, RSI Higher High
        elif recent_p_high < prior_p_high and recent_rsi_high > prior_rsi_high:
            return {
                "Setup": "🔴 Hidden Bearish DVG",
                "Indication": "Relief Rally Exhausted (Continuation)",
                "Live Price": round(live_price, 2),
                "Price Swing": f"₹{round(prior_p_high, 1)} ↘ ₹{round(recent_p_high, 1)}",
                "RSI Swing": f"{round(prior_rsi_high, 1)} ↗ {round(recent_rsi_high, 1)}"
            }
            
    return None

def resample_to_75m(df):
    """Resamples 15m intraday data into strict 75-minute chunks."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.resample('75min', offset='15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

# ==========================================
# 5. EXECUTION PIPELINE
# ==========================================
if st.button("🚀 EXECUTE RSI SCANNER", type="primary"):
    tickers = get_target_tickers()
    
    if not tickers:
        st.error("No symbols found. Please select a valid universe.")
    else:
        st.write(f"**Scanning {len(tickers)} stocks on `{tf_label}`...**")
        progress_bar = st.progress(0)
        
        # Smart Lookback optimization
        if timeframe == "1mo": 
            period_val, interval_val = "max", "1mo"
        elif timeframe == "1wk": 
            period_val, interval_val = "10y", "1wk"
        elif timeframe == "1d": 
            period_val, interval_val = "2y", "1d"
        elif timeframe == "75m":
            period_val, interval_val = "60d", "15m" # Fetch 15m to rebuild 75m
        else: 
            period_val, interval_val = "30d", "15m"
            
        market_data = yf.download(tickers, period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        alerts = []
        for idx, ticker in enumerate(tickers):
            progress_bar.progress((idx + 1) / len(tickers))
            try:
                df = market_data.copy() if len(tickers) == 1 else market_data[ticker].copy()
                df = df.dropna()
                
                if timeframe == '75m':
                    df = resample_to_75m(df)
                    
                if len(df) < 40: continue
                
                res = check_rsi_divergence(df, is_bullish)
                    
                if res:
                    res['Asset'] = ticker.replace('.NS', '')
                    alerts.append(res)
            except Exception:
                continue
                
        progress_bar.empty()
        st.divider()
        
        if alerts:
            st.success(f"Isolated {len(alerts)} divergence setup(s).")
            out_df = pd.DataFrame(alerts)[['Asset', 'Setup', 'Indication', 'Live Price', 'Price Swing', 'RSI Swing']]
            
            styled = out_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00F2FE; font-weight: 800;', subset=['Asset'])\
              .map(lambda v: 'color: #00FF00; font-weight: 800;' if 'Bull' in str(v) else 'color: #FF4500; font-weight: 800;', subset=['Setup'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Indication'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error(f"0 Matches Found. No distinct RSI Divergences found on {tf_label} for this universe.")
