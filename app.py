import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# --- PAGE CONFIG ---
st.set_page_config(page_title="Dual-TF Supply/Demand Matrix", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 34px; font-weight: 800; color: #0284c7; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #475569; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 Dual-TF Institutional Boring Candle Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Maps Macro HTF Bases (< 50% Body) and hunts for precise LTF execution triggers.</p>', unsafe_allow_html=True)

# --- COMPREHENSIVE 210+ NSE F&O MASTER LIST ---
def get_fo_stocks():
    return [
        "AARTIIND.NS", "ABB.NS", "ABBOTINDIA.NS", "ABCAPITAL.NS", "ABFRL.NS", "ACC.NS", "ADANIENT.NS", "ADANIPORTS.NS",
        "ALKEM.NS", "AMBUJACEM.NS", "APOLLOHOSP.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTRAL.NS", 
        "ATUL.NS", "AUBANK.NS", "AUROPHARMA.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS", 
        "BALKRISIND.NS", "BALRAMCHIN.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BATAINDIA.NS", "BEL.NS", "BERGEPAINT.NS", 
        "BHARATFORG.NS", "BHARTIARTL.NS", "BHEL.NS", "BIOCON.NS", "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS", "CANBK.NS", 
        "CANFINHOME.NS", "CHAMBLFERT.NS", "CHOLAFIN.NS", "CIPLA.NS", "COALINDIA.NS", "COFORGE.NS", "COLPAL.NS", 
        "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS", "DABUR.NS", "DALBHARAT.NS", "DEEPAKNTR.NS", 
        "DIVISLAB.NS", "DIXON.NS", "DLF.NS", "DRREDDY.NS", "EICHERMOT.NS", "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", 
        "GAIL.NS", "GLENMARK.NS", "GMRINFRA.NS", "GNFC.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRANULES.NS", "GRASIM.NS", 
        "GUJGASLTD.NS", "HAL.NS", "HAVELLS.NS", "HCLTECH.NS", "HDFCAMC.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", 
        "HINDALCO.NS", "HINDCOPPER.NS", "HINDPETRO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ICICIGI.NS", "ICICIPRULI.NS", 
        "IDEA.NS", "IDFC.NS", "IDFCFIRSTB.NS", "IEX.NS", "IGL.NS", "INDHOTEL.NS", "INDIACEM.NS", "INDIGO.NS", "INDUSINDBK.NS", 
        "INDUSTOWER.NS", "INFY.NS", "IOC.NS", "IPCALAB.NS", "IRCTC.NS", "ITC.NS", "JINDALSTEL.NS", "JKCEMENT.NS", 
        "JSWSTEEL.NS", "JUBLFOOD.NS", "KOTAKBANK.NS", "L&TFH.NS", "LALPATHLAB.NS", "LAURUSLABS.NS", "LICHSGFIN.NS", 
        "LT.NS", "LTIM.NS", "LTTS.NS", "LUPIN.NS", "M&M.NS", "M&MFIN.NS", "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS", 
        "MCDOWELL-N.NS", "MCX.NS", "METROPOLIS.NS", "MFSL.NS", "MGL.NS", "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS", 
        "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NESTLEIND.NS", "NMDC.NS", "NTPC.NS", 
        "OBEROIRLTY.NS", "OFSS.NS", "ONGC.NS", "PAGEIND.NS", "PEL.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS", 
        "PIDILITIND.NS", "PIIND.NS", "PNB.NS", "POLYCAB.NS", "POWERGRID.NS", "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS", 
        "RECLTD.NS", "RELIANCE.NS", "SAIL.NS", "SBICARD.NS", "SBILIFE.NS", "SBIN.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", 
        "SIEMENS.NS", "SRF.NS", "SUNPHARMA.NS", "SUNTV.NS", "SYNGENE.NS", "TATACHEM.NS", "TATACOMM.NS", "TATACONSUM.NS", 
        "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS", "TRENT.NS", 
        "TVSMOTOR.NS", "UBL.NS", "ULTRACEMCO.NS", "UPL.NS", "VEDL.NS", "VOLTAS.NS", "WIPRO.NS", "ZEEL.NS", "ZYDUSLIFE.NS"
    ]

@st.cache_data(ttl=86400)
def get_sector_symbols(sector_name):
    if sector_name == "F&O Active Stocks (210+)":
        return get_fo_stocks()
        
    urls = {
        "NIFTY 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
        "NIFTY 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    try:
        df = pd.read_csv(urls[sector_name])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return get_fo_stocks()[:50]

# --- INTERNAL 75m AGGREGATOR ---
def convert_to_75m(df_15m):
    if df_15m is None or df_15m.empty: return None
    df_15m['Date_Str'] = df_15m.index.strftime('%Y-%m-%d')
    df_15m['Bar_Chunk'] = df_15m.groupby('Date_Str').cumcount() // 5
    resampled = df_15m.groupby(['Date_Str', 'Bar_Chunk']).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).reset_index(drop=True)
    resampled.index = df_15m.groupby(['Date_Str', 'Bar_Chunk']).index.last().reset_index(drop=True)
    return resampled.dropna()

def fetch_and_resample(ticker, period, interval, target_tf=None):
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)
    if df.empty: return None
    if df.index.tz is not None: df.index = df.index.tz_localize(None)
    
    if target_tf == "75 Min": return convert_to_75m(df)
    return df.dropna(subset=['Close'])

# --- DUAL-TIMEFRAME BORING CANDLE ENGINE ---
def analyze_dual_tf(ticker, htf_conf, ltf_conf, min_base, max_base, mode_choice, tolerance_pct):
    try:
        # 1. Fetch HTF Data to map zones
        df_htf = fetch_and_resample(ticker, htf_conf["period"], htf_conf["interval"], htf_conf.get("custom"))
        if df_htf is None or len(df_htf) < 20: return None
        
        # 2. Fetch LTF Data for execution trigger
        df_ltf = fetch_and_resample(ticker, ltf_conf["period"], ltf_conf["interval"], ltf_conf.get("custom"))
        if df_ltf is None or df_ltf.empty: return None
        
        ltf_close = df_ltf['Close'].iloc[-1]
        
        # --- HTF BORING CANDLE MATH (< 50% Body) ---
        df_htf['Body'] = (df_htf['Close'] - df_htf['Open']).abs()
        df_htf['Range'] = df_htf['High'] - df_htf['Low']
        df_htf['Range'] = df_htf['Range'].replace(0, 0.00001)
        df_htf['Body_Ratio'] = df_htf['Body'] / df_htf['Range']
        df_htf['Is_Green'] = df_htf['Close'] > df_htf['Open']
        
        BORING_THRESHOLD = 0.50 
        
        # Walk back to find Leg Out (Hero) -> Bases -> Leg In
        for i in range(len(df_htf) - 2, 5, -1):
            hero_idx = i
            
            # Leg Out must be explosive (> 50% body)
            if df_htf['Body_Ratio'].iloc[hero_idx] <= BORING_THRESHOLD:
                continue
                
            is_hero_up = df_htf['Is_Green'].iloc[hero_idx]
            
            # Count back-to-back boring candles (the Base)
            base_count = 0
            base_indices = []
            for j in range(hero_idx - 1, 0, -1):
                if df_htf['Body_Ratio'].iloc[j] <= BORING_THRESHOLD:
                    base_count += 1
                    base_indices.append(j)
                else:
                    break
                    
            if not (min_base <= base_count <= max_base):
                continue
                
            leg_in_idx = hero_idx - base_count - 1
            is_leg_in_up = df_htf['Is_Green'].iloc[leg_in_idx]
            
            # Categorize the Zone
            if is_hero_up:
                zone_type = "Demand"
                pattern = "Rally-Base-Rally (RBR)" if is_leg_in_up else "Drop-Base-Rally (DBR)"
            else:
                zone_type = "Supply"
                pattern = "Drop-Base-Drop (DBD)" if not is_leg_in_up else "Rally-Base-Drop (RBD)"
                
            if mode_choice != "All" and mode_choice != zone_type:
                continue
                
            # Define Proximal & Distal Lines based on the Boring Candles
            base_candles_df = df_htf.iloc[base_indices]
            zone_proximal = base_candles_df['High'].max() if zone_type == "Demand" else base_candles_df['Low'].min()
            zone_distal = base_candles_df['Low'].min() if zone_type == "Demand" else base_candles_df['High'].max()
            
            # Check if the zone was mitigated/destroyed by subsequent HTF candles
            post_zone_df = df_htf.iloc[hero_idx + 1:]
            is_destroyed = False
            
            if not post_zone_df.empty:
                if zone_type == "Demand" and post_zone_df['Low'].min() < zone_distal:
                    is_destroyed = True
                elif zone_type == "Supply" and post_zone_df['High'].max() > zone_distal:
                    is_destroyed = True
                    
            if is_destroyed: continue
            
            # --- EVALUATE LTF EXECUTION TRIGGER ---
            # Is the live LTF price touching or very near the HTF zone right now?
            deviation_limit = zone_proximal * (tolerance_pct / 100)
            
            is_touching = False
            if zone_type == "Demand" and (zone_proximal + deviation_limit) >= ltf_close >= zone_distal:
                is_touching = True
            elif zone_type == "Supply" and (zone_proximal - deviation_limit) <= ltf_close <= zone_distal:
                is_touching = True
                
            if is_touching:
                return {
                    "Ticker": ticker.replace('.NS', ''),
                    "Macro Zone Type": "🟢 DEMAND" if zone_type == "Demand" else "🔴 SUPPLY",
                    "HTF Structure": pattern,
                    "Base Candles": f"{base_count} Boring Candles",
                    "HTF Proximal Level": round(zone_proximal, 2),
                    "LTF Execution Price": round(ltf_close, 2),
                    "Action Status": f"🎯 LTF Testing HTF Zone"
                }
        return None
    except Exception:
        return None

# --- SIDEBAR INTERFACE ---
with st.sidebar:
    st.header("1. Target Market Universe")
    sector_input = st.selectbox("Select Target Segment:", [
        "F&O Active Stocks (210+)", "NIFTY 50", "NIFTY Bank", "NIFTY IT", "NIFTY 500"
    ])
    
    st.divider()
    st.header("2. Dual-TF Settings")
    st.markdown("*Map the Base on the HTF, Execute on the LTF.*")
    
    htf_input = st.selectbox("Higher Timeframe (Macro Base):", ["1 Month", "1 Week", "1 Day"], index=1)
    ltf_input = st.selectbox("Lower Timeframe (Micro Trigger):", ["1 Day", "1 Hour", "75 Min", "15 Min"], index=0)
    
    st.divider()
    st.header("3. Boring Candle Params")
    mode_filter = st.selectbox("Zone Direction:", ["All", "Demand", "Supply"])
    
    col1, col2 = st.columns(2)
    with col1:
        min_base_input = st.number_input("Min Base", min_value=1, max_value=3, value=1)
    with col2:
        max_base_input = st.number_input("Max Base", min_value=2, max_value=6, value=4)
        
    sr_tolerance = st.slider("LTF Entry Proximity (%)", 0.1, 3.0, 1.0, step=0.1, help="How close the LTF price needs to be to the HTF Proximal line to trigger an alert.")
    
    st.divider()
    execute_button = st.button("🚀 LAUNCH DUAL-TF SCAN", type="primary", use_container_width=True)

# --- EXECUTION CONTROL CONTROLLER ---
if execute_button:
    symbols_list = get_sector_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** for {htf_input} Bases triggering on the {ltf_input} chart...")
    
    tf_configs = {
        "15 Min": {"period": "60d", "interval": "15m"},
        "75 Min": {"period": "60d", "interval": "15m", "custom": "75 Min"},
        "1 Hour": {"period": "730d", "interval": "1h"},
        "1 Day": {"period": "2y", "interval": "1d"},
        "1 Week": {"period": "5y", "interval": "1wk"},
        "1 Month": {"period": "10y", "interval": "1mo"}
    }
    
    htf_cfg = tf_configs[htf_input]
    ltf_cfg = tf_configs[ltf_input]
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Spawning multithreaded pipelines...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(
                analyze_dual_tf, ticker, htf_cfg, ltf_cfg, 
                min_base_input, max_base_input, mode_filter, sr_tolerance
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
            progress_ui.progress(percent_complete, text=f"Analyzing Multi-TF Structure: {completed_count}/{len(symbols_list)}")
            
            # Micro-throttle to protect against IP rate limits on large F&O list
            if completed_count % 50 == 0:
                time.sleep(0.5)
            
    progress_ui.empty()
    
    # --- DISPLAY ANALYTICAL MATRIX SHEET ---
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Verified Complete: Found **{len(results_df)}** stocks with LTF price resting in a Macro HTF Base.")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks match these structural constraints right now. Try increasing your LTF Entry Proximity (%) to catch near-misses.")
