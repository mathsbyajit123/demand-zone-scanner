import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings

# Suppress pandas warnings for cleaner terminal output
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ SCANNER CONFIGURATION
# ==========================================
# Add your stock tickers here (Use .NS suffix for Indian NSE stocks, e.g., REDINGTON.NS)
TICKERS = [
    "REDINGTON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", 
    "INFY.NS", "TATASTEEL.NS", "SBIN.NS", "AAPL", "MSFT"
]

# Flexible Timeframe Options: '1d' for Daily, '1wk' for Weekly
TIMEFRAME = "1d" 

# How many past candles to fetch to ensure EMAs calculate correctly
LOOKBACK_PERIODS = 150 
# ==========================================

def calculate_indicators(df):
    """Calculates EMAs and Volume SMA."""
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    return df.dropna()

def check_setup(ticker, df):
    """Scans the dataframe for the specific 21/44 Pullback & HH setup."""
    if len(df) < 50:
        return None
        
    df = calculate_indicators(df)
    
    # 1. Find the last time 21 EMA crossed above 44 EMA
    cross_ups = (df['EMA_21'] > df['EMA_44']) & (df['EMA_21'].shift(1) <= df['EMA_44'].shift(1))
    
    if not cross_ups.any():
        return None # No crossover found in lookback period
        
    last_cross_idx = cross_ups[::-1].idxmax()
    post_cross = df.loc[last_cross_idx:]
    
    # Needs at least a few days of data after cross to form a structure
    if len(post_cross) < 3: 
        return None

    # 2. Identify the Swing High (The Resistance / CHoCH level)
    swing_high = post_cross['High'].max()
    
    # 3. Check for the Retracement (Dry Volume + Touches EMA Zone)
    # Rules: Low touches or goes below 21 EMA, Close stays above 44 EMA, Volume is below 20 SMA
    pullback_days = post_cross[
        (post_cross['Low'] <= post_cross['EMA_21']) & 
        (post_cross['Close'] >= post_cross['EMA_44']) & 
        (post_cross['Volume'] < post_cross['Vol_SMA_20'])
    ]
    
    if pullback_days.empty:
        return None # No valid dry volume pullback occurred yet
        
    # 4. Determine Current Market State (Based on the latest completed candle)
    latest = post_cross.iloc[-1]
    
    # Check if the most recent candle is currently sitting in the accumulation zone
    in_accumulation_zone = (
        (latest['Low'] <= latest['EMA_21']) and 
        (latest['Close'] >= latest['EMA_44']) and 
        (latest['Volume'] < latest['Vol_SMA_20'])
    )
    
    # Check if the most recent candle has broken out above the swing high (HH Confirmed)
    hh_confirmed = latest['Close'] > swing_high
    
    if hh_confirmed:
        return {"Ticker": ticker, "Status": "🔥 Breakout Confirmed (HH)", "Swing High": round(swing_high, 2), "Latest Close": round(latest['Close'], 2)}
    elif in_accumulation_zone:
        return {"Ticker": ticker, "Status": "📉 In Pullback Zone (HL)", "Swing High": round(swing_high, 2), "Latest Close": round(latest['Close'], 2)}
    
    return None

def main():
    print(f"\n🚀 Running Market Structure Scanner...")
    print(f"Timeframe: {TIMEFRAME.upper()} | Tickers to Scan: {len(TICKERS)}\n")
    print("-" * 65)
    print(f"{'TICKER':<15} | {'STATUS':<28} | {'BREAKOUT LVL':<12} | {'CURRENT'}")
    print("-" * 65)
    
    results_found = False
    
    for ticker in TICKERS:
        try:
            # Fetch data from Yahoo Finance
            df = yf.download(ticker, period="1y", interval=TIMEFRAME, progress=False)
            if df.empty:
                continue
                
            # Flatten multi-index columns if they exist (happens in newer yfinance versions)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            result = check_setup(ticker, df)
            
            if result:
                results_found = True
                print(f"{result['Ticker']:<15} | {result['Status']:<28} | {result['Swing High']:<12} | {result['Latest Close']}")
                
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            
    print("-" * 65)
    if not results_found:
        print("No stocks currently meet the setup criteria.")
    print("Scan Complete.\n")

if __name__ == "__main__":
    main()
