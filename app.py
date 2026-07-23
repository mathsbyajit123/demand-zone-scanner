import yfinance as yf
import pandas as pd
import warnings
import sys

warnings.filterwarnings('ignore')

TICKERS = [
    "REDINGTON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", 
    "INFY.NS", "TATASTEEL.NS", "SBIN.NS", "AAPL", "MSFT"
]
TIMEFRAME = "1d" 
IGNORE_LIVE_CANDLE = True 

def calculate_indicators(df):
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    return df.dropna()

def check_setup(ticker, df):
    if IGNORE_LIVE_CANDLE and len(df) > 0:
        df = df.iloc[:-1]

    if len(df) < 50:
        return None
        
    df = calculate_indicators(df)
    
    cross_ups = (df['EMA_21'] > df['EMA_44']) & (df['EMA_21'].shift(1) <= df['EMA_44'].shift(1))
    if not cross_ups.any(): return None 
        
    last_cross_idx = cross_ups[::-1].idxmax()
    post_cross = df.loc[last_cross_idx:]
    if len(post_cross) < 3: return None

    prior_candles = post_cross.iloc[:-1]
    if prior_candles.empty: return None
        
    swing_high = prior_candles['High'].max()
    
    pullback_days = prior_candles[
        (prior_candles['Low'] <= prior_candles['EMA_21']) & 
        (prior_candles['Close'] >= prior_candles['EMA_44']) & 
        (prior_candles['Volume'] < prior_candles['Vol_SMA_20'])
    ]
    if pullback_days.empty: return None 
        
    latest = post_cross.iloc[-1]
    
    in_accumulation_zone = (
        (latest['Low'] <= latest['EMA_21']) and 
        (latest['Close'] >= latest['EMA_44']) and 
        (latest['Volume'] < latest['Vol_SMA_20'])
    )
    hh_confirmed = latest['Close'] > swing_high
    
    if hh_confirmed:
        return {"Status": "🔥 Breakout Confirmed (HH)", "Swing High": round(float(swing_high), 2), "Latest": round(float(latest['Close']), 2)}
    elif in_accumulation_zone:
        return {"Status": "📉 In Pullback Zone (HL)", "Swing High": round(float(swing_high), 2), "Latest": round(float(latest['Close']), 2)}
    return None

def main():
    print("=" * 70)
    print("🚀 RUNNING MARKET STRUCTURE SCANNER...")
    print(f"Settings -> Timeframe: {TIMEFRAME} | Ignoring Today's Live Candle: {IGNORE_LIVE_CANDLE}")
    print("=" * 70)
    
    results = []
    
    for ticker in TICKERS:
        # sys.stdout.flush forces the terminal to print this immediately before downloading
        print(f"-> Fetching data for {ticker}... ", end="", flush=True) 
        
        try:
            # Using Ticker().history() is much more stable than download() for individual stocks
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y", interval=TIMEFRAME)
            
            if df.empty:
                print("❌ No data found.")
                continue
                
            print("✅ Data received. Scanning...", end="", flush=True)
            result = check_setup(ticker, df)
            
            if result:
                print(f" 🎯 SETUP FOUND: {result['Status']}")
                result['Ticker'] = ticker
                results.append(result)
            else:
                print(" ➖ No setup.")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            
    print("\n" + "=" * 70)
    print("📊 FINAL SCAN RESULTS")
    print("=" * 70)
    
    if results:
        print(f"{'TICKER':<15} | {'STATUS':<28} | {'SWING HIGH':<12} | {'CURRENT'}")
        print("-" * 70)
        for r in results:
            print(f"{r['Ticker']:<15} | {r['Status']:<28} | {r['Swing High']:<12} | {r['Latest']}")
    else:
        print("No stocks met the criteria today.")
    
    print("=" * 70)
    
    # THIS KEEPS THE WINDOW OPEN IF YOU DOUBLE-CLICKED THE FILE

if __name__ == "__main__":
    main()
