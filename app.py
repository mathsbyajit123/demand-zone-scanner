import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- PAGE CONFIGURATION & UI THEME ---
st.set_page_config(page_title="Institutional Sniper v2.0", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: 800; color: #00E676; margin-bottom: 0px; letter-spacing: 1px; }
    .sub-title { font-size: 16px; color: #90A4AE; margin-bottom: 30px; }
    .metric-card { background-color: #1E293B; padding: 15px; border-radius: 10px; border-left: 5px solid #00E676; }
    .stButton>button { border-radius: 8px; font-weight: 700; letter-spacing: 0.5px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">⚡ INSTITUTIONAL SNIPER ENGINE v2.0</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Advanced Order Block, Multi-Timeframe Multi-Segment Liquidity Scanner</p>', unsafe_allow_html=True)

# --- AUTOMATED SECTOR DATA LOADER ---
@st.cache_data(ttl=86400)
def load_all_nse_segments():
    segments = {}
    def format_tickers(url):
        try:
            df = pd.read_csv(url)
            return (df['Symbol'].astype(str).str.strip() + ".NS").tolist()
        except:
            return []

    segments["NIFTY 50 (Mega Cap)"] = format_tickers("https://archives.nseindia.com/content/indices/ind_nifty50list.csv")
    segments["NIFTY 100 (Large Cap)"] = format_tickers("https://archives.nseindia.com/content/indices/ind_nifty100list.csv")
    segments["NIFTY Midcap 100"] = format_tickers("https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv")
    segments["NIFTY Smallcap 250"] = format_tickers("https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv")
    segments["Full NIFTY 500"] = format_tickers("https://archives.nseindia.com/content/indices/ind_nifty500list.csv")
    
    fallback = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "TATAMOTORS.NS", "SBIN.NS", "ITC.NS"]
    for k in list(segments.keys()):
        if not segments[k]:
            segments[k] = fallback
            
    return segments

all_segments = load_all_nse_segments()

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.header("🎛️ Strategic Controls")
    market_segment = st.selectbox("🎯 Select Market Segment", list(all_segments.keys()))
    scan_range = st.radio("Scan Target Length", ["Full Segment Scan", "Quick Test (First 5 Stocks)"])
    
    st.divider()
    st.markdown("### 📈 Trading Profile Pre-sets")
    profile = st.selectbox("Choose Profile", ["Custom", "Intraday Trading", "Swing Trading", "Long-Term Investing"])
    
    if profile == "Intraday Trading":
        timeframe = st.selectbox("⏳ Timeframe", ["15m", "75m", "125m"])
    elif profile == "Swing Trading":
        timeframe = st.selectbox("⏳ Timeframe", ["1d", "1wk"])
    elif profile == "Long-Term Investing":
        timeframe = st.selectbox("⏳ Timeframe", ["1wk", "1mo", "3mo"])
    else:
        timeframe = st.selectbox("⏳ Timeframe", ["15m", "75m", "125m", "1d", "1wk", "1mo", "3mo"])
        
    zone_type = st.selectbox("📉 Order Type", ["Bullish Demand Zone", "Bearish Supply Zone"])
    
    st.divider()
    st.markdown("### 🎯 Zone State Filter")
    state_filter = st.selectbox("Filter by Zone Condition", [
        "All Valid Zones",
        "Just Approaching (Nearing Edge)",
        "In the Zone (2-3 Candles Formed)",
        "Unmitigated (100% Completely Fresh)"
    ])
    
    st.divider()
    st.markdown("### 🕯️ Advanced Candle Strictness")
    base_limit = st.slider("Max Base Candles Allowed", 1, 6, 4)
    min_legout = st.slider("Min Leg-Out Candles Required", 1, 4, 1)
    min_legout_size_pct = st.slider("Minimum Leg-Out Candle Body Size (%)", 51, 100, 55)

base_list = all_segments[market_segment]
symbols_to_scan = base_list[:5] if "Quick Test" in scan_range else base_list

# --- RESAMPLING ENGINE FOR 75M & 125M ---
def fetch_and_resample(ticker, tf):
    t = yf.Ticker(ticker)
    if tf == "15m":
        return t.history(period='60d', interval='15m', timeout=1.5)
    elif tf == "75m":
        raw = t.history(period='60d', interval='15m', timeout=1.5)
        if len(raw) < 5: return None
        raw['group'] = np.arange(len(raw)) // 5
        df = raw.groupby('group').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'})
        df.index = raw.index[::5][:len(df)]
        return df
    elif tf == "125m":
        raw = t.history(period='60d', interval='5m', timeout=1.5)
        if len(raw) < 25: return None
        raw['group'] = np.arange(len(raw)) // 25
        df = raw.groupby('group').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'})
        df.index = raw.index[::25][:len(df)]
        return df
    elif tf in ["1d", "1wk"]:
        return t.history(period='3y', interval=tf, timeout=1.5)
    else:
        return t.history(period='10y', interval=tf, timeout=1.5)

# --- CORE STRICT ALGORITHM ENGINE ---
def scan_zones(ticker, tf, mode, max_base, min_leg, min_size_threshold):
    try:
        df = fetch_and_resample(ticker, tf)
        if df is None or len(df) < 20: return None
        
        current_price = round(df['Close'].iloc[-1], 2)
        
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = df['High'] - df['Low']
        df['Range'] = np.where(df['Range'] == 0, 0.0001, df['Range'])
        
        df['Body_Pct'] = (df['Body'] / df['Range']) * 100.0
        
        df['Is_Base'] = df['Body_Pct'] < 50.0
        
        if mode == "Bullish Demand Zone":
            df['Is_Strong'] = (df['Close'] > df['Open']) & (df['Body_Pct'] >= float(min_size_threshold))
        else:
            df['Is_Strong'] = (df['Close'] < df['Open']) & (df['Body_Pct'] >= float(min_size_threshold))
            
        matches = []
        i = 1
        while i < len(df) - min_leg - 1:
            if df['Is_Base'].iloc[i]:
                base_start = i
                base_end = i
                
                while base_end + 1 < len(df) and df['Is_Base'].iloc[base_end + 1]:
                    base_end += 1
                
                base_count = base_end - base_start + 1
                
                if base_count <= max_base:
                    legout_start = base_end + 1
                    legout_count = 0
                    
                    while legout_start + legout_count < len(df) and df['Is_Strong'].iloc[legout_start + legout_count]:
                        actual_body_pct = df['Body_Pct'].iloc[legout_start + legout_count]
                        if actual_body_pct < min_size_threshold:
                            break 
                        legout_count += 1
                        
                    if legout_count >= min_leg:
                        future_data = df.iloc[legout_start + legout_count :]
                        
                        if mode == "Bullish Demand Zone":
                            z_ceil = round(max(df['Open'].iloc[base_start : base_end + 1].max(), df['Close'].iloc[base_start : base_end + 1].max()), 2)
                            z_floor = round(df['Low'].iloc[base_start : base_end + 1].min(), 2)
                            
                            if future_data.empty:
                                state = "Unmitigated 🟢"
                            else:
                                lowest_since = future_data['Low'].min()
                                if lowest_since < z_floor:
                                    state = "Mitigated 🔴"
                                elif lowest_since <= z_ceil:
                                    candles_in_zone = ((future_data['Low'] <= z_ceil) & (future_data['High'] >= z_floor)).sum()
                                    if 2 <= candles_in_zone <= 3:
                                        state = "In the Zone (2-3 Candles) 🟡"
                                    else:
                                        state = "Mitigated 🔴"
                                else:
                                    state = "Unmitigated 🟢"
                                    
                            if state == "Unmitigated 🟢" and (z_ceil < current_price <= z_ceil * 1.015):
                                proximity = "Just Approaching 🎯"
                            elif "In the Zone" in state:
                                proximity = "Inside Zone ⚡"
                            else:
                                proximity = "Normal"
                                
                        else: # Bearish Supply Zone
                            z_ceil = round(df['High'].iloc[base_start : base_end + 1].max(), 2)
                            z_floor = round(min(df['Open'].iloc[base_start : base_end + 1].min(), df['Close'].iloc[base_start : base_end + 1].min()), 2)
                            
                            if future_data.empty:
                                state = "Unmitigated 🟢"
                            else:
                                highest_since = future_data['High'].max()
                                if highest_since > z_ceil:
                                    state = "Mitigated 🔴"
                                elif highest_since >= z_floor:
                                    candles_in_zone = ((future_data['High'] >= z_floor) & (future_data['Low'] <= z_ceil)).sum()
                                    if 2 <= candles_in_zone <= 3:
                                        state = "In the Zone (2-3 Candles) 🟡"
                                    else:
                                        state = "Mitigated 🔴"
                                else:
                                    state = "Unmitigated 🟢"
                                    
                            if state == "Unmitigated 🟢" and (z_floor * 0.985 <= current_price < z_floor):
                                proximity = "Just Approaching 🎯"
                            elif "In the Zone" in state:
                                proximity = "Inside Zone ⚡"
                            else:
                                proximity = "Normal"

                        date_detected = df.index[legout_start].strftime('%Y-%m-%d %H:%M') if hasattr(df.index[legout_start], 'strftime') else str(df.index[legout_start])
                        first_legout_pct = df['Body_Pct'].iloc[legout_start]
                        
                        # NEW COLUMN ADDED HERE
                        matches.append({
                            "Ticker": ticker.replace('.NS', ''),
                            "Formation Date": date_detected,
                            "Leg-Out Count": legout_count,
                            "Leg-Out Strength": f"{round(first_legout_pct, 1)}%",
                            "Base": base_count,
                            "Proximal (Ceiling)": z_ceil,
                            "Distal (Floor)": z_floor,
                            "Current Price": current_price,
                            "Zone State": state,
                            "Live Alignment": proximity
                        })
                i = base_end + 1
            else:
                i += 1
        return matches
    except Exception:
        return None

# --- SCANNER RUNNER EXECUTION ---
if st.button("🔍 Run Institutional Alignment Scan", type="primary", use_container_width=True):
    results = []
    
    progress_bar = st.progress(0, text="Initializing network data streams...")
    total_symbols = len(symbols_to_scan)
    
    for idx, ticker in enumerate(symbols_to_scan):
        progress_bar.progress((idx + 1) / total_symbols, text=f"Analyzing {ticker} Structure ({idx+1}/{total_symbols})...")
        time.sleep(0.01)
        
        res = scan_zones(ticker, timeframe, zone_type, base_limit, min_legout, min_legout_size_pct)
        if res:
            results.extend(res)
            
    progress_bar.empty()
    
    if results:
        df_display = pd.DataFrame(results)
        df_display = df_display.sort_values(by="Formation Date", ascending=False).drop_duplicates(subset=["Ticker"], keep="first")
        
        if state_filter == "Just Approaching (Nearing Edge)":
            df_display = df_display[df_display['Live Alignment'] == "Just Approaching 🎯"]
        elif state_filter == "In the Zone (2-3 Candles Formed)":
            df_display = df_display[df_display['Zone State'] == "In the Zone (2-3 Candles) 🟡"]
        elif state_filter == "Unmitigated (100% Completely Fresh)":
            df_display = df_display[df_display['Zone State'] == "Unmitigated 🟢"]
        else:
            df_display = df_display[df_display['Zone State'] != "Mitigated 🔴"]
            
        if df_display.empty:
            st.warning("No institutional zones matched your exact state filter conditions at this moment.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"<div class='metric-card'><b>Total Formations:</b><br><span style='font-size:24px;'>{len(df_display)}</span></div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='metric-card' style='border-left-color:#00E676;'><b>100% Unmitigated:</b><br><span style='font-size:24px;'>{len(df_display[df_display['Zone State'] == 'Unmitigated 🟢'])}</span></div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div class='metric-card' style='border-left-color:#FFD600;'><b>Active Plays:</b><br><span style='font-size:24px;'>{len(df_display[df_display['Live Alignment'] != 'Normal'])}</span></div>", unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            def highlight_live_state(val):
                if "Approaching" in str(val): return 'background-color: #1B5E20; color: white;'
                if "Inside" in str(val): return 'background-color: #E65100; color: white;'
                return ''
                
            st.dataframe(
                df_display.style.map(highlight_live_state, subset=['Live Alignment']),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.warning("No institutional setups detected matching these core settings within the selected market segment.")
