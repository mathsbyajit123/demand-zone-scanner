import yfinance as yf
import pandas as pd

# Define Sector Watchlists or Custom Tickers
SECTORS = {
    "IT": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "BANK": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"],
    "AUTO": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "BAJAJ-AUTO.NS"],
    "US_TECH": ["AAPL", "NVDA", "MSFT", "AMZN", "GOOGL"]
}

def scan_pullback_stocks(sector_name="BANK", timeframe="1d"):
    """
    timeframe options: '1d' for Daily, '1wk' for Weekly
    """
    tickers = SECTORS.get(sector_name, [])
    results = []

    for ticker in tickers:
        # Fetch price data
        df = yf.download(ticker, period="1y", interval=timeframe, progress=False)
        if df.empty or len(df) < 50:
            continue
            
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Calculate Indicators
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()

        latest = df.iloc[-1]

        # 1. Uptrend Condition: Price & 20 EMA above 50 EMA
        in_uptrend = (latest['Close'] > latest['EMA_50']) and (latest['EMA_20'] > latest['EMA_50'])

        # 2. Pullback Condition: Low touches within 1.5% of 20 EMA, Close holds near/above
        near_20_ema = (latest['Low'] <= latest['EMA_20'] * 1.015) and (latest['Close'] >= latest['EMA_20'] * 0.985)

        # 3. Low Volume Condition: Pullback volume < 20-period average volume
        low_volume = latest['Volume'] < latest['Vol_SMA_20']

        if in_uptrend and near_20_ema and low_volume:
            results.append({
                "Ticker": ticker,
                "Sector": sector_name,
                "Close": round(float(latest['Close']), 2),
                "EMA_20": round(float(latest['EMA_20']), 2),
                "Vol_Ratio": round(float(latest['Volume'] / latest['Vol_SMA_20']), 2)
            })

    return pd.DataFrame(results)

# Example Usage: Run scan on 'BANK' sector with '1d' (Daily) timeframe
matching_stocks = scan_pullback_stocks(sector_name="BANK", timeframe="1d")
print(matching_stocks)
