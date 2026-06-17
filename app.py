import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --- PAGE SETUP ---
st.set_page_config(page_title="Dual Institutional Matrix Engine", layout="wide", page_icon="🛡️")

st.markdown("""
    <style>
    .main-title { font-size: 36px; font-weight: 800; color: #1E3A8A; margin-bottom: 0px; }
    .sub-title { font-size: 16px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🛡️ Dual Institutional Phase & S/R Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Complete Long/Short Macro Scanner. Detects Bullish Accumulation & Bearish Liquidation Cycles.</p>', unsafe_allow_html=True)

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

# --- ADVANCED DUAL MACRO STRUCTURAL MATH ENGINE ---
def analyze_macro_structure(df, df_weekly, trading_bias, sr_tolerance=1.5):
    if df is None or len(df) < 200 or df_weekly is None or len(df_weekly) < 50:
        return None
    
    latest_close = df['Close'].iloc[-1]
    
    # 1. Trend Identification (Weekly Filter)
    df_weekly['EMA50_W'] = df_weekly['Close'].ewm(span=50, adjust=False).mean()
    weekly_close = df_weekly['Close'].iloc[-1]
    weekly_ema = df_weekly['EMA50_W'].iloc[-1]
    
    if weekly_close > weekly_ema:
        macro_trend = "🟢 STRONG UPTREND"
    else:
        macro_trend = "🔴 MACRO DOWNTREND"
    
    # 2. Wyckoff Phase Classification (Daily Moving Average Geometry)
    df['EMA50_D'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200_D'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    ema50_latest = df['EMA50_D'].iloc[-1]
    ema200_latest = df['EMA200_D'].iloc[-1]
    
    ema200_slope = (df['EMA200_D'].iloc[-1] - df['EMA200_D'].iloc[-20]) / df['EMA200_D'].iloc[-20] * 100
    price_60_days_ago = df['Close'].iloc[-60]
    ema200_60_days_ago = df['EMA200_D'].iloc[-60]
    
    if latest_close > ema200_latest and ema50_latest > ema200_latest and ema200_slope > 0.05:
        market_phase = "Phase 2: MARKUP (Explosive Bull Run)"
    elif latest_close < ema200_latest and ema50_latest < ema200_latest and ema200_slope < -0.05:
        market_phase = "Phase 4: MARKDOWN (Severe Liquidation)"
    else:
        if price_60_days_ago < ema200_60_days_ago:
            market_phase = "Phase 1: ACCUMULATION (Institutional Load)"
        else:
            market_phase = "Phase 3: DISTRIBUTION (Retail Trap / Top Heavy)"

    # 3. Dual-Direction S/R Flip Detection Algorithm
    historical_window = df.iloc[-70:-10]
    recent_window = df.iloc[-10:]
    
    sr_flip_status = "❌ No Setup Active"
    proximity_val = "N/A"
    
    if "Bullish" in trading_bias:
        # Old Resistance becomes New Support
        macro_resistance_peak = historical_window['High'].max()
        has_broken_out = recent_window['High'].max() > macro_resistance_peak
        distance_to_peak = ((latest_close - macro_resistance_peak) / macro_resistance_peak) * 100
        
        if has_broken_out:
            if abs(distance_to_peak) <= sr_tolerance and latest_close >= (macro_resistance_peak * 0.995):
                sr_flip_status = f"🎯 BULLISH S/R FLIP (Old Res: ₹{round(macro_resistance_peak, 2)})"
                proximity_val = f"{round(distance_to_peak, 2)}%"
            elif latest_close > macro_resistance_peak:
                sr_flip_status = "📈 Breakout Extended (Waiting for Pullback)"
                proximity_val = f"{round(distance_to_peak, 2)}%"
                
    elif "Bearish" in trading_bias:
        # Old Support becomes New Resistance (Ceiling)
        macro_support_trough = historical_window['Low'].min()
        has_broken_down = recent_window['Low'].min() < macro_support_trough
        # Proximity measurement from underneath the broken floor
        distance_to_trough = ((latest_close - macro_support_trough) / macro_support_trough) * 100
        
        if has_broken_down:
            if abs(distance_to_trough) <= sr_tolerance and latest_close <= (macro_support_trough * 1.005):
                sr_flip_status = f"🩸 BEARISH S/R FLIP (Old Supp: ₹{round(macro_support_trough, 2)})"
                proximity_val = f"{round(distance_to_trough, 2)}%"
            elif latest_close < macro_support_trough:
                sr_flip_status = "📉 Breakdown Extended (Waiting for Relief Rally)"
                proximity_val = f"{round(distance_to_trough, 2)}%"

    return {
        "live_price": round(latest_close, 2),
        "trend": macro_trend,
        "phase": market_phase,
        "sr_status": sr_flip_status,
        "proximity": proximity_val
    }

# --- SIDEBAR INTERFACE CONTROL ---
with st.sidebar:
    st.header("1. Strategy Bias")
    trading_mode = st.radio("Select Trading Engine Direction:", ["Bullish (Long / Buy Setups)", "Bearish (Short / Sell Setups)"])
    
    st.divider()
    st.header("2. Core Liquidity")
    selected_sector = st.selectbox("Market Index Universe", ["Test Universe", "NIFTY 50", "NIFTY Bank", "NIFTY Midcap 100", "NIFTY 500"])
    
    st.divider()
    st.header("3. Structural Filters")
    phase_filter = st.selectbox("Filter by Wyckoff Phase:", ["All Phases", "Phase 1: ACCUMULATION", "Phase 2: MARKUP", "Phase 3: DISTRIBUTION", "Phase 4: MARKDOWN"])
    only_activated_flips = st.checkbox("Show ONLY confirmed S/R Flips", value=False)
    sr_box_tolerance = st.slider("S/R Trigger Tolerance (%)", 0.5, 3.0, 1.5, step=0.1)
    
    st.divider()
    run_scan = st.button("🚀 EXECUTE TRACKING ENGINE", type="primary", use_container_width=True)

# Assign symbol arrays
target_symbols = load_symbols("NIFTY 50")[:6] if "Test" in selected_sector else load_symbols(selected_sector)

# --- CODE EXECUTION CORE ENGINE ---
if run_scan:
    scanned_opportunities = []
    st.info(f"📊 Running comprehensive structural sweeps for {trading_mode} formations...")
    execution_progress = st.progress(0, text="Calibrating macro streams...")
    
    total_symbols = len(target_symbols)
    
    for idx, ticker in enumerate(target_symbols):
        clean_ticker = ticker.replace('.NS', '')
        execution_progress.progress((idx + 1) / total_symbols, text=f"Processing {clean_ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            df_daily = stock.history(period='1y', interval='1d')
            df_weekly = stock.history(period='2y', interval='1wk')
            
            if df_daily.empty or len(df_daily) < 200 or df_weekly.empty:
                continue
                
            if df_daily.index.tz is not None: df_daily.index = df_daily.index.tz_localize(None)
            if df_weekly.index.tz is not None: df_weekly.index = df_weekly.index.tz_localize(None)
                
            df_daily = df_daily.ffill().dropna(subset=['Close'])
            df_weekly = df_weekly.ffill().dropna(subset=['Close'])
            
            # Process calculations with active direction tracking
            struct = analyze_macro_structure(df_daily, df_weekly, trading_mode, sr_box_tolerance)
            
            if struct is None:
                continue
            
            # --- FILTER APPLICATION LOGIC ---
            if "All" not in str(phase_filter) and str(phase_filter) not in struct["phase"]:
                continue
                
            if only_activated_flips and ("BULLISH S/R FLIP" not in struct["sr_status"] and "BEARISH S/R FLIP" not in struct["sr_status"]):
                continue
                
            # Build clean row mapping
            scanned_opportunities.append({
                "Stock Symbol": clean_ticker,
                "Live Price (₹)": struct["live_price"],
                "Macro Trend (1W)": struct["trend"],
                "Current Market Phase": struct["phase"],
                "Structural S/R Status": struct["sr_status"],
                "Distance to Flip Barrier": struct["proximity"]
            })
                
        except Exception:
            pass
            
    execution_progress.empty()
    
    # --- RENDER STRATEGIC DISPLAY SHEET ---
    if scanned_opportunities:
        display_df = pd.DataFrame(scanned_opportunities)
        st.success(f"🛡️ Scan Complete: Isolated **{len(display_df)}** match profiles.")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Professional Execution Cheat Sheet
        if "Bullish" in trading_mode:
            st.markdown("""
            ### 💡 How to Play These Bullish Setups:
            * **The Target Profile:** Look for stocks in **Phase 1** or **Phase 2** showing a **Bullish S/R Flip**. 
            * **The Entry Window:** Wait for a 75-minute chart confirmation (bullish engulfing or a hammer pinbar wick rejecting the old resistance line).
            """)
        else:
            st.markdown("""
            ### 💡 How to Play These Bearish Setups:
            * **The Shorting Target:** Look for stocks inside **Phase 3: DISTRIBUTION** or **Phase 4: MARKDOWN** that display **🔴 BEARISH S/R FLIP**.
            * **The Shorting Execution:** The price has broken down below a major historical support floor and has rallied back up to test that line from below. If the 75-minute candle prints a heavy red shooting-star or bearish rejection wick at this line, it's an elite shorting entry setup. Placed your tight stop loss 3.5% above the rejection wick.
            """)
    else:
        st.warning("No structural setups match your exact criteria. Try switching phases or widening the tolerance.")
