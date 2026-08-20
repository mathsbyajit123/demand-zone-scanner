import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. UI & STYLING CONFIGURATION
# ==========================================
st.set_page_config(page_title="HTF Demand + LTF BOS Scanner", layout="wide")

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
    .metric-box {
        background-color: #11151C; border-radius: 8px; padding: 15px;
        border: 1px solid #1E293B; text-align: center;
    }
    .metric-box span { color: #4FACFE; font-weight: 600; font-size: 13px; }
    .metric-box h3 { color: #F8FAFC; margin: 0; padding-top: 5px; font-size: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">HTF DEMAND + LTF BOS SCANNER</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Daily Demand Interaction | 75-Min Structure Break | Volume Confirmation</p>', unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR CONFIGURATION
# ==========================================
with st.sidebar:
    st.markdown("### **SCANNER CONTROLS**")
    st.divider()
    
    universe_selection = st.selectbox(
        "Select Watchlist",
        ["Top Heavyweights", "Nifty 50 Sample", "Custom Input"]
    )
    
    if universe_selection == "Top Heavyweights":
        default_tickers = "RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, ICICIBANK.NS, SBIN.NS, BHARTIARTL.NS, LT.NS"
    elif universe_selection == "Nifty 50 Sample":
        default_tickers = "RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, ICICIBANK.NS, AXISBANK.NS, KOTAKBANK.NS, ITC.NS, MARUTI.NS, TATAMOTORS.NS, TATASTEEL.NS, BAJFINANCE.NS"
    else:
        default_tickers = "RELIANCE.NS, TCS.NS, INFY.NS"
        
    tickers_input = st.text_area("Stock Tickers (Comma separated)", value=default_tickers, height=100)
    ticker_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    
    st.divider()
    vol_multiplier = st.slider("Volume Spike Multiplier", min_value=1.0, max_value=3.0, value=1.3, step=0.1)

# ==========================================
# 3. DATA & ZONE DETECTION ENGINE
# ==========================================
def get_clean_ohlc(df):
    """Flattens MultiIndex columns from newer yfinance versions."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()

def get_data(ticker, period="60d"):
    """Fetches Daily and 15m data, resampled to 75m."""
    htf_raw = yf.download(ticker, period="1y", interval="1d", progress=False)
    htf_data = get_clean_ohlc(htf_raw)
    
    ltf_raw = yf.download(ticker, period=period, interval="15m", progress=False)
    ltf_clean = get_clean_ohlc(ltf_raw)
    
    if ltf_clean.empty or htf_data.empty:
        return pd.DataFrame(), pd.DataFrame()
        
    # Standard modern pandas resampling for NSE 75-minute intervals
    ltf_data = ltf_clean.resample('75min', offset='15min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    
    return htf_data, ltf_data

def identify_zones(df, left_bars=3, right_bars=3):
    """Finds Pivot Highs (Supply) and Pivot Lows (Demand) without breaking end-of-series data."""
    df = df.copy()
    window = left_bars + right_bars + 1
    
    # Calculate rolling min/max
    df['Pivot_Low'] = df['Low'] == df['Low'].rolling(window=window, center=True).min()
    df['Pivot_High'] = df['High'] == df['High'].rolling(window=window, center=True).max()
    
    # Map Zones and forward-fill active levels
    df['Demand_Zone_High'] = np.where(df['Pivot_Low'], df['High'], np.nan)
    df['Demand_Zone_Low'] = np.where(df['Pivot_Low'], df['Low'], np.nan)
    df['Demand_Zone_High'] = df['Demand_Zone_High'].ffill()
    df['Demand_Zone_Low'] = df['Demand_Zone_Low'].ffill()

    df['Supply_Zone_High'] = np.where(df['Pivot_High'], df['High'], np.nan)
    df['Supply_Zone_Low'] = np.where(df['Pivot_High'], df['Low'], np.nan)
    df['Supply_Zone_High'] = df['Supply_Zone_High'].ffill()
    df['Supply_Zone_Low'] = df['Supply_Zone_Low'].ffill()
    
    return df

# ==========================================
# 4. EXECUTION HANDLER
# ==========================================
if st.button("🔥 RUN SCANNER", type="primary"):
    if not ticker_list:
        st.warning("Please provide at least one valid ticker symbol.")
    else:
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        alerts = []
        total = len(ticker_list)
        
        for idx, ticker in enumerate(ticker_list):
            progress_text.markdown(f"**Analyzing ({idx+1}/{total}):** `{ticker}`")
            progress_bar.progress((idx + 1) / total)
            
            try:
                htf, ltf = get_data(ticker)
                
                if htf.empty or ltf.empty or len(htf) < 20 or len(ltf) < 20:
                    continue
                
                htf = identify_zones(htf)
                ltf = identify_zones(ltf)
                
                ltf['Vol_SMA'] = ltf['Volume'].rolling(20).mean()
                
                latest_price = float(ltf['Close'].iloc[-1])
                latest_vol = float(ltf['Volume'].iloc[-1])
                avg_vol = float(ltf['Vol_SMA'].iloc[-1]) if pd.notna(ltf['Vol_SMA'].iloc[-1]) else 0.0
                
                htf_demand_high = float(htf['Demand_Zone_High'].dropna().iloc[-1]) if not htf['Demand_Zone_High'].dropna().empty else None
                htf_demand_low = float(htf['Demand_Zone_Low'].dropna().iloc[-1]) if not htf['Demand_Zone_Low'].dropna().empty else None
                ltf_supply_high = float(ltf['Supply_Zone_High'].dropna().iloc[-1]) if not ltf['Supply_Zone_High'].dropna().empty else None
                
                if None in (htf_demand_high, htf_demand_low, ltf_supply_high):
                    continue
                
                # Condition A: Interaction with HTF Demand Zone
                in_htf_demand = (latest_price <= htf_demand_high * 1.01) and (latest_price >= htf_demand_low * 0.99)
                
                # Condition B: LTF Break of Structure (Close above prior supply zone)
                ltf_bos = latest_price > ltf_supply_high
                
                # Condition C: Volume Confirmation
                volume_confirmed = (latest_vol > (vol_multiplier * avg_vol)) if avg_vol > 0 else True
                
                if in_htf_demand and ltf_bos and volume_confirmed:
                    vol_ratio = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 1.0
                    alerts.append({
                        "Asset": ticker.replace(".NS", ""),
                        "Live Price": round(latest_price, 2),
                        "HTF Demand Range": f"{round(htf_demand_low, 2)} - {round(htf_demand_high, 2)}",
                        "LTF Supply Broken": round(ltf_supply_high, 2),
                        "Volume Spike": f"🔥 {vol_ratio}x Avg",
                        "Status": "🎯 ENTRY READY"
                    })
            except Exception as e:
                pass
                
        progress_text.empty()
        progress_bar.empty()
        
        st.divider()
        
        if alerts:
            st.success(f"Isolated {len(alerts)} setup(s) matching your multi-timeframe criteria.")
            results_df = pd.DataFrame(alerts)
            
            styled_df = results_df.style.set_properties(**{
                'background-color': '#11151C',
                'color': '#F8FAFC',
                'border-color': '#1E293B',
                'text-align': 'center'
            }).map(lambda v: 'color: #00FF00; font-weight: 800;', subset=['Status'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Volume Spike'])
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info("No matching setups found right now. No stocks are currently testing a Daily Demand Zone while simultaneously confirming a 75m BOS with volume.")
