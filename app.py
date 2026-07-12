# --- LIVE NSE F&O EXTRACTION ENGINE ---
@st.cache_data(ttl=86400) # Caches the live list for 24 hours to prevent IP bans
def get_sector_symbols(sector_name):
    if sector_name == "F&O Active Stocks (210+)":
        try:
            # Dynamically fetch the official live F&O lot size list directly from NSE
            url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
            df = pd.read_csv(url)
            
            # Clean up whitespace in column names and data
            df.columns = df.columns.str.strip()
            symbols = df['SYMBOL'].str.strip().unique()
            
            # Filter out broad market indices to only keep individual equity stocks
            indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
            active_fo_stocks = [str(sym) + ".NS" for sym in symbols if sym not in indices]
            
            return active_fo_stocks
        except Exception:
            st.error("NSE Server Timeout. Loading backup core liquidity tickers...")
            return ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]
        
    # Standard Sector Lists
    urls = {
        "NIFTY 50 (Large Cap)": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        "NIFTY Next 50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        "NIFTY Bank": "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        "NIFTY IT": "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
        "NIFTY Midcap 100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        "NIFTY Smallcap 100": "https://archives.nseindia.com/content/indices/ind_niftysmallcap100list.csv",
        "NIFTY 500 (All Sectors)": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    }
    
    try:
        df = pd.read_csv(urls[sector_name])
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol'].tolist()]
    except Exception:
        return ["RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TCS.NS", "INFY.NS", "SBIN.NS"]
