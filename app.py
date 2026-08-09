# ==========================================
# 2. COMMAND CENTER
# ==========================================
with st.sidebar:
    st.markdown("### **COMMAND CENTER**")
    st.divider()
    sector_options = ["F&O Stocks (~223+)", "Nifty 50", "Nifty 500"]
    selected_sector = st.selectbox("Market Universe", sector_options, index=0)
    
    # RESTORED: 1 Month and 3 Month Institutional Timeframes
    tf_options = {
        "75 Min": "75m", 
        "1 Day": "1d", 
        "1 Week": "1wk", 
        "1 Month": "1mo", 
        "3 Month": "3mo"
    }
    tf_label = st.selectbox("Resolution", list(tf_options.keys()), index=0)
    timeframe = tf_options[tf_label]
    
    direction = st.radio("Target Vector", ("🟢 Active Demand (Buy)", "🔴 Active Supply (Sell)"))

# ... [Keep Section 3 and 4 exactly the same] ...

# ==========================================
# 5. HIGH-SPEED SCANNER (DYNAMIC PAYLOAD)
# ==========================================
col1, col2, col3 = st.columns([1, 1, 1])

if st.button("⚡ SCAN FOR LIVE EXECUTIONS", type="primary"):
    is_bull = "Demand" in direction
    ticker_list = get_index_tickers(selected_sector)
    
    if ticker_list:
        with col1: st.metric("TRACKING", f"{len(ticker_list)} ASSETS")
        with col2: st.metric("RESOLUTION", f"{tf_label}")
        with col3: st.metric("VECTOR", "LONG" if is_bull else "SHORT")

        # DYNAMIC PAYLOAD: Adjusts history size based on timeframe to prevent crashes
        if timeframe == "3mo":
            period_val = "max"
        elif timeframe == "1mo":
            period_val = "10y"
        elif timeframe == "1wk":
            period_val = "5y"
        elif timeframe == "1d":
            period_val = "2y"
        else:
            period_val = "60d" # For 75-min charts

        interval_val = "15m" if timeframe == "75m" else timeframe
        
        tickers_str = " ".join(ticker_list)
        progress_ui = st.empty()
        progress_ui.markdown(render_hud(10, "FETCHING MARKET DATA..."), unsafe_allow_html=True)
        
        # Threads=True allows yfinance to pull all stocks concurrently
        market_data = yf.download(tickers_str, period=period_val, interval=interval_val, group_by='ticker', threads=True)
        progress_ui.markdown(render_hud(60, "HUNTING LIVE PENETRATIONS..."), unsafe_allow_html=True)
        
        results = []
        total = len(ticker_list)
        
        for i, ticker in enumerate(ticker_list):
            try:
                df = market_data if len(ticker_list) == 1 else market_data[ticker]
                df = df.dropna()
                
                if not df.empty:
                    if timeframe == '75m': df = resample_to_75m(df)
                    setup = get_active_zone(df, is_bull)
                    
                    if setup:
                        setup['Asset'] = ticker.replace(".NS", "")
                        results.append(setup)
            except Exception:
                pass
            
            if i % 25 == 0 or i == total - 1:
                progress_ui.markdown(render_hud(60 + (i/total)*40, f"ANALYZING {ticker.replace('.NS', '')}"), unsafe_allow_html=True)
                
        progress_ui.empty()
        st.divider()
        st.markdown(f"### 🎯 IMMEDIATE EXECUTIONS")
        
        if results:
            final_df = pd.DataFrame(results)[['Asset', 'Zone Type', 'Live Price', 'Entry', 'SL', 'Action']]
            
            styled = final_df.style.set_properties(**{
                'background-color': '#11151C', 'color': '#F8FAFC', 'border-color': '#1E293B'
            }).map(lambda v: 'color: #00F2FE; font-weight: 900;' if 'EXECUTE' in str(v) else 'color: #64748B;', subset=['Action'])\
              .map(lambda v: 'color: #00FF00; font-weight: 800;' if 'Demand' in str(v) else 'color: #FF0000; font-weight: 800;', subset=['Zone Type'])
            
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.error("0 MATCHES. No assets are actively trading inside a valid, pristine zone right now. Wait for the market to come to your levels.")
