import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import io
import requests

warnings.filterwarnings('ignore')

# ==========================================
# 1. UI & STYLING
# ==========================================
st.set_page_config(page_title="Professional GTF Scanner", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #090B10; color: #E2E8F0; }
    .gradient-text {
        font-weight: 900; font-size: 32px; letter-spacing: -1px;
        background: -webkit-linear-gradient(45deg, #00F2FE, #4FACFE, #F6D365);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px; text-transform: uppercase;
    }
    .sub-text { font-size: 14px; color: #64748B; margin-bottom: 25px; font-weight: 600;}
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #00C6FF 0%, #0072FF 100%);
        color: white; border: none; border-radius: 6px;
        padding: 12px 24px; font-size: 16px; font-weight: 700; width: 100%; text-transform: uppercase;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">PROFESSIONAL GTF SCANNER</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Strict Leg-In | Base | Leg-Out | Proximal/Distal Mapping</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **1. MARKET UNIVERSE**")
    universe_choice = st.selectbox(
        "Choose NSE List (>₹5000 Cr):",
        ["Nifty 500 (Broad Market)", "Nifty 50", "Custom Tickers"]
    )
    
    custom_pasted = ""
    if universe_choice == "Custom Tickers":
        custom_pasted = st.text_area("Paste Symbols (comma-separated):", "RELIANCE, TCS, HDFCBANK")
        
    st.divider()
    st.markdown("### **2. TIMEFRAME & BIAS**")
    tf_options = {"75 Min": "75m", "1 Day": "1d", "1 Week": "1wk"}
    tf_label = st.selectbox("Resolution:", list(tf_options.keys()), index=1)
    timeframe = tf_options[tf_label]
    
    direction = st.radio("Market Bias:", ("🟢 Demand Zones", "🔴 Supply Zones"))
    is_bullish = "Demand" in direction

# ==========================================
# 3. UNIVERSE FETCHING
# ==========================================
@st.cache_data(ttl=3600)
def load_nse_list(index_name):
    urls = {
        "Nifty 500 (Broad Market)": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
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
        except Exception: pass
    return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "LT.NS"]

def get_target_tickers():
    if universe_choice == "Custom Tickers":
        return [f"{t.strip().upper()}.NS" if not t.strip().upper().endswith(".NS") else t.strip().upper() for t in custom_pasted.split(",") if t.strip()]
    return load_nse_list(universe_choice)

# ==========================================
# 4. STRICT MATH ENGINE
# ==========================================
def resample_custom(df, tf_rule):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.resample(tf_rule, offset='15min' if tf_rule=='75m' else None).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

def analyze_structure(df):
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    cond = [
        (df['Body_Pct'] >= 60) & (df['Close'] > df['Open']),  # Strong Green Leg-Out
        (df['Body_Pct'] >= 60) & (df['Close'] < df['Open']),  # Strong Red Leg-Out
        (df['Body_Pct'] > 50) & (df['Close'] > df['Open']),   # Standard Green Leg-In
        (df['Body_Pct'] > 50) & (df['Close'] < df['Open']),   # Standard Red Leg-In
        (df['Body_Pct'] <= 50)                                # Base Candle
    ]
    df['Type'] = np.select(cond, ['Green Out', 'Red Out', 'Green In', 'Red In', 'Base'], default='Base')
    return df

def scan_strict_zones(df, is_bull):
    if len(df) < 30: return None
    df = analyze_structure(df)
    last_idx = len(df) - 1
    live_price = float(df['Close'].iloc[-1])
    
    for i in range(last_idx - 1, 4, -1):
        leg_out = df.iloc[i]
        
        # 1. LEG-OUT CHECK (Strict 60% Body)
        if is_bull and leg_out['Type'] != 'Green Out': continue
        if not is_bull and leg_out['Type'] != 'Red Out': continue
        
        # 2. BASE CHECK (1 to 3 candles)
        base_cnt = 0
        leg_in_idx = None
        
        for j in range(i-1, max(-1, i-5), -1):
            if df.iloc[j]['Type'] == 'Base':
                base_cnt += 1
            else:
                leg_in_idx = j
                break
                
        if base_cnt == 0 or base_cnt > 3 or leg_in_idx is None: continue
        
        # 3. LEG-IN CHECK (Must be an exciting candle > 50% body)
        leg_in = df.iloc[leg_in_idx]
        if leg_in['Type'] == 'Base': continue 
        
        bases = df.iloc[leg_in_idx+1 : i]
        
        # 4. ZONE MAPPING & BREAKOUT CONFIRMATION
        if is_bull:
            # Proximal (Demand): Highest body of bases
            prox = float(max(bases['Open'].max(), bases['Close'].max()))
            # Distal (Demand): Lowest wick of bases
            dist = float(bases['Low'].min())
            
            # Did Leg-Out close above the highest base?
            if leg_out['Close'] > bases['High'].max():
                # Freshness: Has the zone been tested before today?
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['Low'] <= prox).any(): break
                
                # Active Touch: Is live price inside the zone NOW?
                if live_price <= prox and live_price >= dist:
                    return {"Setup": "🟢 Demand: Leg-In -> Base -> Leg-Out", "Live Price": round(live_price, 2), "Proximal (Entry)": round(prox, 2), "Distal (SL)": round(dist, 2), "Bases": base_cnt}
                    
        else:
            # Proximal (Supply): Lowest body of bases
            prox = float(min(bases['Open'].min(), bases['Close'].min()))
            # Distal (Supply): Highest wick of bases
            dist = float(bases['High'].max())
            
            if leg_out['Close'] < bases['Low'].min():
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['High'] >= prox).any(): break
                
                if live_price >= prox and live_price <= dist:
                    return {"Setup": "🔴 Supply: Leg-In -> Base -> Leg-Out", "Live Price": round(live_price, 2), "Proximal (Entry)": round(prox, 2), "Distal (SL)": round(dist, 2), "Bases": base_cnt}
    return None

# ==========================================
# 5. EXECUTION PIPELINE
# ==========================================
if st.button("🚀 EXECUTE PROFESSIONAL SCANNER", type="primary"):
    tickers = get_target_tickers()
    if not tickers:
        st.error("No symbols loaded.")
    else:
        st.write(f"**Scanning {len(tickers)} stocks on `{tf_label}`...**")
        progress = st.progress(0)
        
        period_val, interval_val = ("2y", "1d")
        if timeframe == "1wk": period_val, interval_val = ("5y", "1wk")
        elif timeframe == "75m": period_val, interval_val = ("60d", "15m")
            
        data = yf.download(tickers, period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        alerts = []
        
        for idx, ticker in enumerate(tickers):
            progress.progress((idx + 1) / len(tickers))
            try:
                df = data.copy() if len(tickers) == 1 else data[ticker].copy()
                df = df.dropna()
                
                if timeframe == '75m': df = resample_custom(df, '75m')
                if len(df) < 30: continue
                
                res = scan_strict_zones(df, is_bullish)
                if res:
                    res['Asset'] = ticker.replace('.NS', '')
                    alerts.append(res)
            except Exception: pass
                
        progress.empty()
        st.divider()
        
        if alerts:
            st.success(f"Isolated {len(alerts)} setup(s) strictly trading inside the target zones.")
            df_out = pd.DataFrame(alerts)[['Asset', 'Setup', 'Live Price', 'Proximal (Entry)', 'Distal (SL)', 'Bases']]
            
            styled = df_out.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00F2FE; font-weight: 800;', subset=['Asset'])\
              .map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else 'color: #FF4500; font-weight: 800;', subset=['Setup'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error(f"0 Matches. The strict parameters (Leg-in -> Base -> Leg-out > 60% Body) returned no results trading inside the zone today.")
