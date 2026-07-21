import pandas as pd
import yfinance as yf
import requests
import io
import time
from datetime import datetime

def get_nifty500_tickers():
    """Fetch official Nifty 500 ticker symbols for Yahoo Finance (.NS)"""
    url = "https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/ind_nifty500list.csv"
    try:
        s = requests.get(url).content
        df = pd.read_csv(io.StringIO(s.decode('utf-8')))
        tickers = [f"{symbol.strip()}.NS" for symbol in df['Symbol'].dropna().unique()]
        return tickers
    except Exception as e:
        print(f"Error fetching ticker list: {e}")
        # Fallback core list
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "ICICIBANK.NS", "BHARTIARTL.NS", "HDFCBANK.NS", "SBIN.NS"]

def scan_stock(ticker):
    """Applies Weekly Trend + Daily Boring Candle & Fresh Demand Zone Rules"""
    try:
        # Fetch 1 year of historical data
        stock = yf.Ticker(ticker)
        df_daily = stock.history(period="1y")
        
        if df_daily.empty or len(df_daily) < 100:
            return None

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

        df_weekly['EMA21'] = df_weekly['Close'].ewm(span=21, adjust=False).mean()
        df_weekly['EMA44'] = df_weekly['Close'].ewm(span=44, adjust=False).mean()

        w_close = df_weekly['Close'].iloc[-1]
        w_ema21 = df_weekly['EMA21'].iloc[-1]
        w_ema44 = df_weekly['EMA44'].iloc[-1]
        w_ema21_prev = df_weekly['EMA21'].iloc[-2]

        # Weekly Check: Price > EMA21 > EMA44 and EMA21 is sloping up
        weekly_trend = (w_close > w_ema21) and (w_ema21 > w_ema44) and (w_ema21 > w_ema21_prev)
        if not weekly_trend:
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

        # Scan the last 30 trading sessions for setups
        recent = df.iloc[-30:].copy()
        
        for i in range(4, len(recent) - 1):
            leg_out = recent.iloc[i]
            
            # Leg-Out Rule: Strong Green Candle + Volume > 1.3x 20-day Average
            is_leg_out = (
                leg_out['Close'] > leg_out['Open'] and
                leg_out['Body'] > 1.2 * leg_out['Avg_Body'] and
                leg_out['Volume'] > 1.2 * leg_out['Avg_Vol']
            )

            if not is_leg_out:
                continue

            # Check 1 to 3 candles immediately left for Boring Candle(s)
            base_candles = []
            for k in range(1, 4):
                prev_candle = recent.iloc[i - k]
                if prev_candle['Is_Boring']:
                    base_candles.append(prev_candle)
                else:
                    break
            
            if len(base_candles) == 0:
                continue # No base candle preceding leg-out

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

            # Freshness Check: Price has NOT dropped below distal line (Zone intact)
            if min_low_after < distal_line:
                continue

            # Retrace Check: Price is currently pulling back near/into proximal line
            is_near_zone = (current_close >= distal_line) and (current_close <= proximal_line * 1.025)
            
            # Low Volume on Retrace: Latest volume is below 20-day average
            low_retrace_volume = current_vol < avg_vol_latest

            if is_near_zone and low_retrace_volume:
                stop_loss = round(distal_line * 0.995, 2)
                entry_price = round(proximal_line, 2)
                risk_pct = round(((entry_price - stop_loss) / entry_price) * 100, 2)

                return {
                    "Ticker": ticker.replace(".NS", ""),
                    "Current_Price": round(current_close, 2),
                    "Entry_Zone": entry_price,
                    "Stop_Loss": stop_loss,
                    "Risk_%": risk_pct,
                    "Weekly_EMA21": round(w_ema21, 2)
                }

    except Exception:
        return None

    return None

# -------------------------------------------------------------
# MAIN EXECUTION ENGINE
# -------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("  NIFTY 500 DEMAND ZONE & WEEKLY TREND SCANNER")
    print("=" * 60)
    
    tickers = get_nifty500_tickers()
    print(f"\n[+] Loaded {len(tickers)} stocks from Nifty 500.")
    print("[+] Running scans (this takes ~1-2 minutes)...\n")

    matched_stocks = []
    start_time = time.time()

    for idx, ticker in enumerate(tickers, 1):
        result = scan_stock(ticker)
        if result:
            print(f"🔥 MATCH FOUND: {result['Ticker']} | Entry: ₹{result['Entry_Zone']} | SL: ₹{result['Stop_Loss']} (Risk: {result['Risk_%']}%)")
            matched_stocks.append(result)

    elapsed = round((time.time() - start_time) / 60, 2)
    print(f"\n[✔] Scan Finished in {elapsed} minutes.")

    # Save to CSV
    if matched_stocks:
        res_df = pd.DataFrame(matched_stocks)
        res_df.to_csv("demand_zone_signals.csv", index=False)
        print(f"\n[✔] Saved {len(matched_stocks)} setups to 'demand_zone_signals.csv'\n")
        print(res_df.to_string(index=False))
    else:
        print("\n[!] No stocks strictly matched the setup today. Check again tomorrow after market close.")
