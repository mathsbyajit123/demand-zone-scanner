import yfinance as yf
import pandas as pd
import numpy as np
import warnings

# Suppress pandas warnings for cleaner terminal output
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ SCANNER CONFIGURATION
# ==========================================
TICKERS = [
    "REDINGTON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", 
    "INFY.NS", "TATASTEEL.NS", "SBIN.NS", "AAPL", "MSFT"
]

# Flexible Timeframe Options: '1d' for Daily, '1wk' for Weekly
TIMEFRAME = "1d" 

# Set to True if running DURING live market hours (Ignores incomplete today's bar)
# Set to False if running AFTER market close
IGNORE_LIVE_CANDLE = True 
# ==========================================

def calculate_indicators(df):
    """Calculates EMAs and Volume SMA."""
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    return df.dropna()

def check_setup(ticker, df):
    """Scans the dataframe for the specific 21/44 Pullback & HH setup."""
    
    # If market is currently open, drop the incomplete live candle
    if IGNORE_LIVE_CANDLE and len(df) > 0:
        df = df.iloc[:-1]

    if len(df) < 50:
        return None
        
    df = calculate_indicators(df)
    
    # 1. Find the last time 21 EMA crossed above 44 EMA
    cross_ups = (df['EMA_21'] > df['EMA_44']) & (df['EMA_21'].shift(1) <= df['EMA_44'].shift(1))
    
    if not cross_ups.any():
        return None # No crossover found
        
    last_cross_idx = cross_ups[::-1].idxmax()
    post_cross = df.loc[last_cross_idx:]
    
    # Needs at least 3 candles after the cross to establish a valid structure
    if len(post_cross) < 3: 
        return None

    # 2. Identify Swing High from PAST candles (Excluding the latest candle being evaluated)
    prior_candles = post_cross.iloc[:-1]
    if prior_candles.empty:
        return None
        
    swing_high = prior_candles['High'].max()
    
    # 3. Check for Retracement (Dry Volume + Touched EMA Zone in prior structure)
    pullback_days = prior_candles[
        (prior_candles['Low'] <= prior_candles['EMA_21']) & 
        (prior_candles['Close'] >= prior_candles['EMA_44']) & 
        (prior_candles['Volume'] < prior_candles['Vol_SMA_20'])
    ]
    
    if pullback_days.empty:
        return None # No valid dry volume pullback occurred yet
        
    # 4. Evaluate Current Completed Candle
    latest = post_cross.iloc[-1]
    
    # Check if latest candle is sitting in the accumulation zone
    in_accumulation_zone = (
        (latest['Low'] <= latest['EMA_21']) and 
        (latest['Close'] >= latest['EMA_44']) and 
        (latest['Volume'] < latest['Vol_SMA_20'])
    )
    
    # Check if latest candle closed strictly ABOVE the prior swing high
    hh_confirmed = latest['Close'] > swing_high
    
    if hh_confirmed:
        return {
            "Ticker": ticker, 
            "Status": "🔥 Breakout Confirmed (HH)", 
            "Swing High": round(float(swing_high), 2), 
            "Latest Close": round(float(latest['Close']), 2)
        }
    elif in_accumulation_zone:
        return {
            "Ticker": ticker, 
            "Status": "📉 In Pullback Zone (HL)", 
            "Swing High": round(float(swing_high), 2), 
            "Latest Close": round(float(latest['Close']), 2)
        }
    
    return None

def main():
    print(f"\n🚀 Running Market Structure Scanner...")
    print(f"Timeframe: {TIMEFRAME.upper()} | Live Candle Ignored: {IGNORE_LIVE_CANDLE} | Tickers: {len(TICKERS)}\n")
    print("-" * 65)
    print(f"{'TICKER':<15} | {'STATUS':<28} | {'SWING HIGH':<12} | {'CURRENT'}")
    print("-" * 65)
    
    results_found = False
    
    for ticker in TICKERS:
        try:
            df = yf.download(ticker, period="1y", interval=TIMEFRAME, progress=False, auto_adjust=True)
            if df.empty:
                continue
                
            # Flatten multi-index columns if present (compatibility with newer yfinance versions)
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
