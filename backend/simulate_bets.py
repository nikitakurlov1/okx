import sqlite3
import random
import time
from datetime import datetime, timedelta

def simulate_bet_results():
    """Simulate bet results and update user balances accordingly"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get all active bets
    c.execute("SELECT b.id, b.user_id, b.amount, b.direction, b.time_minutes, u.telegram_username FROM bets b JOIN users u ON b.user_id = u.id WHERE b.status = 'active'")
    active_bets = c.fetchall()
    
    for bet in active_bets:
        bet_id, user_id, amount, direction, time_minutes, telegram_username = bet
        
        # Check if bet time has expired (for simplicity, we'll assume all bets expire after 1 minute in this simulation)
        c.execute("SELECT timestamp FROM bets WHERE id = ?", (bet_id,))
        timestamp_str = c.fetchone()[0]
        bet_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        
        # If bet is older than its time limit, resolve it
        if datetime.now() > bet_time + timedelta(minutes=time_minutes):
            # Simulate random win/loss (50% chance to win)
            won = random.choice([True, False])
            
            if won:
                # User wins - add winnings (for simplicity, we'll double the bet amount)
                winnings = amount  # 100% return
                c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (winnings, user_id))
                c.execute("UPDATE bets SET status = 'completed', result = 'win' WHERE id = ?", (bet_id,))
                print(f"User {telegram_username} won {winnings} on bet {bet_id}")
            else:
                # User loses - amount is already deducted
                c.execute("UPDATE bets SET status = 'completed', result = 'loss' WHERE id = ?", (bet_id,))
                print(f"User {telegram_username} lost bet {bet_id}")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    print("Starting bet simulation...")
    while True:
        simulate_bet_results()
        time.sleep(30)  # Check every 30 seconds