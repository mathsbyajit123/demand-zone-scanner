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
st.set_page_config(page_title="Strict Price Action Terminal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #090B10; color: #E2E8F0; }
    .gradient-text {
        font-weight: 900; font-size: 32px; letter-spacing: -1px;
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

st.markdown('<p class="gradient-text">STRICT GTF & RSI TERMINAL</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Live Price Must Be INSIDE The Zone | No Buffers | No Fake Setups</p>', unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR CONTROLS
# ==========================================
with st.sidebar:
    st.markdown("### **1. STRATEGY ENGINE**")
    strategy = st.selectbox(
        "Select Trading Engine:",
        [
            "1. Pure GTF Demand/Supply",
            "2. Supply/Demand Flip (Breaker)",
            "3. True Pivot RSI Divergence"
        ]
    )
    
    st.divider()
    st.markdown("### **2. MARKET UNIVERSE (>₹5000 Cr)**")
    universe_choice = st.selectbox(
        "Choose NSE List:",
        [
            "Nifty 500 (Broad Market)", 
            "Nifty MidSmallcap 400", 
            "Nifty 50",
            "Custom Tickers"
        ]
    )
    
    custom_pasted = ""
    if universe_choice == "Custom Tickers":
        custom_pasted = st.text_area("Paste Symbols (comma-separated):", "RELIANCE, TCS, HDFCBANK")
        
    st.divider()
    st.markdown("### **3. TIMEFRAME & BIAS**")
    tf_options = {
        "75 Min": "75m", 
        "1 Day": "1d", 
        "1 Week": "1wk", 
        "1 Month": "1mo"
    }
    tf_label = st.selectbox("Resolution:", list(tf_options.keys()), index=1)
    timeframe = tf_options[tf_label]
    
    direction = st.radio("Market Bias:", ("🟢 Bullish (Demand/Long)", "🔴 Bearish (Supply/Short)"))
    is_bullish = "Bullish" in direction

# ==========================================
# 3. ROBUST UNIVERSE PARSER (NSE ARCHIVES)
# ==========================================
@st.cache_data(ttl=3600)
def load_nse_list(index_name):
    urls = {
        "Nifty 500 (Broad Market)": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "Nifty MidSmallcap 400": "https://archives.nseindia.com/content/indices/ind_niftymidsmallcap400list.csv",
        "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
    }
    
    url = urls.get(index_name)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    if url:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                df = pd.read_csv(io.StringIO(res.text))
                return [f"{s.strip()}.NS" for s in df['Symbol']]
        except Exception:
            pass
            
    # Hard fallback to top liquid stocks if NSE API blocks
    return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "HINDUNILVR.NS", "BAJFINANCE.NS", "AXISBANK.NS", "MARUTI.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "KOTAKBANK.NS"]

def get_target_tickers():
    if universe_choice == "Custom Tickers":
        return [f"{t.strip().upper()}.NS" if not t.strip().upper().endswith(".NS") else t.strip().upper() for t in custom_pasted.split(",") if t.strip()]
    else:
        return load_nse_list(universe_choice)

# ==========================================
# 4. STRICT MATH & RESAMPLING ENGINES
# ==========================================
def resample_custom(df, tf_rule):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.resample(tf_rule, offset='15min' if tf_rule=='75min' else None).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

def analyze_candles_strict(df):
    """
    STRICT GTF LOGIC: 
    Base candles must be strictly <= 50% body.
    Exciting Leg-Outs must be >= 60% body to filter out fake breakouts.
    """
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Body_Pct'] = np.where(df['Range'] == 0, 0, (df['Body'] / df['Range']) * 100)
    
    conditions = [
        (df['Body_Pct'] >= 60) & (df['Close'] > df['Open']),  # Strong Green ERC
        (df['Body_Pct'] >= 60) & (df['Close'] < df['Open']),  # Strong Red ERC
        (df['Body_Pct'] <= 50)                                # Strict Base
    ]
    df['Candle_Type'] = np.select(conditions, ['Green Exciting', 'Red Exciting', 'Base'], default='Ignored')
    return df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- ENGINE 1: PURE GTF (STRICT INSIDE ZONE) ---
def run_pure_gtf_scan(df, is_bull):
    if len(df) < 30: return None
    df = analyze_candles_strict(df)
    
    last_idx = len(df) - 1
    live_price = float(df['Close'].iloc[-1])
    
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
            prox = float(max(bases['Open'].max(), bases['Close'].max()))
            dist = float(bases['Low'].min())
            
            # Freshness test: Zone must not have been tested between breakout and yesterday
            future = df.iloc[i+1 : last_idx]
            if not future.empty and (future['Low'] <= prox).any(): break
            
            # STRICT CHECK: Live Price must be physically INSIDE the zone right now
            if live_price <= prox and live_price >= dist:
                return {"Setup": "🟢 Trading IN Demand", "Entry": round(prox, 2), "SL": round(dist, 2), "Price": round(live_price, 2), "Detail": f"{base_cnt} Base Candle(s)"}
                
        elif not is_bull and leg_out['Close'] < bases['Low'].min():
            prox = float(min(bases['Open'].min(), bases['Close'].min()))
            dist = float(bases['High'].max())
            
            # Freshness test
            future = df.iloc[i+1 : last_idx]
            if not future.empty and (future['High'] >= prox).any(): break
            
            # STRICT CHECK: Live Price must be physically INSIDE the zone right now
            if live_price >= prox and live_price <= dist:
                return {"Setup": "🔴 Trading IN Supply", "Entry": round(prox, 2), "SL": round(dist, 2), "Price": round(live_price, 2), "Detail": f"{base_cnt} Base Candle(s)"}
    return None

# --- ENGINE 2: S/D FLIPS (STRICT INSIDE ZONE) ---
def run_flip_scan(df, is_bull):
    if len(df) < 50: return None
    df = analyze_candles_strict(df)
    last_idx = len(df) - 1
    live_price = float(df['Close'].iloc[-1])
    
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
            old_supply_high = float(df['High'].iloc[max(0, leg_in_idx-15) : leg_in_idx].max())
            
            if leg_out['Close'] > old_supply_high:
                prox = float(max(bases['Open'].max(), bases['Close'].max()))
                dist = float(bases['Low'].min())
                
                # Freshness test
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['Low'] <= prox).any(): break
                
                # STRICT CHECK: Live Price must be physically INSIDE the zone right now
                if live_price <= prox and live_price >= dist:
                    return {"Setup": "🟢 Trading IN Demand Flip", "Entry": round(prox, 2), "SL": round(dist, 2), "Price": round(live_price, 2), "Detail": f"Broke Supply ₹{round(old_supply_high,1)}"}
                    
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
            old_demand_low = float(df['Low'].iloc[max(0, leg_in_idx-15) : leg_in_idx].min())
            
            if leg_out['Close'] < old_demand_low:
                prox = float(min(bases['Open'].min(), bases['Close'].min()))
                dist = float(bases['High'].max())
                
                # Freshness test
                future = df.iloc[i+1 : last_idx]
                if not future.empty and (future['High'] >= prox).any(): break
                
                # STRICT CHECK: Live Price must be physically INSIDE the zone right now
                if live_price >= prox and live_price <= dist:
                    return {"Setup": "🔴 Trading IN Supply Flip", "Entry": round(prox, 2), "SL": round(dist, 2), "Price": round(live_price, 2), "Detail": f"Broke Demand ₹{round(old_demand_low,1)}"}
    return None

# --- ENGINE 3: TRUE PIVOT RSI DIVERGENCE ---
def run_rsi_divergence_scan(df, is_bull):
    if len(df) < 50: return None
    
    df['RSI'] = calculate_rsi(df['Close'], 14)
    live_price = float(df['Close'].iloc[-1])
    pivot_window = 3
    
    if is_bull:
        df['Pivot_Low'] = df['Low'] == df['Low'].rolling(window=pivot_window*2+1, center=True).min()
        pivots = df[df['Pivot_Low']].copy()
        
        if len(pivots) < 2: return None
        p2, p1 = pivots.iloc[-1], pivots.iloc[-2]
        
        if (len(df) - df.index.get_loc(p2.name)) > 15: return None
        
        price_1, price_2 = float(p1['Low']), float(p2['Low'])
        rsi_1, rsi_2 = float(p1['RSI']), float(p2['RSI'])
        
        if price_2 < price_1 and rsi_2 > rsi_1:
            return {"Setup": "🟢 Regular Bullish DVG", "Entry": round(live_price, 2), "SL": round(price_2 * 0.99, 2), "Price": round(live_price, 2), "Detail": f"RSI {round(rsi_1,1)} ↗ {round(rsi_2,1)}"}
        elif price_2 > price_1 and rsi_2 < rsi_1:
            return {"Setup": "🟢 Hidden Bullish DVG", "Entry": round(live_price, 2), "SL": round(price_2 * 0.99, 2), "Price": round(live_price, 2), "Detail": f"RSI {round(rsi_1,1)} ↘ {round(rsi_2,1)}"}
            
    else:
        df['Pivot_High'] = df['High'] == df['High'].rolling(window=pivot_window*2+1, center=True).max()
        pivots = df[df['Pivot_High']].copy()
        
        if len(pivots) < 2: return None
        p2, p1 = pivots.iloc[-1], pivots.iloc[-2]
        
        if (len(df) - df.index.get_loc(p2.name)) > 15: return None
        
        price_1, price_2 = float(p1['High']), float(p2['High'])
        rsi_1, rsi_2 = float(p1['RSI']), float(p2['RSI'])
        
        if price_2 > price_1 and rsi_2 < rsi_1:
            return {"Setup": "🔴 Regular Bearish DVG", "Entry": round(live_price, 2), "SL": round(price_2 * 1.01, 2), "Price": round(live_price, 2), "Detail": f"RSI {round(rsi_1,1)} ↘ {round(rsi_2,1)}"}
        elif price_2 < price_1 and rsi_2 > rsi_1:
            return {"Setup": "🔴 Hidden Bearish DVG", "Entry": round(live_price, 2), "SL": round(price_2 * 1.01, 2), "Price": round(live_price, 2), "Detail": f"RSI {round(rsi_1,1)} ↗ {round(rsi_2,1)}"}
            
    return None

# ==========================================
# 5. EXECUTION PIPELINE
# ==========================================
if st.button("🚀 EXECUTE STRICT SCANNER", type="primary"):
    tickers = get_target_tickers()
    
    if not tickers:
        st.error("No symbols found. Please select a valid universe.")
    else:
        st.write(f"**Scanning {len(tickers)} stocks on `{tf_label}`...**")
        progress_bar = st.progress(0)
        
        if timeframe == "1mo": 
            period_val, interval_val = "10y", "1mo"
        elif timeframe == "1wk": 
            period_val, interval_val = "5y", "1wk"
        elif timeframe == "1d": 
            period_val, interval_val = "2y", "1d"
        elif timeframe == "75m":
            period_val, interval_val = "60d", "15m" 
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
                    df = resample_custom(df, '75min')
                    
                if len(df) < 40: continue
                
                res = None
                if "1." in strategy:
                    res = run_pure_gtf_scan(df, is_bullish)
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
            st.success(f"Isolated {len(alerts)} setup(s) strictly trading inside the target zones.")
            out_df = pd.DataFrame(alerts)[['Asset', 'Setup', 'Price', 'Entry', 'SL', 'Detail']]
            
            styled = out_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B', 'text-align': 'center'
            }).map(lambda v: 'color: #00F2FE; font-weight: 800;', subset=['Asset'])\
              .map(lambda v: 'color: #00FF00; font-weight: 800;' if 'Bull' in str(v) or 'Demand' in str(v) else 'color: #FF4500; font-weight: 800;', subset=['Setup'])\
              .map(lambda v: 'color: #F6D365; font-weight: 800;', subset=['Detail'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error(f"0 Matches Found. Market structure does not currently align with these strict parameters on {tf_label}. No stocks are currently trading perfectly inside an untested zone.")
