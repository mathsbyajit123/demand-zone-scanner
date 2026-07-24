import yfinance as yf
import pandas as pd

# Define Sector Watchlists
SECTORS = {
    "IT": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS"],
    "BANK": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS"],
    "AUTO": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS"],
    "US_TECH": ["AAPL", "NVDA", "MSFT", "AMZN"]
}

def scan_depth_pullback(sector_name="BANK", timeframe="1d"):
    """
    timeframe: 
      - '1d' -> Daily scan with 4% to 7% retracement from recent peak
      - '1wk' -> Weekly scan with 10% to 12% retracement from recent peak
    """
    tickers = SECTORS.get(sector_name, [])
    results = []

    # Set parameters dynamically based on timeframe
    if timeframe == '1d':
        min_retrace, max_retrace, lookback = 0.04, 0.07, 20
    elif timeframe == '1wk':
        min_retrace, max_retrace, lookback = 0.10, 0.12, 10
    else:
        raise ValueError("Use '1d' or '1wk'")

    for ticker in tickers:
        df = yf.download(ticker, period="1y", interval=timeframe, progress=False)
        if df.empty or len(df) < max(50, lookback + 5):
            continue
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
        
        # Calculate recent peak excluding the current candle
        df['Recent_Peak'] = df['High'].rolling(window=lookback).max()

        latest = df.iloc[-1]
        prev_peak = df['Recent_Peak'].iloc[-2]

        # 1. Trend Condition: 20 EMA > 50 EMA
        uptrend = latest['EMA_20'] > latest['EMA_50']

        # 2. 20 EMA Pullback Condition: Low touches/dips below 20 EMA, Close stays above
        pullback_touch = (latest['Low'] <= latest['EMA_20']) and (latest['Close'] > latest['EMA_20'])

        # 3. Retracement Depth Condition
        retracement = (prev_peak - latest['Close']) / prev_peak
        depth_match = (min_retrace <= retracement <= max_retrace)

        # 4. Low Volume Condition
        low_volume = latest['Volume'] < latest['Vol_SMA_20']

        if uptrend and pullback_touch and depth_match and low_volume:
            results.append({
                "Ticker": ticker,
                "Sector": sector_name,
                "Close": round(float(latest['Close']), 2),
                "Recent_Peak": round(float(prev_peak), 2),
                "Retracement_%": round(float(retracement * 100), 2),
                "EMA_20": round(float(latest['EMA_20']), 2),
                "Vol_Ratio": round(float(latest['Volume'] / latest['Vol_SMA_20']), 2)
            })

    return pd.DataFrame(results)

# Run Daily Scan (4% to 7% drop)
print("--- Daily Scan Results (4-7% Pullback) ---")
print(scan_depth_pullback(sector_name="BANK", timeframe="1d"))

# Run Weekly Scan (10% to 12% drop)
print("\n--- Weekly Scan Results (10-12% Pullback) ---")
print(scan_depth_pullback(sector_name="BANK", timeframe="1wk"))
