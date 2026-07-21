import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Weekly Trend & Demand Zone Scanner", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .main-title { font-size: 32px; font-weight: 800; color: #8B5CF6; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #64748B; margin-bottom: 20px; }
    .stProgress > div > div > div > div { background-color: #8B5CF6; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🎯 Institutional Demand Zone Scanner</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Scans for Weekly Upward Trend + Daily Boring Candle Base + High-Volume Leg-Out + Fresh Low-Volume Retrace.</p>', unsafe_allow_html=True)

# --- ROBUST DATA UNIVERSE LOADER ---
@st.cache_data(ttl=86400)
def load_symbols(category):
    urls = {
        "NIFTY 500": "https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/ind_nifty500list.csv",
        "NIFTY 50": "https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/ind_nifty50list.csv",
        "NIFTY BANK": "https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/ind_niftybanklist.csv",
    }
    url = urls.get(category, urls["NIFTY 500"])
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        return [f"{str(symbol).strip()}.NS" for symbol in df['Symbol'].dropna().unique()]
    except Exception:
        st.sidebar.warning("⚠️ Market list server busy. Falling back to core liquid universe.")
        return [
            'RELIANCE.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'TCS.NS', 
            'ITC.NS', 'LT.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'AXISBANK.NS',
            'KOTAKBANK.NS', 'M&M.NS', 'TATAMOTORS.NS', 'NTPC.NS', 'SUNPHARMA.NS'
        ]

# --- STRATEGY ALGORITHM ---
def analyze_stock_setup(ticker):
    try:
        stock = yf.Ticker(ticker)
        df_daily = stock.history(period="1y", interval="1d")
        
        if df_daily.empty or len(df_daily) < 100:
            return None
            
        if df_daily.index.tz is not None:
            df_daily.index = df_daily.index.tz_localize(None)

        # -------------------------------------------------------------
        # 1. WEEKLY TREND FILTER (21 EMA > 44 EMA & Sloping Upward)
        # -------------------------------------------------------------
        df_weekly = df_daily.resample('W-FRI').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()

        if len(df_weekly) < 45:
            return None

        df_weekly['EMA21'] = df_weekly['Close'].ewm(span=21, adjust=False).mean()
        df_weekly['EMA44'] = df_weekly['Close'].ewm(span=44, adjust=False).mean()

        w_close = df_weekly['Close'].iloc[-1]
        w_ema21 = df_weekly['EMA21'].iloc[-1]
        w_ema44 = df_weekly['EMA44'].iloc[-1]
        w_ema21_prev = df_weekly['EMA21'].iloc[-2]

        # Weekly Trend Condition
        weekly_uptrend = (w_close > w_ema21) and (w_ema21 > w_ema44) and (w_ema21 > w_ema21_prev)
        if not weekly_uptrend:
            return None

        # -------------------------------------------------------------
        # 2. DAILY BORING CANDLE & LEG-OUT IDENTIFICATION
        # -------------------------------------------------------------
        df = df_daily.copy()
        df['Body'] = abs(df['Close'] - df['Open'])
        df['Range'] = df['High'] - df['Low']
        df['Avg_Body'] = df['Body'].rolling(20).mean()
        df['Avg_Vol'] = df['Volume'].rolling(20).mean()

        # Boring Candle Rule: Body size <= 50% of total candle range
        df['Is_Boring'] = (df['Range'] > 0) & ((df['Body'] / df['Range']) <= 0.50)

        recent = df.iloc[-30:].copy()
        
        # Look for Leg-Out and Base within recent 30 sessions
        for i in range(4, len(recent) - 1):
            leg_out = recent.iloc[i]
            
            # Leg-Out Rule: Strong Green Candle + High Volume (>1.1x avg)
            is_leg_out = (
                leg_out['Close'] > leg_out['Open'] and
                leg_out['Body'] > 1.1 * leg_out['Avg_Body'] and
                leg_out['Volume'] > 1.1 * leg_out['Avg_Vol']
            )

            if not is_leg_out:
                continue

            # Check 1 to 3 candles immediately to the left for Boring Candle(s)
            base_candles = []
            for k in range(1, 4):
                prev_candle = recent.iloc[i - k]
                if prev_candle['Is_Boring']:
                    base_candles.append(prev_candle)
                else:
                    break
            
            if len(base_candles) == 0:
                continue # No base found

            # Define Zone Boundaries
            proximal_line = max([max(c['Open'], c['Close']) for c in base_candles]) # Entry Trigger
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

            # Freshness Check: Price hasn't broken below the Distal Line (Zone Intact)
            if min_low_after < distal_line:
                continue

            # Retrace Check: Current price is within or near entry zone (+3% buffer)
            is_near_zone = (current_close >= distal_line) and (current_close <= proximal_line * 1.03)
            
            # Low Volume Check: Retrace volume is controlled (<= 1.2x average)
            low_retrace_vol = current_vol <= (avg_vol_latest * 1.2)

            if is_near_zone and low_retrace_vol:
                entry_price = round(proximal_line, 2)
                stop_loss = round(distal_line * 0.995, 2) # 0.5% buffer
                risk_per_share = round(entry_price - stop_loss, 2)
                risk_pct = round((risk_per_share / entry_price) * 100, 2)
                
                target_1 = round(entry_price + (2 * risk_per_share), 2) # 1:2 RR
                target_2 = round(entry_price + (4 * risk_per_share), 2) # 1:4 RR

                return {
                    "Ticker": ticker.replace('.NS', ''),
                    "Live Price": f"₹{round(current_close, 2)}",
                    "Entry Zone (GTT)": f"₹{entry_price}",
                    "Stop Loss": f"₹{stop_loss}",
                    "Risk %": f"{risk_pct}%",
                    "Target 1 (1:2 RR)": f"₹{target_1}",
                    "Target 2 (1:4 RR)": f"₹{target_2}",
                    "Weekly Trend": "🟢 21 > 44 EMA Up",
                    "Status": "✅ Fresh Zone Retrace"
                }

        return None
    except Exception:
        return None

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("1. Target Universe")
    sector_input = st.selectbox("Market Universe:", [
        "NIFTY 500", 
        "NIFTY 50", 
        "NIFTY BANK"
    ])
    
    st.divider()
    st.header("2. Strategy Parameters")
    st.markdown("""
    * **Weekly Trend:** Price > 21 EMA > 44 EMA
    * **Daily Base:** Body $\le$ 50% of range (1–3 candles)
    * **Leg-Out:** Strong green candle + High Volume
    * **Freshness:** Untested demand zone
    * **Retrace:** Low volume pullback into zone
    """)
    
    st.divider()
    execute_button = st.button("🚀 EXECUTE DEMAND SCAN", type="primary", use_container_width=True)

# --- EXECUTION ENGINE ---
if execute_button:
    symbols_list = load_symbols(sector_input)
    st.info(f"Scanning **{len(symbols_list)} stocks** across **{sector_input}**...")
    
    confirmed_setups = []
    progress_ui = st.progress(0, text="Initializing scanner...")
    
    start_time = time.time()
    
    # Run multi-threaded scanner
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures_map = {
            executor.submit(analyze_stock_setup, ticker): ticker for ticker in symbols_list
        }
        
        completed_count = 0
        total_symbols = len(symbols_list)
        
        for future in as_completed(futures_map):
            completed_count += 1
            result = future.result()
            if result:
                confirmed_setups.append(result)
            
            percent_complete = completed_count / total_symbols
            progress_ui.progress(percent_complete, text=f"Analyzed {completed_count}/{total_symbols} stocks...")
            
    progress_ui.empty()
    elapsed_time = round(time.time() - start_time, 2)
    
    if confirmed_setups:
        results_df = pd.DataFrame(confirmed_setups)
        st.success(f"🎯 Scan Complete in **{elapsed_time}s**: Found **{len(results_df)}** setup(s) meeting all rules!")
        st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No stocks strictly matched all criteria today (Completed in {elapsed_time}s). This happens naturally during market pullbacks or chop.")
