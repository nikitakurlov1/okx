# OKX Backend API

This is the backend API for the OKX trading platform clone. It handles user registration, authentication, balance management, and bet placement.

## Features

- User registration with starting balance of 0
- User authentication
- Real-time balance updates via WebSocket
- Bet placement and balance deduction
- Automatic bet result simulation
- SQLite database for data storage

## Technologies Used

- Python 3.x
- Flask
- Flask-SocketIO
- SQLite

## Setup Instructions

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Run the application:
   ```
   python app.py
   ```
   
   Or use the startup script:
   ```
   ./start.sh
   ```

5. The backend will start on `http://localhost:5000`

## API Endpoints

### User Registration
- **URL**: `/api/register`
- **Method**: `POST`
- **Body**: 
  ```json
  {
    "telegram": "username",
    "email": "user@example.com",
    "password": "password123"
  }
  ```
- **Response**: 
  ```json
  {
    "success": true,
    "message": "User registered successfully",
    "balance": 0.0
  }
  ```

### User Login
- **URL**: `/api/login`
- **Method**: `POST`
- **Body**: 
  ```json
  {
    "telegram": "username",
    "password": "password123"
  }
  ```
- **Response**: 
  ```json
  {
    "success": true,
    "telegram": "username",
    "balance": 0.0
  }
  ```

### Get User Balance
- **URL**: `/api/balance/<telegram_username>`
- **Method**: `GET`
- **Response**: 
  ```json
  {
    "telegram_username": "username",
    "balance": 0.0
  }
  ```

### Place Bet
- **URL**: `/api/bet`
- **Method**: `POST`
- **Body**: 
  ```json
  {
    "telegram": "username",
    "amount": 10.0,
    "direction": "long",
    "time": 5
  }
  ```
- **Response**: 
  ```json
  {
    "success": true,
    "message": "Bet placed successfully",
    "new_balance": 90.0
  }
  ```

## WebSocket Events

### Connect
Connect to `http://localhost:5000` using Socket.IO client.

### Request Balance
- **Event**: `request_balance`
- **Data**: 
  ```json
  {
    "telegram_username": "username"
  }
  ```

### Receive Balance Update
- **Event**: `balance_update`
- **Data**: 
  ```json
  {
    "telegram_username": "username",
    "balance": 100.0
  }
  ```

## Bet Simulation

The backend includes an automatic bet simulation feature that runs in a separate thread:
- Checks for active bets every 30 seconds
- Resolves bets when their time expires
- Randomly determines win/loss (50% chance)
- Updates user balances accordingly
- Sends real-time balance updates via WebSocket

## Database Schema

The application uses SQLite with two tables:

### Users Table
```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_username TEXT UNIQUE,
  email TEXT,
  password TEXT,
  balance REAL DEFAULT 0.0
);
```

### Bets Table
```sql
CREATE TABLE bets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  amount REAL,
  direction TEXT,
  time_minutes INTEGER,
  status TEXT DEFAULT 'active',
  result TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Frontend Integration

The frontend connects to the backend using:
1. HTTP requests for API endpoints
2. WebSocket connection for real-time balance updates

Make sure the backend is running on `http://localhost:5000` when using the frontend.