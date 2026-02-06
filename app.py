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
import plotly.graph_objects as go
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
        font-size: 1.5rem;
        color: #94A3B8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 500;
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

    /* Input Fields */
    input, select, textarea {
        background-color: #0F172A !important;
        color: white !important;
        border: 1px solid #334155 !important;
    }

    /* Custom P&L Colors */
    .pnl-positive { color: #10B981; font-weight: bold; }
    .pnl-negative { color: #EF4444; font-weight: bold; }
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
    TSL_TRIGGER = 25
    TSL_STEP = 10
    MAX_TRADES_PER_DAY = 5
    MAX_LOSS_PER_DAY = 3000
    TRADE_START = dtime(9, 20)
    ENTRY_END = dtime(14, 45)
    SQUARE_OFF_TIME = dtime(15, 10)
    
    # MCX specific timings for CRUDEOIL
    MCX_TRADE_START = dtime(9, 30)
    MCX_ENTRY_END = dtime(22, 0)
    MCX_SQUARE_OFF_TIME = dtime(23, 00)
    
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
        'api_secret': ''
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
            'TSL_TRIGGER': Config.TSL_TRIGGER,
            'TSL_STEP': Config.TSL_STEP,
            'MAX_TRADES_PER_DAY': Config.MAX_TRADES_PER_DAY,
            'MAX_LOSS_PER_DAY': Config.MAX_LOSS_PER_DAY
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
        trade_start, entry_end, _ = get_trading_hours(index_name)
        
        now_time = datetime.now().time()
        if not (trade_start <= now_time <= entry_end):
            return False, "Outside trading hours"
        
        if st.session_state.today_trades_count >= Config.MAX_TRADES_PER_DAY:
            return False, "Max trades reached"
        
        if st.session_state.today_loss >= Config.MAX_LOSS_PER_DAY:
            return False, "Max loss reached"
        
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
                
                sl_price = ltp - Config.SL_POINTS
                tp_price = ltp + Config.TP_POINTS
                
                sl_price = round_to_tick(sl_price, index_name)
                tp_price = round_to_tick(tp_price, index_name)
                
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
                    'reason': 'Order placed successfully'
                }
                
                self.add_order_record(order_record)
                
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
        for trade in st.session_state.active_trades[:]:
            try:
                exchange = trade.get('exchange', 'NFO')
                ltp_data = self.kite.ltp(f"{exchange}:{trade['symbol']}")
                current = ltp_data[f"{exchange}:{trade['symbol']}"]["last_price"]
                
                current = round_to_tick(current, trade['index'])
                
                if current <= trade['sl_price']:
                    self.exit_trade(trade, current, "SL")
                    trade['exit_price'] = current
                    trade['exit_time'] = datetime.now().isoformat()
                    trade['exit_reason'] = "SL"
                    trade['status'] = 'CLOSED'
                    trade['pnl'] = (current - trade['entry_price']) * trade['quantity']
                    completed.append(trade)
                    st.session_state.active_trades.remove(trade)
                elif current >= trade['tp_price']:
                    self.exit_trade(trade, current, "TP")
                    trade['exit_price'] = current
                    trade['exit_time'] = datetime.now().isoformat()
                    trade['exit_reason'] = "TP"
                    trade['status'] = 'CLOSED'
                    trade['pnl'] = (current - trade['entry_price']) * trade['quantity']
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
            
            self.add_order_record({
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
            })
            
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
            except Exception as e:
                print(f"Error squareing off {trade.get('symbol')}: {e}")
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

# --- AUTHENTICATION (RIGHT SIDE DASHBOARD) ---

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
                <span style="color: #15803D; font-weight: bold;">✓ Credentials (api_key , api_secret & access_token) Found</span>
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
    
    st.markdown('</div>', unsafe_allow_html=True)
# --- SIDEBAR CONTROLS ---
def render_sidebar_controls(kite, trade_manager):
    """Render bot controls in the left sidebar"""
    if kite and st.session_state.auth_status:
        st.sidebar.markdown('<div class="section-header">🤖 BOT CONTROLS</div>', unsafe_allow_html=True)
        
        # Bot Status Display
        status_color = "status-green" if st.session_state.bot_running else "status-red"
        status_text = "RUNNING" if st.session_state.bot_running else "STOPPED"
        st.sidebar.markdown(f'''
        <div class="metric-container">
            <div class="metric-label">BOT STATUS</div>
            <span class="status-badge {status_color}">{status_text}</span>
        </div>
        ''', unsafe_allow_html=True)
        
        # Control Buttons
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            start_disabled = st.session_state.bot_running
            if st.button("▶️ START", 
                        use_container_width=True,
                        disabled=start_disabled,
                        type="primary"):
                st.session_state.bot_running = True
                st.rerun()
        
        with col2:
            stop_disabled = not st.session_state.bot_running
            if st.button("⏹️ STOP", 
                        use_container_width=True,
                        disabled=stop_disabled,
                        type="secondary"):
                st.session_state.bot_running = False
                st.rerun()
        
        # Refresh Orders Button
        if st.sidebar.button("🔄 REFRESH ORDERS", 
                           use_container_width=True,
                           type="secondary"):
            trade_manager.refresh_order_statuses()
            st.rerun()
        
        # Square Off Button
        square_disabled = len(st.session_state.active_trades) == 0
        if st.sidebar.button("🔄 SQUARE OFF ALL", 
                           use_container_width=True,
                           disabled=square_disabled,
                           type="secondary"):
            trade_manager.square_off_all()
            st.rerun()
        
        # Quick Stats
        st.sidebar.markdown('<div class="section-header">📊 QUICK STATS</div>', unsafe_allow_html=True)
        
        # Today's P&L
        today_pnl = sum(t.get('pnl', 0) for t in st.session_state.trade_history 
                       if t.get('status') == 'CLOSED' and 
                       datetime.fromisoformat(t['entry_time']).date() == datetime.now().date())
        
        st.sidebar.markdown(f'''
        <div class="metric-container">
            <div class="metric-label">TODAY'S P&L</div>
            <div class="metric-value">{format_pnl(today_pnl)}</div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Active Trades Count
        st.sidebar.markdown(f'''
        <div class="metric-container">
            <div class="metric-label">ACTIVE TRADES</div>
            <div class="metric-value">{len(st.session_state.active_trades)}</div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Rejected Orders Count
        rejected_count = sum(1 for o in st.session_state.order_history if o.get('status') == 'REJECTED')
        st.sidebar.markdown(f'''
        <div class="metric-container">
            <div class="metric-label">REJECTED ORDERS</div>
            <div class="metric-value">{rejected_count}</div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Trades Left Today
        remaining = max(0, Config.MAX_TRADES_PER_DAY - st.session_state.today_trades_count)
        st.sidebar.markdown(f'''
        <div class="metric-container">
            <div class="metric-label">TRADES LEFT</div>
            <div class="metric-value">{remaining}</div>
        </div>
        ''', unsafe_allow_html=True)
        
        # User Info
        st.sidebar.markdown('<div class="section-header">👤 USER INFO</div>', unsafe_allow_html=True)
        st.sidebar.markdown(f'''
        <div class="metric-container">
            <div class="metric-label">LOGGED IN AS</div>
            <div class="metric-value" style="font-size: 1rem;">
                {st.session_state.user_name[:20] if st.session_state.user_name else "N/A"}
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Logout Button
        if st.sidebar.button("🚪 LOGOUT", use_container_width=True, type="secondary"):
            st.session_state.auth_status = False
            st.session_state.kite = None
            st.session_state.user_name = None
            st.session_state.bot_running = False
            st.rerun()

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
        
        return True
        
    except Exception as e:
        print(f"Error in fetch_market_data: {e}")
        import traceback
        traceback.print_exc()
        return False
# --- DASHBOARD LAYOUT ---
def dashboard_tab(kite, trade_manager):
    """Dashboard layout - Shows after authentication"""
    
    # Get current index info
    index_name = st.session_state.selected_index
    index_info = Config.INDEX_MAP.get(index_name, {})
    
    # Calculate current lot size
    try:
        current_base_lot = get_base_lot_size(kite, index_name)
    except:
        current_base_lot = index_info.get("default_lot_size", 30)
    
    current_total_qty = current_base_lot * Config.NUMBER_OF_LOTS
    
    # Get trading hours
    trade_start, entry_end, square_off = get_trading_hours(index_name)
    
    # TOP BAR
    top_cols = st.columns([2, 1])
    
    with top_cols[0]:
        exchange_display = "MCX" if index_name == "CRUDEOIL" else "NFO"
        tick_size = index_info.get("tick_size", 0.05)
        st.markdown(f'''
        <div style="text-align: left;">
            <h3 style="margin: 0; color: #333;">{index_name} AUTO TRADING BOT</h3>
            <p style="margin: 0; color: #666; font-size: 0.9rem;">
                {exchange_display} • Lot: {current_base_lot} × {Config.NUMBER_OF_LOTS} = {current_total_qty} • Tick: {tick_size}
            </p>
        </div>
        ''', unsafe_allow_html=True)
    
    with top_cols[1]:
        user_display = st.session_state.user_name[:20] if st.session_state.user_name else "Not Logged In"
        st.markdown(f'''
        <div class="metric-container" style="text-align: right;">
            <div class="metric-label">USER • TIME</div>
            <div class="metric-value" style="font-size: 1rem;">
                {user_display}<br>
                {get_current_time()}
            </div>
        </div>
        ''', unsafe_allow_html=True)
    
    # MARKET DATA SECTION - Compact Card
    st.markdown('<div class="section-header">📊 MARKET DATA</div>', unsafe_allow_html=True)
    
    # Fetch market data
    fetch_success = fetch_market_data(kite, index_name)
    
    if not fetch_success:
        try:
            current_price = get_reference_price(kite, index_name)
            st.session_state.market_data = {
                'current_price': current_price,
                'signal': 'Data Fetch Failed'
            }
        except:
            st.session_state.market_data = {
                'current_price': 6000.0 if index_name == "CRUDEOIL" else 22000.0,
                'signal': 'Data Unavailable'
            }
    
    market_data = st.session_state.market_data
    
    # Create a compact grid for market data in one card
    st.markdown('<div class="metric-container">', unsafe_allow_html=True)
    
    # Row 1: Basic market info
    row1_cols = st.columns(6)
    with row1_cols[0]:
        current_price = market_data.get('current_price', 0)
        st.metric("Price", f"₹ {format_price(current_price)}")
    
    with row1_cols[1]:
        signal = market_data.get('signal', 'No Signal')
        signal_icon = "🟢" if signal == "Bullish" else "🔴" if signal == "Bearish" else "⚪"
        st.metric("Signal", f"{signal_icon} {signal}")
    
    with row1_cols[2]:
        now_time = datetime.now().time()
        market_open = trade_start <= now_time <= square_off
        market_status = "🟢 OPEN" if market_open else "🔴 CLOSED"
        st.metric("Market", market_status)
    
    with row1_cols[3]:
        if 'adx' in market_data:
            adx = market_data.get('adx', 0)
            st.metric("ADX", f"{adx:.2f}")
        else:
            st.metric("ADX", "N/A")
    
    with row1_cols[4]:
        st.metric("Trades Today", st.session_state.today_trades_count)
    
    with row1_cols[5]:
        st.metric("Trade Hours", f"{trade_start.strftime('%H:%M')}-{entry_end.strftime('%H:%M')}")
    
    # Row 2: EMA values
    row2_cols = st.columns(5)
    with row2_cols[0]:
        if 'ema5' in market_data:
            ema5 = market_data.get('ema5', 0)
            st.metric("EMA 5", f"₹ {format_price(ema5)}")
        else:
            st.metric("EMA 5", "N/A")
    
    with row2_cols[1]:
        if 'ema8' in market_data:
            ema8 = market_data.get('ema8', 0)
            st.metric("EMA 8", f"₹ {format_price(ema8)}")
        else:
            st.metric("EMA 8", "N/A")
    
    with row2_cols[2]:
        if 'ema13' in market_data:
            ema13 = market_data.get('ema13', 0)
            st.metric("EMA 13", f"₹ {format_price(ema13)}")
        else:
            st.metric("EMA 13", "N/A")
    
    with row2_cols[3]:
        if all(key in market_data for key in ['ema5', 'ema8', 'ema13']):
            ema5 = market_data.get('ema5', 0)
            ema8 = market_data.get('ema8', 0)
            ema13 = market_data.get('ema13', 0)
            trend = "BULLISH" if ema5 > ema8 > ema13 else "BEARISH" if ema5 < ema8 < ema13 else "NEUTRAL"
            st.metric("Trend", trend)
        else:
            st.metric("Trend", "N/A")
    
    with row2_cols[4]:
        remaining_trades = max(0, Config.MAX_TRADES_PER_DAY - st.session_state.today_trades_count)
        st.metric("Trades Left", remaining_trades)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ACTIVE TRADES
    st.markdown('<div class="section-header">📦 ACTIVE TRADES</div>', unsafe_allow_html=True)
    
    if st.session_state.active_trades:
        for trade in st.session_state.active_trades:
            try:
                exchange = trade.get('exchange', 'NFO')
                ltp_data = kite.ltp(f"{exchange}:{trade['symbol']}")
                current = ltp_data[f"{exchange}:{trade['symbol']}"]["last_price"]
                pnl = (current - trade['entry_price']) * trade['quantity']
                
                pnl_color = "#28a745" if pnl >= 0 else "#dc3545"
                
                st.markdown(f'''
                <div class="trade-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>{trade["symbol"]}</strong><br>
                            <small>{trade["option_type"]} • Qty: {trade["quantity"]}</small>
                        </div>
                        <div style="text-align: right;">
                            <div>Entry: ₹ {format_price(trade["entry_price"])}</div>
                            <div>LTP: ₹ {format_price(current)}</div>
                            <div>P&L: <span style="color: {pnl_color}">{format_pnl(pnl)}</span></div>
                        </div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            except:
                continue
    else:
        st.info("No active trades")
    
    # TRADING STATISTICS - Compact Card
    st.markdown('<div class="section-header">📈 TRADING STATISTICS</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="metric-container">', unsafe_allow_html=True)
    
    stats_cols = st.columns(4)
    
    with stats_cols[0]:
        total_pnl = sum(t.get('pnl', 0) for t in st.session_state.trade_history if t.get('status') == 'CLOSED')
        today_pnl = sum(t.get('pnl', 0) for t in st.session_state.trade_history 
                       if t.get('status') == 'CLOSED' and 
                       datetime.fromisoformat(t['entry_time']).date() == datetime.now().date())
        
        st.metric("Total P&L", format_pnl(total_pnl))
        st.metric("Today's P&L", format_pnl(today_pnl))
    
    with stats_cols[1]:
        st.metric("Today's Loss", f"₹ {format_full_number(st.session_state.today_loss, 2)}")
        buffer = max(0, Config.MAX_LOSS_PER_DAY - st.session_state.today_loss)
        st.metric("Loss Buffer", f"₹ {format_full_number(buffer, 2)}")
    
    with stats_cols[2]:
        rejected_today = sum(1 for o in st.session_state.order_history 
                           if o.get('status') == 'REJECTED' and 
                           datetime.fromisoformat(o['entry_time']).date() == datetime.now().date())
        total_orders = sum(1 for o in st.session_state.order_history 
                          if datetime.fromisoformat(o['entry_time']).date() == datetime.now().date())
        rejection_rate = (rejected_today / total_orders * 100) if total_orders > 0 else 0
        
        st.metric("Today's Rejections", rejected_today)
        st.metric("Rejection Rate", f"{rejection_rate:.1f}%")
    
    with stats_cols[3]:
        active_trades = len(st.session_state.active_trades)
        closed_today = sum(1 for t in st.session_state.trade_history 
                          if t.get('status') == 'CLOSED' and 
                          datetime.fromisoformat(t['entry_time']).date() == datetime.now().date())
        
        st.metric("Active Trades", active_trades)
        st.metric("Closed Today", closed_today)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ORDER HISTORY SECTION
    st.markdown('<div class="section-header">📋 ORDER HISTORY</div>', unsafe_allow_html=True)
    
    # Filter controls for orders
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        filter_date = st.selectbox(
            "Date Filter",
            ["Today", "Yesterday", "Last 7 Days", "All"],
            index=0
        )
    
    with col2:
        status_filter = st.selectbox(
            "Status Filter",
            ["All", "REJECTED", "COMPLETE", "OPEN", "PENDING"],
            index=0
        )
    
    with col3:
        sort_order = st.selectbox(
            "Sort",
            ["Newest First", "Oldest First"],
            index=0
        )
    
    # Filter orders
    filtered_orders = st.session_state.order_history.copy()
    
    # Apply date filter
    today = datetime.now().date()
    if filter_date == "Today":
        filtered_orders = [o for o in filtered_orders 
                          if datetime.fromisoformat(o['entry_time']).date() == today]
    elif filter_date == "Yesterday":
        yesterday = today - timedelta(days=1)
        filtered_orders = [o for o in filtered_orders 
                          if datetime.fromisoformat(o['entry_time']).date() == yesterday]
    elif filter_date == "Last 7 Days":
        week_ago = today - timedelta(days=7)
        filtered_orders = [o for o in filtered_orders 
                          if datetime.fromisoformat(o['entry_time']).date() >= week_ago]
    
    # Apply status filter
    if status_filter != "All":
        filtered_orders = [o for o in filtered_orders if o.get('status') == status_filter]
    
    # Sort orders
    if sort_order == "Newest First":
        filtered_orders.sort(key=lambda x: x.get('entry_time', ''), reverse=True)
    else:
        filtered_orders.sort(key=lambda x: x.get('entry_time', ''))
    
    if filtered_orders:
        # Create display data
        order_data = []
        for order in filtered_orders:
            try:
                entry_time = datetime.fromisoformat(order['entry_time'])
                time_str = entry_time.strftime("%H:%M:%S")
                date_str = entry_time.strftime("%Y-%m-%d")
                
                status = order.get('status', 'UNKNOWN')
                reason = order.get('reason', '')
                rejection_reason = order.get('rejection_reason', '')
                
                if status == 'REJECTED' and rejection_reason:
                    reason = f"{reason} ({rejection_reason})"
                
                order_data.append({
                    "Date": date_str,
                    "Time": time_str,
                    "Order ID": order.get('order_id', 'N/A'),
                    "Symbol": order.get('symbol', 'N/A'),
                    "Type": order.get('option_type', 'N/A'),
                    "Qty": order.get('quantity', 'N/A'),
                    "Price": format_price(order.get('entry_price', 0)) if order.get('entry_price') else 'N/A',
                    "Status": status,
                    "Reason": reason,
                    "Signal": order.get('signal', 'N/A')
                })
            except:
                continue
        
        if order_data:
            # Create DataFrame
            order_df = pd.DataFrame(order_data)
            
            # Style function for status
            def color_status(val):
                if val == 'REJECTED':
                    return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
                elif val == 'COMPLETE':
                    return 'background-color: #d4edda; color: #155724;'
                elif val == 'OPEN':
                    return 'background-color: #d1ecf1; color: #0c5460;'
                elif val == 'PENDING':
                    return 'background-color: #fff3cd; color: #856404;'
                else:
                    return ''
            
            # Display as styled table with word wrap for Reason column
            st.dataframe(
                order_df.style.applymap(color_status, subset=['Status']),
                use_container_width=True,
                hide_index=True,
                height=400,
                column_config={
                    "Date": st.column_config.TextColumn("Date", width="small"),
                    "Time": st.column_config.TextColumn("Time", width="small"),
                    "Order ID": st.column_config.TextColumn("Order ID", width="medium"),
                    "Symbol": st.column_config.TextColumn("Symbol", width="medium"),
                    "Type": st.column_config.TextColumn("Type", width="small"),
                    "Qty": st.column_config.NumberColumn("Qty", width="small"),
                    "Price": st.column_config.TextColumn("Price", width="small"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Reason": st.column_config.TextColumn("Reason", width="large", help="Reason for order status"),
                    "Signal": st.column_config.TextColumn("Signal", width="small")
                },
                column_order=["Date", "Time", "Order ID", "Symbol", "Type", "Qty", "Price", "Status", "Reason", "Signal"]
            )
            
            # Summary stats
            total_orders = len(filtered_orders)
            rejected_orders = sum(1 for o in filtered_orders if o.get('status') == 'REJECTED')
            complete_orders = sum(1 for o in filtered_orders if o.get('status') == 'COMPLETE')
            rejection_rate = (rejected_orders / total_orders * 100) if total_orders > 0 else 0
            
            summary_cols = st.columns(4)
            with summary_cols[0]:
                st.metric("Total Orders", total_orders)
            with summary_cols[1]:
                st.metric("Rejected Orders", rejected_orders)
            with summary_cols[2]:
                st.metric("Complete Orders", complete_orders)
            with summary_cols[3]:
                st.metric("Rejection Rate", f"{rejection_rate:.1f}%")
            
            # Export button
            if st.button("📥 Export Order History to CSV"):
                csv = order_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"order_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    else:
        st.info("No order history found with current filters")
    
    # REJECTED ORDERS DETAILS
    with st.expander("⚠️ DETAILED REJECTED ORDERS"):
        rejected_orders = [o for o in st.session_state.order_history if o.get('status') == 'REJECTED']
        
        if rejected_orders:
            rejected_orders.sort(key=lambda x: x.get('entry_time', ''), reverse=True)
            
            for order in rejected_orders[:10]:
                try:
                    entry_time = datetime.fromisoformat(order['entry_time'])
                    time_str = entry_time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    st.markdown(f'''
                    <div class="trade-card">
                        <div style="margin-bottom: 0.5rem;">
                            <strong>Rejected Order</strong> • {time_str}
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.9rem;">
                            <div>
                                <strong>Symbol:</strong> {order.get('symbol', 'N/A')}<br>
                                <strong>Type:</strong> {order.get('option_type', 'N/A')}<br>
                                <strong>Qty:</strong> {order.get('quantity', 'N/A')}
                            </div>
                            <div>
                                <strong>Signal:</strong> {order.get('signal', 'N/A')}<br>
                                <strong>Index:</strong> {order.get('index', 'N/A')}<br>
                                <strong>Exchange:</strong> {order.get('exchange', 'N/A')}
                            </div>
                        </div>
                        <div style="margin-top: 0.5rem; padding: 0.5rem; background: #f8d7da; border-radius: 4px; white-space: normal; word-wrap: break-word;">
                            <strong>Rejection Reason:</strong><br>
                            {order.get('reason', 'No reason provided')}
                        </div>
                        {f"<div style='margin-top: 0.5rem; padding: 0.5rem; background: #f5c6cb; border-radius: 4px; white-space: normal; word-wrap: break-word;'><strong>Detailed Reason:</strong><br>{order.get('rejection_reason', '')}</div>" if order.get('rejection_reason') else ""}
                        {f"<div style='margin-top: 0.5rem; padding: 0.5rem; background: #f5c6cb; border-radius: 4px; white-space: normal; word-wrap: break-word;'><strong>Status Message:</strong><br>{order.get('status_message', '')}</div>" if order.get('status_message') else ""}
                    </div>
                    ''', unsafe_allow_html=True)
                except:
                    continue
        else:
            st.info("No rejected orders found")
    
    # TRADE HISTORY
    st.markdown('<div class="section-header">💰 TRADE HISTORY (Today)</div>', unsafe_allow_html=True)
    
    today = datetime.now().date()
    today_trades = []
    for trade in st.session_state.trade_history:
        try:
            entry_time = datetime.fromisoformat(trade['entry_time'])
            if entry_time.date() == today and trade.get('status') == 'CLOSED':
                today_trades.append(trade)
        except:
            continue
    
    if today_trades:
        today_trades.sort(key=lambda x: x.get('entry_time', ''), reverse=True)
        
        history_data = []
        for trade in today_trades:
            try:
                entry_time = datetime.fromisoformat(trade['entry_time']).strftime("%H:%M:%S")
                exit_time = datetime.fromisoformat(trade['exit_time']).strftime("%H:%M:%S") if trade.get('exit_time') else "N/A"
                
                history_data.append({
                    "Time": f"{entry_time} → {exit_time}",
                    "Symbol": trade['symbol'],
                    "Type": trade['option_type'],
                    "Qty": trade['quantity'],
                    "Entry": format_price(trade['entry_price']),
                    "Exit": format_price(trade.get('exit_price', 0)),
                    "P&L": format_pnl(trade.get('pnl', 0)),
                    "Reason": trade.get('exit_reason', 'N/A')
                })
            except:
                continue
        
        if history_data:
            history_df = pd.DataFrame(history_data)
            
            def color_pnl(val):
                if '₹ +' in str(val):
                    return 'color: #28a745; font-weight: bold;'
                elif '₹ -' in str(val):
                    return 'color: #dc3545; font-weight: bold;'
                else:
                    return ''
            
            st.dataframe(
                history_df.style.applymap(color_pnl, subset=['P&L']),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Time": st.column_config.TextColumn("Time", width="medium"),
                    "Symbol": st.column_config.TextColumn("Symbol", width="medium"),
                    "Type": st.column_config.TextColumn("Type", width="small"),
                    "Qty": st.column_config.NumberColumn("Qty", width="small"),
                    "Entry": st.column_config.TextColumn("Entry", width="medium"),
                    "Exit": st.column_config.TextColumn("Exit", width="medium"),
                    "P&L": st.column_config.TextColumn("P&L", width="medium"),
                    "Reason": st.column_config.TextColumn("Reason", width="small")
                }
            )
            
            closed_pnl = sum(t.get('pnl', 0) for t in today_trades)
            win_trades = sum(1 for t in today_trades if t.get('pnl', 0) > 0)
            loss_trades = sum(1 for t in today_trades if t.get('pnl', 0) < 0)
            win_rate = (win_trades / len(today_trades) * 100) if today_trades else 0
            
            summary_cols = st.columns(4)
            with summary_cols[0]:
                st.metric("Total Closed Trades", len(today_trades))
            with summary_cols[1]:
                st.metric("Win Rate", f"{win_rate:.1f}%")
            with summary_cols[2]:
                st.metric("Wins/Losses", f"{win_trades}/{loss_trades}")
            with summary_cols[3]:
                st.metric("Today's Closed P&L", format_pnl(closed_pnl))
    else:
        st.info("No trade history for today")
def configuration_tab():
    """Clean configuration tab"""
    st.markdown('<div class="section-header">⚙️ BOT CONFIGURATION</div>', unsafe_allow_html=True)
    
    index_name = st.session_state.selected_index
    index_info = Config.INDEX_MAP.get(index_name, {})
    
    # Index Selection
    index_cols = st.columns([2, 1])
    with index_cols[0]:
        index_options = list(Config.INDEX_MAP.keys())
        selected = st.selectbox("TRADING INDEX", index_options, index=index_options.index(index_name))
        if selected != st.session_state.selected_index:
            st.session_state.selected_index = selected
            index_info = Config.INDEX_MAP.get(selected, {})
    
    with index_cols[1]:
        exchange_display = "MCX" if selected == "CRUDEOIL" else "NFO"
        tick_size = index_info.get("tick_size", 0.05)
        st.markdown(f'''
        <div class="metric-container">
            <div class="metric-label">INDEX INFO</div>
            <div class="metric-value" style="font-size: 1rem;">
                Exchange: {exchange_display}<br>
                Step: {index_info.get('step_size', 100)}<br>
                Tick: {tick_size}<br>
                Base Lot: {index_info.get('default_lot_size', 1)}
            </div>
        </div>
        ''', unsafe_allow_html=True)
    
    # Configuration in 3 columns
    config_cols = st.columns(3)
    
    with config_cols[0]:
        st.markdown("**TRADING PARAMETERS**")
        Config.OTM_DISTANCE = st.slider("OTM Strikes", 1, 5, Config.OTM_DISTANCE)
        Config.SL_POINTS = st.number_input("Stop Loss (Points)", 5, 100, Config.SL_POINTS)
        Config.TP_POINTS = st.number_input("Take Profit (Points)", 10, 200, Config.TP_POINTS)
        Config.MAX_TRADES_PER_DAY = st.number_input("Max Trades/Day", 1, 20, Config.MAX_TRADES_PER_DAY)
    
    with config_cols[1]:
        st.markdown("**POSITION SIZING**")
        Config.NUMBER_OF_LOTS = st.number_input("Number of Lots", 1, 10, Config.NUMBER_OF_LOTS)
        
        base_lot = index_info.get("default_lot_size", 1)
        auto_quantity = base_lot * Config.NUMBER_OF_LOTS
        
        st.markdown(f'''
        <div class="metric-container">
            <div class="metric-label">QUANTITY PER TRADE</div>
            <div class="metric-value">{auto_quantity}</div>
        </div>
        ''', unsafe_allow_html=True)
        
        Config.OVERRIDE_QUANTITY = st.checkbox("Override Quantity", Config.OVERRIDE_QUANTITY)
        if Config.OVERRIDE_QUANTITY:
            Config.TOTAL_QUANTITY = st.number_input("Manual Quantity", 1, 1000, Config.TOTAL_QUANTITY)
    
    with config_cols[2]:
        st.markdown("**RISK MANAGEMENT**")
        Config.MAX_LOSS_PER_DAY = st.number_input("Max Loss/Day (₹)", 500, 10000, Config.MAX_LOSS_PER_DAY)
        Config.TSL_TRIGGER = st.number_input("TSL Trigger (Points)", 5, 50, Config.TSL_TRIGGER)
        Config.TSL_STEP = st.number_input("TSL Step (Points)", 5, 50, Config.TSL_STEP)
        
        remaining_loss = max(0, Config.MAX_LOSS_PER_DAY - st.session_state.today_loss)
        st.markdown(f'''
        <div class="metric-container">
            <div class="metric-label">REMAINING LOSS LIMIT</div>
            <div class="metric-value">₹ {format_full_number(remaining_loss, 0)}</div>
        </div>
        ''', unsafe_allow_html=True)
    
    # Save button
    if st.button("💾 SAVE CONFIGURATION", use_container_width=True, type="primary"):
        if save_config():
            st.success("Configuration saved successfully!")


# ... (keep all the previous code until main function)

# --- MAIN APP ---
def check_auto_login():
    """Check if we can auto-login with saved credentials and token"""
    if st.session_state.auth_status:
        return True
    
    # Load saved credentials
    saved_api_key, saved_api_secret = load_credentials()
    
    if saved_api_key and saved_api_secret and os.path.exists(Config.TOKEN_FILE):
        try:
            # Try to authenticate with saved credentials
            kite = KiteConnect(api_key=saved_api_key)
            
            with open(Config.TOKEN_FILE, "r") as f:
                saved_token = f.read().strip()
            
            if saved_token:
                kite.set_access_token(saved_token)
                
                # Test authentication by fetching profile
                profile = kite.profile()
                
                # Update session state
                st.session_state.auth_status = True
                st.session_state.kite = kite
                st.session_state.user_name = profile['user_name']
                st.session_state.api_key = saved_api_key
                st.session_state.api_secret = saved_api_secret
                
                print(f"Auto-login successful for user: {profile['user_name']}")
                return True
            else:
                print("No token found in file")
                return False
                
        except Exception as e:
            print(f"Auto-login failed: {e}")
            # Token might be expired, clear it
            clear_access_token()
            return False
    
    return False

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
            signal_reason = fetch_market_data('signal_reason', 'No reason')
            st.markdown(f'<div class="metric-card"><div class="metric-label">Signal Reason</div><div class="metric-value">{signal_reason}</div></div>', unsafe_allow_html=True)
        with m5:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Today P&L</div><div class="metric-value">{format_pnl(st.session_state.today_loss)}</div></div>', unsafe_allow_html=True)
        with m6:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Daily Trades</div><div class="metric-value">{st.session_state.today_trades_count} / {Config.MAX_TRADES_PER_DAY}</div></div>', unsafe_allow_html=True)

        # --- MAIN DASHBOARD TABS ---
        tabs = st.tabs(["📊 Live Market", "📜 Order Log", "🛠 Setup"])
        
        with tabs[0]:
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.markdown("#### Active Positions")
                if st.session_state.active_trades:
                    # Filter and show active trades
                    active_df = pd.DataFrame(st.session_state.active_trades)
                    st.dataframe(active_df[['symbol', 'entry_price', 'quantity', 'status', 'sl_price', 'tp_price']], use_container_width=True)
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
                st.divider()
                if st.button("🚨 SQUARE OFF ALL", type="primary", use_container_width=True):
                    trade_manager.square_off_all()
                    st.warning("All active positions have been squared off.")

        with tabs[1]:
            st.markdown("#### Activity & Order History")
            # LOG FIX: Retrieve from session state order history
            if st.session_state.order_history:
                log_df = pd.DataFrame(st.session_state.order_history)
                # Sort by most recent first
                log_df = log_df.sort_index(ascending=False)
                st.dataframe(log_df[['entry_time', 'symbol', 'signal', 'quantity', 'status', 'reason']], use_container_width=True)
            else:
                st.info("Log is currently empty. Orders will appear here once the bot starts trading.")

        with tabs[2]:
            st.markdown("#### ⚙️ Instrument & Risk Settings")
            
            # INSTRUMENT SELECTION
            index_options = list(Config.INDEX_MAP.keys())
            st.session_state.selected_index = st.selectbox(
                "Select Trading Instrument (Nifty, Banknifty, Crudeoil)", 
                options=index_options, 
                index=index_options.index(st.session_state.selected_index)
            )

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                Config.NUMBER_OF_LOTS = st.number_input("Lots", 1, 100, Config.NUMBER_OF_LOTS)
                Config.SL_POINTS = st.number_input("Stop Loss (Points)", 1, 500, Config.SL_POINTS)
                Config.MAX_LOSS_PER_DAY = st.number_input("Daily Max Loss (₹)", 500, 50000, Config.MAX_LOSS_PER_DAY)
            with col_p2:
                Config.OTM_DISTANCE = st.number_input("OTM Strike Distance", 0, 10, Config.OTM_DISTANCE)
                Config.TP_POINTS = st.number_input("Target (Points)", 1, 1000, Config.TP_POINTS)
                Config.MAX_TRADES_PER_DAY = st.number_input("Max Trades/Day", 1, 50, Config.MAX_TRADES_PER_DAY)
            
            if st.button("Apply & Save Settings", use_container_width=True):
                save_config()
                st.success("Configuration updated and saved to bot_config.json")

        # --- BOT LOGIC LOOP ---
        if st.session_state.bot_running:
            # Monitor active trades for SL/TP
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
