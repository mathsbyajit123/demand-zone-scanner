import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

# --- PAGE SETUP ---
st.set_page_config(page_title="Pro Demand Zone Scanner", layout="wide")

# --- TICKER LISTS (Expandable) ---
TICKERS = {
    "NIFTY 50": ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'SBI.NS', 'BHARTIARTL.NS', 'ITC.NS'],
    "NIFTY MIDCAP": ['VOLTAS.NS', 'TRENT.NS', 'FEDERALBNK.NS', 'IDFCFIRSTB.NS', 'MRF.NS', 'POLYCAB.NS'],
    "NIFTY SMALLCAP": ['SUZLON.NS', 'IRFC.NS', 'ZOMATO.NS', 'RVNL.NS', 'BSE.NS'],
}
# To keep the app fast, we are using top stocks. You can paste all 500 Nifty tickers here later!

# --- DEMAND ZONE LOGIC ---
def check_mitigation(df, zone_end_idx, proximal, distal):
    future_data = df.iloc[zone_end_idx + 1:]
    if future_data.empty:
        return "Fresh (Unmitigated)"
    
    min_future_low = future_data['Low'].min()
    current_price = df['Close'].iloc[-1]
    
    if min_future_low < distal:
        return "Zone Broken"
    elif min_future_low <= proximal:
        return "Mitigated (Tested)"
    else:
        # Check if approaching
        distance = (current_price - proximal) / proximal
        if distance <= 0.05 and distance > 0:
            return "Approaching Zone (Near 5%)"
        return "Fresh (Unmitigated)"

def find_demand_zones(df, min_base, max_base, min_legout_size):
    if df.empty or len(df) < (2 + max_base):
        return []
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    safe_range = df['Range'].replace(0, 0.001)
    
    # Calculate sizes and types
    df['Body_Pct'] = (df['Body'] / safe_range) * 100
    df['Is_Boring'] = df['Body_Pct'] <= 50
    df['Is_Exciting'] = df['Body_Pct'] > 50
    df['Is_Bullish'] = df['Close'] > df['Open']
    
    zones = []
    
    # Scan logic
    for i in range(len(df) - 3 - max_base):
        leg_in = df.iloc[i]
        
        if not leg_in['Is_Exciting']:
            continue
            
        # Try different base lengths
        for b in range(min_base, max_base + 1):
            base_candles = df.iloc[i+1 : i+1+b]
            
            # All base candles must be boring
            if not all(base_candles['Is_Boring']):
                continue
                
            leg_out_1 = df.iloc[i+1+b]
            leg_out_2 = df.iloc[i+2+b]
            
            # Leg outs must be exciting, bullish, and meet size criteria
            if (leg_out_1['Is_Exciting'] and leg_out_1['Is_Bullish'] and leg_out_1['Body_Pct'] >= min_legout_size and
                leg_out_2['Is_Exciting'] and leg_out_2['Is_Bullish'] and leg_out_2['Body_Pct'] >= min_legout_size):
                
                proximal = max(base_candles[['Open', 'Close']].max())
                distal = base_candles['Low'].min()
                
                # Check what happened after the zone
                status = check_mitigation(df, i+2+b, proximal, distal)
                
                # Only keep active/useful zones
                if status != "Zone Broken":
                    zones.append({
                        'Date Formed': df.index[i+1].strftime('%Y-%m-%d'),
                        'Base Candles': b,
                        'Proximal (Entry)': round(proximal, 2),
                        'Distal (Stop)': round(distal, 2),
                        'Status': status,
                        'Current Price': round(df['Close'].iloc[-1], 2)
                    })
                break # Move to next pattern once found
                
    return zones

# --- APP UI ---
st.title("📊 Institutional Demand Zone Scanner")
st.markdown("Scan the Indian market for Leg-in ➡️ Boring Base ➡️ Leg-outs.")

# SIDEBAR CONTROLS
st.sidebar.header("⚙️ Scanner Settings")

selected_sector = st.sidebar.selectbox("Select Index/Sector", ["All Combined"] + list(TICKERS.keys()))

st.sidebar.subheader("Time & Data")
timeframe = st.sidebar.selectbox("Timeframe", ['1d (Daily)', '1wk (Weekly)', '1mo (Monthly)', '3mo (Quarterly)'])
tf_map = {'1d (Daily)': '1d', '1wk (Weekly)': '1wk', '1mo (Monthly)': '1mo', '3mo (Quarterly)': '3mo'}

lookback = st.sidebar.selectbox("Data Lookback", ['1y', '2y', '3y', '5y', '10y'], index=2) # Default 3 years

st.sidebar.subheader("Candle Rules")
base_range = st.sidebar.slider("Number of Base Candles", min_value=1, max_value=6, value=(1, 3))
min_legout = st.sidebar.slider("Min Leg-out Body Size (%)", min_value=51, max_value=100, value=60)

# EXECUTE SCAN
if st.button("🚀 Start Professional Scan", type="primary"):
    
    # Determine tickers to scan
    scan_list = []
    if selected_sector == "All Combined":
        for lst in TICKERS.values():
            scan_list.extend(lst)
    else:
        scan_list = TICKERS[selected_sector]
        
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, ticker in enumerate(scan_list):
        status_text.text(f"Scanning: {ticker}...")
        try:
            data = yf.download(ticker, period=lookback, interval=tf_map[timeframe], progress=False)
            zones = find_demand_zones(data, base_range[0], base_range[1], min_legout)
            
            for z in zones:
                z['Ticker'] = ticker.replace('.NS', '')
                results.append(z)
        except Exception as e:
            pass
            
        progress_bar.progress((idx + 1) / len(scan_list))
        
    status_text.text("Scan Complete!")
    
    # DISPLAY RESULTS
    if results:
        df_results = pd.DataFrame(results)
        # Reorder columns for better reading
        df_results = df_results[['Ticker', 'Status', 'Current Price', 'Proximal (Entry)', 'Distal (Stop)', 'Date Formed', 'Base Candles']]
        
        st.success(f"Found {len(df_results)} Active Demand Zones!")
        
        # Color coding the status column
        def color_status(val):
            if 'Fresh' in val: return 'background-color: #d4edda; color: green'
            elif 'Approaching' in val: return 'background-color: #fff3cd; color: orange'
            elif 'Mitigated' in val: return 'background-color: #e2e3e5; color: gray'
            return ''
            
        st.dataframe(df_results.style.applymap(color_status, subset=['Status']), use_container_width=True)
    else:
        st.warning("No un-broken Demand Zones found with these exact settings. Try adjusting your candle rules.")
