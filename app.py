import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from scipy.signal import argrelextrema
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIG ---
st.set_page_config(page_title="Institutional Swap & Void Engine", layout="wide", page_icon="🏛️")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #8B5CF6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🏛️ S/R Confluence & Liquidity Void Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Detects structural channels and isolates clean momentum legs with no internal speed bumps.</p>', unsafe_allow_html=True)

# --- OFFLINE DATA UNIVERSE LOADER ---
def get_sector_symbols(sector_name):
    fo_stocks = [
        "AARTIIND.NS", "ABB.NS", "ABBOTINDIA.NS", "ABCAPITAL.NS", "ACC.NS", "ADANIENT.NS", "ADANIPORTS.NS", "ALKEM.NS", "AMBUJACEM.NS", "APOLLOHOSP.NS", 
        "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTRAL.NS", "ATUL.NS", "AUBANK.NS", "AUROPHARMA.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", 
        "BAJFINANCE.NS", "BALKRISIND.NS", "BALRAMCHIN.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BATAINDIA.NS", "BEL.NS", "BERGEPAINT.NS", "BHARATFORG.NS", 
        "BHARTIARTL.NS", "BHEL.NS", "BIOCON.NS", "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS", "CANBK.NS", "CANFINHOME.NS", "CHAMBLFERT.NS", "CHOLAFIN.NS", 
        "CIPLA.NS", "COALINDIA.NS", "COFORGE.NS", "COLPAL.NS", "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS", "DABUR.NS", 
        "DALBHARAT.NS", "DEEPAKNTR.NS", "DIVISLAB.NS", "DIXON.NS", "DLF.NS", "DRREDDY.NS", "EICHERMOT.NS", "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", 
        "GAIL.NS", "GLENMARK.NS", "GMRINFRA.NS", "GNFC.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRANULES.NS", "GRASIM.NS", "GUJGASLTD.NS", "HAL.NS", 
        "HAVELLS.NS", "HCLTECH.NS", "HDFCAMC.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDCOPPER.NS", "HINDPETRO.NS", 
        "HINDUNILVR.NS", "ICICIBANK.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDEA.NS", "IDFCFIRSTB.NS", "IEX.NS", "IGL.NS", "INDHOTEL.NS", "INDIACEM.NS", 
        "INDIGO.NS", "INDUSINDBK.NS", "INDUSTOWER.NS", "INFY.NS", "IOC.NS", "IPCALAB.NS", "IRCTC.NS", "ITC.NS", "JINDALSTEL.NS", "JKCEMENT.NS", 
        "JSWSTEEL.NS", "JUBLFOOD.NS", "KOTAKBANK.NS", "LALPATHLAB.NS", "LAURUSLABS.NS", "LICHSGFIN.NS", "LT.NS", "LTIM.NS", "LTTS.NS", "LUPIN.NS", 
        "M&M.NS", "M&MFIN.NS", "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS", "MCDOWELL-N.NS", "MCX.NS", "METROPOLIS.NS", "MFSL.NS", "MGL.NS", 
        "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NESTLEIND.NS", "NMDC.NS", "NTPC.NS", 
        "OBEROIRLTY.NS", "OFSS.NS", "ONGC.NS", "PAGEIND.NS", "PEL.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS", "PIDILITIND.NS", "PIIND.NS", 
        "PNB.NS", "POLYCAB.NS", "POWERGRID.NS", "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS", "SAIL.NS", "SBICARD.NS", 
        "SBILIFE.NS", "SBIN.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", "SIEMENS.NS", "SRF.NS", "SUNPHARMA.NS", "SUNTV.NS", "SYNGENE.NS", "TATACHEM.NS", 
        "TATACOMM.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS", "TRENT.NS", 
        "TVSMOTOR.NS", "UBL.NS", "ULTRACEMCO.NS", "UPL.NS", "VEDL.NS", "VOLTAS.NS", "WIPRO.NS", "ZEEL.NS", "ZYDUSLIFE.NS"
    ]
    nifty50_stocks = [
        "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS",
        "BHARTIARTL.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS",
        "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS",
        "INDUSINDBK.NS", "INFY.NS", "ITC.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS",
        "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS",
        "SUNPHARMA.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS",
        "ULTRACEMCO.NS", "WIPRO.NS"
    ]
    if sector_name == "Live F&O Active Stocks": return fo_stocks
    elif sector_name == "NIFTY 50": return nifty50_stocks
    else: return list(set(fo_stocks + nifty50_stocks))

# --- PINE SCRIPT PIVOT S/R ALGORITHM ---
def map_sr_channels(df, pivot_len, max_width_pct, min_touches):
    try:
        highs = df['High'].values
        lows = df['Low'].values
        peak_idx = argrelextrema(highs, np.greater, order=pivot_len)[0]
        valley_idx = argrelextrema(lows, np.less, order=pivot_len)[0]
        pivots = np.sort(np.concatenate((highs[peak_idx], lows[valley_idx])))
        
        if len(pivots) == 0: return []
        channels = []
        current_cluster = [pivots[0]]
        
        for i in range(1, len(pivots)):
            if (pivots[i] - current_cluster[0]) / current_cluster[0] <= (max_width_pct / 100.0):
                current_cluster.append(pivots[i])
            else:
                if len(current_cluster) >= min_touches:
                    channels.append({'floor': min(current_cluster), 'ceiling': max(current_cluster), 'strength': len(current_cluster)})
                current_cluster = [pivots[i]]
        if len(current_cluster) >= min_touches:
            channels.append({'floor': min(current_cluster), 'ceiling': max(current_cluster), 'strength': len(current_cluster)})
        return channels
    except Exception: return []

# --- EXTENDED CONFLUENCE & VOID ENGINE ---
def analyze_confluence(ticker, period, interval, pivot_len, sr_width, min_touches, min_base, max_base, mode_choice, strict_mode, leg_style):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df.empty or len(df) < 80: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        
        df = df.ffill().dropna(subset=['Close', 'Open', 'High', 'Low'])
        latest_close = df['Close'].iloc[-1]
        sr_zones = map_sr_channels(df, pivot_len, sr_width, min_touches)
        
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = (df['High'] - df['Low']).replace(0, 0.00001)
        df['Body_Ratio'] = df['Body'] / df['Range']
        df['Is_Green'] = df['Close'] > df['Open']
        
        BORING_THRESHOLD = 0.50
        LEG_OUT_THRESHOLD = 0.60 
        
        for i in range(len(df) - 1, len(df) - 25, -1):
            hero_idx = i
            if df['Body_Ratio'].iloc[hero_idx] < LEG_OUT_THRESHOLD: continue
            is_hero_up = df['Is_Green'].iloc[hero_idx]
            
            # Extract main base cluster
            base_count = 0
            base_indices = []
            for j in range(hero_idx - 1, max(0, hero_idx - 10), -1):
                if df['Body_Ratio'].iloc[j] <= BORING_THRESHOLD:
                    base_count += 1
                    base_indices.append(j)
                else: break
            if not (min_base <= base_count <= max_base): continue
                
            base_candles = df.iloc[base_indices]
            zone_type = "Demand" if is_hero_up else "Supply"
            if mode_choice != "Both" and mode_choice != zone_type: continue
                
            sd_upper = base_candles['High'].max()
            sd_lower = base_candles['Low'].min()
            
            # --- NEW: INTERNAL LEG MOMENTUM FILTER (THE RED/GREEN CIRCLE CHECKER) ---
            leg_in_idx = hero_idx - base_count - 1
            # Track the historical run up to 12 bars back to see the internal leg structure
            leg_start_idx = max(0, leg_in_idx - 10)
            leg_bars = df.iloc[leg_start_idx:leg_in_idx]
            
            internal_boring_count = 0
            if len(leg_bars) > 0:
                internal_boring_count = (leg_bars['Body_Ratio'] <= BORING_THRESHOLD).sum()
            
            # Apply the leg structure filter
            if leg_style == "Clean Momentum Leg (Red Circle)":
                if internal_boring_count > 1: continue # Drop structural climbs with intermediate speed bumps
            elif leg_style == "Structural Staircase Leg (Green Circle)":
                if internal_boring_count <= 1: continue # Drop vertical void lines
            
            # Check Role Reversal status
            swap_status = "Standard Zone"
            if zone_type == "Demand":
                for k in range(leg_in_idx - 2, 5, -1):
                    if df['Body_Ratio'].iloc[k] >= LEG_OUT_THRESHOLD and not df['Is_Green'].iloc[k]:
                        h_base_indices = [m for m in range(k - 1, max(0, k - 10), -1) if df['Body_Ratio'].iloc[m] <= BORING_THRESHOLD]
                        if min_base <= len(h_base_indices) <= max_base:
                            h_candles = df.iloc[h_base_indices]
                            if max(sd_lower, h_candles['Low'].min()) <= min(sd_upper, h_candles['High'].max()):
                                swap_status = "🔄 Swap: Prior Supply Broken"
                                break
            elif zone_type == "Supply":
                for k in range(leg_in_idx - 2, 5, -1):
                    if df['Body_Ratio'].iloc[k] >= LEG_OUT_THRESHOLD and df['Is_Green'].iloc[k]:
                        h_base_indices = [m for m in range(k - 1, max(0, k - 10), -1) if df['Body_Ratio'].iloc[m] <= BORING_THRESHOLD]
                        if min_base <= len(h_base_indices) <= max_base:
                            h_candles = df.iloc[h_base_indices]
                            if max(sd_lower, h_candles['Low'].min()) <= min(sd_upper, h_candles['High'].max()):
                                swap_status = "🔄 Swap: Prior Demand Broken"
                                break

            overlapping_sr = None
            for sr in sr_zones:
                if max(sd_lower, sr['floor']) <= min(sd_upper, sr['ceiling']):
                    overlapping_sr = sr
                    break
            if strict_mode and not overlapping_sr: continue 
                
            deviation = sd_upper * 0.015 
            is_testing = False
            if zone_type == "Demand" and (sd_upper + deviation) >= latest_close >= sd_lower: is_testing = True
            elif zone_type == "Supply" and (sd_lower - deviation) <= latest_close <= sd_upper: is_testing = True
                
            if not strict_mode or is_testing:
                leg_desc = f"⚡ VOID LEG ({internal_boring_count} Base Candles)" if internal_boring_count <= 1 else f"🧱 STAIRCASE LEG ({internal_boring_count} Base Candles)"
                return {
                    "Ticker": ticker.replace('.NS', ''),
                    "Zone Type": f"{'🟢' if zone_type == 'Demand' else '🔴'} {zone_type}",
                    "Leg Profile": leg_desc,
                    "Role Reversal": swap_status,
                    "Live Price": f"₹{round(latest_close, 2)}",
                    "Zone Bounds": f"₹{round(sd_lower, 2)} - ₹{round(sd_upper, 2)}",
                    "S/R Alignment": f"₹{round(overlapping_sr['floor'], 2)} - ₹{round(overlapping_sr['ceiling'], 2)}" if overlapping_sr else "❌ No Pivot Overlap",
                    "S/R Touches": f"⭐ {overlapping_sr['strength']}" if overlapping_sr else "0"
                }
        return None
    except Exception: return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Index", ["NIFTY 50", "Live F&O Active Stocks", "NIFTY 500"])
    
    st.divider()
    st.header("2. Execution Timeframe")
    tf_input = st.selectbox("Select Chart Horizon:", ["15 Min", "1 Hour", "Daily", "Weekly"], index=2)
    
    st.divider()
    st.header("3. Leg Structure Filter")
    leg_style_input = st.selectbox("Rally/Drop Leg Profile:", [
        "All Run Styles", 
        "Clean Momentum Leg (Red Circle)", 
        "Structural Staircase Leg (Green Circle)"
    ], index=0, help="Clean Momentum finds legs with zero or one base candles inside the run up/down for sudden drops.")
    
    st.divider()
    st.header("4. S/R Channel Logic")
    pivot_length = st.number_input("Pivot Lookback", 5, 30, 10)
    sr_width_pct = st.slider("Max Channel Width (%)", 1.0, 10.0, 5.0, step=0.5)
    min_touches = st.number_input("Min S/R Touches", 2, 10, 3)
    
    st.divider()
    st.header("5. Boring Candle Logic")
    mode_filter = st.selectbox("Zone Direction:", ["Both", "Demand", "Supply"])
    col1, col2 = st.columns(2)
    with col1: min_base_input = st.number_input("Min Base", 1, 3, 1)
    with col2: max_base_input = st.number_input("Max Base", 2, 6, 4)
        
    st.divider()
    st.header("6. Engine Mode")
    strict_toggle = st.checkbox("Strict Confluence Mode", value=False)
        
    st.divider()
    execute_button = st.button("🚀 EXECUTE SWAP SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = get_sector_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** on the **{tf_input}** chart...")
    
    tf_configs = {
        "15 Min": {"period": "60d", "interval": "15m"},
        "1 Hour": {"period": "730d", "interval": "1h"},
        "Daily": {"period": "3y", "interval": "1d"},
        "Weekly": {"period": "10y", "interval": "1wk"}
    }
    active_cfg = tf_configs[tf_input]
    confirmed_setups = []
    progress_ui = st.progress(0, text="Igniting engine...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(
                analyze_confluence, ticker, active_cfg["period"], active_cfg["interval"],
                pivot_length, sr_width_pct, min_touches, min_base_input, max_base_input, mode_filter, strict_toggle, leg_style_input
            ): ticker for ticker in symbols_list
        }
        
        completed_count = 0
        for future in as_completed(futures_map):
            completed_count += 1
            result = future.result()
            if result: confirmed_setups.append(result)
            
            percent_complete = completed_count / len(symbols_list)
            progress_ui.progress(percent_complete, text=f"Mapping Matrix: {completed_count}/{len(symbols_list)}")
            if completed_count % 30 == 0: time.sleep(0.3)
            
    progress_ui.empty()
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Complete: Found **{len(results_df)}** setups matching your specific structural filter.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No active setups matched this exact formation right now. Keep 'Strict Confluence' unchecked to expand the layout scan.")
