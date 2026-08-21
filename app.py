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
st.set_page_config(page_title="Master Institutional Terminal", layout="wide")

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

st.markdown('<p class="gradient-text">MASTER INSTITUTIONAL TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">GTF Pullbacks | S/D Flips | RSI Divergence | Fast Batch Processing</p>', unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR CONTROLS
# ==========================================
with st.sidebar:
    st.markdown("### **1. STRATEGY ENGINE**")
    strategy = st.selectbox(
        "Select Trading Engine:",
        [
            "1. Pure GTF + 50 SMA (Pullback to Demand/Supply)",
            "2. Supply/Demand Flip (BOS Breaker)",
            "3. RSI Divergence (Regular & Hidden)"
        ]
    )
    
    st.divider()
    st.markdown("### **2. MARKET UNIVERSE (>₹5000 Cr)**")
    
    universe_choice = st.selectbox(
        "Choose Official NSE List:",
        [
            "Nifty 500 (Broad Market)", 
            "Nifty MidSmallcap 400", 
            "Nifty Smallcap 250",
            "Nifty Midcap 150",
            "Nifty 50",
            "Custom Tickers"
        ]
    )
    
    custom_pasted = ""
    if universe_choice == "Custom Tickers":
        custom_pasted = st.text_area("Paste Symbols (comma-separated):", "RELIANCE, TCS, HDFCBANK")
        
    st.divider()
    st.markdown("### **3. TIMEFRAME & VECTOR**")
    tf_options = {"1 Day": "1d", "1 Week": "1wk", "1 Month": "1mo", "3 Month": "3mo"}
    tf_label = st.selectbox("Resolution:", list(tf_options.keys()), index=0)
    timeframe = tf_options[tf_label]
    
    direction = st.radio("Market Bias:", ("🟢 Bullish (Demand / Long)", "🔴 Bearish (Supply / Short)"))
    is_bullish = "Bullish" in direction

# ==========================================
# 3. FAST UNIVERSE PARSER (NSE ARCHIVES)
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
            
    # Fallback in case NSE servers block the request
    return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "ITC.NS", "LT.NS"]

def get_target_tickers():
    if universe_choice == "Custom Tickers":
        return [f"{t.strip().upper()}.NS" if not t.strip().upper().endswith(".NS") else t.strip().upper() for t in custom_pasted.split(",") if t.strip()]
    else:
        return load_nse_list(universe_choice)

# ==========================================
# 4. MATHEMATICS & INDICATOR ENGINES
# ==========================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_candles(df):
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    conditions = [
        (df['Body_Pct'] > 50) & (df['Close'] > df['Open']),
        (df['Body_Pct'] > 50) & (df['Close'] < df['Open']),
        (df['Body_Pct'] <= 50)
    ]
    df['Candle_Type'] = np.select(conditions, ['Green Exciting', 'Red Exciting', 'Base'], default='Base')
    return df

def resample_custom_months(df, months):
    """Stitches 1-month candles into Quarterly (3-Month) blocks."""
    rule = f'{months}ME'
    return df.resample(rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

# --- ENGINE 1: PURE GTF + 50 SMA (PULLBACKS) ---
def run_gtf_sma_scan(df, is_bull):
    if len(df) < 55: return None
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df = analyze_candles(df)
    
    last_idx = len(df) - 1
    live_price = df['Close'].iloc[-1]
    sma = df['SMA_50'].iloc[-1]
    
    if pd.isna(sma): return None
    if is_bull and live_price <= sma: return None
    if not is_bull and live_price >= sma: return None
    
    for i in range(last_idx - 1, 1, -1):
        leg_out = df.iloc[i]
        expected = 'Green Exciting' if is_bull else 'Red Exciting'
        if leg_out['Candle_Type'] != expected: continue
        
        base_cnt = 0
        leg_in_idx = None
        for j in range(i-1, max(-1, i-5), -1):
            if df.iloc[j]['Candle_Type'] == 'Base': base_cnt += 1
            else:
                leg_in_idx = j
                break
                
        if base_cnt == 0 or base_cnt > 3 or leg_in_idx is None: continue
        bases = df.iloc[leg_in_idx+1 : i]
        
        if is_bull and leg_out['Close'] > bases['High'].max():
            prox = max(bases['Open'].max(), bases['Close'].max())
            dist = bases['Low'].min()
            future = df.iloc[i+1 : last_idx]
            if not future.empty and (future['Low'] <= prox).any(): break
            
            # Allow tight 1.5% buffer for entry
            if df.iloc[-1]['Low'] <= (prox * 1.015) and df.iloc[-1]['Close'] >= dist:
                return {"Setup": "GTF + 50 SMA Pullback", "Entry": round(prox, 2), "SL": round(dist, 2), "Price": round(live_price, 2), "Detail": f"{base_cnt} Base Candle(s)"}
                
        elif not is_bull and leg_out['Close'] < bases['Low'].min():
            prox = min(bases['Open'].min(), bases['Close'].min())
            dist = bases['High'].max()
            future = df.iloc[i+1 : last_idx]
            if not future.empty and (future['High'] >= prox).any(): break
            
            if df.iloc[-1]['High'] >= (prox * 0.985) and df.iloc[-1]['Close'] <= dist:
                return {"Setup": "GTF + 50 SMA Pullback", "Entry": round(prox, 2), "SL": round(dist, 2), "Price": round(live_price, 2), "Detail": f"{base_cnt} Base Candle(s)"}
    return None

# --- ENGINE 2: S/D FLIP (BREAKER) ---
def run_flip_scan(df, is_bull):
    if len(df) < 50: return None
    df = analyze_candles(df)
    last_idx = len(df) - 1
    live_price = df['Close'].iloc[-1]
    
    for i in range(last_idx - 1, 15, -1):
        leg_out = df.iloc[i]
        if is_bull and leg_out['Candle_Type'] == 'Green Exciting':
            base_cnt = 0
            leg_in_idx = None
            for j in range(i-1, max(-1, i-5), -1):
                if df.iloc[j]['Candle_Type'] == 'Base': base_cnt += 1
                else:
                    leg_in_idx = j
                    break
            if base_cnt == 0 or base_cnt > 3 or leg_in_idx is None: continue
            
            bases = df.iloc[leg_in_idx+1 : i]
            old_supply_high = df['High'].iloc[leg_in_idx-15 : leg_in_idx].max()
            
            if leg_out['Close'] > old_supply_high:
                prox = max(bases['Open'].max(), bases['Close'].max())
                dist = bases['Low'].min()
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['Low'] <= prox).any(): break
                if df.iloc[-1]['Low'] <= (prox * 1.02) and df.iloc[-1]['Close'] >= dist:
                    return {"Setup": "Demand Flip (BOS)", "Entry": round(prox, 2), "SL": round(dist, 2), "Price": round(live_price, 2), "Detail": f"Broke Supply ₹{round(old_supply_high,1)}"}
                    
        elif not is_bull and leg_out['Candle_Type'] == 'Red Exciting':
            base_cnt = 0
            leg_in_idx = None
            for j in range(i-1, max(-1, i-5), -1):
                if df.iloc[j]['Candle_Type'] == 'Base': base_cnt += 1
                else:
                    leg_in_idx = j
                    break
            if base_cnt == 0 or base_cnt > 3 or leg_in_idx is None: continue
            
            bases = df.iloc[leg_in_idx+1 : i]
            old_demand_low = df['Low'].iloc[leg_in_idx-15 : leg_in_idx].min()
            
            if leg_out['Close'] < old_demand_low:
                prox = min(bases['Open'].min(), bases['Close'].min())
                dist = bases['High'].max()
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['High'] >= prox).any(): break
                if df.iloc[-1]['High'] >= (prox * 0.98) and df.iloc[-1]['Close'] <= dist:
                    return {"Setup": "Supply Flip (BOS)", "Entry": round(prox, 2), "SL": round(dist, 2), "Price": round(live_price, 2), "Detail": f"Broke Demand ₹{round(old_demand_low,1)}"}
    return None

# --- ENGINE 3: RSI DIVERGENCE ---
def run_rsi_divergence_scan(df, is_bull):
    if len(df) < 40: return None
    df['RSI'] = calculate_rsi(df['Close'], 14)
    live_price = df['Close'].iloc[-1]
    
    recent_p_low = df['Low'].iloc[-15:].min()
    prior_p_low = df['Low'].iloc[-30:-15].min()
    recent_rsi_low = df['RSI'].iloc[-15:].min()
    prior_rsi_low = df['RSI'].iloc[-30:-15].min()
    
    recent_p_high = df['High'].iloc[-15:].max()
    prior_p_high = df['High'].iloc[-30:-15].max()
    recent_rsi_high = df['RSI'].iloc[-15:].max()
    prior_rsi_high = df['RSI'].iloc[-30:-15].max()
    
    if is_bull:
        if recent_p_low < prior_p_low and recent_rsi_low > prior_rsi_low:
            return {"Setup": "Regular Bullish DVG", "Entry": round(live_price, 2), "SL": round(recent_p_low * 0.99, 2), "Price": round(live_price, 2), "Detail": f"RSI: {round(recent_rsi_low,1)} > {round(prior_rsi_low,1)}"}
        elif recent_p_low > prior_p_low and recent_rsi_low < prior_rsi_low:
            return {"Setup": "Hidden Bullish DVG", "Entry": round(live_price, 2), "SL": round(recent_p_low * 0.99, 2), "Price": round(live_price, 2), "Detail": f"RSI: {round(recent_rsi_low,1)} < {round(prior_rsi_low,1)}"}
    else:
        if recent_p_high > prior_p_high and recent_rsi_high < prior_rsi_high:
            return {"Setup": "Regular Bearish DVG", "Entry": round(live_price, 2), "SL": round(recent_p_high * 1.01, 2), "Price": round(live_price, 2), "Detail": f"RSI: {round(recent_rsi_high,1)} < {round(prior_rsi_high,1)}"}
        elif recent_p_high < prior_p_high and recent_rsi_high > prior_rsi_high:
            return {"Setup": "Hidden Bearish DVG", "Entry": round(live_price, 2), "SL": round(recent_p_high * 1.01, 2), "Price": round(live_price, 2), "Detail": f"RSI: {round(recent_rsi_high,1)} > {round(prior_rsi_high,1)}"}
            
    return None

# ==========================================
# 5. EXECUTION PIPELINE
# ==========================================
if st.button("🔥 EXECUTE MASTER SCANNER", type="primary"):
    tickers = get_target_tickers()
    
    if not tickers:
        st.error("No symbols found. Please select a valid universe.")
    else:
        st.write(f"**Scanning {len(tickers)} stocks on `{tf_label}` using `{strategy}`...**")
        progress_bar = st.progress(0)
        
        # Optimize data limits
        if timeframe in ["1mo", "3mo"]: 
            period, interval_val = "max", "1mo"
        elif timeframe == "1wk": 
            period, interval_val = "10y", "1wk"
        else: 
            period, interval_val = "3y", "1d"
            
        market_data = yf.download(tickers, period=period, interval=interval_val, group_by='ticker', threads=True, progress=False)
        
        alerts = []
        for idx, ticker in enumerate(tickers):
            progress_bar.progress((idx + 1) / len(tickers))
            try:
                df = market_data.copy() if len(tickers) == 1 else market_data[ticker].copy()
                df = df.dropna()
                if len(df) < 30: continue
                
                # Apply Custom 3 Month Resampling if needed
                if timeframe == '3mo': 
                    df = resample_custom_months(df, 3)
                
                res = None
                if "1." in strategy:
                    res = run_gtf_sma_scan(df, is_bullish)
                elif "2." in strategy:
                    res = run_flip_scan(df, is_bullish)
                elif "3." in strategy:
                    res = run_rsi_divergence_scan(df, is_bullish)
                    
                if res:
                    res['Asset'] = ticker.replace('.NS', '')
                    alerts.append(res)
            except Exception:
                continue
                
        progress_bar.empty()
        st.divider()
        
        if alerts:
            st.success(f"Isolated {len(alerts)} setup(s) matching your strict institutional parameters.")
            out_df = pd.DataFrame(alerts)[['Asset', 'Setup', 'Price', 'Entry', 'SL', 'Detail']]
            
            styled = out_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00F2FE; font-weight: 800;', subset=['Asset'])\
              .map(lambda v: 'color: #00FF00; font-weight: 800;' if 'Bull' in str(v) or 'Demand' in str(v) or 'GTF' in str(v) else 'color: #FF4500; font-weight: 800;', subset=['Setup'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Detail'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 Matches Found. Market structure does not currently align with this engine's strict parameters.")
