import pandas as pd
import yfinance as yf
import requests
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set DEBUG = True if you want to see detailed error messages for failing stocks
DEBUG = False

def get_nifty500_tickers():
    """Fetch official Nifty 500 ticker symbols with reliable fallback"""
    url = "https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/ind_nifty500list.csv"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        tickers = [f"{symbol.strip()}.NS" for symbol in df['Symbol'].dropna().unique()]
        if len(tickers) > 100:
            return tickers
    except Exception as e:
        if DEBUG:
            print(f"[!] Ticker list download failed: {e}")
            
    # Fallback liquid universe if URL fails
    print("[i] Using fallback Nifty top stock list...")
    return [
        "RELIANCE.NS", "TCS.NS", "INFY.NS", "ICICIBANK.NS", "BHARTIARTL.NS", 
        "HDFCBANK.NS", "SBIN.NS", "LT.NS", "HINDUNILVR.NS", "ITC.NS",
        "AXISBANK.NS", "KOTAKBANK.NS", "M&M.NS", "TATAMOTORS.NS", "NTPC.NS",
        "POWERGRID.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "BAJFINANCE.NS"
    ]

def scan_stock(ticker):
    """Applies Weekly Trend + Daily Boring Candle & Fresh Demand Zone Rules"""
    try:
        # Fetch data fast
        stock = yf.Ticker(ticker)
        df_daily = stock.history(period="1y", interval="1d")
        
        if df_daily.empty or len(df_daily) < 100:
            return None

        # Fix index timezone if present
        if df_daily.index.tz is not None:
            df_daily.index = df_daily.index.tz_localize(None)

        # -------------------------------------------------------------
        # 1. WEEKLY TIMEFRAME FILTER (21 EMA > 44 EMA & Upward Slope)
        # -------------------------------------------------------------
        df_weekly = df_daily.resample('W-FRI').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()

        if len(df_weekly) < 45:
            return None

        df_weekly['EMA21'] = df_weekly['Close'].ewm(span=21, adjust=False).mean()
        df_weekly['EMA44'] = df_weekly['Close'].ewm(span=44, adjust=False).mean()

        w_close = df_weekly['Close'].iloc[-1]
        w_ema21 = df_weekly['EMA21'].iloc[-1]
        w_ema44 = df_weekly['EMA44'].iloc[-1]
        w_ema21_prev = df_weekly['EMA21'].iloc[-2]

        # Filter: Price > EMA21 > EMA44 & EMA21 is sloping upwards
        if not ((w_close > w_ema21) and (w_ema21 > w_ema44) and (w_ema21 > w_ema21_prev)):
            return None

        # -------------------------------------------------------------
        # 2. DAILY TIMEFRAME: BORING CANDLE & LEG-OUT IDENTIFICATION
        # -------------------------------------------------------------
        df = df_daily.copy()
        df['Body'] = abs(df['Close'] - df['Open'])
        df['Range'] = df['High'] - df['Low']
        df['Avg_Body'] = df['Body'].rolling(20).mean()
        df['Avg_Vol'] = df['Volume'].rolling(20).mean()

        # Boring Candle Rule: Body size <= 50% of total candle range
        df['Is_Boring'] = (df['Range'] > 0) & ((df['Body'] / df['Range']) <= 0.50)

        recent = df.iloc[-30:].copy()
        
        for i in range(4, len(recent) - 1):
            leg_out = recent.iloc[i]
            
            # Leg-Out Rule: Strong Green Candle + High Volume
            is_leg_out = (
                leg_out['Close'] > leg_out['Open'] and
                leg_out['Body'] > 1.1 * leg_out['Avg_Body'] and
                leg_out['Volume'] > 1.1 * leg_out['Avg_Vol']
            )

            if not is_leg_out:
                continue

            # Check 1 to 3 candles left for Boring Candle(s)
            base_candles = []
            for k in range(1, 4):
                prev_candle = recent.iloc[i - k]
                if prev_candle['Is_Boring']:
                    base_candles.append(prev_candle)
                else:
                    break
            
            if len(base_candles) == 0:
                continue

            # Define Zone Boundaries
            proximal_line = max([max(c['Open'], c['Close']) for c in base_candles]) # Entry
            distal_line = min([c['Low'] for c in base_candles])                   # Base Low

            # -------------------------------------------------------------
            # 3. FRESHNESS & RETRACE VERIFICATION
            # -------------------------------------------------------------
            subsequent = recent.iloc[i + 1:]
            if len(subsequent) == 0:
                continue

            min_low_after = subsequent['Low'].min()
            current_close = recent['Close'].iloc[-1]
            current_vol = recent['Volume'].iloc[-1]
            avg_vol_latest = recent['Avg_Vol'].iloc[-1]

            # Freshness Check: Price hasn't dropped below distal line
            if min_low_after < distal_line:
                continue

            # Retrace Check: Price is currently inside or near entry zone (+3% buffer)
            is_near_zone = (current_close >= distal_line) and (current_close <= proximal_line * 1.03)
            low_retrace_volume = current_vol <= (avg_vol_latest * 1.2)

            if is_near_zone and low_retrace_volume:
                stop_loss = round(distal_line * 0.995, 2)
                entry_price = round(proximal_line, 2)
                risk_pct = round(((entry_price - stop_loss) / entry_price) * 100, 2)

                return {
                    "Ticker": ticker.replace(".NS", ""),
                    "Current_Price": round(current_close, 2),
                    "Entry_Zone": entry_price,
                    "Stop_Loss": stop_loss,
                    "Risk_%": risk_pct
                }

    except Exception as e:
        if DEBUG:
            print(f"Error scanning {ticker}: {e}")
        return None

    return None

# -------------------------------------------------------------
# MULTI-THREADED EXECUTION ENGINE
# -------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("  NIFTY 500 DEMAND ZONE SCANNER (FAST MULTI-THREADED)")
    print("=" * 60)
    
    tickers = get_nifty500_tickers()
    print(f"\n[+] Loaded {len(tickers)} stocks.")
    print("[+] Running multi-threaded scan across all stocks...\n")

    matched_stocks = []
    start_time = time.time()

    # Process 15 stocks simultaneously using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_ticker = {executor.submit(scan_stock, ticker): ticker for ticker in tickers}
        
        for future in as_completed(future_to_ticker):
            result = future.result()
            if result:
                print(f"🔥 MATCH: {result['Ticker']:<12} | Price: ₹{result['Current_Price']:<7} | Entry: ₹{result['Entry_Zone']:<7} | SL: ₹{result['Stop_Loss']:<7} | Risk: {result['Risk_%']}%")
                matched_stocks.append(result)

    elapsed = round(time.time() - start_time, 2)
    print(f"\n[✔] Scan Finished in {elapsed} seconds.")

    # Save Results
    if matched_stocks:
        res_df = pd.DataFrame(matched_stocks)
        res_df.to_csv("demand_zone_signals.csv", index=False)
        print(f"\n[✔] Saved {len(matched_stocks)} setups to 'demand_zone_signals.csv'\n")
        print(res_df.to_string(index=False))
    else:
        print("\n[!] No stocks strictly matched the criteria today.")
        print("[i] Tip: If market is in a sharp pullback or sideways chop, fewer setups appear naturally.")
