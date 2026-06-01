import streamlit as st
import yfinance as yf
import pandas as pd

# 1. Define Indian Stock Tickers (You can expand this list with NIFTY 500 stocks)
NIFTY_50 = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS']
NIFTY_MIDCAP = ['VOLTAS.NS', 'TRENT.NS', 'FEDERALBNK.NS', 'IDFCFIRSTB.NS']
SMALL_CAP = ['SUZLON.NS', 'IRFC.NS', 'ZOMATO.NS']
ALL_TICKERS = NIFTY_50 + NIFTY_MIDCAP + SMALL_CAP

# 2. Demand Zone Logic
def find_demand_zones(df):
    if df.empty:
        return []
        
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    # Avoid division by zero on flat candles
    safe_range = df['Range'].replace(0, 0.001)
    
    # Identify Candle Types
    df['Is_Boring'] = (df['Body'] / safe_range) <= 0.5
    df['Is_Exciting'] = (df['Body'] / safe_range) > 0.5
    df['Is_Bullish'] = df['Close'] > df['Open']
    
    zones = []
    
    # Loop to find: Leg-In -> Base (Boring) -> 2x Leg-Out (Exciting Bullish)
    for i in range(len(df) - 3):
        leg_in = df.iloc[i]
        base = df.iloc[i+1]
        leg_out_1 = df.iloc[i+2]
        leg_out_2 = df.iloc[i+3]
        
        if (base['Is_Boring'] and 
            leg_out_1['Is_Exciting'] and leg_out_1['Is_Bullish'] and 
            leg_out_2['Is_Exciting'] and leg_out_2['Is_Bullish'] and 
            leg_in['Is_Exciting']):
            
            proximal = max(base['Open'], base['Close'])
            distal = base['Low']
            
            zones.append({
                'Date': df.index[i+1].strftime('%Y-%m-%d'),
                'Proximal Line': round(proximal, 2),
                'Distal Line': round(distal, 2)
            })
            
    return zones

# 3. Streamlit Interface
st.title("📈 Demand Zone Swing Trade Scanner")
st.write("Scans for: Exciting Leg-in ➡️ Boring Base ➡️ 2x Exciting Bullish Leg-outs")

timeframe = st.selectbox("Select Timeframe", ['1d', '1wk', '1mo'])
lookback = st.selectbox("Data Lookback Period", ['3mo', '6mo', '1y', '2y'])

if st.button("Scan Market"):
    st.write("Scanning tickers...")
    results = []
    
    for ticker in ALL_TICKERS:
        try:
            # Fetch data
            data = yf.download(ticker, period=lookback, interval=timeframe, progress=False)
            zones = find_demand_zones(data)
            
            if zones:
                for zone in zones:
                    results.append({
                        'Ticker': ticker.replace('.NS', ''),
                        'Base Date': zone['Date'],
                        'Proximal Line (Entry)': zone['Proximal Line'],
                        'Distal Line (Stop)': zone['Distal Line']
                    })
        except Exception as e:
            continue
            
    if results:
        st.success("Scan Complete! Demand Zones Found:")
        st.dataframe(pd.DataFrame(results))
    else:
        st.warning("No Demand Zones found with the current criteria.")
