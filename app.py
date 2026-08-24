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
        font-weight: 900; font-size: 30px; letter-spacing: -1px;
        background: -webkit-linear-gradient(45deg, #00F2FE, #4FACFE, #F6D365);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px; text-transform: uppercase;
    }
    .sub-text { font-size: 14px; color: #64748B; margin-bottom: 25px; font-weight: 600;}
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #FF416C 0%, #FF4B2B 100%);
        color: white; border: none; border-radius: 6px;
        padding: 12px 24px; font-size: 16px; font-weight: 700; width: 100%; text-transform: uppercase;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="gradient-text">HEAVYWEIGHT GTF TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Strict Leg-In | Base | Leg-Out | Proximal/Distal Mapping</p>', unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR CONTROLS
# ==========================================
with st.sidebar:
    st.markdown("### **1. MARKET UNIVERSE**")
    universe_choice = st.selectbox(
        "Choose Stock List:",
        [
            "Upload CSV / Text File",
            "Nifty 500 (Pre-filtered >₹5000 Cr)",
            "Custom Tickers Paste"
        ]
    )
    
    uploaded_file = None
    custom_pasted = ""
    
    if universe_choice == "Upload CSV / Text File":
        st.info("Upload your CSV or TXT file with symbols.")
        uploaded_file = st.file_uploader("Upload File", type=["csv", "txt"])
    elif universe_choice == "Custom Tickers Paste":
        custom_pasted = st.text_area("Paste Symbols (comma-separated):", "RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK")
        
    st.divider()
    st.markdown("### **2. TIMEFRAME & BIAS**")
    tf_options = {"75 Min": "75m", "1 Day": "1d", "1 Week": "1wk", "1 Month": "1mo"}
    tf_label = st.selectbox("Resolution:", list(tf_options.keys()), index=1)
    timeframe = tf_options[tf_label]
    
    direction = st.radio("Target Zone:", ("🟢 Demand (Support)", "🔴 Supply (Resistance)"))
    is_bullish = "Demand" in direction

# ==========================================
# 3. UNIVERSE FETCHING & PARSING
# ==========================================
@st.cache_data(ttl=3600)
def load_nifty_500():
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            df = pd.read_csv(io.StringIO(res.text))
            return [f"{s.strip()}.NS" for s in df['Symbol']]
    except Exception:
        pass
    return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "LT.NS"]

def get_target_tickers():
    if universe_choice == "Custom Tickers Paste":
        return [f"{t.strip().upper()}.NS" if not t.strip().upper().endswith(".NS") else t.strip().upper() for t in custom_pasted.split(",") if t.strip()]
    
    elif universe_choice == "Upload CSV / Text File" and uploaded_file is not None:
        try:
            # Handle multi-encoding support (UTF-8, Latin1, CP1252)
            bytes_data = uploaded_file.getvalue()
            for encoding in ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']:
                try:
                    user_df = pd.read_csv(io.BytesIO(bytes_data), encoding=encoding)
                    break
                except Exception:
                    continue
            
            # Identify symbol column
            col = 'Symbol' if 'Symbol' in user_df.columns else user_df.columns[0]
            symbols = user_df[col].dropna().astype(str).str.strip().tolist()
            return [f"{s}.NS" if not s.endswith(".NS") else s for s in symbols if s]
        except Exception as e:
            st.error(f"Error reading uploaded file: {e}")
            return []
            
    else:
        return load_nifty_500()

# ==========================================
# 4. STRICT GTF CALCULATION ENGINE
# ==========================================
def analyze_structure(df):
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    cond = [
        (df['Body_Pct'] >= 60) & (df['Close'] > df['Open']),  # Leg-Out Green (>=60%)
        (df['Body_Pct'] >= 60) & (df['Close'] < df['Open']),  # Leg-Out Red (>=60%)
        (df['Body_Pct'] > 50) & (df['Close'] > df['Open']),   # Leg-In Green (>50%)
        (df['Body_Pct'] > 50) & (df['Close'] < df['Open']),   # Leg-In Red (>50%)
        (df['Body_Pct'] <= 50)                                # Base Candle (<=50%)
    ]
    df['Type'] = np.select(cond, ['Green Out', 'Red Out', 'Green In', 'Red In', 'Base'], default='Base')
    return df

def scan_strict_zones(df, is_bull):
    if len(df) < 30: 
        return None
    df = analyze_structure(df)
    last_idx = len(df) - 1
    live_price = float(df['Close'].iloc[-1])
    
    for i in range(last_idx - 1, 4, -1):
        leg_out = df.iloc[i]
        
        # 1. Check Leg-Out
        if is_bull and leg_out['Type'] != 'Green Out': 
            continue
        if not is_bull and leg_out['Type'] != 'Red Out': 
            continue
        
        # 2. Check Base (1 to 3 candles max)
        base_cnt = 0
        leg_in_idx = None
        
        for j in range(i-1, max(-1, i-5), -1):
            if df.iloc[j]['Type'] == 'Base':
                base_cnt += 1
            else:
                leg_in_idx = j
                break
                
        if base_cnt == 0 or base_cnt > 3 or leg_in_idx is None: 
            continue
        
        # 3. Check Leg-In
        leg_in = df.iloc[leg_in_idx]
        if leg_in['Type'] == 'Base': 
            continue 
        
        bases = df.iloc[leg_in_idx+1 : i]
        
        # 4. Map Proximal & Distal
        if is_bull:
            prox = float(max(bases['Open'].max(), bases['Close'].max()))
            dist = float(bases['Low'].min())
            
            if leg_out['Close'] > bases['High'].max():
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['Low'] <= prox).any(): 
                    break
                
                # Check if live price is strictly inside the zone
                if live_price <= prox and live_price >= dist:
                    return {
                        "Setup": "🟢 Demand Zone", 
                        "Live Price": round(live_price, 2), 
                        "Proximal (Entry)": round(prox, 2), 
                        "Distal (SL)": round(dist, 2), 
                        "Structure": f"Leg-In -> {base_cnt} Base -> Leg-Out"
                    }
        else:
            prox = float(min(bases['Open'].min(), bases['Close'].min()))
            dist = float(bases['High'].max())
            
            if leg_out['Close'] < bases['Low'].min():
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['High'] >= prox).any(): 
                    break
                
                # Check if live price is strictly inside the zone
                if live_price >= prox and live_price <= dist:
                    return {
                        "Setup": "🔴 Supply Zone", 
                        "Live Price": round(live_price, 2), 
                        "Proximal (Entry)": round(prox, 2), 
                        "Distal (SL)": round(dist, 2), 
                        "Structure": f"Leg-In -> {base_cnt} Base -> Leg-Out"
                    }
    return None

def resample_to_75m(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.resample('75min', offset='15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

# ==========================================
# 5. EXECUTION PIPELINE
# ==========================================
if st.button("🚀 SCAN LOADED UNIVERSE", type="primary"):
    tickers = get_target_tickers()
    if not tickers:
        st.warning("Please upload a file or specify tickers first.")
    else:
        st.write(f"**Scanning {len(tickers)} stocks on timeframe `{tf_label}`...**")
        progress = st.progress(0)
        
        # Determine appropriate download period
        if timeframe == "1mo": 
            period_val, interval_val = ("10y", "1mo")
        elif timeframe == "1wk": 
            period_val, interval_val = ("5y", "1wk")
        elif timeframe == "75m": 
            period_val, interval_val = ("60d", "15m")
        else: 
            period_val, interval_val = ("2y", "1d")
            
        data = yf.download(tickers, period=period_val, interval=interval_val, group_by='ticker', threads=True, progress=False)
        alerts = []
        
        for idx, ticker in enumerate(tickers):
            progress.progress((idx + 1) / len(tickers))
            try:
                df = data.copy() if len(tickers) == 1 else data[ticker].copy()
                df = df.dropna()
                
                if timeframe == '75m': 
                    df = resample_to_75m(df)
                if len(df) < 20: 
                    continue
                
                res = scan_strict_zones(df, is_bullish)
                if res:
                    res['Asset'] = ticker.replace('.NS', '')
                    alerts.append(res)
            except Exception:
                continue
                
        progress.empty()
        st.divider()
        
        if alerts:
            st.success(f"Isolated {len(alerts)} setup(s) strictly trading inside the zone today.")
            df_out = pd.DataFrame(alerts)[['Asset', 'Setup', 'Structure', 'Live Price', 'Proximal (Entry)', 'Distal (SL)']]
            
            styled = df_out.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00F2FE; font-weight: 800;', subset=['Asset'])\
              .map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else 'color: #FF4500; font-weight: 800;', subset=['Setup'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info("0 Matches. No stocks from your list are currently trading strictly inside an active, untested zone on this timeframe.")
