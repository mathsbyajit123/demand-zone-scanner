import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from scipy.signal import argrelextrema
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Human-Like S/R Role Reversal Engine", layout="wide", page_icon="🧠")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #10B981; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🧠 Human-Like S/R Role Reversal Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for major 3-4 touch resistance ceilings with 5%-10%+ deep pullbacks, breakout confirmation, and 20/50 EMA retests.</p>', unsafe_allow_html=True)

# --- DATA UNIVERSE LOADER ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY MIDCAP 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY SMALLCAP 250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls.get(category))
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS"]

# --- HUMAN-LIKE PIVOT DETECTION ---
def find_human_like_ceilings(df, min_dip_pct, min_touches, max_touches, tolerance_pct):
    highs = df['High'].values
    lows = df['Low'].values
    
    # Use a wider window (order=10) to identify macro swing peaks
    peak_indices = argrelextrema(highs, np.greater, order=10)[0]
    if len(peak_indices) < min_touches:
        return []
    
    # Filter peaks: Each peak MUST have a deep drop (5%-10%+) following it or preceding it
    valid_peaks = []
    for p_idx in range(len(peak_indices)):
        curr_idx = peak_indices[p_idx]
        peak_price = highs[curr_idx]
        
        # Look at the trough between this peak and the next peak (or recent low)
        if p_idx < len(peak_indices) - 1:
            next_idx = peak_indices[p_idx + 1]
            trough_price = lows[curr_idx:next_idx].min()
        else:
            trough_price = lows[curr_idx:].min()
            
        dip_depth = ((peak_price - trough_price) / peak_price) * 100.0
        
        # Only keep peaks that had a legitimate human-visible drop
        if dip_depth >= min_dip_pct:
            valid_peaks.append({
                'index': curr_idx,
                'price': peak_price,
                'dip': dip_depth
            })
            
    if len(valid_peaks) < min_touches:
        return []
    
    # Cluster valid deep-dip peaks into horizontal ceiling zones
    prices = np.array([p['price'] for p in valid_peaks])
    indices = np.array([p['index'] for p in valid_peaks])
    
    clusters = []
    used_indices = set()
    
    for i in range(len(prices)):
        if i in used_indices: continue
        
        base_price = prices[i]
        cluster_peaks = [prices[i]]
        cluster_idxs = [indices[i]]
        used_indices.add(i)
        
        for j in range(i + 1, len(prices)):
            if j in used_indices: continue
            # Check if this peak sits within the tolerance range of the ceiling
            if abs(prices[j] - base_price) / base_price * 100.0 <= tolerance_pct:
                cluster_peaks.append(prices[j])
                cluster_idxs.append(indices[j])
                used_indices.add(j)
                
        if min_touches <= len(cluster_peaks) <= max_touches:
            clusters.append({
                'bottom': min(cluster_peaks),
                'top': max(cluster_peaks),
                'touches': len(cluster_peaks),
                'last_touch_idx': max(cluster_idxs)
            })
            
    return clusters

# --- MASTER HUMAN-LIKE ENGINE ---
def analyze_human_like_sr(ticker, period, interval, min_dip_pct, min_touches, max_touches, slope_min, entry_buffer):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 120: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        
        latest_close = df['Close'].iloc[-1]
        latest_low = df['Low'].iloc[-1]
        
        # 1. EMA TREND & MOMENTUM SLOPE
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        ema_20_live = df['EMA_20'].iloc[-1]
        ema_50_live = df['EMA_50'].iloc[-1]
        
        # Condition A: 20 EMA > 50 EMA
        if ema_20_live <= ema_50_live: return None
            
        # Condition B: ~45 Degree Upward Slope (20 EMA rising over last 5 bars)
        ema_20_past = df['EMA_20'].iloc[-5]
        slope_pct = ((ema_20_live - ema_20_past) / ema_20_past) * 100.0
        if slope_pct < slope_min: return None
            
        # Condition C: Price pulling back into the 20/50 EMA corridor
        if not (latest_low <= ema_20_live and latest_close >= (ema_50_live * 0.995)): return None

        # 2. HUMAN-LIKE CEILING DETECTION (Deep Dips + 3-4 Touches)
        ceilings = find_human_like_ceilings(df, min_dip_pct, min_touches, max_touches, tolerance_pct=2.0)
        if not ceilings: return None
            
        for ceiling in ceilings:
            c_top = ceiling['top']
            c_bottom = ceiling['bottom']
            last_touch = ceiling['last_touch_idx']
            
            # Condition D: Breakout Confirmation (Must have closed at least 2% above the ceiling after the last touch)
            post_ceiling_df = df.iloc[last_touch:]
            if post_ceiling_df['Close'].max() < (c_top * 1.02):
                continue # No clear breakout happened
                
            # Condition E: Current Retest (Price pulling back to test broken ceiling as Demand)
            buffer_val = c_top * (entry_buffer / 100.0)
            
            # Live price is sitting on or slightly above the broken ceiling
            if (c_bottom - buffer_val) <= latest_close <= (c_top + buffer_val):
                dist_pct = ((latest_close - c_top) / c_top) * 100.0
                
                return {
                    "Ticker": ticker.replace('.NS', ''),
                    "Status": f"🔄 ROLE REVERSAL ({ceiling['touches']} Touches)",
                    "Live Price": f"₹{round(latest_close, 2)}",
                    "Old Ceiling (New Demand)": f"₹{round(c_bottom, 2)} - ₹{round(c_top, 2)}",
                    "Min Dip Depth": f"📉 >{min_dip_pct}% Pullbacks",
                    "20 EMA Slope": f"📈 +{round(slope_pct, 2)}% / 5 Bars",
                    "Distance to Zone": f"{round(dist_pct, 2)}%"
                }
                
        return None
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Universe", ["NIFTY 500", "NIFTY 50", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 250"])
    
    st.divider()
    st.header("2. Timeframe Selection")
    tf_input = st.selectbox("Select Horizon:", ["1D", "1W", "1M", "1 Hour", "15 Minutes"], index=0)
    
    st.divider()
    st.header("3. Human-Like Swing Rules")
    col1, col2 = st.columns(2)
    with col1:
        min_touches = st.number_input("Min Touches", 2, 6, 3)
    with col2:
        max_touches = st.number_input("Max Touches", 3, 10, 4)
        
    min_dip_pct = st.slider("Min Pullback Depth Between Touches (%)", 3.0, 15.0, 5.0, step=0.5, 
                            help="Requires price to drop by at least this percentage between touches to eliminate noise.")
    
    st.divider()
    st.header("4. EMA Corridor & Slope")
    slope_min = st.slider("Min 20 EMA Upward Slope (%)", 0.1, 3.0, 0.8, step=0.1, 
                          help="Verifies a strong ~45 degree uptrend.")
    entry_buffer = st.slider("Retest Buffer (%)", 0.0, 4.0, 1.5, step=0.1, 
                             help="How far above the broken ceiling the live price can be.")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE HUMAN S/R SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for Human-Like Role Reversals on the **{tf_input}** chart...")
    
    tf_configs = {
        "15 Minutes": {"period": "60d", "interval": "15m"},
        "1 Hour": {"period": "730d", "interval": "1h"},
        "1D": {"period": "3y", "interval": "1d"},
        "1W": {"period": "10y", "interval": "1wk"},
        "1M": {"period": "20y", "interval": "1mo"}
    }
    active_cfg = tf_configs[tf_input]
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures_map = {
            executor.submit(
                analyze_human_like_sr, ticker, active_cfg["period"], active_cfg["interval"],
                min_dip_pct, min_touches, max_touches, slope_min, entry_buffer
            ): ticker 
            for ticker in symbols_list
        }
        
        completed_count = 0
        for future in as_completed(futures_map):
            completed_count += 1
            result = future.result()
            if result:
                confirmed_setups.append(result)
            
            percent_complete = completed_count / len(symbols_list)
            progress_ui.progress(percent_complete, text=f"Analyzing Deep Swing Ceilings: {completed_count}/{len(symbols_list)}")
            
            if completed_count % 40 == 0:
                time.sleep(0.3)
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Complete: Found **{len(results_df)}** stocks retesting verified 3-4 touch ceilings with 5%+ dips.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks currently match these strict criteria. Requiring 3-4 distinct ceiling touches with >5% drops in between + a breakout + an EMA retest is a very strict filter. Try dropping 'Min Pullback Depth' to 3.5% or 4.0%.")
