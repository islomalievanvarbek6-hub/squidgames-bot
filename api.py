#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Бардык домендерден сурамдарды кабыл алуу

DATABASE_NAME = "rdno.db"

def get_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/get_balance/<int:user_id>', methods=['GET'])
def get_balance(user_id):
    """Колдонуучунун балансын алуу"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return jsonify({"success": True, "balance": result[0]})
    else:
        return jsonify({"success": False, "message": "User not found"}), 404

@app.route('/api/sync_balance', methods=['POST'])
def sync_balance():
    """Балансты синхрондоштуруу (боттон келет)"""
    data = request.json
    user_id = data.get('user_id')
    balance = data.get('balance')
    
    if not user_id or balance is None:
        return jsonify({"success": False, "message": "Missing data"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Колдонуучу барбы?
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance, user_id))
    else:
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, balance, display_name)
            VALUES (?, 'user', 'User', ?, 'User')
        """, (user_id, balance))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Balance synced"})

@app.route('/api/get_user_info/<int:user_id>', methods=['GET'])
def get_user_info(user_id):
    """Колдонуучунун толук маалыматын алуу"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, first_name, balance, display_name, 
               premium_type, premium_expires, tournament_wins
        FROM users WHERE user_id = ?
    """, (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return jsonify({
            "success": True,
            "user": {
                "id": user[0],
                "username": user[1],
                "first_name": user[2],
                "balance": user[3],
                "display_name": user[4],
                "premium_type": user[5],
                "premium_expires": user[6],
                "tournament_wins": user[7]
            }
        })
    else:
        return jsonify({"success": False, "message": "User not found"}), 404

@app.route('/api/update_balance', methods=['POST'])
def update_balance():
    """Веб сайттан балансты өзгөртүү (краш, дурак, бонус)"""
    data = request.json
    user_id = data.get('user_id')
    amount = data.get('amount')
    description = data.get('description', 'web_game')
    
    if not user_id or amount is None:
        return jsonify({"success": False, "message": "Missing data"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Учурдагы балансты алуу
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if not result:
        return jsonify({"success": False, "message": "User not found"}), 404
    
    current_balance = result[0]
    new_balance = current_balance + amount
    
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    
    if amount > 0:
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (?, ?, 'win', ?)
        """, (user_id, amount, description))
    else:
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (?, ?, 'bet', ?)
        """, (user_id, -amount, description))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "new_balance": new_balance,
        "message": f"Balance updated by {amount}"
    })

@app.route('/api/get_top_users', methods=['GET'])
def get_top_users():
    """Топ 10 колдонуучуну алуу"""
    limit = request.args.get('limit', 10, type=int)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, display_name, username, first_name, balance
        FROM users
        WHERE balance > 0
        ORDER BY balance DESC LIMIT ?
    """, (limit,))
    
    users = cursor.fetchall()
    conn.close()
    
    result = []
    for user in users:
        result.append({
            "id": user[0],
            "name": user[1] or user[2] or user[3],
            "balance": user[4]
        })
    
    return jsonify({"success": True, "users": result})

@app.route('/api/get_tournament_registrations', methods=['GET'])
def get_tournament_registrations():
    """Турнирге катталгандарды алуу"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM tournament_registrations WHERE tournament_id = 1")
    registrations = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "success": True,
        "count": len(registrations),
        "registrations": [{"id": r[0], "username": r[1]} for r in registrations]
    })

@app.route('/api/add_bonus', methods=['POST'])
def add_bonus():
    """Веб сайттан бонус кошуу (60 канал системасы)"""
    data = request.json
    user_id = data.get('user_id')
    bonus_type = data.get('type')  # 'free', 'paid1', 'paid2'
    channel_index = data.get('channel_index')  # 0-19
    
    if not user_id or not bonus_type or channel_index is None:
        return jsonify({"success": False, "message": "Missing data"}), 400
    
    # Бонус суммасын аныктоо
    import random
    
    if bonus_type == 'free':
        amount = random.randint(6000, 20000)
    elif bonus_type == 'paid1':
        amount = random.randint(20000, 40000)
    elif bonus_type == 'paid2':
        amount = random.randint(200000, 1000000)
    else:
        return jsonify({"success": False, "message": "Invalid bonus type"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if not result:
        return jsonify({"success": False, "message": "User not found"}), 404
    
    current_balance = result[0]
    new_balance = current_balance + amount
    
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    
    cursor.execute("""
        INSERT INTO transactions (user_id, amount, type, description)
        VALUES (?, ?, 'bonus', ?)
    """, (user_id, amount, f"Bonus from channel {bonus_type}"))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "amount": amount,
        "new_balance": new_balance
    })

@app.route('/api/get_user_premium', methods=['GET'])
def get_user_premium():
    """Колдонуучунун premium статусун алуу"""
    user_id = request.args.get('user_id', type=int)
    
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT premium_type, premium_expires FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        is_premium = result[0] > 0
        expires = result[1]
        
        # Мөөнөтү өткөнүн текшерүү
        if expires:
            from datetime import datetime
            expires_date = datetime.strptime(expires, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expires_date:
                is_premium = False
        
        return jsonify({
            "success": True,
            "premium_type": result[0],
            "is_premium": is_premium,
            "expires": expires
        })
    else:
        return jsonify({"success": False, "message": "User not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
