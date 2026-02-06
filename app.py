import streamlit as st
import time
import pandas as pd
import talib
import os
import sys
import json
import warnings
from datetime import datetime, timedelta, time as dtime
from kiteconnect import KiteConnect, exceptions
import numpy as np
import base64
from cryptography.fernet import Fernet
import hashlib

warnings.filterwarnings('ignore')

# Page config
st.set_page_config(
    page_title="Options Auto Trading Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- MODERN DARK MODE CSS ---
st.markdown("""
<style>
    /* Global Background & Text */
    .stApp {
        background-color: #0F172A !important;
        color: #E2E8F0 !important;
    }
    
    /* Header & Sidebar */
    header[data-testid="stHeader"] { background-color: #0F172A !important; }
    section[data-testid="stSidebar"] {
        background-color: #1E293B !important;
        border-right: 1px solid #334155;
    }

    /* Modern Dark Metric Cards */
    .metric-card {
        background: #1E293B;
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        margin-bottom: 0.5rem;
        transition: transform 0.2s ease;
    }
    .metric-card:hover {
        border-color: #4F46E5;
        transform: translateY(-2px);
    }
    
    .metric-label {
        font-size: 1rem;
        color: #94A3B8;
        font-weight: 400;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .metric-value {
        font-size: 1rem;
        font-weight: 400;
        color: #F8FAFC;
        margin-top: 4px;
    }

    /* Subheading Styling */
    .subheading {
        color: #94A3B8;
        font-size: 1rem;
        font-weight: 400;
        margin-top: -15px;
        margin-bottom: 20px;
    }

    /* Tables & Dataframes in Dark Mode */
    [data-testid="stTable"], [data-testid="stDataFrame"] {
        background-color: #1E293B;
        border-radius: 8px;
    }

    /* Buttons */
    .stButton button {
        border-radius: 8px !important;
        background-color: #4F46E5 !important;
        color: white !important;
        border: none !important;
    }
    .stButton button:hover {
        background-color: #6366F1 !important;
        box-shadow: 0 0 15px rgba(79, 70, 229, 0.4);
    }

    /* Input Fields and Labels - FIX FOR DARK MODE */
    div[data-baseweb="input"] label,
    div[data-baseweb="select"] label,
    div[data-baseweb="textarea"] label {
        color: #E2E8F0 !important;
        font-weight: 500;
    }
    
    /* Form labels and widget labels */
    .stNumberInput label,
    .stSelectbox label,
    .stTextInput label,
    .stCheckbox label,
    .stTextArea label {
        color: #E2E8F0 !important;
        font-weight: 500;
    }
    
    /* Specific styling for number input labels */
    div[data-testid="stNumberInput"] label {
        color: #E2E8F0 !important;
    }
    
    /* Checkbox labels */
    .stCheckbox span {
        color: #E2E8F0 !important;
    }
    
    /* Widget containers */
    div[data-testid="stVerticalBlock"] > div > div > div {
        color: #E2E8F0 !important;
    }
    
    /* Warning and info text */
    .stAlert,
    .stWarning,
    .stError,
    .stSuccess,
    .stInfo {
        color: #E2E8F0 !important;
    }

    /* Input Fields */
    input, select, textarea {
        background-color: #0F172A !important;
        color: white !important;
        border: 1px solid #334155 !important;
    }
    
    /* Number input spinner */
    input[type="number"] {
        background-color: #0F172A !important;
        color: white !important;
    }
    
    /* Placeholder text */
    ::placeholder {
        color: #94A3B8 !important;
    }

    /* Custom P&L Colors */
    .pnl-positive { color: #10B981; font-weight: bold; }
    .pnl-negative { color: #EF4444; font-weight: bold; }
    
    /* TSL Status Colors */
    .tsl-active { color: #F59E0B; font-weight: bold; }
    .tsl-inactive { color: #94A3B8; }
</style>
""", unsafe_allow_html=True)

# --- ENCRYPTION UTILITIES ---
def generate_key():
    """Generate encryption key"""
    return Fernet.generate_key()

def get_encryption_key():
    """Get or create encryption key"""
    key_file = "encryption.key"
    
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            key = f.read()
    else:
        key = generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
    
    return key

def encrypt_data(data, key):
    """Encrypt sensitive data"""
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return encrypted

def decrypt_data(encrypted_data, key):
    """Decrypt sensitive data"""
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_data)
    return decrypted.decode()

# --- CONFIGURATION ---
class Config:
    INDEX = "BANKNIFTY"
    OTM_DISTANCE = 1
    BASE_LOT_SIZE = 30
    NUMBER_OF_LOTS = 1
    OVERRIDE_QUANTITY = False
    TOTAL_QUANTITY = 30
    SL_POINTS = 25
    TP_POINTS = 100
    TSL_ENABLED = True  # New: Enable/disable TSL
    TSL_TRIGGER = 25
    TSL_STEP = 10
    MAX_TRADES_PER_DAY = 5
    MAX_LOSS_PER_DAY = 3000
    TRADE_START = dtime(9, 20)
    ENTRY_END = dtime(14, 45)  # Last entry time for NSE indices
    SQUARE_OFF_TIME = dtime(15, 10)  # Square off before market close
    
    # MCX specific timings for CRUDEOIL
    MCX_TRADE_START = dtime(9, 30)
    MCX_ENTRY_END = dtime(22, 0)  # Last entry time for MCX
    MCX_SQUARE_OFF_TIME = dtime(23, 00)  # Square off before MCX close
    
    # Cooldown settings (in seconds)
    COOLDOWN_AFTER_ORDER = 30  # 30 seconds cooldown after placing an order
    COOLDOWN_AFTER_SIGNAL = 10  # 10 seconds cooldown after receiving a signal
    
    TOKEN_FILE = "access_token.txt"
    CREDENTIALS_FILE = "credentials.enc"
    TRADES_FILE = "trades_log.json"
    ORDERS_FILE = "orders_log.json"
    INSTRUMENTS_FILE = "instruments.csv"
    CONFIG_FILE = "bot_config.json"
    
    # Index mapping
    INDEX_MAP = {
        "BANKNIFTY": {
            "spot_symbol": "NSE:NIFTY BANK",
            "spot_token": 260105,
            "step_size": 100,
            "tick_size": 0.05,
            "name": "BANKNIFTY",
            "default_lot_size": 30,
            "exchange": "NFO",
            "segment": "NSE"
        },
        "NIFTY": {
            "spot_symbol": "NSE:NIFTY 50",
            "spot_token": 256265,
            "step_size": 50,
            "tick_size": 0.05,
            "name": "NIFTY",
            "default_lot_size": 75,
            "exchange": "NFO",
            "segment": "NSE"
        },
        "CRUDEOIL": {
            "spot_symbol": "MCX:CRUDEOIL",
            "step_size": 100,
            "tick_size": 0.1,
            "name": "CRUDEOIL",
            "default_lot_size": 1,
            "exchange": "MCX",
            "segment": "MCX"
        }
    }

# --- SESSION STATE ---
def init_session_state():
    defaults = {
        'kite': None,
        'user_name': None,
        'bot_running': False,
        'last_signal': None,
        'signal_cooldown': 0,
        'market_data': {},
        'active_trades': [],
        'trade_history': [],
        'order_history': [],
        'auth_status': False,
        'selected_index': Config.INDEX,
        'today_trades_count': 0,
        'today_loss': 0,
        'last_refresh': None,
        'instruments_df': None,
        'show_rejected_only': False,
        'credentials_saved': False,
        'login_step': 'initial',
        'api_key': '',
        'api_secret': '',
        'last_order_time': None,  # Track last order placement time
        'last_signal_time': None,  # Track last signal generation time
        'square_off_triggered': False  # Track if square off has been triggered
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    load_config()

def load_config():
    try:
        if os.path.exists(Config.CONFIG_FILE):
            with open(Config.CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            for key, value in config_data.items():
                if hasattr(Config, key):
                    setattr(Config, key, value)
            if 'selected_index' in config_data:
                st.session_state.selected_index = config_data['selected_index']
            return True
    except:
        pass
    return False

def save_config():
    try:
        config_data = {
            'INDEX': st.session_state.selected_index,
            'OTM_DISTANCE': Config.OTM_DISTANCE,
            'NUMBER_OF_LOTS': Config.NUMBER_OF_LOTS,
            'OVERRIDE_QUANTITY': Config.OVERRIDE_QUANTITY,
            'TOTAL_QUANTITY': Config.TOTAL_QUANTITY,
            'SL_POINTS': Config.SL_POINTS,
            'TP_POINTS': Config.TP_POINTS,
            'TSL_ENABLED': Config.TSL_ENABLED,
            'TSL_TRIGGER': Config.TSL_TRIGGER,
            'TSL_STEP': Config.TSL_STEP,
            'MAX_TRADES_PER_DAY': Config.MAX_TRADES_PER_DAY,
            'MAX_LOSS_PER_DAY': Config.MAX_LOSS_PER_DAY,
            'COOLDOWN_AFTER_ORDER': Config.COOLDOWN_AFTER_ORDER,
            'COOLDOWN_AFTER_SIGNAL': Config.COOLDOWN_AFTER_SIGNAL
        }
        
        with open(Config.CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        return True
    except:
        return False

# --- CREDENTIALS MANAGEMENT ---
def save_credentials(api_key, api_secret):
    """Save encrypted credentials to file"""
    try:
        encryption_key = get_encryption_key()
        
        credentials = {
            'api_key': api_key,
            'api_secret': api_secret,
            'saved_at': datetime.now().isoformat()
        }
        
        encrypted_data = encrypt_data(json.dumps(credentials), encryption_key)
        
        with open(Config.CREDENTIALS_FILE, 'wb') as f:
            f.write(encrypted_data)
        
        return True
    except Exception as e:
        print(f"Error saving credentials: {e}")
        return False

def load_credentials():
    """Load and decrypt credentials from file"""
    try:
        if not os.path.exists(Config.CREDENTIALS_FILE):
            return None, None
        
        encryption_key = get_encryption_key()
        
        with open(Config.CREDENTIALS_FILE, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = decrypt_data(encrypted_data, encryption_key)
        credentials = json.loads(decrypted_data)
        
        return credentials.get('api_key'), credentials.get('api_secret')
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None, None

def clear_credentials():
    """Clear saved credentials"""
    try:
        if os.path.exists(Config.CREDENTIALS_FILE):
            os.remove(Config.CREDENTIALS_FILE)
        return True
    except:
        return False

def clear_access_token():
    """Clear saved access token"""
    try:
        if os.path.exists(Config.TOKEN_FILE):
            os.remove(Config.TOKEN_FILE)
        return True
    except:
        return False

# --- UTILITY FUNCTIONS ---
def format_full_number(num, decimals=2):
    """Display full numbers with proper formatting"""
    try:
        if pd.isna(num):
            return "0"
        
        if isinstance(num, str):
            return num
        
        if st.session_state.selected_index == "CRUDEOIL":
            return f"{num:,.1f}"
        
        if decimals == 0:
            return f"{int(num):,}"
        else:
            return f"{num:,.{decimals}f}"
    except:
        return str(num)

def format_pnl(value):
    """Formats P&L with dark-mode friendly colors."""
    style_class = "pnl-positive" if value >= 0 else "pnl-negative"
    sign = "+" if value >= 0 else ""
    return f'<span class="{style_class}">{sign}₹{value:,.2f}</span>'

def format_price(value):
    """Ensures price text is bright in dark mode."""
    return f'<span style="color: #F8FAFC;">{value:,.2f}</span>'

def format_tsl_status(is_active):
    """Formats TSL status with appropriate color."""
    if is_active:
        return '<span class="tsl-active">ACTIVE</span>'
    else:
        return '<span class="tsl-inactive">INACTIVE</span>'

def get_current_time():
    return datetime.now().strftime("%H:%M:%S")

def get_trading_hours(index_name):
    """Get trading hours based on index"""
    if index_name == "CRUDEOIL":
        return Config.MCX_TRADE_START, Config.MCX_ENTRY_END, Config.MCX_SQUARE_OFF_TIME
    else:
        return Config.TRADE_START, Config.ENTRY_END, Config.SQUARE_OFF_TIME

def round_to_tick(price, index_name):
    """Round price to tick size"""
    index_info = Config.INDEX_MAP.get(index_name, {})
    tick_size = index_info.get("tick_size", 0.05)
    
    if tick_size <= 0:
        return price
    
    if tick_size >= 1:
        return round(price / tick_size) * tick_size
    else:
        multiplier = 1 / tick_size
        return round(price * multiplier) / multiplier

def is_cooldown_active():
    """Check if cooldown period is active"""
    now = datetime.now()
    
    # Check order cooldown
    if st.session_state.last_order_time:
        order_cooldown_end = st.session_state.last_order_time + timedelta(seconds=Config.COOLDOWN_AFTER_ORDER)
        if now < order_cooldown_end:
            time_left = (order_cooldown_end - now).seconds
            return True, f"Order cooldown active: {time_left}s remaining"
    
    # Check signal cooldown
    if st.session_state.last_signal_time:
        signal_cooldown_end = st.session_state.last_signal_time + timedelta(seconds=Config.COOLDOWN_AFTER_SIGNAL)
        if now < signal_cooldown_end:
            time_left = (signal_cooldown_end - now).seconds
            return True, f"Signal cooldown active: {time_left}s remaining"
    
    return False, ""

def should_square_off_before_close(index_name):
    """Check if we should square off positions before market close"""
    now = datetime.now()
    now_time = now.time()
    
    if index_name == "CRUDEOIL":
        # Square off 5 minutes before MCX close
        square_off_time = Config.MCX_SQUARE_OFF_TIME
        # Check if it's 5 minutes before square off time
        five_min_before = (datetime.combine(now.date(), square_off_time) - timedelta(minutes=5)).time()
        return now_time >= five_min_before and now_time <= square_off_time
    else:
        # Square off 5 minutes before NSE close
        square_off_time = Config.SQUARE_OFF_TIME
        # Check if it's 5 minutes before square off time
        five_min_before = (datetime.combine(now.date(), square_off_time) - timedelta(minutes=5)).time()
        return now_time >= five_min_before and now_time <= square_off_time

# --- INSTRUMENTS ---
def load_instruments(kite, exchange="ALL"):
    """Load instruments for all exchanges or specific exchange"""
    try:
        file_name = f"instruments_{exchange}.csv" if exchange != "ALL" else Config.INSTRUMENTS_FILE
        
        if os.path.exists(file_name):
            try:
                if exchange == "MCX":
                    df = pd.read_csv(file_name, header=None)
                    df.columns = ['instrument_token', 'exchange_token', 'tradingsymbol', 'name', 
                                  'last_price', 'expiry', 'strike', 'tick_size', 'lot_size', 
                                  'instrument_type', 'segment', 'exchange']
                else:
                    df = pd.read_csv(file_name)
                
                file_time = datetime.fromtimestamp(os.path.getmtime(file_name))
                if (datetime.now() - file_time).days < 1:
                    return df
            except Exception as e:
                print(f"Error reading existing instruments file: {e}")
        
        if exchange == "ALL":
            nfo_instruments = kite.instruments("NFO")
            mcx_instruments = kite.instruments("MCX")
            instruments = nfo_instruments + mcx_instruments
        else:
            instruments = kite.instruments(exchange)
        
        df = pd.DataFrame(instruments)
        df.to_csv(file_name, index=False)
        return df
        
    except Exception as e:
        print(f"Error loading instruments: {e}")
        if os.path.exists(file_name):
            try:
                if exchange == "MCX":
                    df = pd.read_csv(file_name, header=None)
                    df.columns = ['instrument_token', 'exchange_token', 'tradingsymbol', 'name', 
                                  'last_price', 'expiry', 'strike', 'tick_size', 'lot_size', 
                                  'instrument_type', 'segment', 'exchange']
                else:
                    df = pd.read_csv(file_name)
                return df
            except:
                pass
        return None

def get_base_lot_size(kite, index_name):
    """Get base lot size for index"""
    try:
        index_info = Config.INDEX_MAP.get(index_name, {})
        exchange = index_info.get("exchange", "NFO")
        
        df = load_instruments(kite, exchange)
        if df is None:
            return index_info.get("default_lot_size", 50)
        
        if index_name == "CRUDEOIL":
            if 'instrument_type' in df.columns:
                options = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                            (df['instrument_type'].isin(['CE', 'PE']))]
            else:
                options = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                            (df.iloc[:, 9].isin(['CE', 'PE']))]
            
            if len(options) > 0:
                if 'lot_size' in options.columns:
                    return int(options.iloc[0]['lot_size'])
                else:
                    return int(options.iloc[0].iloc[8])
            
            if 'instrument_type' in df.columns:
                futures = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                            (df['instrument_type'] == 'FUT')]
            else:
                futures = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                            (df.iloc[:, 9] == 'FUT')]
            
            if len(futures) > 0:
                if 'lot_size' in futures.columns:
                    return int(futures.iloc[0]['lot_size'])
                else:
                    return int(futures.iloc[0].iloc[8])
        else:
            futures = df[(df['name'] == index_name) & (df['instrument_type'] == 'FUT')]
            if len(futures) > 0:
                return int(futures.iloc[0]['lot_size'])
        
        return index_info.get("default_lot_size", 50)
    except Exception as e:
        print(f"Error getting base lot size: {e}")
        return Config.INDEX_MAP.get(index_name, {}).get("default_lot_size", 50)

def get_option_symbol(kite, index_name, reference_price, option_type="CE"):
    """Get OTM option symbol"""
    try:
        index_info = Config.INDEX_MAP.get(index_name, {})
        exchange = index_info.get("exchange", "NFO")
        step_size = index_info.get("step_size", 100)
        
        df = load_instruments(kite, exchange)
        if df is None:
            return None, None, None
        
        if index_name == "CRUDEOIL":
            if 'instrument_type' in df.columns:
                options = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                            (df['instrument_type'].isin(['CE', 'PE']))]
                symbol_col = 'tradingsymbol'
                strike_col = 'strike'
                expiry_col = 'expiry'
                type_col = 'instrument_type'
            else:
                options = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                            (df.iloc[:, 9].isin(['CE', 'PE']))]
                symbol_col = df.columns[2]
                strike_col = df.columns[6]
                expiry_col = df.columns[5]
                type_col = df.columns[9]
        else:
            options = df[(df['name'] == index_name) & 
                        (df['instrument_type'].isin(['CE', 'PE']))]
            symbol_col = 'tradingsymbol'
            strike_col = 'strike'
            expiry_col = 'expiry'
            type_col = 'instrument_type'
        
        if len(options) == 0:
            return None, None, None
        
        options = options.copy()
        
        try:
            options['expiry'] = pd.to_datetime(options[expiry_col])
        except:
            return None, None, None
        
        latest_expiry = options['expiry'].min().date()
        
        filtered = options[
            (options['expiry'].dt.date == latest_expiry) &
            (options[type_col] == option_type)
        ].copy()
        
        if len(filtered) == 0:
            return None, None, None
        
        atm_strike = round(reference_price / step_size) * step_size
        
        if option_type == "CE":
            target_strike = atm_strike + (Config.OTM_DISTANCE * step_size)
        else:
            target_strike = atm_strike - (Config.OTM_DISTANCE * step_size)
        
        filtered['strike_diff'] = abs(filtered[strike_col].astype(float) - target_strike)
        
        closest_idx = filtered['strike_diff'].idxmin()
        closest = filtered.loc[closest_idx]
        
        return closest[symbol_col], float(closest[strike_col]), latest_expiry
        
    except Exception as e:
        print(f"Error getting option symbol: {e}")
        return None, None, None

def get_reference_price(kite, index_name):
    """Get reference price for strike calculation"""
    try:
        index_info = Config.INDEX_MAP.get(index_name, {})
        
        if index_name == "CRUDEOIL":
            exchange = "MCX"
            df = load_instruments(kite, exchange)
            
            if df is not None:
                if 'instrument_type' in df.columns:
                    futures = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                                (df['instrument_type'] == 'FUT')].copy()
                else:
                    futures = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                                (df.iloc[:, 9] == 'FUT')].copy()
                
                if len(futures) > 0:
                    if 'expiry' in futures.columns:
                        futures['expiry_dt'] = pd.to_datetime(futures['expiry'])
                    else:
                        futures['expiry_dt'] = pd.to_datetime(futures.iloc[:, 5])
                    
                    nearest_fut = futures.loc[futures['expiry_dt'].idxmin()]
                    
                    if 'tradingsymbol' in nearest_fut:
                        symbol = nearest_fut['tradingsymbol']
                    else:
                        symbol = nearest_fut.iloc[2]
                    
                    ltp_data = kite.ltp(f"{exchange}:{symbol}")
                    price = list(ltp_data.values())[0]['last_price']
                    return round_to_tick(price, index_name)
            
            symbol = "MCX:CRUDEOIL"
            ltp_data = kite.ltp(symbol)
            price = list(ltp_data.values())[0]['last_price']
            return round_to_tick(price, index_name)
        else:
            spot_symbol = index_info.get("spot_symbol")
            ltp_data = kite.ltp(spot_symbol)
            return list(ltp_data.values())[0]['last_price']
    except Exception as e:
        print(f"Error getting reference price: {e}")
        if index_name == "CRUDEOIL":
            return 6000.0
        elif index_name == "NIFTY":
            return 22000.0
        else:
            return 48000.0

# --- TRADE MANAGER ---
class TradeManager:
    def __init__(self, kite):
        self.kite = kite
        self.load_trades()
        self.load_orders()
        self.update_stats()
    
    def load_trades(self):
        if os.path.exists(Config.TRADES_FILE):
            try:
                with open(Config.TRADES_FILE, 'r') as f:
                    trades = json.load(f)
                st.session_state.trade_history = trades
                st.session_state.active_trades = [t for t in trades if t.get('status') == 'ACTIVE']
            except:
                st.session_state.trade_history = []
                st.session_state.active_trades = []
    
    def load_orders(self):
        if os.path.exists(Config.ORDERS_FILE):
            try:
                with open(Config.ORDERS_FILE, 'r') as f:
                    orders = json.load(f)
                st.session_state.order_history = orders
            except:
                st.session_state.order_history = []
    
    def save_orders(self):
        try:
            with open(Config.ORDERS_FILE, 'w') as f:
                json.dump(st.session_state.order_history, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving orders: {e}")
    
    def update_stats(self):
        today = datetime.now().date()
        today_trades = []
        for trade in st.session_state.trade_history:
            try:
                entry_time = datetime.fromisoformat(trade['entry_time'])
                if entry_time.date() == today:
                    today_trades.append(trade)
            except:
                continue
        
        st.session_state.today_trades_count = len(today_trades)
        st.session_state.today_loss = sum(abs(t.get('pnl', 0)) for t in today_trades if t.get('status') == 'CLOSED' and t.get('pnl', 0) < 0)
    
    def save_trades(self):
        try:
            with open(Config.TRADES_FILE, 'w') as f:
                json.dump(st.session_state.trade_history, f, indent=2, default=str)
        except:
            pass
    
    def calculate_quantity(self, index_name):
        base_lot = get_base_lot_size(self.kite, index_name)
        Config.BASE_LOT_SIZE = base_lot
        
        if Config.OVERRIDE_QUANTITY:
            return Config.TOTAL_QUANTITY
        else:
            return base_lot * Config.NUMBER_OF_LOTS
    
    def can_trade(self):
        if not st.session_state.bot_running:
            return False, "Bot stopped"
        
        index_name = st.session_state.selected_index
        trade_start, entry_end, square_off_time = get_trading_hours(index_name)
        
        now_time = datetime.now().time()
        
        # Check if we're within trading hours for new entries
        if not (trade_start <= now_time <= entry_end):
            return False, f"Outside entry hours ({trade_start.strftime('%H:%M')}-{entry_end.strftime('%H:%M')})"
        
        # Check cooldown periods
        cooldown_active, cooldown_msg = is_cooldown_active()
        if cooldown_active:
            return False, cooldown_msg
        
        # Check daily limits
        if st.session_state.today_trades_count >= Config.MAX_TRADES_PER_DAY:
            return False, "Max trades reached"
        
        if st.session_state.today_loss >= Config.MAX_LOSS_PER_DAY:
            return False, "Max loss reached"
        
        # Check if there's already an active trade
        if len(st.session_state.active_trades) > 0:
            return False, "Active trade exists"
        
        return True, ""
    
    def place_order(self, index_name, signal_type, reference_price):
        try:
            option_type = "CE" if signal_type == "BUY" else "PE"
            symbol, strike, expiry = get_option_symbol(self.kite, index_name, reference_price, option_type)
            
            if not symbol:
                error_msg = f"Failed to get option symbol for {index_name} {option_type}"
                self.add_order_record({
                    'order_id': None,
                    'symbol': None,
                    'index': index_name,
                    'exchange': None,
                    'strike': None,
                    'option_type': option_type,
                    'entry_price': None,
                    'entry_time': datetime.now().isoformat(),
                    'quantity': None,
                    'status': 'REJECTED',
                    'reason': error_msg,
                    'signal': signal_type
                })
                return None
            
            index_info = Config.INDEX_MAP.get(index_name, {})
            exchange = index_info.get("exchange", "NFO")
            
            ltp_data = self.kite.ltp(f"{exchange}:{symbol}")
            ltp = ltp_data[f"{exchange}:{symbol}"]["last_price"]
            ltp = round_to_tick(ltp, index_name)
            
            quantity = self.calculate_quantity(index_name)
            
            order_type = self.kite.ORDER_TYPE_MARKET
            price = None
            
            if exchange == "MCX":
                order_type = self.kite.ORDER_TYPE_LIMIT
                price = ltp
                price = round_to_tick(price, index_name)
            
            try:
                order_id = self.kite.place_order(
                    variety=self.kite.VARIETY_REGULAR,
                    exchange=exchange,
                    tradingsymbol=symbol,
                    transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                    quantity=quantity,
                    order_type=order_type,
                    price=price,
                    product=self.kite.PRODUCT_MIS,
                    validity=self.kite.VALIDITY_DAY
                )
                
                # Calculate initial SL/TP
                sl_price = ltp - Config.SL_POINTS
                tp_price = ltp + Config.TP_POINTS
                
                sl_price = round_to_tick(sl_price, index_name)
                tp_price = round_to_tick(tp_price, index_name)
                
                # For TSL tracking
                highest_price = ltp  # Track highest price reached
                tsl_triggered = False
                tsl_price = sl_price  # Initial TSL price = SL price
                
                order_record = {
                    'order_id': order_id,
                    'symbol': symbol,
                    'index': index_name,
                    'exchange': exchange,
                    'strike': strike,
                    'option_type': option_type,
                    'entry_price': ltp,
                    'entry_time': datetime.now().isoformat(),
                    'quantity': quantity,
                    'status': 'PENDING',
                    'sl_price': sl_price,
                    'tp_price': tp_price,
                    'signal': signal_type,
                    'reason': 'Order placed successfully',
                    # TSL tracking fields
                    'highest_price': highest_price,
                    'tsl_triggered': tsl_triggered,
                    'tsl_price': tsl_price,
                    'tsl_enabled': Config.TSL_ENABLED
                }
                
                self.add_order_record(order_record)
                
                # Set last order time for cooldown
                st.session_state.last_order_time = datetime.now()
                
                time.sleep(2)
                self.check_order_status(order_id)
                
                for order in st.session_state.order_history:
                    if order.get('order_id') == order_id and order.get('status') == 'COMPLETE':
                        trade = order.copy()
                        trade['status'] = 'ACTIVE'
                        st.session_state.active_trades.append(trade)
                        st.session_state.trade_history.append(trade)
                        st.session_state.today_trades_count += 1
                        self.save_trades()
                        break
                
                return order_id
                
            except Exception as e:
                error_msg = str(e)
                print(f"Order placement error: {error_msg}")
                
                self.add_order_record({
                    'order_id': None,
                    'symbol': symbol,
                    'index': index_name,
                    'exchange': exchange,
                    'strike': strike,
                    'option_type': option_type,
                    'entry_price': ltp,
                    'entry_time': datetime.now().isoformat(),
                    'quantity': quantity,
                    'status': 'REJECTED',
                    'reason': error_msg,
                    'signal': signal_type
                })
                return None
            
        except Exception as e:
            error_msg = f"General error: {str(e)}"
            print(f"Error placing order: {error_msg}")
            
            self.add_order_record({
                'order_id': None,
                'symbol': None,
                'index': index_name,
                'exchange': None,
                'strike': None,
                'option_type': option_type,
                'entry_price': None,
                'entry_time': datetime.now().isoformat(),
                'quantity': None,
                'status': 'REJECTED',
                'reason': error_msg,
                'signal': signal_type
            })
            return None
    
    def add_order_record(self, order_record):
        order_record['record_id'] = f"{datetime.now().timestamp()}-{len(st.session_state.order_history)}"
        st.session_state.order_history.append(order_record)
        self.save_orders()
    
    def check_order_status(self, order_id):
        try:
            if not order_id:
                return
            
            orders = self.kite.orders()
            for kite_order in orders:
                if str(kite_order['order_id']) == str(order_id):
                    for i, order in enumerate(st.session_state.order_history):
                        if order.get('order_id') == order_id:
                            st.session_state.order_history[i]['status'] = kite_order['status']
                            st.session_state.order_history[i]['reason'] = kite_order.get('status_message', kite_order.get('rejection_reason', ''))
                            
                            if kite_order['status'] == 'REJECTED':
                                st.session_state.order_history[i]['rejection_reason'] = kite_order.get('rejection_reason', '')
                                st.session_state.order_history[i]['status_message'] = kite_order.get('status_message', '')
                            
                            self.save_orders()
                            break
                    break
        except Exception as e:
            print(f"Error checking order status: {e}")
    
    def monitor_trades(self):
        completed = []
        
        # First check if we need to square off before market close
        if len(st.session_state.active_trades) > 0:
            index_name = st.session_state.selected_index
            if should_square_off_before_close(index_name) and not st.session_state.square_off_triggered:
                st.warning(f"⚠️ Market closing soon! Squaring off all positions for {index_name}...")
                self.square_off_all()
                st.session_state.square_off_triggered = True
                return completed
        
        # Monitor trades for SL/TP/TSL
        for trade in st.session_state.active_trades[:]:
            try:
                exchange = trade.get('exchange', 'NFO')
                ltp_data = self.kite.ltp(f"{exchange}:{trade['symbol']}")
                current = ltp_data[f"{exchange}:{trade['symbol']}"]["last_price"]
                current = round_to_tick(current, trade['index'])
                
                # Update highest price if current is higher
                if current > trade.get('highest_price', trade['entry_price']):
                    trade['highest_price'] = current
                    
                    # Check if TSL should be triggered (only if TSL is enabled)
                    if Config.TSL_ENABLED and not trade.get('tsl_triggered', False):
                        price_move_from_entry = current - trade['entry_price']
                        if price_move_from_entry >= Config.TSL_TRIGGER:
                            trade['tsl_triggered'] = True
                            trade['tsl_price'] = current - Config.TSL_STEP
                            trade['tsl_price'] = round_to_tick(trade['tsl_price'], trade['index'])
                    elif Config.TSL_ENABLED and trade.get('tsl_triggered', False):
                        # Update trailing stop if TSL already triggered
                        new_tsl_price = current - Config.TSL_STEP
                        if new_tsl_price > trade.get('tsl_price', trade['sl_price']):
                            trade['tsl_price'] = round_to_tick(new_tsl_price, trade['index'])
                
                # Determine which SL to use (TSL if triggered and enabled, otherwise initial SL)
                if Config.TSL_ENABLED and trade.get('tsl_triggered', False):
                    effective_sl_price = trade.get('tsl_price', trade['sl_price'])
                else:
                    effective_sl_price = trade['sl_price']
                
                # Check exit conditions
                exit_trade = False
                exit_reason = ""
                
                if current <= effective_sl_price:
                    exit_trade = True
                    if Config.TSL_ENABLED and trade.get('tsl_triggered', False):
                        exit_reason = "TSL"
                    else:
                        exit_reason = "SL"
                elif current >= trade['tp_price']:
                    exit_trade = True
                    exit_reason = "TP"
                
                if exit_trade:
                    self.exit_trade(trade, current, exit_reason)
                    trade['exit_price'] = current
                    trade['exit_time'] = datetime.now().isoformat()
                    trade['exit_reason'] = exit_reason
                    trade['status'] = 'CLOSED'
                    trade['pnl'] = (current - trade['entry_price']) * trade['quantity']
                    
                    # Add TSL info to trade record
                    if Config.TSL_ENABLED:
                        trade['tsl_final_price'] = effective_sl_price
                        trade['tsl_was_triggered'] = trade.get('tsl_triggered', False)
                        trade['highest_reached'] = trade.get('highest_price', trade['entry_price'])
                    
                    completed.append(trade)
                    st.session_state.active_trades.remove(trade)
                    
            except Exception as e:
                print(f"Error monitoring trade {trade.get('symbol', 'Unknown')}: {e}")
                continue
        
        if completed:
            self.save_trades()
        return completed
    
    def exit_trade(self, trade, price, reason):
        try:
            exchange = trade.get('exchange', 'NFO')
            order_type = self.kite.ORDER_TYPE_MARKET
            exit_price = None
            
            if exchange == "MCX":
                order_type = self.kite.ORDER_TYPE_LIMIT
                exit_price = price
                exit_price = round_to_tick(exit_price, trade['index'])
            
            exit_order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=exchange,
                tradingsymbol=trade['symbol'],
                transaction_type=self.kite.TRANSACTION_TYPE_SELL,
                quantity=trade['quantity'],
                order_type=order_type,
                price=exit_price,
                product=self.kite.PRODUCT_MIS,
                validity=self.kite.VALIDITY_DAY
            )
            
            exit_record = {
                'order_id': exit_order_id,
                'symbol': trade['symbol'],
                'index': trade['index'],
                'exchange': exchange,
                'strike': trade.get('strike'),
                'option_type': trade['option_type'],
                'entry_price': price,
                'entry_time': datetime.now().isoformat(),
                'quantity': trade['quantity'],
                'status': 'PENDING',
                'signal': 'EXIT',
                'reason': f'{reason} exit'
            }
            
            # Add TSL info to exit record if applicable
            if Config.TSL_ENABLED and reason == 'TSL':
                exit_record['tsl_info'] = {
                    'triggered': trade.get('tsl_triggered', False),
                    'final_tsl_price': trade.get('tsl_price'),
                    'highest_price': trade.get('highest_price')
                }
            
            self.add_order_record(exit_record)
            
        except Exception as e:
            print(f"Error exiting trade: {e}")
            self.add_order_record({
                'order_id': None,
                'symbol': trade['symbol'],
                'index': trade['index'],
                'exchange': exchange,
                'strike': trade.get('strike'),
                'option_type': trade['option_type'],
                'entry_price': price,
                'entry_time': datetime.now().isoformat(),
                'quantity': trade['quantity'],
                'status': 'REJECTED',
                'signal': 'EXIT',
                'reason': f'Exit failed: {str(e)}'
            })
    
    def square_off_all(self):
        for trade in st.session_state.active_trades:
            try:
                exchange = trade.get('exchange', 'NFO')
                ltp_data = self.kite.ltp(f"{exchange}:{trade['symbol']}")
                current = ltp_data[f"{exchange}:{trade['symbol']}"]["last_price"]
                current = round_to_tick(current, trade['index'])
                self.exit_trade(trade, current, "Square Off")
                trade['exit_price'] = current
                trade['exit_time'] = datetime.now().isoformat()
                trade['exit_reason'] = "Square Off"
                trade['status'] = 'CLOSED'
                trade['pnl'] = (current - trade['entry_price']) * trade['quantity']
            except Exception as e:
                print(f"Error squaring off {trade.get('symbol')}: {e}")
                continue
        
        st.session_state.active_trades.clear()
        self.save_trades()
    
    def refresh_order_statuses(self):
        try:
            kite_orders = self.kite.orders()
            kite_orders_dict = {str(o['order_id']): o for o in kite_orders}
            
            updated = False
            for i, order in enumerate(st.session_state.order_history):
                order_id = order.get('order_id')
                if order_id and order_id in kite_orders_dict:
                    kite_order = kite_orders_dict[order_id]
                    if order.get('status') != kite_order['status']:
                        st.session_state.order_history[i]['status'] = kite_order['status']
                        st.session_state.order_history[i]['reason'] = kite_order.get('status_message', kite_order.get('rejection_reason', ''))
                        
                        if kite_order['status'] == 'REJECTED':
                            st.session_state.order_history[i]['rejection_reason'] = kite_order.get('rejection_reason', '')
                            st.session_state.order_history[i]['status_message'] = kite_order.get('status_message', '')
                        
                        updated = True
            
            if updated:
                self.save_orders()
                return True
        except Exception as e:
            print(f"Error refreshing order statuses: {e}")
        
        return False

# --- AUTHENTICATION ---
def render_login_screen():
    """Render the login screen on the right dashboard"""
    if st.session_state.auth_status:
        return None
    
    st.markdown("""
        <div style="text-align: center; margin-bottom: 3rem;">
            <h1 style="color: #4F46E5; margin-bottom: 0.5rem;">OPTIONS AUTO TRADING BOT</h1>
            <h3 style="color: #4F46E5; margin-bottom: 0.5rem;">🔐 ZERODHA LOGIN</h3>
        </div>
    """, unsafe_allow_html=True)
    
    # Load saved credentials if they exist
    saved_api_key, saved_api_secret = load_credentials()
    
    # Check if access token exists
    has_token = os.path.exists(Config.TOKEN_FILE)
    
    if saved_api_key and saved_api_secret and has_token:
        st.markdown(f'''
        <div style="background: #E8F5E9; border-radius: 10px; padding: 1rem; margin-bottom: 1rem;">
            <div style="text-align: center; margin-bottom: 0.5rem;">
                <span style="color: #15803D; font-weight: bold;">✓ Saved Credentials Found</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Auto-login button
        if st.button("🔓 AUTO LOGIN", type="primary", use_container_width=True):
            try:
                kite = KiteConnect(api_key=saved_api_key)
                
                with open(Config.TOKEN_FILE, "r") as f:
                    saved_token = f.read().strip()
                
                kite.set_access_token(saved_token)
                profile = kite.profile()
                
                st.session_state.auth_status = True
                st.session_state.kite = kite
                st.session_state.user_name = profile['user_name']
                st.session_state.api_key = saved_api_key
                st.session_state.api_secret = saved_api_secret
                
                st.success(f"✅ Welcome back {profile['user_name']}!")
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"Auto-login failed: {str(e)}")
                if "invalid_session" in str(e).lower() or "expired" in str(e).lower():
                    st.info("Session expired. Please re-authenticate.")
                    clear_access_token()
                    st.session_state.login_step = 'initial'
                    st.rerun()
        
        if st.button("🗑️ Clear Saved Credentials", type="secondary", use_container_width=True):
            if clear_credentials() and clear_access_token():
                st.session_state.login_step = 'initial'
                st.rerun()
    
    # Login steps (only show if no auto-login or auto-login failed)
    if not st.session_state.auth_status:
        if st.session_state.login_step == 'initial':
            api_key = st.text_input("API Key", type="password", value=st.session_state.api_key)
            api_secret = st.text_input("API Secret", type="password", value=st.session_state.api_secret)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔑 Save & Continue", use_container_width=True, type="primary"):
                    if api_key and api_secret:
                        if save_credentials(api_key, api_secret):
                            st.session_state.api_key = api_key
                            st.session_state.api_secret = api_secret
                            st.session_state.login_step = 'request_token'
                            st.rerun()
                        else:
                            st.error("Failed to save credentials")
            
            with col2:
                if st.button("Skip Saving", use_container_width=True):
                    if api_key and api_secret:
                        st.session_state.api_key = api_key
                        st.session_state.api_secret = api_secret
                        st.session_state.login_step = 'request_token'
                        st.rerun()
        
        elif st.session_state.login_step == 'request_token':
            st.info("Step 2: Get Request Token from Zerodha")
            
            try:
                kite = KiteConnect(api_key=st.session_state.api_key)
                login_url = kite.login_url()
                
                st.markdown(f'''
                <div style="text-align: center; margin: 1rem 0;">
                    <a href="{login_url}" target="_blank">
                        <button style="width: 100%; padding: 0.8rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 10px; font-weight: bold; cursor: pointer; font-size: 1rem;">
                            🔗 Login to Zerodha & Get Request Token
                        </button>
                    </a>
                </div>
                ''', unsafe_allow_html=True)
                
                request_token = st.text_input("Request Token", type="password", placeholder="Paste your request token here")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("✅ Authenticate", use_container_width=True, type="primary"):
                        if request_token:
                            try:
                                data = kite.generate_session(request_token, api_secret=st.session_state.api_secret)
                                
                                with open(Config.TOKEN_FILE, "w") as f:
                                    f.write(data["access_token"])
                                
                                kite.set_access_token(data["access_token"])
                                profile = kite.profile()
                                
                                st.session_state.auth_status = True
                                st.session_state.kite = kite
                                st.session_state.user_name = profile['user_name']
                                st.session_state.login_step = 'initial'
                                
                                if not (saved_api_key and saved_api_secret):
                                    save_credentials(st.session_state.api_key, st.session_state.api_secret)
                                
                                st.success(f"✅ Authentication successful! Welcome {profile['user_name']}!")
                                time.sleep(2)
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Authentication failed: {str(e)}")
                
                with col2:
                    if st.button("🔄 Back", use_container_width=True):
                        st.session_state.login_step = 'initial'
                        st.rerun()
            
            except Exception as e:
                st.error(f"Error: {str(e)}")
                if st.button("Back to Credentials"):
                    st.session_state.login_step = 'initial'
                    st.rerun()
    
    st.markdown("""
        <div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #E5E7EB; text-align: center;">
            <p style="color: #6B7280; font-size: 0.8rem;">
                Need help? Visit <a href="https://kite.trade/docs/connect/v3/" target="_blank" style="color: #4F46E5;">Zerodha API Documentation</a>
            </p>
        </div>
    """, unsafe_allow_html=True)

# --- MARKET DATA ---
def fetch_market_data(kite, index_name):
    """Fetch historical data and calculate indicators using Stochastic instead of ADX"""
    try:
        index_info = Config.INDEX_MAP.get(index_name, {})
        
        if index_name == "CRUDEOIL":
            exchange = "MCX"
            df = load_instruments(kite, exchange)
            
            if df is None:
                return False
            
            if 'instrument_type' in df.columns:
                futures = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                            (df['instrument_type'] == 'FUT')].copy()
            else:
                futures = df[(df['name'].str.contains('CRUDEOIL', case=False, na=False)) & 
                            (df.iloc[:, 9] == 'FUT')].copy()
            
            if len(futures) == 0:
                return False
            
            if 'expiry' in futures.columns:
                futures['expiry_dt'] = pd.to_datetime(futures['expiry'])
            else:
                futures['expiry_dt'] = pd.to_datetime(futures.iloc[:, 5])
            
            nearest_fut = futures.loc[futures['expiry_dt'].idxmin()]
            
            if 'instrument_token' in nearest_fut:
                token = nearest_fut['instrument_token']
            else:
                token = nearest_fut.iloc[0]
                
        else:
            token = index_info.get("spot_token")
        
        if not token:
            return False
        
        now = datetime.now()
        from_date = now - timedelta(days=5)
        
        try:
            hist = kite.historical_data(instrument_token=token, 
                                       from_date=from_date, 
                                       to_date=now, 
                                       interval="5minute")
        except Exception as e:
            print(f"Error fetching historical data: {e}")
            try:
                hist = kite.historical_data(instrument_token=token, 
                                           from_date=from_date, 
                                           to_date=now, 
                                           interval="5minute",
                                           continuous=False,
                                           oi=False)
            except Exception as e2:
                print(f"Error fetching historical data (2nd attempt): {e2}")
                return False
        
        if len(hist) < 50:
            print(f"Insufficient historical data: {len(hist)} records")
            return False
        
        df = pd.DataFrame(hist)
        
        # Calculate EMAs
        df['ema5'] = talib.EMA(df['close'], 5)
        df['ema8'] = talib.EMA(df['close'], 8)
        df['ema13'] = talib.EMA(df['close'], 13)
        
        # Calculate Stochastic indicator (14,3,3 is standard)
        df['slowk'], df['slowd'] = talib.STOCH(df['high'], df['low'], df['close'],
                                               fastk_period=14,
                                               slowk_period=3,
                                               slowk_matype=0,
                                               slowd_period=3,
                                               slowd_matype=0)
        
        # Remove NaN values
        df = df.dropna()
        
        if len(df) == 0:
            print("No valid data after removing NaN")
            return False
        
        last = df.iloc[-1]
        
        # Get current price
        current_price = get_reference_price(kite, index_name)
        
        # Generate signal based on EMA alignment and Stochastic position
        bullish_ema = (last['close'] > last['ema5'] > last['ema8'] > last['ema13'])
        bearish_ema = (last['close'] < last['ema5'] < last['ema8'] < last['ema13'])
        
        # Stochastic conditions
        stoch_k = last['slowk'] if not pd.isna(last['slowk']) else 50
        stoch_d = last['slowd'] if not pd.isna(last['slowd']) else 50
        
        # Check if Stochastic is in overbought (>80) or oversold (<20) territory
        stoch_overbought = stoch_k > 80 and stoch_d > 80
        stoch_oversold = stoch_k < 20 and stoch_d < 20
        
        # Check if Stochastic lines are crossing
        stoch_bullish_cross = stoch_k > stoch_d and stoch_k > 50
        stoch_bearish_cross = stoch_k < stoch_d and stoch_k < 50
        
        # Generate signal
        if bullish_ema and (stoch_oversold or stoch_bullish_cross):
            signal = "Bullish"
            signal_reason = "EMA alignment + Stochastic favorable"
        elif bearish_ema and (stoch_overbought or stoch_bearish_cross):
            signal = "Bearish"
            signal_reason = "EMA alignment + Stochastic favorable"
        elif stoch_oversold:
            signal = "Bullish (Stoch Oversold)"
            signal_reason = "Stochastic in oversold territory"
        elif stoch_overbought:
            signal = "Bearish (Stoch Overbought)"
            signal_reason = "Stochastic in overbought territory"
        elif stoch_bullish_cross:
            signal = "Bullish (Stoch Cross)"
            signal_reason = "Stochastic bullish crossover"
        elif stoch_bearish_cross:
            signal = "Bearish (Stoch Cross)"
            signal_reason = "Stochastic bearish crossover"
        elif bullish_ema:
            signal = "Bullish (EMA only)"
            signal_reason = "EMA alignment but Stochastic neutral"
        elif bearish_ema:
            signal = "Bearish (EMA only)"
            signal_reason = "EMA alignment but Stochastic neutral"
        else:
            signal = "No Trade"
            signal_reason = "No clear signal"
        
        # Store in session state
        st.session_state.market_data = {
            'current_price': current_price,
            'stoch_k': stoch_k,
            'stoch_d': stoch_d,
            'stoch_position': "Overbought" if stoch_overbought else "Oversold" if stoch_oversold else "Neutral",
            'ema5': last['ema5'],
            'ema8': last['ema8'],
            'ema13': last['ema13'],
            'signal': signal,
            'signal_reason': signal_reason,
            'stoch_bullish_cross': stoch_bullish_cross,
            'stoch_bearish_cross': stoch_bearish_cross
        }
        
        # Set last signal time for cooldown
        if signal != "No Trade":
            st.session_state.last_signal_time = datetime.now()
        
        return True
        
    except Exception as e:
        print(f"Error in fetch_market_data: {e}")
        import traceback
        traceback.print_exc()
        return False

# --- MAIN APP ---
def main():
    init_session_state()
    
    if st.session_state.auth_status and st.session_state.kite:
        kite = st.session_state.kite
        trade_manager = TradeManager(kite)
        
        # --- TOP NAVIGATION & HEADER ---
        col_h1, col_h2 = st.columns([3, 1])
        with col_h1:
            st.markdown('<h1 style="color: white; margin-bottom: 0;">🤖 Options Trading Bot Dashboard</h1>', unsafe_allow_html=True)
            st.markdown('<p class="subheading">Trade Banknifty, Nifty & MCX Options</p>', unsafe_allow_html=True)
        with col_h2:
            st.markdown(f"👤 **{st.session_state.user_name}**")
            if st.button("Logout", use_container_width=True):
                clear_access_token()
                st.rerun()

        # --- LIVE DATA SYNC ---
        try:
            ref_price = get_reference_price(kite, st.session_state.selected_index)
            st.session_state.market_data['ltp'] = ref_price
        except:
            st.session_state.market_data['ltp'] = 0.0

        # --- COMPACT METRICS BAR (LTP & SIGNAL) ---
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        with m1:
            status = "🟢 Active" if st.session_state.bot_running else "🔴 Idle"
            st.markdown(f'<div class="metric-card"><div class="metric-label">Bot Status</div><div class="metric-value">{status}</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{st.session_state.selected_index} LTP</div><div class="metric-value">₹ {format_price(st.session_state.market_data["ltp"])}</div></div>', unsafe_allow_html=True)
        with m3:
            signal_text = st.session_state.last_signal if st.session_state.last_signal else "WAITING"
            st.markdown(f'<div class="metric-card"><div class="metric-label">Last Signal</div><div class="metric-value">{signal_text}</div></div>', unsafe_allow_html=True)
        with m4:
            signal_reason = st.session_state.market_data.get('signal_reason', 'No reason')
            st.markdown(f'<div class="metric-card"><div class="metric-label">Signal Reason</div><div class="metric-value">{signal_reason}</div></div>', unsafe_allow_html=True)
        with m5:
            # Show cooldown status if active
            cooldown_active, cooldown_msg = is_cooldown_active()
            if cooldown_active:
                status_msg = f"⏳ {cooldown_msg.split(':')[-1].strip()}"
            else:
                status_msg = "✅ Ready"
            st.markdown(f'<div class="metric-card"><div class="metric-label">Order Status</div><div class="metric-value">{status_msg}</div></div>', unsafe_allow_html=True)
        with m6:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Daily Trades</div><div class="metric-value">{st.session_state.today_trades_count} / {Config.MAX_TRADES_PER_DAY}</div></div>', unsafe_allow_html=True)
        
        # --- MAIN DASHBOARD TABS ---
        tabs = st.tabs(["📊 Live Market", "📜 Order Log", "🛠 Setup"])
        
        with tabs[0]:
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.markdown("#### Active Positions")
                if st.session_state.active_trades:
                    # Create a formatted dataframe for active trades
                    active_data = []
                    for trade in st.session_state.active_trades:
                        row = {
                            'Symbol': trade['symbol'],
                            'Entry': f"₹{trade['entry_price']:.2f}",
                            'Qty': trade['quantity'],
                            'Current SL': f"₹{trade['sl_price']:.2f}",
                            'TP': f"₹{trade['tp_price']:.2f}",
                            'Status': trade['status']
                        }
                        
                        # Add TSL info if enabled
                        if Config.TSL_ENABLED:
                            tsl_status = "ACTIVE" if trade.get('tsl_triggered', False) else "INACTIVE"
                            row['TSL Status'] = tsl_status
                            if trade.get('tsl_triggered', False):
                                row['TSL Price'] = f"₹{trade.get('tsl_price', 0):.2f}"
                            row['Highest'] = f"₹{trade.get('highest_price', trade['entry_price']):.2f}"
                        
                        active_data.append(row)
                    
                    if active_data:
                        active_df = pd.DataFrame(active_data)
                        st.dataframe(active_df, use_container_width=True)
                    
                    # Show square off warning if approaching market close
                    index_name = st.session_state.selected_index
                    if should_square_off_before_close(index_name):
                        trade_start, entry_end, square_off_time = get_trading_hours(index_name)
                        st.warning(f"⚠️ Market closing soon! All positions will be squared off by {square_off_time.strftime('%H:%M')}")
                else:
                    st.info("No active trades. Waiting for signal...")
            
            with col_r:
                st.markdown("#### Trading Controls")
                # START/STOP BUTTONS
                if not st.session_state.bot_running:
                    if st.button("▶️ START BOT", type="primary", use_container_width=True):
                        st.session_state.bot_running = True
                        st.rerun()
                else:
                    if st.button("⏹️ STOP BOT", type="secondary", use_container_width=True):
                        st.session_state.bot_running = False
                        st.rerun()
                
                # SQUARE OFF BUTTON
                if st.button("🚨 SQUARE OFF ALL", type="primary", use_container_width=True):
                    trade_manager.square_off_all()
                    st.warning("All active positions have been squared off.")

        with tabs[1]:
            st.markdown("#### Activity & Order History")
            if st.session_state.order_history:
                # Create a formatted dataframe for order history
                log_data = []
                for order in reversed(st.session_state.order_history[-50:]):  # Show last 50 orders
                    row = {
                        'Time': order.get('entry_time', ''),
                        'Symbol': order.get('symbol', ''),
                        'Signal': order.get('signal', ''),
                        'Qty': order.get('quantity', ''),
                        'Status': order.get('status', ''),
                        'Reason': order.get('reason', '')[:50]  # Limit length
                    }
                    
                    # Add exit reason if available
                    if order.get('signal') == 'EXIT':
                        row['Exit Reason'] = order.get('reason', '').split(' ')[0] if order.get('reason') else ''
                    
                    log_data.append(row)
                
                if log_data:
                    log_df = pd.DataFrame(log_data)
                    st.dataframe(log_df, use_container_width=True)
            else:
                st.info("Log is currently empty. Orders will appear here once the bot starts trading.")

        with tabs[2]:
            st.markdown("#### ⚙️ Instrument & Risk Settings")
            
            # INSTRUMENT SELECTION
            index_options = list(Config.INDEX_MAP.keys())
            st.session_state.selected_index = st.selectbox(
                "Select Trading Instrument (Crudeoil, Banknifty, Nifty)", 
                options=index_options, 
                index=index_options.index(st.session_state.selected_index)
            )

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                Config.NUMBER_OF_LOTS = st.number_input("Lots", 1, 100, Config.NUMBER_OF_LOTS)
                Config.SL_POINTS = st.number_input("Stop Loss (Points)", 1, 500, Config.SL_POINTS)
                Config.TP_POINTS = st.number_input("Target (Points)", 1, 1000, Config.TP_POINTS)
                Config.MAX_LOSS_PER_DAY = st.number_input("Daily Max Loss (₹)", 500, 50000, Config.MAX_LOSS_PER_DAY)
                Config.COOLDOWN_AFTER_ORDER = st.number_input("Order Cooldown (seconds)", 10, 300, Config.COOLDOWN_AFTER_ORDER)
                
            with col_p2:
                Config.OTM_DISTANCE = st.number_input("OTM Strike Distance", 0, 10, Config.OTM_DISTANCE)
                Config.TSL_ENABLED = st.checkbox("Enable Trailing Stop Loss (TSL)", value=Config.TSL_ENABLED)
                if Config.TSL_ENABLED:
                    Config.TSL_TRIGGER = st.number_input("TSL Trigger (Points)", 1, 200, Config.TSL_TRIGGER)
                    Config.TSL_STEP = st.number_input("TSL Step (Points)", 1, 100, Config.TSL_STEP)
                    
                    # Validation: TSL Step must be less than TSL Trigger
                    if Config.TSL_STEP >= Config.TSL_TRIGGER:
                        st.warning("⚠️ TSL Step should be less than TSL Trigger for proper trailing.")
                
                Config.MAX_TRADES_PER_DAY = st.number_input("Max Trades/Day", 1, 50, Config.MAX_TRADES_PER_DAY)
                Config.COOLDOWN_AFTER_SIGNAL = st.number_input("Signal Cooldown (seconds)", 5, 120, Config.COOLDOWN_AFTER_SIGNAL)
            
            if st.button("Apply & Save Settings", use_container_width=True):
                # Validate TSL settings
                if Config.TSL_ENABLED and Config.TSL_STEP >= Config.TSL_TRIGGER:
                    st.error("TSL Step must be less than TSL Trigger. Please adjust values.")
                else:
                    if save_config():
                        st.success("Configuration updated and saved to bot_config.json")
                    else:
                        st.error("Failed to save configuration")

        # --- BOT LOGIC LOOP ---
        if st.session_state.bot_running:
            # Reset square off flag at the start of each day
            now = datetime.now()
            if now.hour == 0 and now.minute < 5:  # Reset at midnight
                st.session_state.square_off_triggered = False
            
            # Fetch market data and generate signals
            if fetch_market_data(kite, st.session_state.selected_index):
                signal = st.session_state.market_data.get('signal', 'No Trade')
                signal_reason = st.session_state.market_data.get('signal_reason', '')
                
                # Update last signal
                st.session_state.last_signal = f"{signal} - {signal_reason}"
                
                # Check if we should place a trade
                can_trade, reason = trade_manager.can_trade()
                
                if can_trade and ("Bullish" in signal or "Bearish" in signal):
                    # Determine signal type
                    signal_type = "BUY" if "Bullish" in signal else "SELL"
                    
                    # Get reference price
                    ref_price = get_reference_price(kite, st.session_state.selected_index)
                    
                    # Place order
                    order_id = trade_manager.place_order(
                        st.session_state.selected_index, 
                        signal_type, 
                        ref_price
                    )
                    
                    if order_id:
                        st.toast(f"Order placed: {signal_type} {st.session_state.selected_index}")
                    else:
                        st.toast(f"Failed to place order for {signal_type} signal")
                elif not can_trade and reason:
                    # Show why we can't trade
                    st.toast(f"Not trading: {reason}")
            
            # Monitor active trades for SL/TP/TSL
            trade_manager.monitor_trades()
            trade_manager.update_stats()
            
            # Small delay before next refresh
            time.sleep(2)
            st.rerun()

    else:
        # Show login screen if not authenticated
        render_login_screen()

if __name__ == "__main__":
    main()
