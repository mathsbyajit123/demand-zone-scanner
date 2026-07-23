import yfinance as yf
import pandas as pd
import warnings
import traceback

# Suppress warnings
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ SCANNER CONFIGURATION
# ==========================================
TICKERS = [
    "REDINGTON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", 
    "INFY.NS", "TATASTEEL.NS", "SBIN.NS", "AAPL", "MSFT"
]
TIMEFRAME = "1d"

def calculate_indicators(df):
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA_44'] = df['Close'].ewm(span=44, adjust=False).mean()
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    return df

def check_setup(ticker, df):
    # 1. LIVE MARKET CLEANUP: Drop corrupted rows with missing data instantly
    df = df.dropna()
    
    # 2. IGNORE TODAY'S INCOMPLETE CANDLE: 
    if len(df) > 0:
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
        return {"Ticker": ticker, "Status": "🔥 Breakout Confirmed (HH)", "Swing High": round(float(swing_high), 2), "Latest": round(float(latest['Close']), 2)}
    elif in_accumulation_zone:
        return {"Ticker": ticker, "Status": "📉 In Pullback Zone (HL)", "Swing High": round(float(swing_high), 2), "Latest": round(float(latest['Close']), 2)}
    return None

def main():
    print("=" * 75)
    print("🚀 RUNNING MARKET STRUCTURE SCANNER (LIVE MARKET SAFE)...")
    print("=" * 75)
    
    results = []
    
    for ticker in TICKERS:
        # flush=True forces the terminal to print this BEFORE it freezes on the download
        print(f"-> Fetching data for {ticker:<15} ... ", end="", flush=True) 
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y", interval=TIMEFRAME)
            
            if df.empty:
                print("❌ No data found.")
                continue
                
            print("✅ Data received. Scanning...", end="", flush=True)
            result = check_setup(ticker, df)
            
            if result:
                print(f" 🎯 SETUP FOUND: {result['Status']}")
                results.append(result)
            else:
                print(" ➖ No setup.")
                
        except Exception as e:
            # If Yahoo Finance sends broken data, it prints the error but DOES NOT crash the script
            print(f"❌ Error: {e}")
            
    print("\n" + "=" * 75)
    print("📊 FINAL SCAN RESULTS")
    print("=" * 75)
    
    if results:
        print(f"{'TICKER':<15} | {'STATUS':<28} | {'SWING HIGH':<12} | {'CURRENT'}")
        print("-" * 75)
        for r in results:
            print(f"{r['Ticker']:<15} | {r['Status']:<28} | {r['Swing High']:<12} | {r['Latest']}")
    else:
        print("No stocks met the criteria today.")
    print("=" * 75)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n❌ A FATAL ERROR OCCURRED:")
        traceback.print_exc()
    finally:
        # This absolutely guarantees the black screen stays open so you can read it
        input("\nPress Enter to exit...")
