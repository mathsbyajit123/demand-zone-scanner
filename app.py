import yfinance as yf
import pandas as pd
import numpy as np

# 1. Configuration & Tickers (Add your Top Nifty stocks here)
TICKERS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

def get_data(ticker, period="60d"):
    """Fetches Daily and 15-minute data, then resamples to 75-minute."""
    # Fetch Daily data (HTF)
    htf_data = yf.download(ticker, period="1y", interval="1d", progress=False)
    
    # Fetch 15m data and resample to 75m (LTF)
    ltf_raw = yf.download(ticker, period=period, interval="15m", progress=False)
    
    # Custom resampling to 75-minute candles for NSE timings
    ltf_data = ltf_raw.resample('75T', offset='15T').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    
    return htf_data, ltf_data

def identify_zones(df, left_bars=3, right_bars=3):
    """Finds Pivot Highs (Supply) and Pivot Lows (Demand)"""
    df['Pivot_Low'] = df['Low'] == df['Low'].rolling(window=left_bars+right_bars+1, center=True).min()
    df['Pivot_High'] = df['High'] == df['High'].rolling(window=left_bars+right_bars+1, center=True).max()
    
    # Create Demand Zone (using the candle body/wicks of the pivot low)
    df['Demand_Zone_High'] = np.where(df['Pivot_Low'], df['High'], np.nan)
    df['Demand_Zone_Low'] = np.where(df['Pivot_Low'], df['Low'], np.nan)
    df['Demand_Zone_High'] = df['Demand_Zone_High'].ffill()
    df['Demand_Zone_Low'] = df['Demand_Zone_Low'].ffill()

    # Create Supply Zone (using the candle body/wicks of the pivot high)
    df['Supply_Zone_High'] = np.where(df['Pivot_High'], df['High'], np.nan)
    df['Supply_Zone_Low'] = np.where(df['Pivot_High'], df['Low'], np.nan)
    df['Supply_Zone_High'] = df['Supply_Zone_High'].ffill()
    df['Supply_Zone_Low'] = df['Supply_Zone_Low'].ffill()
    
    return df

def scan_market(tickers):
    alerts = []
    
    for ticker in tickers:
        try:
            htf, ltf = get_data(ticker)
            
            # Map Zones
            htf = identify_zones(htf) # Daily Zones
            ltf = identify_zones(ltf) # 75m Zones
            
            # 2. Volume Confirmation Setup (20 SMA of Volume)
            ltf['Vol_SMA'] = ltf['Volume'].rolling(20).mean()
            
            # Get latest data points
            latest_price = ltf['Close'].iloc[-1]
            latest_vol = ltf['Volume'].iloc[-1]
            avg_vol = ltf['Vol_SMA'].iloc[-1]
            
            htf_demand_high = htf['Demand_Zone_High'].iloc[-1]
            htf_demand_low = htf['Demand_Zone_Low'].iloc[-1]
            ltf_supply_high = ltf['Supply_Zone_High'].iloc[-1]
            
            # 3. Core Logic Checks
            
            # Condition A: Is price currently interacting with HTF Demand Zone?
            in_htf_demand = (latest_price <= htf_demand_high * 1.01) and (latest_price >= htf_demand_low * 0.99)
            
            # Condition B: Did LTF close above the latest LTF Supply Zone? (Break of Structure)
            ltf_bos = latest_price > ltf_supply_high
            
            # Condition C: Is there a Volume Spike? (> 1.5x average volume)
            volume_confirmed = latest_vol > (1.5 * avg_vol)
            
            # 4. Trigger Alert
            if in_htf_demand and ltf_bos and volume_confirmed:
                alerts.append({
                    "Stock": ticker,
                    "Price": round(latest_price, 2),
                    "HTF_Demand": f"{round(htf_demand_low, 2)} - {round(htf_demand_high, 2)}",
                    "LTF_Supply_Broken": round(ltf_supply_high, 2),
                    "Volume_Spike": f"{round(latest_vol / avg_vol, 1)}x Avg"
                })
                
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            
    return pd.DataFrame(alerts)

# Run Scanner
if __name__ == "__main__":
    print("Scanning for HTF Demand + LTF Structure Break with Volume...")
    results = scan_market(TICKERS)
    
    if not results.empty:
        print("\n🔥 HIGH PROBABILITY SETUPS DETECTED 🔥")
        print(results.to_string(index=False))
    else:
        print("\nNo setups found in the current scan. Wait for the market to align.")
