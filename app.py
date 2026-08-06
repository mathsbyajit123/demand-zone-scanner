import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. STREAMLIT UI & SETTINGS
# ==========================================
st.set_page_config(page_title="Strict S&D Trend Scanner", layout="wide")
st.title("🎯 Strict 1-Base S&D + Trend Alignment Scanner")
st.markdown("Mathematically locked to exactly 1 base candle and strict leg-out rules, now featuring macro trend alignment (44/200 EMA).")

st.sidebar.header("⚙️ Market Settings")
sector_options = [
    "Nifty 50",
    "Nifty 500",
    "Nifty Midcap 100",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Auto"
]
selected_sector = st.sidebar.selectbox("Select Sector / Index", sector_options, index=1)

timeframe_options = {
    "1 Day": "1d",
    "75 Minutes (Intraday)": "75m",
    "1 Week": "1wk",
    "1 Month": "1mo"
}
selected_tf_label = st.sidebar.selectbox("Timeframe", list(timeframe_options.keys()))
timeframe = timeframe_options[selected_tf_label]

st.sidebar.header("🎯 Trade Setup")
direction = st.sidebar.radio(
    "Select Setup Direction",
    ("🟢 Bullish (Demand: RBR, DBR)", "🔴 Bearish (Supply: RBD, DBD)")
)

st.sidebar.header("📈 Macro Trend Filter")
strict_trend = st.sidebar.checkbox(
    "✅ Require Strict Trend Alignment", 
    value=True, 
    help="Bullish: Live Price > 44 EMA > 200 EMA. Bearish: Live Price < 44 EMA < 200 EMA."
)

st.sidebar.header("📐 Base Settings")
base_body_pct = st.sidebar.slider("Max Base Candle Body %", min_value=10, max_value=80, value=45, help="Body size relative to total high-to-low range.")

st.sidebar.header("📍 Entry & Confluence")
proximity_filter = st.sidebar.radio(
    "Where is the Live Price?",
    (
        "Any (In Zone or Near Zone)",
        "Strictly IN Zone",
        "Strictly NEAR Zone (Approaching)"
    )
)

hitbox_buffer = st.sidebar.slider("Near Zone Buffer %", min_value=0.0, max_value=5.0, value=2.0, step=0.5)

ema_filter = st.sidebar.radio(
    "Require EMA Confluence at Zone?",
    ("None (Pure Price Action)", "Near 44 EMA", "Near 200 EMA"),
    help="Ensures the chosen EMA is physically passing through or sitting right next to the zone entry."
)

# ==========================================
# 2. DATA FETCHER
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    csv_file = {
        "Nifty 50": "ind_nifty50list.csv",
        "Nifty 500": "ind_nifty500list.csv",
        "Nifty Midcap 100": "ind_niftymidcap100list.csv",
        "Nifty Bank": "ind_niftybanklist.csv",
        "Nifty IT": "ind_niftyitlist.csv",
        "Nifty Auto": "ind_niftyautolist.csv"
    }.get(sector_name, "ind_nifty500list.csv")
    
    mirrors = [
        f"https://raw.githubusercontent.com/althk/zerobha/main/{csv_file}",
        f"https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/{csv_file}",
        f"https://raw.githubusercontent.com/faizanahemad/data-science-utils/master/data_science_utils/financial/{csv_file}"
    ]
    
    for url in mirrors:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                symbol_col = next((col for col in df.columns if 'Symbol' in col or 'SYMBOL' in col), None)
                if symbol_col:
                    return [str(s).strip() + ".NS" for s in df[symbol_col]]
        except Exception:
            continue
            
    st.sidebar.error("⚠️ Unable to fetch ticker list.")
    return []

# ==========================================
# 3. CORE LOGIC
# ==========================================
def resample_to_75m(df):
    resampled = df.resample('75min', offset='15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    return resampled

def check_setup(df, dir_choice, prox_choice, body_pct, buffer_pct, ema_choice, require_trend):
    df = df[['Open', 'High', 'Low', 'Close']].dropna()
    if len(df) < 200: return None # Need 200 for EMAs
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    is_bullish = "Bullish" in dir_choice
    current = df.iloc[-1]
    
    # 0. STRICT MACRO TREND CHECK (GATEKEEPER)
    if require_trend:
        if is_bullish:
            if not (current['Close'] > current['EMA_44'] and current['EMA_44'] > current['EMA_200']):
                return None
        else:
            if not (current['Close'] < current['EMA_44'] and current['EMA_44'] < current['EMA_200']):
                return None
    
    target_zones = []
    
    # 1. STRICT 1-BASE PATTERN SCAN
    # Must stop at len-3 to safely check leg_in(i-1), base(i), leg1(i+1), leg2(i+2)
    for i in range(1, len(df) - 3):
        leg_in_idx = i - 1
        base_idx = i
        leg1_idx = i + 1
        leg2_idx = i + 2
        
        # A. LEG-IN
        leg_in_green = df['Close'].iloc[leg_in_idx] > df['Open'].iloc[leg_in_idx]
        leg_in_type = "R" if leg_in_green else "D" 
        
        # B. BASE CANDLE (Exactly 1)
        base_range = df['Range'].iloc[base_idx]
        if base_range == 0: continue
        
        candle_body_pct = (df['Body'].iloc[base_idx] / base_range) * 100
        if candle_body_pct > body_pct: continue # Reject if body is too big
            
        base_high = df['High'].iloc[base_idx]
        base_low = df['Low'].iloc[base_idx]
        
        # C. LEG-OUT LOGIC
        leg1_range = df['Range'].iloc[leg1_idx]
        leg1_body_pct = (df['Body'].iloc[leg1_idx] / leg1_range) * 100 if leg1_range > 0 else 0
        leg1_green = df['Close'].iloc[leg1_idx] > df['Open'].iloc[leg1_idx]
        
        leg2_range = df['Range'].iloc[leg2_idx]
        leg2_body_pct = (df['Body'].iloc[leg2_idx] / leg2_range) * 100 if leg2_range > 0 else 0
        leg2_green = df['Close'].iloc[leg2_idx] > df['Open'].iloc[leg2_idx]
        
        # Define strict momentum rules
        leg1_strong = leg1_body_pct >= 50
        leg2_strong = leg2_body_pct >= 50
        
        # 1 Massive Leg Rule: Body is 60%+ of range, and candle is 1.5x bigger than base
        leg1_massive = (leg1_body_pct >= 60) and (leg1_range >= (base_range * 1.5))
        
        if is_bullish:
            # DEMAND: Breakout must be green and close strictly above base high
            if leg1_green and (df['Close'].iloc[leg1_idx] > base_high):
                
                # 2 Strong Legs Rule: Both green, both strong, leg 2 closes higher than leg 1
                two_strong = leg1_strong and leg2_green and leg2_strong and (df['Close'].iloc[leg2_idx] > df['Close'].iloc[leg1_idx])
                
                if leg1_massive or two_strong:
                    target_zones.append({
                        'pattern': f"{leg_in_type}BR",
                        'proximal': base_high, 
                        'distal': base_low, 
                        'index': leg2_idx if two_strong else leg1_idx
                    })
        else:
            # SUPPLY: Breakdown must be red and close strictly below base low
            if not leg1_green and (df['Close'].iloc[leg1_idx] < base_low):
                
                # 2 Strong Legs Rule: Both red, both strong, leg 2 closes lower than leg 1
                two_strong = leg1_strong and not leg2_green and leg2_strong and (df['Close'].iloc[leg2_idx] < df['Close'].iloc[leg1_idx])
                
                if leg1_massive or two_strong:
                    target_zones.append({
                        'pattern': f"{leg_in_type}BD",
                        'proximal': base_low, 
                        'distal': base_high, 
                        'index': leg2_idx if two_strong else leg1_idx
                    })

    # 2. VALIDATE ZONES (Reject Broken Zones)
    valid_zones = []
    for z in target_zones:
        future_data = df.iloc[z['index']+1 : -1] 
        if len(future_data) == 0:
            valid_zones.append(z)
        else:
            if is_bullish:
                if not (future_data['Close'] < z['distal']).any(): valid_zones.append(z)
            else:
                if not (future_data['Close'] > z['distal']).any(): valid_zones.append(z)

    if not valid_zones: return None
    
    # 3. LIVE PRICE PROXIMITY & EMA CONFLUENCE LOGIC
    buffer_mult_bull = 1 + (buffer_pct / 100)
    buffer_mult_bear = 1 - (buffer_pct / 100)
    
    for z in reversed(valid_zones): 
        is_in_zone = False
        is_near = False
        ema_passed = True
        
        # PROXIMITY
        if is_bullish:
            if current['Close'] < z['distal']: continue # Zone broken today
            is_in_zone = (current['Low'] <= z['proximal']) and (current['Close'] >= z['distal'])
            is_near = (current['Low'] > z['proximal']) and (current['Low'] <= (z['proximal'] * buffer_mult_bull))
        else:
            if current['Close'] > z['distal']: continue # Zone broken today
            is_in_zone = (current['High'] >= z['proximal']) and (current['Close'] <= z['distal'])
            is_near = (current['High'] < z['proximal']) and (current['High'] >= (z['proximal'] * buffer_mult_bear))

        # APPLY USER PROXIMITY FILTER
        if "Strictly IN Zone" in prox_choice and not is_in_zone: continue
        if "Strictly NEAR Zone" in prox_choice and not is_near: continue
        if "Any" in prox_choice and not (is_in_zone or is_near): continue

        # CONFLUENCE EMA LOGIC
        if ema_choice != "None (Pure Price Action)":
            ema_val = current['EMA_44'] if "44" in ema_choice else current['EMA_200']
            # EMA must be within 3% of the entry line
            if abs(ema_val - z['proximal']) / z['proximal'] > 0.03: 
                ema_passed = False

        if ema_passed:
            risk_pct = (abs(z['proximal'] - z['distal']) / max(z['proximal'], 0.01)) * 100
            status = "✅ IN ZONE" if is_in_zone else f"⏳ NEAR ZONE (<{buffer_pct}%)"
            
            ema_str = "N/A"
            if "44" in ema_choice: ema_str = f"44 EMA: {current['EMA_44']:.2f}"
            if "200" in ema_choice: ema_str = f"200 EMA: {current['EMA_200']:.2f}"
            
            return {
                "Pattern": z['pattern'],
                "Live Price": round(current['Close'], 2),
                "Zone Entry": round(z['proximal'], 2),
                "Stop Loss": round(z['distal'], 2),
                "Risk %": f"{risk_pct:.2f}%",
                "EMA Data": ema_str,
                "Status": status
            }
            
    return None

# ==========================================
# 4. EXECUTION ENGINE
# ==========================================
if st.sidebar.button(f"Launch Scanner", type="primary"):
    with st.spinner(f"Fetching {selected_sector} list..."):
        ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        st.info(f"Loaded {len(ticker_list)} stocks. Hunting for strictly validated setups with Trend Filter = {strict_trend}...")
        
        if timeframe == '75m': fetch_period, fetch_interval = "60d", "15m"
        elif timeframe == '1d': fetch_period, fetch_interval = "2y", "1d"
        elif timeframe == '1wk': fetch_period, fetch_interval = "5y", "1wk"
        else: fetch_period, fetch_interval = "10y", "1mo"
        
        progress_bar = st.progress(0)
        results = []
        
        for i, ticker in enumerate(ticker_list):
            try:
                df = yf.Ticker(ticker).history(period=fetch_period, interval=fetch_interval)
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    setup = check_setup(df, direction, proximity_filter, base_body_pct, hitbox_buffer, ema_filter, strict_trend)
                    if setup:
                        setup['Ticker'] = ticker.replace(".NS", "")
                        results.append(setup)
            except: pass
            progress_bar.progress((i + 1) / len(ticker_list))
            
        progress_bar.empty()
        
        st.subheader(f"📊 Scan Results ({selected_tf_label})")
        if results:
            final_df = pd.DataFrame(results)[['Ticker', 'Pattern', 'Live Price', 'Zone Entry', 'Stop Loss', 'Risk %', 'EMA Data', 'Status']]
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.success(f"Results acquired. These strictly match the 1-Base rules and Trend Alignment.")
        else:
            st.warning(f"0 matches found. The strict trend filter and S&D rules eliminated all weak setups.")
