import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- PAGE SETUP ---
st.set_page_config(page_title="Institutional Zone Scanner Pro", layout="wide")

# --- TICKER REGISTRY ---
TICKERS = {
    "NIFTY 50": ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'SBI.NS', 'ITC.NS', 'AXISBANK.NS', 'LT.NS', 'KOTAKBANK.NS'],
    "NIFTY 100": ['ADANIENT.NS', 'BAJFINANCE.NS', 'HAL.NS', 'DMART.NS', 'CHOLAFIN.NS', 'PIDILITIND.NS', 'BEL.NS', 'BAJAJ-AUTO.NS', 'SIEMENS.NS', 'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS'],
    "NIFTY MIDCAP 100": ['VOLTAS.NS', 'TRENT.NS', 'FEDERALBNK.NS', 'IDFCFIRSTB.NS', 'AUBANK.NS', 'BANDHANBNK.NS', 'ESCORT.NS', 'DIXON.NS', 'COFORGE.NS', 'MAXHEALTH.NS'],
    "NIFTY SMALLCAP 250": ['SUZLON.NS', 'IRFC.NS', 'ZOMATO.NS', 'RVNL.NS', 'BSE.NS', 'HUDCO.NS', 'IFCI.NS', 'CENTURYPLY.NS', 'RITES.NS', 'SJVN.NS'],
    "NIFTY 500 (Top Sectoral)": ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'TRENT.NS', 'ZOMATO.NS', 'SUZLON.NS', 'TATAMOTORS.NS', 'SUNPHARMA.NS', 'NTPC.NS', 'ONGC.NS']
}

# --- ADVANCED TIMEFRAME RESAMPLER ---
def get_resampled_data(ticker, timeframe_opt, lookback_years):
    period_map = {"3y": "3y", "5y": "5y", "10y": "10y"}
    p = period_map.get(lookback_years, "5y")
    
    if timeframe_opt in ['1d', '1wk', '1mo']:
        df = yf.download(ticker, period=p, interval=timeframe_opt, progress=False)
        return df
        
    df = yf.download(ticker, period=p, interval='1mo', progress=False)
    if df.empty:
        return df
        
    if timeframe_opt == '3mo':
        rule = '3ME'
    elif timeframe_opt == '6mo':
        rule = '6ME'
    elif timeframe_opt == '12mo':
        rule = '12ME'
    else:
        return df
        
    resampled = df.resample(rule).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return resampled

# --- MATRIX TRACKING ENGINE ---
def process_zones(df, min_base, max_base, min_legout_pct):
    if df.empty or len(df) < 5:
        return []
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    safe_range = np.where(df['Range'] == 0, 0.001, df['Range'])
    
    df['Body_Pct'] = (df['Body'] / safe_range) * 100
    df['Is_Boring'] = df['Body_Pct'] <= 50
    df['Is_Exciting'] = df['Body_Pct'] > 50
    df['Is_Bullish'] = df['Close'] > df['Open']
    
    detected_zones = []
    current_price = float(df['Close'].iloc[-1])
    current_low = float(df['Low'].iloc[-1])
    
    for i in range(len(df) - 4):
        leg_in = df.iloc[i]
        if not leg_in['Is_Exciting']:
            continue
            
        for b_count in range(min_base, max_base + 1):
            if i + 1 + b_count >= len(df):
                continue
                
            base_sequence = df.iloc[i+1 : i+1+b_count]
            if not all(base_sequence['Is_Boring']):
                continue
                
            legout_idx = i + 1 + b_count
            legout_count = 0
            legout_pcts = []
            
            while legout_idx < len(df):
                cand = df.iloc[legout_idx]
                if cand['Is_Exciting'] and cand['Is_Bullish'] and cand['Body_Pct'] >= min_legout_pct:
                    legout_count += 1
                    legout_pcts.append(cand['Body_Pct'])
                    legout_idx += 1
                else:
                    break
            
            if legout_count >= 2:
                proximal = float(max(base_sequence['Open'].max(), base_sequence['Close'].max()))
                distal = float(base_sequence['Low'].min())
                
                post_zone_df = df.iloc[i + 1 + b_count + legout_count:]
                
                if post_zone_df.empty:
                    status = "Fresh (Unmitigated)"
                else:
                    historical_min_low = float(post_zone_df['Low'].min())
                    if historical_min_low < distal:
                        status = "Zone Broken"
                    elif historical_min_low <= proximal:
                        status = "Mitigated (Tested)"
                    else:
                        status = "Fresh (Unmitigated)"
                
                if status != "Zone Broken":
                    if current_low <= proximal and current_low >= distal:
                        status = "Just Touched / In the Zone"
                    elif current_price > proximal and (current_price - proximal) / proximal <= 0.03:
                        status = "Just Approached (Within 3%)"
                        
                    avg_legout_size = sum(legout_pcts) / len(legout_pcts) if legout_pcts else 0
                    
                    detected_zones.append({
                        'Date Formed': df.index[i+1].strftime('%Y-%m-%d'),
                        'Base Candles': int(b_count),
                        'Leg-Out Candles': int(legout_count),
                        'Avg Leg-Out Body %': f"{round(avg_legout_size, 1)}%",
                        'Proximal (Entry)': round(proximal, 2),
                        'Distal (Stop Loss)': round(distal, 2),
                        'Current Price': round(current_price, 2),
                        'Zone Status': status
                    })
                break
                
    return detected_zones

# --- USER INTERFACE ---
st.title("⚡ Structural Supply & Demand Zone Engine")
st.markdown("Automated algorithmic tracking engine for structural market imbalances.")

# SIDEBAR ARCHITECTURE
st.sidebar.header("🎯 Scanner Filter Controls")
index_choice = st.sidebar.selectbox("Market Index Group", list(TICKERS.keys()))

st.sidebar.subheader("Time Horizon Matrix")
tf_choice = st.sidebar.selectbox("Candlestick Interval", ['1d', '1wk', '1mo', '3mo', '6mo', '12mo'], index=0)
lookback_choice = st.sidebar.selectbox("Data Set History", ['3y', '5y', '10y'], index=1)

st.sidebar.subheader("Zone Sizing Restrictions")
min_base = st.sidebar.selectbox("Minimum Base Candles", [1, 2, 3, 4, 5, 6], index=0)
max_base = st.sidebar.selectbox("Maximum Base Candles", [1, 2, 3, 4, 5, 6], index=1)

if min_base > max_base:
    min_base, max_base = max_base, min_base

min_legout_slider = st.sidebar.slider("Minimum Leg-Out Body Power (%)", 51, 100, 55)

st.sidebar.subheader("Filter Status Output")
status_filters = st.sidebar.multiselect(
    "Include Status States", 
    ["Fresh (Unmitigated)", "Just Approached (Within 3%)", "Just Touched / In the Zone", "Mitigated (Tested)"],
    default=["Fresh (Unmitigated)", "Just Approached (Within 3%)", "Just Touched / In the Zone"]
)

# EXECUTION CONSOLE
if st.button("🔍 Run Algorithmic Market Scan", type="primary"):
    selected_tickers = TICKERS[index_choice]
    compiled_results = []
    
    prog_bar = st.progress(0)
    status_msg = st.empty()
    
    for tracking_idx, symbol in enumerate(selected_tickers):
        status_msg.text(f"Processing structural matrix profiles for: {symbol}")
        try:
            historical_data = get_resampled_data(symbol, tf_choice, lookback_choice)
            discovered_zones = process_zones(historical_data, min_base, max_base, min_legout_slider)
            
            for zone_data in discovered_zones:
                zone_data['Ticker'] = symbol.replace('.NS', '')
                if zone_data['Zone Status'] in status_filters:
                    compiled_results.append(zone_data)
        except Exception as system_err:
            pass
        prog_bar.progress((tracking_idx + 1) / len(selected_tickers))
        
    status_msg.text("Scanning protocol concluded.")
    
    # RENDER METRIC GRID
    if compiled_results:
        output_df = pd.DataFrame(compiled_results)
        output_df = output_df[['Ticker', 'Zone Status', 'Current Price', 'Proximal (Entry)', 'Distal (Stop Loss)', 'Date Formed', 'Base Candles', 'Leg-Out Candles', 'Avg Leg-Out Body %']]
        
        st.success(f"Discovered {len(output_df)} structural setup configurations matching parameters!")
        
        def render_visual_states(val):
            if "In the Zone" in str(val):
                return 'background-color: #f8d7da; color: #721c24; font-weight: bold; border-left: 4px solid red;'
            elif "Approached" in str(val):
                return 'background-color: #fff3cd; color: #856404; font-weight: bold;'
            elif "Fresh" in str(val):
                return 'background-color: #d4edda; color: #155724; font-weight: bold;'
            return 'color: #6c757d;'

        # FIX: Changed 'applymap' to 'map' to support the newest version of Pandas
        st.dataframe(
            output_df.style.map(render_visual_states, subset=['Zone Status']), 
            use_container_width=True
        )
    else:
        st.warning("No dynamic structural supply/demand footprints tracked with current filter metrics.")
