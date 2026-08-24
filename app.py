import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import io
import requests
import time

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

st.markdown('<p class="gradient-text">STEALTH GTF TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Anti-429 Rate Limit Protocol | Strict Breakout Math</p>', unsafe_allow_html=True)

# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **1. MARKET UNIVERSE**")
    universe_choice = st.selectbox(
        "Choose Stock List:",
        [
            "Upload CSV / Text File (No Limits)",
            "Nifty 500 (Pre-filtered >₹5000 Cr)",
            "Custom Tickers Paste"
        ]
    )
    
    uploaded_file = None
    custom_pasted = ""
    
    if universe_choice == "Upload CSV / Text File (No Limits)":
        uploaded_file = st.file_uploader("Upload File", type=["csv", "txt"])
    elif universe_choice == "Custom Tickers Paste":
        custom_pasted = st.text_area("Paste Symbols (comma-separated):", "RELIANCE, TCS")
        
    st.divider()
    st.markdown("### **2. TIMEFRAME & BIAS**")
    tf_options = {"75 Min": "75m", "1 Day": "1d", "1 Week": "1wk", "1 Month": "1mo"}
    tf_label = st.selectbox("Resolution:", list(tf_options.keys()), index=1)
    timeframe = tf_options[tf_label]
    direction = st.radio("Target Zone:", ("🟢 Demand (Support)", "🔴 Supply (Resistance)"))
    is_bullish = "Demand" in direction

    st.divider()
    st.markdown("### **3. MATH TOLERANCES**")
    base_max = st.slider("Max Base Body %", 40, 65, 50, 1)
    leg_min = st.slider("Min Leg-Out Body %", 45, 80, 60, 1)
    entry_buffer = st.slider("Entry Zone Buffer %", 0.0, 5.0, 0.5, 0.1)

# ==========================================
# 3. UNIVERSE FETCHING (STRICT FILE CHECK)
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
    except Exception: pass
    return ["RELIANCE.NS", "TCS.NS"]

def get_target_tickers():
    if universe_choice == "Custom Tickers Paste":
        return [f"{t.strip().upper()}.NS" if not t.strip().upper().endswith(".NS") else t.strip().upper() for t in custom_pasted.split(",") if t.strip()]
    
    elif universe_choice == "Upload CSV / Text File (No Limits)":
        if uploaded_file is None:
            st.error("File is missing! Streamlit dropped it. Please re-upload before clicking scan.")
            return []
        
        try:
            bytes_data = uploaded_file.getvalue()
            for encoding in ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']:
                try:
                    user_df = pd.read_csv(io.BytesIO(bytes_data), encoding=encoding)
                    break
                except Exception: continue
            col = 'Symbol' if 'Symbol' in user_df.columns else user_df.columns[0]
            symbols = user_df[col].dropna().astype(str).str.strip().tolist()
            return [f"{s}.NS" if not s.endswith(".NS") else s for s in symbols if s]
        except Exception as e:
            st.error(f"Failed to read file: {e}")
            return []
            
    else:
        return load_nifty_500()

# ==========================================
# 4. DYNAMIC GTF CALCULATION ENGINE
# ==========================================
def analyze_structure(df, base_limit, leg_limit):
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    cond = [
        (df['Body_Pct'] >= leg_limit) & (df['Close'] > df['Open']),  
        (df['Body_Pct'] >= leg_limit) & (df['Close'] < df['Open']),  
        (df['Body_Pct'] > base_limit) & (df['Close'] > df['Open']),   
        (df['Body_Pct'] > base_limit) & (df['Close'] < df['Open']),   
        (df['Body_Pct'] <= base_limit)                                
    ]
    df['Type'] = np.select(cond, ['Green Out', 'Red Out', 'Green In', 'Red In', 'Base'], default='Base')
    return df

def scan_dynamic_zones(df, is_bull, base_limit, leg_limit, buffer):
    if len(df) < 30: return None
    df = analyze_structure(df, base_limit, leg_limit)
    last_idx = len(df) - 1
    live_price = float(df['Close'].iloc[-1])
    
    for i in range(last_idx - 1, 4, -1):
        leg_out = df.iloc[i]
        
        if is_bull and leg_out['Type'] != 'Green Out': continue
        if not is_bull and leg_out['Type'] != 'Red Out': continue
        
        base_cnt = 0
        leg_in_idx = None
        for j in range(i-1, max(-1, i-5), -1):
            if df.iloc[j]['Type'] == 'Base': base_cnt += 1
            else:
                leg_in_idx = j
                break
                
        if base_cnt == 0 or base_cnt > 3 or leg_in_idx is None: continue
        
        leg_in = df.iloc[leg_in_idx]
        if leg_in['Type'] == 'Base': continue 
        
        bases = df.iloc[leg_in_idx+1 : i]
        
        if is_bull:
            prox = float(max(bases['Open'].max(), bases['Close'].max()))
            dist = float(bases['Low'].min())
            
            if leg_out['Close'] > bases['High'].max():
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['Low'] <= prox).any(): break
                
                adjusted_prox = prox * (1 + (buffer / 100))
                if live_price <= adjusted_prox and live_price >= dist:
                    return {"Setup": "🟢 Demand Zone", "Live Price": round(live_price, 2), "Proximal": round(prox, 2), "Distal": round(dist, 2), "Structure": f"{base_cnt} Base"}
        else:
            prox = float(min(bases['Open'].min(), bases['Close'].min()))
            dist = float(bases['High'].max())
            
            if leg_out['Close'] < bases['Low'].min():
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['High'] >= prox).any(): break
                
                adjusted_prox = prox * (1 - (buffer / 100))
                if live_price >= adjusted_prox and live_price <= dist:
                    return {"Setup": "🔴 Supply Zone", "Live Price": round(live_price, 2), "Proximal": round(prox, 2), "Distal": round(dist, 2), "Structure": f"{base_cnt} Base"}
    return None

def resample_to_75m(df):
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return df.resample('75min', offset='15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

# ==========================================
# 5. EXECUTION (ANTI-429 BATCHING)
# ==========================================
if st.button("🚀 SCAN LOADED UNIVERSE", type="primary"):
    tickers = get_target_tickers()
    if not tickers:
        st.warning("Action halted: No valid tickers found to scan.")
    else:
        st.write(f"**Scanning {len(tickers)} stocks on `{tf_label}`... This will take a moment to avoid server bans.**")
        progress = st.progress(0)
        
        if timeframe == "1mo": period_val, interval_val = ("10y", "1mo")
        elif timeframe == "1wk": period_val, interval_val = ("5y", "1wk")
        elif timeframe == "75m": period_val, interval_val = ("60d", "15m")
        else: period_val, interval_val = ("2y", "1d")
        
        alerts = []
        
        # STEALTH DOWNLOADING: Tiny batches, single-threaded, with pauses
        batch_size = 20  # Reduced to 20 to stay under Yahoo's radar
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            
            # threads=False prevents hitting the server concurrently
            data = yf.download(batch, period=period_val, interval=interval_val, group_by='ticker', threads=False, progress=False)
            
            for ticker in batch:
                try:
                    df = data.copy() if len(batch) == 1 else data[ticker].copy()
                    df = df.dropna()
                    
                    if timeframe == '75m': df = resample_to_75m(df)
                    if len(df) < 20: continue
                    
                    res = scan_dynamic_zones(df, is_bullish, base_max, leg_min, entry_buffer)
                    if res:
                        res['Asset'] = ticker.replace('.NS', '')
                        alerts.append(res)
                except Exception: continue
                
            # Update progress bar
            current_progress = min((i + batch_size) / len(tickers), 1.0)
            progress.progress(current_progress)
            
            # MANDATORY PAUSE: Sleep for 1 second between batches to clear the rate limit
            time.sleep(1)
                
        progress.empty()
        st.divider()
        
        if alerts:
            st.success(f"Isolated {len(alerts)} setup(s).")
            df_out = pd.DataFrame(alerts)[['Asset', 'Setup', 'Structure', 'Live Price', 'Proximal', 'Distal']]
            styled = df_out.style.set_properties(**{'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'})\
              .map(lambda v: 'color: #00F2FE; font-weight: 800;', subset=['Asset'])\
              .map(lambda v: 'color: #00FF00; font-weight: 800;' if '🟢' in str(v) else 'color: #FF4500; font-weight: 800;', subset=['Setup'])
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info("0 Matches found. Adjust the tolerances in the sidebar if manual setups are being missed.")
