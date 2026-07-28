# ==========================================
# 1. STREAMLIT UI & SETTINGS (Updated Sector Options)
# ==========================================
# ... (keep your existing page config and sidebar settings) ...

# Change the sector options to point to local filenames instead of URLs
sector_options = {
    "Nifty 50": "ind_nifty50list.csv",
    "Nifty 500": "ind_nifty500list.csv",
    "Nifty Midcap 100": "ind_niftymidcap100list.csv",
    "Nifty Bank": "ind_niftybanklist.csv",
    "Nifty IT": "ind_niftyitlist.csv",
    "Nifty Auto": "ind_niftyautolist.csv"
}
selected_sector = st.sidebar.selectbox("Select Sector / Index", list(sector_options.keys()))

# ... (keep your timeframe and EMA options) ...

# ==========================================
# 2. DATA FETCHER (BULLETPROOF LOCAL CSV METHOD)
# ==========================================
@st.cache_data(ttl=3600)
def get_index_tickers(sector_name):
    filename = sector_options.get(sector_name)
    
    try:
        # Reads the file directly from your GitHub repository
        df = pd.read_csv(filename)
        return [str(symbol).strip() + ".NS" for symbol in df['Symbol']]
    except FileNotFoundError:
        st.sidebar.error(f"Missing file: {filename}. Please upload it to your GitHub.")
        return []
    except Exception as e:
        st.sidebar.error(f"Error reading {filename}: {e}")
        return []
