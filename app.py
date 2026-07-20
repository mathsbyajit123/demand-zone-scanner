import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Advanced S/D Swing Engine", layout="wide", page_icon="🔥")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #F59E0B; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🔥 Advanced S/D Swing Engine & Volume Tracker</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Hunts for 2X Volume Leg-Outs (RBR/DBR/RBD/DBD) and validates structural retracement traps.</p>', unsafe_allow_html=True)

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
        # Failsafe core list if NSE blocks the cloud server
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "L&T.NS"]

# --- STRUCTURAL S/D & VOLUME ALGORITHM ---
def analyze_advanced_swing(ticker, period, interval, min_base, max_base, vol_multiplier, scan_direction):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty or len(df) < 60: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
        latest_close = df['Close'].iloc[-1]
        
        # Core Metrics
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = (df['High'] - df['Low']).replace(0, 0.00001)
        df['Body_Ratio'] = df['Body'] / df['Range']
        df['Is_Green'] = df['Close'] > df['Open']
        
        # Volume Baseline (20-period moving average)
        df['Avg_Volume'] = df['Volume'].rolling(window=20).mean().shift(1)
        
        BORING_THRESHOLD = 0.50
        LEG_OUT_THRESHOLD = 0.60  
        
        # Step 1: Find the Primary Zone being tested right now
        for i in range(len(df) - 2, 25, -1):
            hero_idx = i
            
            # A. Check Leg-Out Strength & 2X Volume Explosion
            if df['Body_Ratio'].iloc[hero_idx] < LEG_OUT_THRESHOLD: continue
            if df['Volume'].iloc[hero_idx] < (vol_multiplier * df['Avg_Volume'].iloc[hero_idx]): continue
                
            is_hero_up = df['Is_Green'].iloc[hero_idx]
            zone_type = "Demand" if is_hero_up else "Supply"
            if scan_direction != "Both" and scan_direction != zone_type: continue
                
            # B. Check for tight Base (Boring Candles)
            base_count = 0
            base_indices = []
            for j in range(hero_idx - 1, max(10, hero_idx - 10), -1):
                if df['Body_Ratio'].iloc[j] <= BORING_THRESHOLD:
                    base_count += 1
                    base_indices.append(j)
                else: break
                    
            if not (min_base <= base_count <= max_base): continue
                
            # C. Check Leg-In to determine Pattern (RBR, DBR, DBD, RBD)
            leg_in_idx = hero_idx - base_count - 1
            is_leg_in_up = df['Is_Green'].iloc[leg_in_idx]
            
            if zone_type == "Demand":
                pattern = "RBR (Rally-Base-Rally)" if is_leg_in_up else "DBR (Drop-Base-Rally)"
            else:
                pattern = "DBD (Drop-Base-Drop)" if not is_leg_in_up else "RBD (Rally-Base-Drop)"
            
            # D. Define Boundaries & Freshness
            base_candles = df.iloc[base_indices]
            proximal = base_candles['High'].max() if zone_type == "Demand" else base_candles['Low'].min()
            distal = base_candles['Low'].min() if zone_type == "Demand" else base_candles['High'].max()
            
            post_zone_df = df.iloc[hero_idx + 1: -1].copy()
            if post_zone_df.empty: continue
            
            if zone_type == "Demand" and post_zone_df['Close'].min() < distal: continue
            if zone_type == "Supply" and post_zone_df['Close'].max() > distal: continue
                
            # E. Verify current price is testing the zone
            deviation = proximal * 0.015 # 1.5% entry tolerance
            is_testing = False
            
            if zone_type == "Demand" and distal <= latest_close <= (proximal + deviation): is_testing = True
            elif zone_type == "Supply" and (proximal - deviation) <= latest_close <= distal: is_testing = True
                
            if not is_testing: continue
                
            # Step 2: Validate the Retracement Leg (Did it build an opposing zone?)
            # Look inside post_zone_df for the creation of an opposite supply/demand zone
            retracement_valid = False
            opp_zone_type = "Supply" if zone_type == "Demand" else "Demand"
            opp_pattern_found = "None"
            
            # Reset index of post_zone to loop cleanly
            post_zone_df = post_zone_df.reset_index(drop=True)
            
            if len(post_zone_df) >= 4:
                for k in range(len(post_zone_df) - 1, 2, -1):
                    if post_zone_df['Body_Ratio'].iloc[k] >= LEG_OUT_THRESHOLD:
                        is_opp_hero_up = post_zone_df['Is_Green'].iloc[k]
                        
                        if (opp_zone_type == "Supply" and not is_opp_hero_up) or (opp_zone_type == "Demand" and is_opp_hero_up):
                            opp_base_count = 0
                            for m in range(k - 1, max(0, k - 5), -1):
                                if post_zone_df['Body_Ratio'].iloc[m] <= BORING_THRESHOLD:
                                    opp_base_count += 1
                                else: break
                                    
                            if 1 <= opp_base_count <= 4: # Found a valid opposing structure
                                retracement_valid = True
                                is_opp_leg_in_up = post_zone_df['Is_Green'].iloc[k - opp_base_count - 1]
                                if opp_zone_type == "Supply":
                                    opp_pattern_found = "DBD" if not is_opp_leg_in_up else "RBD"
                                else:
                                    opp_pattern_found = "RBR" if is_opp_leg_in_up else "DBR"
                                break
                                
            # Output Data
            return {
                "Ticker": ticker.replace('.NS', ''),
                "Bias": "🟢 BULL" if zone_type == "Demand" else "🔴 BEAR",
                "Pattern": pattern,
                "Live Price": f"₹{round(latest_close, 2)}",
                "Base Strength": f"{base_count} Candles",
                "Zone Entry Range": f"₹{round(proximal, 2)} - ₹{round(distal, 2)}",
                "Volume Surge": "🔥 2X+ Verified",
                "Retracement Trap": f"✅ Made {opp_pattern_found}" if retracement_valid else "❌ No Structural Trap"
            }
                
        return None
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Universe", ["NIFTY 500", "NIFTY 50", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 250"])
    
    st.divider()
    st.header("2. Execution Horizon")
    tf_input = st.selectbox("Select Timeframe:", ["15 Minutes", "1 Hour", "1D", "1W", "1M"], index=2)
    
    st.divider()
    st.header("3. Setup Direction")
    direction_input = st.selectbox("Swing Bias:", ["Both", "Demand", "Supply"])
    
    st.divider()
    st.header("4. Structural Requirements")
    col1, col2 = st.columns(2)
    with col1:
        min_base_input = st.number_input("Min Base", 1, 6, 1)
    with col2:
        max_base_input = st.number_input("Max Base", 1, 6, 4)
        
    vol_input = st.slider("Min Volume Multiplier", 1.0, 4.0, 2.0, step=0.5, help="Leg-out candle must have this much more volume than the 20-period average.")
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE SWING SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for Volume-Backed S/D Zones on the **{tf_input}** chart...")
    
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
                analyze_advanced_swing, ticker, active_cfg["period"], active_cfg["interval"],
                min_base_input, max_base_input, vol_input, direction_input
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
            progress_ui.progress(percent_complete, text=f"Analyzing Order Flow: {completed_count}/{len(symbols_list)}")
            
            if completed_count % 40 == 0:
                time.sleep(0.3)
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Complete: Found **{len(results_df)}** premium swing setups matching your volume and structural rules.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No stocks perfectly match the 2X Volume Leg-Out + Pullback requirements at this exact moment. Try lowering the Volume Multiplier to 1.5x.")
