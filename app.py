# ==========================================
# 2. DATA FETCHER (UPGRADED WITH FIREWALL BYPASS)
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    # Heavy browser disguise to bypass NSE Cloud Block
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1'
    }
    
    # Emergency Backup List (Top 50 Highly Liquid Indian Stocks)
    fallback_tickers = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "ITC.NS",
        "SBIN.NS", "BHARTIARTL.NS", "LT.NS", "BAJFINANCE.NS", "HINDUNILVR.NS",
        "AXISBANK.NS", "MARUTI.NS", "SUNPHARMA.NS", "KOTAKBANK.NS", "TITAN.NS",
        "ONGC.NS", "TATASTEEL.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS",
        "ULTRACEMCO.NS", "ASIANPAINT.NS", "COALINDIA.NS", "BAJAJFINSV.NS",
        "TATAMOTORS.NS", "HCLTECH.NS", "ADANIPORTS.NS", "GRASIM.NS", "JSWSTEEL.NS",
        "TECHM.NS", "HINDALCO.NS", "WIPRO.NS", "EICHERMOT.NS", "BRITANNIA.NS",
        "INDUSINDBK.NS", "CIPLA.NS", "APOLLOHOSP.NS", "HEROMOTOCO.NS", "TATACONSUM.NS"
    ]
    
    url = sector_options.get(sector_name)
    
    try:
        # Use a Session to handle cookies exactly like a real browser
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            return [str(symbol).strip() + ".NS" for symbol in df['Symbol']]
        else:
            st.sidebar.warning(f"NSE Blocked the request (Error {response.status_code}). Switching to backup list.")
            return fallback_tickers
            
    except Exception as e:
        st.sidebar.warning("NSE Firewall blocked the cloud server. Using emergency backup list.")
        return fallback_tickers
