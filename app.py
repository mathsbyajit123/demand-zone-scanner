import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- PAGE SETUP ---
st.set_page_config(page_title="Institutional Phase & S/R Matrix", layout="wide", page_icon="🛡️")

st.markdown("""
    <style>
    .main-title { font-size: 36px; font-weight: 800; color: #1E3A8A; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🛡️ Institutional Macro Phase & S/R Flip Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Advanced Higher Timeframe Scanner. Detects Wyckoff Cycles, Macro Trends, and Structural S/R Flips.</p>', unsafe_allow_html=True)

# --- BULLETPROOF INDEX SYMBOL LOADER ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[category])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "LT.NS"]

# --- ADVANCED MACRO STRUCTURAL MATH ENGINE ---
def analyze_macro_structure(df, df_weekly, sr_tolerance=1.5):
    if df is None or len(df) < 200 or df_weekly is None or len(df_weekly) < 50:
        return None
    
    latest_close = df['Close'].iloc[-1]
    
    # 1. Trend Identification (Weekly Filter)
    df_weekly['EMA50_W'] = df_weekly['Close'].ewm(span=50, adjust=False).mean()
    weekly_close = df_weekly['Close'].iloc[-1]
    weekly_ema = df_weekly['EMA50_W'].iloc[-1]
    
    macro_trend = "🟢 STRONG UPTREND" if weekly_close > weekly_ema else "🔴 DOWNTREND / CAUTION"
    
    # 2. Wyckoff Phase Classification (Daily Moving Average Geometry)
    df['EMA50_D'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200_D'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    ema50_latest = df['EMA50_D'].iloc[-1]
    ema200_latest = df['EMA200_D'].iloc[-1]
    
    # Calculate 20-day slope of 200 EMA to identify flattening vs trending regimes
    ema200_slope = (df['EMA200_D'].iloc[-1] - df['EMA200_D'].iloc[-20]) / df['EMA200_D'].iloc[-20] * 100
    
    # Historical baseline from 60 days ago to check trajectory
    price_60_days_ago = df['Close'].iloc[-60]
    ema200_60_days_ago = df['EMA200_D'].iloc[-60]
    
    if latest_close > ema200_latest and ema50_latest > ema200_latest and ema200_slope > 0.05:
        market_phase = "Phase 2: MARKUP (Explosive Bull Run)"
    elif latest_close < ema200_latest and ema50_latest < ema200_latest and ema200_slope < -0.05:
        market_phase = "Phase 4: MARKDOWN (Severe Liquidation)"
    else:
        # Intricate range detection (Phase 1 vs Phase 3)
        if price_60_days_ago < ema200_60_days_ago:
            market_phase = "Phase 1: ACCUMULATION (Institutional Loading Zone)"
        else:
            market_phase = "Phase 3: DISTRIBUTION (Retail Trap / Top Heavy)"

    # 3. S/R Flip Detection Algorithm (Resistance Becomes Support)
    # Step A: Find the highest resistance peak inside a historical window (excluding the last 10 days)
    historical_window = df.iloc[-70:-10]
    macro_resistance_peak = historical_window['High'].max()
    
    # Step B: Check if price broke cleanly above that historical peak within the last 10 days
    recent_window = df.iloc[-10:]
    has_broken_out = recent_window['High'].max() > macro_resistance_peak
    
    # Step C: Check if current price has pulled back right on top of that broken resistance ceiling
    distance_to_peak = ((latest_close - macro_resistance_peak) / macro_resistance_peak) * 100
    
    sr_flip_status = "❌ No Setup Active"
    if has_broken_out:
        if abs(distance_to_peak) <= sr_tolerance:
            sr_flip_status = f"🎯 S/R FLIP ACTIVATED (Old Res: ₹{round(macro_resistance_peak, 2)})"
        elif distance_to_peak > sr_tolerance and latest_close > macro_resistance_peak:
            sr_flip_status = "📈 Breakout Extended (Waiting for Pullback)"

    return {
        "live_price": round(latest_close, 2),
        "trend": macro_trend,
        "phase": market_phase,
        "sr_status": sr_flip_status,
        "proximity_to_flip": round(distance_to_peak, 2) if has_broken_out else None
    }

# --- SIDEBAR INTERFACE CONTROL ---
with st.sidebar:
    st.header("1. Core Liquidity")
    selected_sector = st.selectbox("Market Index Universe", ["Test Universe", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("2. Structural Parameters")
    phase_filter = str(st.selectbox("Filter by Wyckoff Phase:", ["All Phases", "Phase 1: ACCUMULATION", "Phase 2: MARKUP", "Phase 3: DISTRIBUTION", "Phase 4: MARKDOWN"]))
    
    only_sr_flips = st.checkbox("Show ONLY confirmed S/R Flip Pullbacks", value=False,
                                help="Filters the matrix to strictly highlight stocks testing broken resistance levels.")
    
    sr_box_tolerance = st.slider("S/R Touch Tolerance (%)", 0.5, 3.0, 1.5, step=0.1,
                                 help="Maximum allowed percentage distance between current price and the old resistance line.")
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE STRUCTURAL SCAN", type="primary", use_container_width=True)

# Assign symbol arrays
target_symbols = load_symbols("NIFTY 50")[:6] if "Test" in selected_sector else load_symbols(selected_sector)

# --- CODE EXECUTION CORE ENGINE ---
if run_scan:
    scanned_opportunities = []
    st.info("📊 Compiling daily and weekly structural data fields...")
    execution_progress = st.progress(0, text="Synchronizing index streams...")
    
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        clean_ticker = ticker.replace('.NS', '')
        execution_progress.progress((idx + 1) / total_symbols, text=f"Mapping Matrix Coordinates for {clean_ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            
            # Fetch daily data for phase/breakout analytics
            df_daily = stock.history(period='1y', interval='1d')
            # Fetch weekly data for macro trend direction
            df_weekly = stock.history(period='2y', interval='1wk')
            
            if df_daily.empty or len(df_daily) < 200 or df_weekly.empty:
                continue
                
            # Clean indices
            if df_daily.index.tz is not None: df_daily.index = df_daily.index.tz_localize(None)
            if df_weekly.index.tz is not None: df_weekly.index = df_weekly.index.tz_localize(None)
                
            df_daily = df_daily.ffill().dropna(subset=['Close'])
            df_weekly = df_weekly.ffill().dropna(subset=['Close'])
            
            # Process calculations
            struct = analyze_macro_structure(df_daily, df_weekly, sr_box_tolerance)
            
            if struct is None:
                continue
            
            # --- FILTER APPLICATION LOGIC ---
            if "All" not in phase_filter and phase_filter not in struct["phase"]:
                continue
                
            if only_sr_flips and "ACTIVATED" not in struct["sr_status"]:
                continue
                
            # Build clean analytical data rows
            scanned_opportunities.append({
                "Stock Symbol": clean_ticker,
                "Live Price (₹)": struct["live_price"],
                "Macro Trend (1W)": struct["trend"],
                "Current Market Phase": struct["phase"],
                "Structural S/R Status": struct["sr_status"],
                "Distance to Flip Support (%)": f"{struct['proximity_to_flip']}%" if struct['proximity_to_flip'] is not None else "N/A"
            })
                
        except Exception:
            pass
            
    execution_progress.empty()
    
    # --- RENDER STRATEGIC DISPLAY SHEET ---
    if scanned_opportunities:
        display_df = pd.DataFrame(scanned_opportunities)
        st.success(f"🛡️ Structural Map Complete: Found **{len(display_df)}** qualified setups.")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Professional Execution Cheat Sheet
        st.markdown("""
        ### 💡 How to Trade These Structural Matrix Results:
        1. **The Phase 1 Jackpot:** If a stock is listed under **Phase 1: ACCUMULATION** and its macro trend shows **Strong Uptrend**, institutions are heavily loading up on a macro pullback. This is your lowest risk entry area for a massive 1-month swing.
        2. **The S/R Flip Entry:** If a stock prints **🎯 S/R FLIP ACTIVATED**, open its 75-minute chart. Wait for your live confirmation setup (a 75m bullish candle closing higher to prove the old resistance ceiling is successfully acting as a solid new floor).
        3. **Risk Enforcement:** Your stop loss remains an absolute maximum of **3.5% below your entry price**, targeted toward your mechanical **10%+ monthly swing target**.
        """)
    else:
        st.warning("No stocks match the exact structural cycle filters selected. Try setting the Phase Filter to 'All Phases' or widening your S/R Touch Tolerance.")
