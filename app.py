import yfinance as yf
import pandas as pd

# Define Sector Watchlists (You can add your own tickers)
SECTORS = {
    "IT": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS"],
    "BANK": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS"],
    "AUTO": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS"],
    "US_TECH": ["AAPL", "NVDA", "MSFT", "AMZN"]
}

def scan_strict_pullback(sector_name="BANK", timeframe="1d"):
    """
    timeframe options: '1d' (Daily), '1wk' (Weekly)
    """
    tickers = SECTORS.get(sector_name, [])
    results = []

    for ticker in tickers:
        df = yf.download(ticker, period="1y", interval=timeframe, progress=False)
        if df.empty or len(df) < 50:
            continue
            
        # Handle new yfinance MultiIndex output structure
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()

        latest = df.iloc[-1]

        # 1. Trend: 20 EMA is above 50 EMA
        uptrend = latest['EMA_20'] > latest['EMA_50']

        # 2. Pullback: Low touches/dips below 20 EMA, but Close stays above it
        pullback_touch = (latest['Low'] <= latest['EMA_20']) and (latest['Close'] > latest['EMA_20'])

        # 3. Volume: Current volume is lower than the 20-period average
        low_volume = latest['Volume'] < latest['Vol_SMA_20']

        if uptrend and pullback_touch and low_volume:
            results.append({
                "Ticker": ticker,
                "Sector": sector_name,
                "Close": round(float(latest['Close']), 2),
                "EMA_20": round(float(latest['EMA_20']), 2),
                "Vol_Ratio": round(float(latest['Volume'] / latest['Vol_SMA_20']), 2)
            })

    return pd.DataFrame(results)

# Run scan on 'BANK' sector with '1d' (Daily) timeframe
matching_stocks = scan_strict_pullback(sector_name="BANK", timeframe="1d")
print(matching_stocks)
