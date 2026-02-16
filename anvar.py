#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import random
import sqlite3
import asyncio
import requests
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import logging
import re
from collections import defaultdict

# ============ КОНФИГУРАЦИЯ ============
BOT_TOKEN = "8586410588:AAEZmz9upT7ifgdzUETb_6ayl1mC3zPwA5c"  # СИЗДИН ТОКЕНИҢИЗ
ADMIN_ID = 8337481127  # ӨЗҮҮЗДҮН ID
ADMIN_USERNAME = "@SQUIIDGAMES_KASSA"
CHANNELS = []

DONATE_LINK = "https://t.me/SQUIIDGAMES_KASSA"

DATABASE_NAME = "rdno.db"
INITIAL_BALANCE = 5000
REFERRAL_BONUS = 1000
MIN_BET = 1000
MIN_BANDIT_BET = 1000
ROULETTE_LIMIT = 999999999
TRANSFER_COOLDOWN_HOURS = 6
TRANSFER_DAILY_LIMIT = 10000

# Веб сайттын дареги
WEBAPP_URL = "https://islomalievanvarbek6-hub.github.io/squidgames-bot"

# GIF интернеттен алабыз (ишенимдүү вариант)
GIF_URL = "https://islomav4.beget.tech/giphy.mp4"
# ========================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Веб сайт менен байланыш
API_URL = "http://localhost:5000"  # Эгер Flask ошол эле серверде иштесе

def sync_balance_to_web(user_id, balance):
    """Балансты веб сайтка жөнөтүү"""
    try:
        requests.post(f"{API_URL}/api/sync_balance", json={
            "user_id": user_id,
            "balance": balance
        }, timeout=1)
    except:
        pass  # Веб сайт иштебей жатса, ката бербей өтүп кет

def get_web_balance(user_id):
    """Веб сайттан балансты алуу"""
    try:
        response = requests.get(f"{API_URL}/api/get_balance/{user_id}", timeout=1)
        if response.status_code == 200:
            return response.json().get("balance")
    except:
        pass
    return None

class ChatManager:
    def __init__(self):
        self.roulette_bets = defaultdict(dict)
        self.roulette_spinning = defaultdict(bool)
        self.next_roulette_result = {}
        self.group_roulette_results = defaultdict(list)
        self.last_bet_amounts = defaultdict(dict)
        self.last_bet_types = defaultdict(dict)
        self.last_bets_details = defaultdict(dict)
        self.last_game_bets = defaultdict(dict)  # Акыркы оюндагы ставкаларды сактоо
        self.go_tasks = {}
        self.user_bets = defaultdict(list)
        self.chat_members_cache = defaultdict(dict)
        self.muted_users = defaultdict(dict)
        self.banned_users = defaultdict(dict)
        self.tournament_participants = {}
        self.tournament_questions = {}
        self.tournament_scores = {}
        self.tournament_active = False
        self.tournament_start_time = None
        self.last_activity = defaultdict(float)  # Активдүүлүк убактысы
        self.roulette_started = defaultdict(bool)  # Рулетка башталдыбы

    def reset_chat_roulette(self, chat_id):
        if chat_id in self.roulette_bets:
            # Акыркы оюндун ставкаларын сактап калуу
            if chat_id in self.roulette_bets and self.roulette_bets[chat_id]:
                self.last_game_bets[chat_id] = {}
                for user_id, bets in self.roulette_bets[chat_id].items():
                    self.last_game_bets[chat_id][user_id] = bets.copy()
            
            del self.roulette_bets[chat_id]
        if chat_id in self.last_bet_amounts:
            del self.last_bet_amounts[chat_id]
        if chat_id in self.last_bet_types:
            del self.last_bet_types[chat_id]
        if chat_id in self.next_roulette_result:
            del self.next_roulette_result[chat_id]
        if chat_id in self.user_bets:
            del self.user_bets[chat_id]

    def add_tournament_participant(self, user_id, username):
        if user_id not in self.tournament_participants:
            self.tournament_participants[user_id] = {
                'username': username,
                'score': 0,
                'joined_at': datetime.now()
            }
            return True
        return False

    def get_tournament_participants_count(self):
        return len(self.tournament_participants)

    def clear_tournament(self):
        self.tournament_participants = {}
        self.tournament_questions = {}
        self.tournament_scores = {}
        self.tournament_active = False
        self.tournament_start_time = None

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            last_transfer TIMESTAMP,
            referral_code TEXT,
            total_bet INTEGER DEFAULT 0,
            total_win INTEGER DEFAULT 0,
            max_bet INTEGER DEFAULT 0,
            max_win INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Не женат',
            licenses INTEGER DEFAULT 0,
            vip_licenses INTEGER DEFAULT 0,
            roulette_limit INTEGER DEFAULT 2000000,
            display_name TEXT,
            daily_transfer_used INTEGER DEFAULT 0,
            last_daily_reset TIMESTAMP,
            married_to INTEGER DEFAULT NULL,
            marriage_date TIMESTAMP,
            marriage_partner_name TEXT,
            transfer_limit INTEGER DEFAULT 10000,
            added_users INTEGER DEFAULT 0,
            is_muted INTEGER DEFAULT 0,
            mute_until TIMESTAMP,
            mute_by INTEGER DEFAULT NULL,
            can_mute INTEGER DEFAULT 0,
            can_ban INTEGER DEFAULT 0,
            last_rodnoy_bonus_date DATE,
            daily_bonus_count INTEGER DEFAULT 0,
            premium_type INTEGER DEFAULT 0,
            premium_expires TIMESTAMP,
            tournament_wins INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            type TEXT,
            description TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            blocked_by INTEGER,
            blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulette_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            bet_type TEXT,
            bet_value TEXT,
            amount INTEGER,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulette_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            amount INTEGER,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_roulette_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS added_users_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            added_user_id INTEGER,
            chat_id INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            reason TEXT,
            warned_by INTEGER,
            warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            can_mute INTEGER DEFAULT 0,
            can_ban INTEGER DEFAULT 0,
            granted_by INTEGER,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE,
            top_users TEXT,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_bonus (
            user_id INTEGER PRIMARY KEY,
            last_bonus_date DATE,
            bonus_count INTEGER DEFAULT 0,
            total_bonus INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT NULL,
            role_expires TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rodnoy_bonus_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            bonus_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tournament_id INTEGER,
            position INTEGER,
            prize INTEGER,
            participated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS premium_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            premium_type INTEGER,
            price INTEGER,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tournament_id INTEGER DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_winners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            position INTEGER,
            prize INTEGER,
            tournament_id INTEGER,
            awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Краш оюну үчүн таблица
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crash_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            multiplier REAL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Дурак оюну үчүн таблица
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS durak_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            player1_id INTEGER,
            player2_id INTEGER,
            player3_id INTEGER,
            player4_id INTEGER,
            bet_amount INTEGER,
            status TEXT DEFAULT 'waiting',
            winner_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

init_db()

class UserManager:
    @staticmethod
    def get_user(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user

    @staticmethod
    def create_user(user_id, username, first_name, referral_code=None):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        referrer_id = None
        if referral_code:
            cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (referral_code,))
            result = cursor.fetchone()
            if result:
                referrer_id = result[0]

        cursor.execute(
            """INSERT OR IGNORE INTO users
            (user_id, username, first_name, referral_code, balance, display_name,
             roulette_limit, daily_transfer_used, last_daily_reset, transfer_limit, added_users,
             is_muted, mute_until, mute_by, can_mute, can_ban, last_rodnoy_bonus_date, daily_bonus_count,
             premium_type, premium_expires, tournament_wins)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, first_name, f"ref_{user_id}", INITIAL_BALANCE, first_name,
             ROULETTE_LIMIT, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), TRANSFER_DAILY_LIMIT, 0,
             0, None, None, 0, 0, datetime.now().date().strftime("%Y-%m-%d"), 0,
             0, None, 0)
        )

        if referrer_id:
            cursor.execute("UPDATE users SET balance = balance + ?, referrals = referrals + 1 WHERE user_id = ?",
                         (REFERRAL_BONUS, referrer_id))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?",
                         (REFERRAL_BONUS, user_id))

            cursor.execute(
                "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
                (referrer_id, REFERRAL_BONUS, "ref_bonus", f"Реферальный бонус за {username}")
            )
            cursor.execute(
                "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
                (user_id, REFERRAL_BONUS, "ref_bonus", f"Реферальный бонус при регистрации")
            )

        conn.commit()
        conn.close()

        # Веб сайтка дагы синхрондоштуруу
        sync_balance_to_web(user_id, INITIAL_BALANCE)

    @staticmethod
    def update_balance(user_id, amount, description=""):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Учурдагы балансты алуу
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
        
        current_balance = result[0]
        new_balance = current_balance + amount

        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))

        if amount < 0:
            cursor.execute("UPDATE users SET total_bet = total_bet + ? WHERE user_id = ?", (abs(amount), user_id))
            cursor.execute("UPDATE users SET max_bet = MAX(max_bet, ?) WHERE user_id = ?", (abs(amount), user_id))
            transaction_type = "bet"
        else:
            cursor.execute("UPDATE users SET total_win = total_win + ? WHERE user_id = ?", (amount, user_id))
            cursor.execute("UPDATE users SET max_win = MAX(max_win, ?) WHERE user_id = ?", (amount, user_id))
            transaction_type = "win"

        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, abs(amount), transaction_type, description)
        )

        conn.commit()
        conn.close()

        # Веб сайтка дагы синхрондоштуруу
        sync_balance_to_web(user_id, new_balance)
        
        return True

    @staticmethod
    def get_rodnoy_bonus_info(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT last_rodnoy_bonus_date, daily_bonus_count FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    @staticmethod
    def update_rodnoy_bonus(user_id, amount):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        today = datetime.now().date()

        # Учурдагы балансты алуу
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        current_balance = result[0] if result else 0
        new_balance = current_balance + amount

        cursor.execute("UPDATE users SET last_rodnoy_bonus_date = ?, daily_bonus_count = daily_bonus_count + 1, balance = ? WHERE user_id = ?",
                      (today.strftime("%Y-%m-%d"), new_balance, user_id))

        cursor.execute(
            "INSERT INTO rodnoy_bonus_history (user_id, amount, bonus_date) VALUES (?, ?, ?)",
            (user_id, amount, today.strftime("%Y-%m-%d"))
        )

        conn.commit()
        conn.close()

        # Веб сайтка дагы синхрондоштуруу
        sync_balance_to_web(user_id, new_balance)

    @staticmethod
    def get_premium_info(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT premium_type, premium_expires FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    @staticmethod
    def activate_premium(user_id, premium_type, days):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE users SET premium_type = ?, premium_expires = ? WHERE user_id = ?",
                      (premium_type, expires, user_id))

        bonus_amount = 10000 if premium_type == 1 else 20000 if premium_type == 2 else 50000
        
        # Учурдагы балансты алуу
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        current_balance = result[0] if result else 0
        new_balance = current_balance + bonus_amount
        
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))

        cursor.execute(
            "INSERT INTO premium_purchases (user_id, premium_type, price, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, premium_type, 0, expires)
        )

        conn.commit()
        conn.close()

        # Веб сайтка дагы синхрондоштуруу
        sync_balance_to_web(user_id, new_balance)

    @staticmethod
    def check_premium_expiry():
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE users SET premium_type = 0 WHERE premium_expires < ? AND premium_type > 0", (now,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected

    @staticmethod
    def get_user_role(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT role, role_expires FROM user_roles WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    @staticmethod
    def set_user_role(user_id, role, days=30):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT OR REPLACE INTO user_roles (user_id, role, role_expires) VALUES (?, ?, ?)",
                      (user_id, role, expires))

        cursor.execute(
            "INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)",
            (ADMIN_ID, f"give_role_{role}", user_id, f"{role} на {days} дней")
        )

        conn.commit()
        conn.close()

    @staticmethod
    def remove_user_role(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))

        cursor.execute(
            "INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)",
            (ADMIN_ID, "remove_role", user_id, "Роль удалена")
        )

        conn.commit()
        conn.close()

    @staticmethod
    def check_role_expiry():
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("DELETE FROM user_roles WHERE role_expires < ?", (now,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count

    @staticmethod
    def get_all_active_roles():
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ur.user_id, ur.role, ur.role_expires, u.username, u.first_name, u.display_name
            FROM user_roles ur
            LEFT JOIN users u ON ur.user_id = u.user_id
            WHERE ur.role_expires > datetime('now')
            ORDER BY ur.role_expires DESC
        """)

        result = cursor.fetchall()
        conn.close()
        return result

    @staticmethod
    def get_transaction_history(user_id, limit=10):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT date, amount, type, description FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit)
        )
        result = cursor.fetchall()
        conn.close()
        return result

    @staticmethod
    def add_global_roulette_log(chat_id, result):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO global_roulette_logs (chat_id, result) VALUES (?, ?)",
            (chat_id, result)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_global_roulette_logs(chat_id, limit=10):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT result FROM global_roulette_logs WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        )
        result = cursor.fetchall()
        conn.close()
        return [log[0] for log in result]

    @staticmethod
    def get_global_roulette_logs_all(chat_id, limit=21):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT result FROM global_roulette_logs WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        )
        result = cursor.fetchall()
        conn.close()
        return [log[0] for log in result]

    @staticmethod
    def get_global_top_users(limit=10):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, display_name, username, first_name, balance
            FROM users
            WHERE balance > 0
            ORDER BY balance DESC LIMIT ?
        """, (limit,))

        result = cursor.fetchall()
        conn.close()
        return result

    @staticmethod
    def get_user_position_by_balance(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) + 1 as position
            FROM users u1
            WHERE balance > (SELECT balance FROM users WHERE user_id = ?)
        """, (user_id,))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else 1

    @staticmethod
    def set_display_name(user_id, display_name):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (display_name, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def update_user_from_tg(user_id, username, first_name):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT username, first_name, display_name FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        if user:
            current_username, current_first_name, display_name = user

            if current_username != username or current_first_name != first_name:
                cursor.execute("UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
                             (username, first_name, user_id))

                if not display_name or display_name == current_first_name:
                    cursor.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (first_name, user_id))

        conn.commit()
        conn.close()

    @staticmethod
    def add_coins_to_user(user_id, amount):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Учурдагы балансты алуу
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        current_balance = result[0] if result else 0
        new_balance = current_balance + amount

        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))

        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, amount, "admin_add", f"Админ добавил {amount} монет")
        )

        cursor.execute(
            "INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)",
            (ADMIN_ID, "add_coins", user_id, f"{amount} монет")
        )

        conn.commit()
        conn.close()

        # Веб сайтка дагы синхрондоштуруу
        sync_balance_to_web(user_id, new_balance)
        
        return True

    @staticmethod
    def remove_coins_from_user(user_id, amount):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return False, "Пользователь не найден"

        current_balance = result[0]

        if amount > current_balance:
            cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
            removed_amount = current_balance
            new_balance = 0
        else:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
            removed_amount = amount
            new_balance = current_balance - amount

        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, -removed_amount, "admin_remove", f"Админ убрал {removed_amount} монет")
        )

        cursor.execute(
            "INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)",
            (ADMIN_ID, "remove_coins", user_id, f"{removed_amount} монет")
        )

        conn.commit()
        conn.close()

        # Веб сайтка дагы синхрондоштуруу
        sync_balance_to_web(user_id, new_balance)
        
        return True, removed_amount

    @staticmethod
    def add_roulette_log(chat_id, user_id, result):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO roulette_logs (chat_id, user_id, result) VALUES (?, ?, ?)",
            (chat_id, user_id, result)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def update_added_users(user_id, count):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET added_users = added_users + ? WHERE user_id = ?", (count, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_added_users_in_chat(user_id, chat_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM added_users_history WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

    @staticmethod
    def is_muted(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT is_muted, mute_until FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return False

        is_muted, mute_until = result
        if is_muted and mute_until:
            try:
                mute_time = datetime.strptime(mute_until, "%Y-%m-%d %H:%M:%S")
                if datetime.now() > mute_time:
                    conn = sqlite3.connect(DATABASE_NAME)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET is_muted = 0, mute_until = NULL WHERE user_id = ?", (user_id,))
                    conn.commit()
                    conn.close()
                    return False
                return True
            except:
                return False
        return False

    @staticmethod
    def mute_user(user_id, hours, muted_by=None):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        mute_until = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE users SET is_muted = 1, mute_until = ?, mute_by = ? WHERE user_id = ?",
                      (mute_until, muted_by, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def unmute_user(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_muted = 0, mute_until = NULL, mute_by = NULL WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def block_user(user_id, reason, blocked_by):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO blocked_users (user_id, reason, blocked_by) VALUES (?, ?, ?)",
            (user_id, reason, blocked_by)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def is_blocked(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    @staticmethod
    def unblock_user(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blocked_users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def can_make_transfer(user_id, amount):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT transfer_limit, last_transfer, daily_transfer_used FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return False, "Пользователь не найден"

        transfer_limit, last_transfer_str, daily_used = result
        now = datetime.now()

        if daily_used + amount > transfer_limit:
            remaining = transfer_limit - daily_used
            conn.close()
            return False, f"Лимит на передачу {transfer_limit} монет за {TRANSFER_COOLDOWN_HOURS} часов. Вы еще можете передать: {remaining}"

        if last_transfer_str:
            try:
                last_transfer = datetime.strptime(last_transfer_str, "%Y-%m-%d %H:%M:%S")
                time_diff = (now - last_transfer).total_seconds() / 3600
                if time_diff < TRANSFER_COOLDOWN_HOURS:
                    pass
            except:
                pass

        if amount < 10:
            conn.close()
            return False, f"Минимальная сумма перевода: 1 монет"

        remaining = transfer_limit - daily_used

        conn.close()
        return True, f"Можно переводить. Доступно: {remaining}"

    @staticmethod
    def update_transfer_usage(user_id, amount):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("UPDATE users SET last_transfer = ?, daily_transfer_used = daily_transfer_used + ? WHERE user_id = ?",
                      (now, amount, user_id))

        conn.commit()
        conn.close()

    @staticmethod
    def reset_daily_limits():
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("UPDATE users SET daily_transfer_used = 0, last_daily_reset = ?, daily_bonus_count = 0",
                      (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))

        conn.commit()
        conn.close()

    @staticmethod
    def grant_permission(chat_id, user_id, permission_type, granted_by):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        if permission_type == "mute":
            cursor.execute("UPDATE users SET can_mute = 1 WHERE user_id = ?", (user_id,))
            cursor.execute(
                "INSERT INTO admin_permissions (chat_id, user_id, can_mute, granted_by) VALUES (?, ?, ?, ?)",
                (chat_id, user_id, 1, granted_by)
            )
        elif permission_type == "ban":
            cursor.execute("UPDATE users SET can_ban = 1 WHERE user_id = ?", (user_id,))
            cursor.execute(
                "INSERT INTO admin_permissions (chat_id, user_id, can_ban, granted_by) VALUES (?, ?, ?, ?)",
                (chat_id, user_id, 1, granted_by)
            )
        elif permission_type == "all":
            cursor.execute("UPDATE users SET can_mute = 1, can_ban = 1 WHERE user_id = ?", (user_id,))
            cursor.execute(
                "INSERT INTO admin_permissions (chat_id, user_id, can_mute, can_ban, granted_by) VALUES (?, ?, ?, ?, ?)",
                (chat_id, user_id, 1, 1, granted_by)
            )

        conn.commit()
        conn.close()

    @staticmethod
    def revoke_permission(user_id, permission_type):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        if permission_type == "mute":
            cursor.execute("UPDATE users SET can_mute = 0 WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM admin_permissions WHERE user_id = ? AND can_mute = 1", (user_id,))
        elif permission_type == "ban":
            cursor.execute("UPDATE users SET can_ban = 0 WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM admin_permissions WHERE user_id = ? AND can_ban = 1", (user_id,))
        elif permission_type == "all":
            cursor.execute("UPDATE users SET can_mute = 0, can_ban = 0 WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM admin_permissions WHERE user_id = ?", (user_id,))

        conn.commit()
        conn.close()

    @staticmethod
    def has_permission(user_id, permission_type):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        if permission_type == "mute":
            cursor.execute("SELECT can_mute FROM users WHERE user_id = ?", (user_id,))
        elif permission_type == "ban":
            cursor.execute("SELECT can_ban FROM users WHERE user_id = ?", (user_id,))
        else:
            conn.close()
            return False

        result = cursor.fetchone()
        conn.close()

        if result and result[0] == 1:
            return True
        return False

    @staticmethod
    def get_chat_top_users(chat_id, limit=10):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, display_name, username, first_name, balance
            FROM users
            WHERE balance > 0
            ORDER BY balance DESC LIMIT ?
        """, (limit,))

        result = cursor.fetchall()
        conn.close()
        return result

    @staticmethod
    def update_chat_stats(chat_id, top_users_text):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO chat_stats (chat_id, top_users, last_update)
            VALUES (?, ?, ?)
        """, (chat_id, top_users_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        conn.commit()
        conn.close()

    @staticmethod
    def get_chat_stats(chat_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT top_users FROM chat_stats WHERE chat_id = ?", (chat_id,))
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    @staticmethod
    def set_roulette_limit(user_id, limit):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET roulette_limit = ? WHERE user_id = ?", (limit, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def set_transfer_limit(user_id, limit):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET transfer_limit = ? WHERE user_id = ?", (limit, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_transfer_limit(user_id):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT transfer_limit FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()

        if result and result[0]:
            return result[0]
        return TRANSFER_DAILY_LIMIT

    @staticmethod
    def reduce_all_balances_above_limit(limit=100000):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT user_id, balance FROM users WHERE balance > ?", (limit,))
            users = cursor.fetchall()

            affected_users = 0

            for user_id, current_balance in users:
                if current_balance > limit:
                    reduction_amount = current_balance - limit
                    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (limit, user_id))

                    cursor.execute(
                        "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
                        (user_id, -reduction_amount, "system_reduction", f"Система: баланс {limit:,}га түшүрүлдү")
                    )

                    # Веб сайтка дагы синхрондоштуруу
                    sync_balance_to_web(user_id, limit)

                    affected_users += 1

            conn.commit()
            logger.info(f"Баланстары {limit:,}га түшүрүлдү: {affected_users} колдонуучу")

            return affected_users

        except Exception as e:
            conn.rollback()
            logger.error(f"Балансты түшүрүүдө ката: {e}")
            return 0
        finally:
            conn.close()

    @staticmethod
    def register_for_tournament(user_id, username):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO tournament_registrations (user_id, username, tournament_id)
            VALUES (?, ?, 1)
        """, (user_id, username))

        conn.commit()
        conn.close()

    @staticmethod
    def get_tournament_registrations():
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT user_id, username FROM tournament_registrations WHERE tournament_id = 1")
        result = cursor.fetchall()

        conn.close()
        return result

    @staticmethod
    def clear_tournament_registrations():
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tournament_registrations WHERE tournament_id = 1")
        deleted = cursor.rowcount

        conn.commit()
        conn.close()
        return deleted

    @staticmethod
    def add_tournament_winner(user_id, username, position, prize):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tournament_winners (user_id, username, position, prize, tournament_id)
            VALUES (?, ?, ?, ?, 1)
        """, (user_id, username, position, prize))

        # Учурдагы балансты алуу
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        current_balance = result[0] if result else 0
        new_balance = current_balance + prize

        cursor.execute("UPDATE users SET balance = ?, tournament_wins = tournament_wins + 1 WHERE user_id = ?",
                      (new_balance, user_id))

        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, prize, "tournament_prize", f"Приз турнира: {position} место")
        )

        conn.commit()
        conn.close()

        # Веб сайтка дагы синхрондоштуруу
        sync_balance_to_web(user_id, new_balance)

chat_manager = ChatManager()

async def is_group_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        if user_id == ADMIN_ID:
            return True
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки админа: {e}")
        return False

URL_PATTERNS = [
    r'https?://\S+',
    r't\.me/\S+',
    r'@\w+',
    r'telegram\.me/\S+',
    r'bit\.ly/\S+',
    r'tinyurl\.com/\S+'
]

def contains_url(text):
    if not text:
        return False
    text_lower = text.lower()
    for pattern in URL_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False

def calculate_next_result(logs, chat_id=None):
    if not logs:
        return "7🔴"
    if chat_id and chat_id in chat_manager.next_roulette_result:
        result = chat_manager.next_roulette_result[chat_id]
        if result and len(result) >= 2 and re.match(r'^\d+', result):
            return result
        else:
            del chat_manager.next_roulette_result[chat_id]
    last_results = logs[:10]
    red_count = 0
    black_count = 0
    green_count = 0
    for result in last_results:
        if result:
            if "🔴" in result:
                red_count += 1
            elif "⚫️" in result:
                black_count += 1
            elif "💚" in result:
                green_count += 1
    last_result = logs[0] if logs else "0💚"
    if red_count >= black_count and red_count >= green_count:
        black_numbers = ["2⚫️", "4⚫️", "6⚫️", "8⚫️", "10⚫️", "12⚫️"]
        filtered = [num for num in black_numbers if num != last_result]
        if filtered:
            result = random.choice(filtered)
        else:
            result = random.choice(black_numbers)
    elif black_count >= red_count and black_count >= green_count:
        red_numbers = ["1🔴", "3🔴", "5🔴", "7🔴", "9🔴", "11🔴"]
        filtered = [num for num in red_numbers if num != last_result]
        if filtered:
            result = random.choice(filtered)
        else:
            result = random.choice(red_numbers)
    else:
        if green_count > 0 and random.random() < 0.1:
            result = "0💚"
        else:
            all_numbers = [
                "0💚", "1🔴", "2⚫️", "3🔴", "4⚫️", "5🔴", "6⚫️",
                "7🔴", "8⚫️", "9🔴", "10⚫️", "11🔴", "12⚫️"
            ]
            possible_numbers = [num for num in all_numbers if num != last_result]
            if possible_numbers:
                result = random.choice(possible_numbers)
            else:
                result = "7🔴"
    if not result or not re.match(r'^\d+', result):
        result = "7🔴"
    if chat_id:
        chat_manager.next_roulette_result[chat_id] = result
    return result

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🏠 𝗦 ○ U I D G ▲ M [] S")],
        [KeyboardButton("🎁 Бонус"), KeyboardButton("💰 Пополнить баланс")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_bonus_button(user_id):
    return "🎁 Бонус"

async def show_rodnoy_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ['group', 'supergroup']:
        return

    user_id = update.effective_user.id
    user = UserManager.get_user(user_id)

    if not user:
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        UserManager.create_user(user_id, username, first_name, None)
        user = UserManager.get_user(user_id)

    # Веб колдонмого шилтеме
    webapp_button = InlineKeyboardButton("🎮 ИГРАТЬ В MINI APP", web_app={"url": WEBAPP_URL})
    
    keyboard = [
        [webapp_button],
        [InlineKeyboardButton("🏠 ГЛАВНАЯ", callback_data="rodnoy_home")],
        [InlineKeyboardButton("💰 БАЛАНС", callback_data="rodnoy_balance_page")],
        [InlineKeyboardButton("🎰 ИГРЫ", callback_data="rodnoy_games")],
        [InlineKeyboardButton("🎭 РОЛИ", callback_data="rodnoy_roles")],
        [InlineKeyboardButton("🎁 БОНУС", callback_data="rodnoy_bonus_page")],
        [InlineKeyboardButton("🏆 РЕЙТИНГ", callback_data="rodnoy_rating")],
        [InlineKeyboardButton("⚙️ НАСТРОЙКИ", callback_data="rodnoy_settings")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if user[15]:
        display_name = user[15]
    elif user[1]:
        display_name = user[1]
    else:
        display_name = user[2]

    menu_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"👤 {display_name}\n"
        f"🆔 ID: {user_id}\n"
        f"💰 Баланс: {user[3]} 🪙\n\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"👇 Нажмите кнопку для управления:"
    )

    if update.message:
        await update.message.reply_text(menu_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(menu_text, reply_markup=reply_markup)

async def show_rodnoy_balance_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    user = UserManager.get_user(user_id)

    if not user:
        return

    keyboard = [
        [InlineKeyboardButton("💳 Пополнить баланс", url=DONATE_LINK)],
        [InlineKeyboardButton("📊 Статистика", callback_data="rodnoy_stats")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    balance_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## БАЛАНС\n\n"
        f"1. **𝗦 ○ U I D G ▲ M [] S Coins**\n"
        f"   {user[3]} 🪙\n\n"
        f"2. Пополнить баланс\n"
        f"3. Подписки\n\n"
        f"💰 Доступно: {user[3]} 🪙\n"
        f"💳 Для пополнения нажмите кнопку ниже:"
    )

    await update.callback_query.message.edit_text(balance_text, reply_markup=reply_markup)

async def show_rodnoy_bonus_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    user = UserManager.get_user(user_id)

    if not user:
        return

    premium_info = UserManager.get_premium_info(user_id)
    premium_type = premium_info[0] if premium_info else 0
    premium_expires = premium_info[1] if premium_info else None

    today = datetime.now().date()

    bonus_data = UserManager.get_rodnoy_bonus_info(user_id)
    daily_bonus_taken = False

    if bonus_data and bonus_data[0]:
        last_date = datetime.strptime(bonus_data[0], "%Y-%m-%d").date()
        if last_date == today:
            daily_bonus_taken = True

    # Веб бонус системасына шилтеме
    webapp_bonus = InlineKeyboardButton("🎁 БОНУСЫ В MINI APP", web_app={"url": f"{WEBAPP_URL}?page=bonus"})
    
    keyboard = [
        [webapp_bonus],
        [InlineKeyboardButton("🎁 Ежедневный бонус 10.000", callback_data="daily_bonus")],
        [InlineKeyboardButton("💰 Premium 1 (100 руб/30 дней)", callback_data="premium_1_info")],
        [InlineKeyboardButton("💎 Premium 2 (200 руб/30 дней)", callback_data="premium_2_info")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    bonus_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## БОНУСНАЯ СИСТЕМА\n\n"
    )

    if premium_type > 0:
        expires_date = datetime.strptime(premium_expires, "%Y-%m-%d %H:%M:%S") if premium_expires else None
        days_left = (expires_date.date() - today).days if expires_date and expires_date.date() > today else 0
        bonus_text += f"✅ Активен Premium {premium_type}\n"
        bonus_text += f"⏳ Осталось дней: {days_left}\n\n"

    bonus_text += (
        f"🎁 **Ежедневный бонус**\n"
        f"   • 10.000 монет каждый день\n"
        f"   • Доступен всем пользователям\n"
        f"   • Сегодня: {'✅ Получено' if daily_bonus_taken else '🔄 Доступно'}\n\n"
        f"💰 **Premium 1 (100 руб)**\n"
        f"   • 20.000 монет ежедневно\n"
        f"   • Срок: 30 дней\n"
        f"   • Бонус при активации: 10.000\n\n"
        f"💎 **Premium 2 (200 руб)**\n"
        f"   • 50.000 монет ежедневно\n"
        f"   • Срок: 30 дней\n"
        f"   • Бонус при активации: 20.000\n\n"
        f"🎮 **Mini App Бонусы**\n"
        f"   • 60 каналов для подписки\n"
        f"   • Бонусы от 6.000 до 1.000.000\n"
        f"   • Ежедневное обновление\n\n"
        f"👇 Выберите бонус:"
    )

    await update.callback_query.message.edit_text(bonus_text, reply_markup=reply_markup)

async def handle_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    user = UserManager.get_user(user_id)

    if not user:
        return

    bonus_data = UserManager.get_rodnoy_bonus_info(user_id)
    today = datetime.now().date()

    if bonus_data and bonus_data[0]:
        last_date = datetime.strptime(bonus_data[0], "%Y-%m-%d").date()
        if last_date == today:
            await update.callback_query.answer("❌ Сегодня уже получили ежедневный бонус!", show_alert=True)
            return

    bonus_amount = 10000
    UserManager.update_balance(user_id, bonus_amount, f"Ежедневный бонус: +{bonus_amount}")
    UserManager.update_rodnoy_bonus(user_id, bonus_amount)

    new_user = UserManager.get_user(user_id)

    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_bonus_page")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    bonus_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## 🎁 БОНУС ПОЛУЧЕН!\n\n"
        f"💰 +{bonus_amount} 🪙\n\n"
        f"💰 Новый баланс: {new_user[3]} 🪙\n\n"
        f"✅ Ежедневный бонус успешно получен!\n"
        f"📅 Следующий бонус: завтра"
    )

    await update.callback_query.message.edit_text(bonus_text, reply_markup=reply_markup)
    await update.callback_query.answer(f"🎁 +{bonus_amount} монет получено!")

async def handle_premium_1_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id

    keyboard = [
        [InlineKeyboardButton("💳 Купить Premium 1 (100 руб)", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_bonus_page")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    premium_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## 💰 PREMIUM 1\n\n"
        f"💰 Цена: 100 руб\n"
        f"⏰ Срок: 30 дней\n\n"
        f"**Преимущества:**\n"
        f"• 20.000 монет ежедневно\n"
        f"• Бонус при активации: 10.000 монет\n"
        f"• Приоритетная поддержка\n\n"
        f"**Для покупки:**\n"
        f"1. Нажмите кнопку 'Купить Premium 1'\n"
        f"2. Отправьте 100 руб администратору\n"
        f"3. Отправьте скриншот оплаты\n"
        f"4. Ваш ID: {user_id}\n\n"
        f"💡 После оплаты Premium активируется в течение 5 минут"
    )

    await update.callback_query.message.edit_text(premium_text, reply_markup=reply_markup)

async def handle_premium_2_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id

    keyboard = [
        [InlineKeyboardButton("💳 Купить Premium 2 (200 руб)", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_bonus_page")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    premium_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## 💎 PREMIUM 2\n\n"
        f"💰 Цена: 200 руб\n"
        f"⏰ Срок: 30 дней\n\n"
        f"**Преимущества:**\n"
        f"• 50.000 монет ежедневно\n"
        f"• Бонус при активации: 20.000 монет\n"
        f"• Приоритетная поддержка\n"
        f"• Участие в турнирах\n\n"
        f"**Для покупки:**\n"
        f"1. Нажмите кнопку 'Купить Premium 2'\n"
        f"2. Отправьте 200 руб администратору\n"
        f"3. Отправьте скриншот оплаты\n"
        f"4. Ваш ID: {user_id}\n\n"
        f"💡 После оплаты Premium активируется в течение 5 минут"
    )

    await update.callback_query.message.edit_text(premium_text, reply_markup=reply_markup)

async def show_rodnoy_roles_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id

    role_data = UserManager.get_user_role(user_id)

    current_role = "Нет"
    role_expires = ""

    if role_data:
        current_role = role_data[0]
        if role_data[1]:
            expire_date = datetime.strptime(role_data[1], "%Y-%m-%d %H:%M:%S")
            role_expires = expire_date.strftime("%d.%m.%Y %H:%M")

    keyboard = [
        [InlineKeyboardButton("👑 Вор в законе", callback_data="rodnoy_buy_thief")],
        [InlineKeyboardButton("👮 Полицейский", callback_data="rodnoy_buy_police")],
        [InlineKeyboardButton("ℹ️ Информация", callback_data="rodnoy_roles_info")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    roles_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## 🎭 РОЛИ\n\n"
        f"📊 Текущая роль: {current_role}\n"
        f"⏰ Действует: {role_expires if role_expires else 'Нет'}\n\n"
        f"🛒 **Доступные роли:**\n\n"
        f"👑 **Вор в законе** - 4,000₽ / 30 дней\n"
        f"   • Возможность красть монеты у других игроков\n"
        f"   • Защищен от некоторых ограничений\n\n"
        f"👮 **Полицейский** - 2,000₽ / 30 дней\n"
        f"   • Защищен от Вора в законе\n"
        f"   • Возможность ловить воров\n\n"
        f"👇 Выберите роль для покупки:"
    )

    await update.callback_query.message.edit_text(roles_text, reply_markup=reply_markup)

async def handle_rodnoy_buy_thief(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id

    keyboard = [
        [InlineKeyboardButton("💳 Купить за 4,000₽", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_roles")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    thief_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## 👑 ВОР В ЗАКОНЕ\n\n"
        f"💰 Цена: 4,000₽\n"
        f"⏰ Срок: 30 дней\n\n"
        f"**Преимущества:**\n"
        f"• Возможность красть монеты у других игроков\n"
        f"• Команда: ответьте на сообщение игрока и напишите 'вор -9000'\n"
        f"• Защищен от некоторых ограничений\n"
        f"• Автоматически снимается через 30 дней\n\n"
        f"**Для покупки:**\n"
        f"1. Нажмите кнопку 'Купить за 4,000₽'\n"
        f"2. Отправьте 4,000₽ администратору\n"
        f"3. Отправьте скриншот оплаты\n"
        f"4. Ваш ID: {user_id}\n\n"
        f"💡 После оплаты роль активируется в течение 5 минут"
    )

    await update.callback_query.message.edit_text(thief_text, reply_markup=reply_markup)

async def handle_rodnoy_buy_police(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id

    keyboard = [
        [InlineKeyboardButton("💳 Купить за 2,000₽", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_roles")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    police_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## 👮 ПОЛИЦЕЙСКИЙ\n\n"
        f"💰 Цена: 2,000₽\n"
        f"⏰ Срок: 30 дней\n\n"
        f"**Преимущества:**\n"
        f"• Защищен от Вора в законе\n"
        f"• Возможность ловить воров\n"
        f"• Команда: 'полиция' для защиты\n"
        f"• Автоматически снимается через 30 дней\n\n"
        f"**Для покупки:**\n"
        f"1. Нажмите кнопку 'Купить за 2,000₽'\n"
        f"2. Отправьте 2,000₽ администратору\n"
        f"3. Отправьте скриншот оплаты\n"
        f"4. Ваш ID: {user_id}\n\n"
        f"💡 После оплаты роль активируется в течение 5 минут"
    )

    await update.callback_query.message.edit_text(police_text, reply_markup=reply_markup)

async def show_rodnoy_rating_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    user = UserManager.get_user(user_id)

    top_users = UserManager.get_global_top_users(10)

    user_position = UserManager.get_user_position_by_balance(user_id)

    rating_text = f"#𝗦 ○ U I D G ▲ M [] S\n\n## РЕЙТИНГ\n\n"
    rating_text += "| Игрок | Баланс |\n"
    rating_text += "|-------|--------|\n"

    for i, (top_user_id, display_name, username, first_name, balance) in enumerate(top_users, 1):
        if display_name:
            name = display_name
        elif username:
            name = username
        else:
            name = first_name

        if len(name) > 15:
            name = name[:12] + "..."

        rating_text += f"| **{i}. {name}** | {balance:,} |\n"

    if user[15]:
        display_name = user[15]
    elif user[1]:
        display_name = user[1]
    else:
        display_name = user[2]

    rating_text += f"\n📊 **Ваша позиция:** {user_position}\n"
    rating_text += f"👤 **Вы:** {display_name}\n"
    rating_text += f"💰 **Ваш баланс:** {user[3]:,} 🪙"

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="rodnoy_rating")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.edit_text(rating_text, reply_markup=reply_markup)

async def show_rodnoy_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data="rodnoy_profile_settings")],
        [InlineKeyboardButton("🔔 Уведомления", callback_data="rodnoy_notifications")],
        [InlineKeyboardButton("🌙 Внешний вид", callback_data="rodnoy_appearance")],
        [InlineKeyboardButton("🔒 Конфиденциальность", callback_data="rodnoy_privacy")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    settings_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## ⚙️ НАСТРОЙКИ\n\n"
        f"👇 Настройте приложение под себя:\n\n"
        f"👤 **Профиль** - настройки профиля и отображение\n"
        f"🔔 **Уведомления** - управление уведомлений\n"
        f"🌙 **Внешний вид** - тема и дизайн\n"
        f"🔒 **Конфиденциальность** - настройки конфиденциальности\n\n"
        f"С любовью создано 𝗦 ○ U I D G ▲ M [] S Technologies, 1.0.2"
    )

    await update.callback_query.message.edit_text(settings_text, reply_markup=reply_markup)

async def show_rodnoy_games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎰 Рулетка", callback_data="rodnoy_roulette_game")],
        [InlineKeyboardButton("🎴 Бандит", callback_data="rodnoy_bandit_game")],
        [InlineKeyboardButton("🎮 ИГРАТЬ В MINI APP", web_app={"url": WEBAPP_URL})],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    games_text = (
        f"#𝗦 ○ U I D G ▲ M [] S\n\n"
        f"## 🎮 ИГРЫ\n\n"
        f"👇 Играть в игры:\n\n"
        f"🎰 **Рулетка** - угадайте число или цвет\n"
        f"🎴 **Бандит** - соберите одинаковые символы\n"
        f"🎮 **Mini App** - краш, дурак, бонусы\n\n"
        f"🏆 Участвуйте и выигрывайте призы!"
    )

    await update.callback_query.message.edit_text(games_text, reply_markup=reply_markup)

async def handle_thief_steal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    role_data = UserManager.get_user_role(user_id)

    if not role_data or role_data[0] != "вор_в_законе":
        return

    if role_data[1]:
        expire_date = datetime.strptime(role_data[1], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expire_date:
            UserManager.remove_user_role(user_id)
            return

    if not update.message.reply_to_message:
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    target_role = UserManager.get_user_role(target_id)

    if target_role and target_role[0] == "полицейский":
        await update.effective_chat.send_message(
            f"⚠️ <a href='tg://user?id={user_id}'>Вор</a> пытался украсть у <a href='tg://user?id={target_id}'>полицейского</a>, но был остановлен!",
            parse_mode='HTML'
        )
        return

    target_user_data = UserManager.get_user(target_id)
    if not target_user_data or target_user_data[3] < 1000:
        return

    text = update.message.text.lower()
    steal_amount = 0

    match = re.search(r'вор\s*(-?\s*\d+)', text)
    if match:
        try:
            steal_amount = int(match.group(1).replace(' ', '').replace('-', ''))
            if steal_amount < 0:
                steal_amount = abs(steal_amount)
        except:
            steal_amount = 0

    if steal_amount <= 0:
        target_balance = target_user_data[3]
        steal_amount = int(target_balance * random.uniform(0.1, 0.9))

        if steal_amount < 100:
            steal_amount = min(100, target_balance)

    max_steal = int(target_user_data[3] * 0.9)
    if steal_amount > max_steal:
        steal_amount = max_steal

    if steal_amount < 10:
        return

    # Украл
    UserManager.update_balance(target_id, -steal_amount, f"Кража вором в законе: -{steal_amount}")
    UserManager.update_balance(user_id, steal_amount, f"Кража как вор в законе: +{steal_amount}")

    target_name = target_user.first_name
    if target_user.username:
        target_name = target_user.username

    thief_name = update.effective_user.first_name
    if update.effective_user.username:
        thief_name = update.effective_user.username

    await update.effective_chat.send_message(
        f"💰 Вор в законе <a href='tg://user?id={user_id}'>{thief_name}</a>\n"
        f"👤 Украл у <a href='tg://user?id={target_id}'>{target_name}</a>: {steal_amount} монет!\n"
        f"💸 Новый баланс жертвы: {target_user_data[3] - steal_amount} 🪙",
        parse_mode='HTML'
    )

async def handle_police_protect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    role_data = UserManager.get_user_role(user_id)

    if not role_data or role_data[0] != "полицейский":
        return

    if role_data[1]:
        expire_date = datetime.strptime(role_data[1], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expire_date:
            UserManager.remove_user_role(user_id)
            return

    police_name = update.effective_user.first_name
    if update.effective_user.username:
        police_name = update.effective_user.username

    await update.effective_chat.send_message(
        f"👮 Полицейский <a href='tg://user?id={user_id}'>{police_name}</a>\n"
        f"✅ Вы защищены от воров в законе на 24 часа!",
        parse_mode='HTML'
    )

async def handle_text_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not update.message.reply_to_message:
        await update.effective_chat.send_message("❌ Команда должна быть ответом на сообщение пользователя!")
        return

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "mute") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на мутирование!")
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    if target_id == user_id:
        await update.effective_chat.send_message("❌ Нельзя замутить самого себя!")
        return

    target_is_admin = await is_group_admin(context, chat_id, target_id)
    if target_is_admin and user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Нельзя замутить другого администратора!")
        return

    UserManager.mute_user(target_id, 24, user_id)

    target_name = target_user.first_name
    if target_user.username:
        target_name = target_user.username

    admin_name = update.effective_user.first_name
    if update.effective_user.username:
        admin_name = update.effective_user.username

    await update.effective_chat.send_message(
        f"🔇 Пользователь <a href='tg://user?id={target_id}'>{target_name}</a> замьючен на 24 часа!\n"
        f"👮 Администратор: <a href='tg://user?id={user_id}'>{admin_name}</a>",
        parse_mode='HTML'
    )

async def handle_text_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not update.message.reply_to_message:
        await update.effective_chat.send_message("❌ Команда должна быть ответом на сообщение пользователя!")
        return

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "mute") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на размучивание!")
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    UserManager.unmute_user(target_id)

    target_name = target_user.first_name
    if target_user.username:
        target_name = target_user.username

    admin_name = update.effective_user.first_name
    if update.effective_user.username:
        admin_name = update.effective_user.username

    await update.effective_chat.send_message(
        f"🔊 Пользователь <a href='tg://user?id={target_id}'>{target_name}</a> размьючен!\n"
        f"👮 Администратор: <a href='tg://user?id={user_id}'>{admin_name}</a>",
        parse_mode='HTML'
    )

async def handle_text_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not update.message.reply_to_message:
        await update.effective_chat.send_message("❌ Команда должна быть ответом на сообщение пользователя!")
        return

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "ban") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на бан!")
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    if target_id == user_id:
        await update.effective_chat.send_message("❌ Нельзя забанить самого себя!")
        return

    target_is_admin = await is_group_admin(context, chat_id, target_id)
    if target_is_admin and user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Нельзя забанить другого администратора!")
        return

    UserManager.block_user(target_id, "Нарушение правил", user_id)

    target_name = target_user.first_name
    if target_user.username:
        target_name = target_user.username

    admin_name = update.effective_user.first_name
    if update.effective_user.username:
        admin_name = update.effective_user.username

    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_id
        )
    except Exception as e:
        logger.error(f"Ошибка при бане в чате: {e}")

    await update.effective_chat.send_message(
        f"🚫 Пользователь <a href='tg://user?id={target_id}'>{target_name}</a> забанен!\n"
        f"📝 Причина: Нарушение правил\n"
        f"👮 Администратор: <a href='tg://user?id={user_id}'>{admin_name}</a>",
        parse_mode='HTML'
    )

async def handle_text_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not update.message.reply_to_message:
        await update.effective_chat.send_message("❌ Команда должна быть ответом на сообщение пользователя!")
        return

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "ban") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на разбан!")
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    UserManager.unblock_user(target_id)

    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_id
        )
    except Exception as e:
        logger.error(f"Ошибка при разбане в чате: {e}")

    target_name = target_user.first_name
    if target_user.username:
        target_name = target_user.username

    admin_name = update.effective_user.first_name
    if update.effective_user.username:
        admin_name = update.effective_user.username

    await update.effective_chat.send_message(
        f"✅ Пользователь <a href='tg://user?id={target_id}'>{target_name}</a> разбанен!\n"
        f"👮 Администратор: <a href='tg://user?id={user_id}'>{admin_name}</a>",
        parse_mode='HTML'
    )

async def handle_mute_list_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "mute") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на просмотр мутов!")
        return

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, mute_until, mute_by FROM users WHERE is_muted = 1")
    muted_users = cursor.fetchall()
    conn.close()

    if not muted_users:
        await update.effective_chat.send_message("✅ Список мутов пуст!")
        return

    mute_list_text = "🔇 **СПИСОК ЗАМУЧЕННЫХ ПОЛЬЗОВАТЕЛЕЙ:**\n\n"

    for user_id, mute_until, mute_by in muted_users:
        user = UserManager.get_user(user_id)
        if user:
            if user[15]:
                name = user[15]
            elif user[1]:
                name = user[1]
            else:
                name = user[2]
        else:
            name = f"ID: {user_id}"

        admin = UserManager.get_user(mute_by)
        if admin:
            if admin[15]:
                admin_name = admin[15]
            elif admin[1]:
                admin_name = admin[1]
            else:
                admin_name = admin[2]
        else:
            admin_name = f"ID: {mute_by}"

        mute_list_text += f"👤 <a href='tg://user?id={user_id}'>{name}</a> (ID: {user_id})\n"
        mute_list_text += f"⏰ До: {mute_until}\n"
        mute_list_text += f"👮 Замутил: {admin_name}\n"
        mute_list_text += "─" * 30 + "\n"

    await update.effective_chat.send_message(mute_list_text, parse_mode='HTML')

async def handle_ban_list_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "ban") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на просмотр банов!")
        return

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, reason, blocked_by, blocked_at FROM blocked_users")
    banned_users = cursor.fetchall()
    conn.close()

    if not banned_users:
        await update.effective_chat.send_message("✅ Список банов пуст!")
        return

    ban_list_text = "🚫 **СПИСОК ЗАБАНЕННЫХ ПОЛЬЗОВАТЕЛЕЙ:**\n\n"

    for user_id, reason, blocked_by, blocked_at in banned_users:
        user = UserManager.get_user(user_id)
        if user:
            if user[15]:
                name = user[15]
            elif user[1]:
                name = user[1]
            else:
                name = user[2]
        else:
            name = f"ID: {user_id}"

        admin = UserManager.get_user(blocked_by)
        if admin:
            if admin[15]:
                admin_name = admin[15]
            elif admin[1]:
                admin_name = admin[1]
            else:
                admin_name = admin[2]
        else:
            admin_name = f"ID: {blocked_by}"

        ban_list_text += f"👤 <a href='tg://user?id={user_id}'>{name}</a> (ID: {user_id})\n"
        ban_list_text += f"📝 Причина: {reason}\n"
        ban_list_text += f"👮 Забанил: {admin_name}\n"
        ban_list_text += f"🕐 Дата: {blocked_at}\n"
        ban_list_text += "─" * 30 + "\n"

    await update.effective_chat.send_message(ban_list_text, parse_mode='HTML')

async def handle_mutdan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "mute") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на просмотр мутов!")
        return

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, mute_until, mute_by FROM users WHERE is_muted = 1")
    muted_users = cursor.fetchall()
    conn.close()

    if not muted_users:
        await update.effective_chat.send_message("✅ Список мутов пуст!")
        return

    mute_list_text = "🔇 **МУТДАН ТҮШКӨНДӨР:**\n\n"

    for user_id, mute_until, mute_by in muted_users:
        user = UserManager.get_user(user_id)
        if user:
            if user[15]:
                name = user[15]
            elif user[1]:
                name = user[1]
            else:
                name = user[2]
        else:
            name = f"ID: {user_id}"

        admin = UserManager.get_user(mute_by)
        if admin:
            if admin[15]:
                admin_name = admin[15]
            elif admin[1]:
                admin_name = admin[1]
            else:
                admin_name = admin[2]
        else:
            admin_name = f"ID: {mute_by}"

        mute_list_text += f"👤 <a href='tg://user?id={user_id}'>{name}</a> (ID: {user_id})\n"
        mute_list_text += f"⏰ До: {mute_until}\n"
        mute_list_text += f"👮 Замутил: {admin_name}\n"
        mute_list_text += "─" * 30 + "\n"

    await update.effective_chat.send_message(mute_list_text, parse_mode='HTML')

async def handle_bandan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "ban") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на просмотр банов!")
        return

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, reason, blocked_by, blocked_at FROM blocked_users")
    banned_users = cursor.fetchall()
    conn.close()

    if not banned_users:
        await update.effective_chat.send_message("✅ Список банов пуст!")
        return

    ban_list_text = "🚫 **БАНДАН ТҮШКӨНДӨР:**\n\n"

    for user_id, reason, blocked_by, blocked_at in banned_users:
        user = UserManager.get_user(user_id)
        if user:
            if user[15]:
                name = user[15]
            elif user[1]:
                name = user[1]
            else:
                name = user[2]
        else:
            name = f"ID: {user_id}"

        admin = UserManager.get_user(blocked_by)
        if admin:
            if admin[15]:
                admin_name = admin[15]
            elif admin[1]:
                admin_name = admin[1]
            else:
                admin_name = admin[2]
        else:
            admin_name = f"ID: {blocked_by}"

        ban_list_text += f"👤 <a href='tg://user?id={user_id}'>{name}</a> (ID: {user_id})\n"
        ban_list_text += f"📝 Причина: {reason}\n"
        ban_list_text += f"👮 Забанил: {admin_name}\n"
        ban_list_text += f"🕐 Дата: {blocked_at}\n"
        ban_list_text += "─" * 30 + "\n"

    await update.effective_chat.send_message(ban_list_text, parse_mode='HTML')

async def handle_razmut_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "mute") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на размучивание!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 2:
        await update.effective_chat.send_message("❌ Формат: размут @username\nИли: размут <user_id>")
        return

    target_identifier = words[1]

    if target_identifier.startswith('@'):
        username = target_identifier[1:].lower()

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE username LIKE ?", (f'%{username}%',))
        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.effective_chat.send_message(f"❌ Пользователь @{username} не найден!")
            return

        target_id = result[0]

    elif target_identifier.isdigit():
        target_id = int(target_identifier)

    else:
        await update.effective_chat.send_message("❌ Неверный формат! Используйте: размут @username или размут <id>")
        return

    user = UserManager.get_user(target_id)
    if not user:
        await update.effective_chat.send_message("❌ Пользователь не найден!")
        return

    UserManager.unmute_user(target_id)

    target_name = user[15] if user[15] else (user[1] if user[1] else user[2])
    admin_name = update.effective_user.first_name
    if update.effective_user.username:
        admin_name = update.effective_user.username

    await update.effective_chat.send_message(
        f"🔊 Пользователь <a href='tg://user?id={target_id}'>{target_name}</a> размьючен!\n"
        f"👮 Администратор: <a href='tg://user?id={user_id}'>{admin_name}</a>",
        parse_mode='HTML'
    )

async def handle_razban_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "ban") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на разбан!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 2:
        await update.effective_chat.send_message("❌ Формат: разбан @username\nИли: разбан <user_id>")
        return

    target_identifier = words[1]

    if target_identifier.startswith('@'):
        username = target_identifier[1:].lower()

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE username LIKE ?", (f'%{username}%',))
        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.effective_chat.send_message(f"❌ Пользователь @{username} не найден!")
            return

        target_id = result[0]

    elif target_identifier.isdigit():
        target_id = int(target_identifier)

    else:
        await update.effective_chat.send_message("❌ Неверный формат! Используйте: разбан @username или разбан <id>")
        return

    user = UserManager.get_user(target_id)
    if not user:
        await update.effective_chat.send_message("❌ Пользователь не найден!")
        return

    UserManager.unblock_user(target_id)

    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_id
        )
    except Exception as e:
        logger.error(f"Ошибка при разбане в чате: {e}")

    target_name = user[15] if user[15] else (user[1] if user[1] else user[2])
    admin_name = update.effective_user.first_name
    if update.effective_user.username:
        admin_name = update.effective_user.username

    await update.effective_chat.send_message(
        f"✅ Пользователь <a href='tg://user?id={target_id}'>{target_name}</a> разбанен!\n"
        f"👮 Администратор: <a href='tg://user?id={user_id}'>{admin_name}</a>",
        parse_mode='HTML'
    )

async def handle_dai_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для главного администратора!")
        return

    if not update.message.reply_to_message:
        await update.effective_chat.send_message("❌ Команда должна быть ответом на сообщение пользователя!")
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 2:
        await update.effective_chat.send_message(
            "❌ Формат команды: дай админ <тип>\n\n"
            "📋 Примеры:\n"
            "• дай админ мут - дать право на мут\n"
            "• дай админ бан - дать право на бан\n"
            "• дай админ все - дать все права\n\n"
            "💡 Пользователь сможет использовать:\n"
            "• мут/размут\n"
            "• бан/разбан\n"
            "• мут список/бан список"
        )
        return

    permission_type = words[2].lower()

    if permission_type == "мут":
        UserManager.grant_permission(chat_id, target_id, "mute", user_id)
        message = f"✅ Пользователю дано право на мут!"
    elif permission_type == "бан":
        UserManager.grant_permission(chat_id, target_id, "ban", user_id)
        message = f"✅ Пользователю дано право на бан!"
    elif permission_type == "все":
        UserManager.grant_permission(chat_id, target_id, "all", user_id)
        message = f"✅ Пользователю даны все права (мут и бан)!"
    else:
        await update.effective_chat.send_message("❌ Неверный тип прав! Используйте: мут, бан или все")
        return

    target_name = target_user.first_name
    if target_user.username:
        target_name = target_user.username

    await update.effective_chat.send_message(
        f"{message}\n\n"
        f"👤 Пользователь: <a href='tg://user?id={target_id}'>{target_name}</a>\n"
        f"🆔 ID: {target_id}\n"
        f"🎯 Права: {permission_type}",
        parse_mode='HTML'
    )

async def handle_uberi_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для главного администратора!")
        return

    if not update.message.reply_to_message:
        await update.effective_chat.send_message("❌ Команда должна быть ответом на сообщение пользователя!")
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 2:
        await update.effective_chat.send_message(
            "❌ Формат команды: убери админ <тип>\n\n"
            "📋 Примеры:\n"
            "• убери админ мут - убрать право на мут\n"
            "• убери админ бан - убрать право на бан\n"
            "• убери админ все - убрать все права"
        )
        return

    permission_type = words[2].lower()

    if permission_type == "мут":
        UserManager.revoke_permission(target_id, "mute")
        message = f"✅ У пользователя убрано право на мут!"
    elif permission_type == "бан":
        UserManager.revoke_permission(target_id, "ban")
        message = f"✅ У пользователя убрано право на бан!"
    elif permission_type == "все":
        UserManager.revoke_permission(target_id, "all")
        message = f"✅ У пользователя убраны все права!"
    else:
        await update.effective_chat.send_message("❌ Неверный тип прав! Используйте: мут, бан или все")
        return

    target_name = target_user.first_name
    if target_user.username:
        target_name = target_user.username

    await update.effective_chat.send_message(
        f"{message}\n\n"
        f"👤 Пользователь: <a href='tg://user?id={target_id}'>{target_name}</a>\n"
        f"🆔 ID: {target_id}\n"
        f"🎯 Убраны права: {permission_type}",
        parse_mode='HTML'
    )

async def handle_tournament_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = UserManager.get_user(user_id)

    if not user:
        return

    username = update.effective_user.username or update.effective_user.first_name

    premium_info = UserManager.get_premium_info(user_id)
    if not premium_info or premium_info[0] < 2:
        await update.effective_chat.send_message(
            "❌ Для участия в турнире нужен Premium 2!\n\n"
            "💎 Premium 2 включает:\n"
            "• Участие в турнирах\n"
            "• 50.000 монет ежедневно\n"
            "• Приоритетная поддержка\n\n"
            "💰 Стоимость: 200 руб/30 дней"
        )
        return

    UserManager.register_for_tournament(user_id, username)
    chat_manager.add_tournament_participant(user_id, username)

    await update.effective_chat.send_message(
        f"✅ Вы зарегистрированы на турнир!\n\n"
        f"👤 Участник: {username}\n"
        f"🆔 ID: {user_id}\n\n"
        f"📊 Зарегистрировано: {chat_manager.get_tournament_participants_count()}/150\n"
        f"💰 Призовой фонд: 650.000.000 🪙"
    )

async def handle_tournament_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    if chat_manager.tournament_active:
        await update.effective_chat.send_message("❌ Турнир уже запущен!")
        return

    participants = UserManager.get_tournament_registrations()
    if len(participants) < 10:
        await update.effective_chat.send_message(f"❌ Недостаточно участников! Нужно минимум 10, сейчас: {len(participants)}")
        return

    chat_manager.tournament_active = True
    chat_manager.tournament_start_time = datetime.now()

    for participant_id, username in participants:
        UserManager.update_balance(participant_id, 1000000, f"Стартовый бонус турнира")

    await update.effective_chat.send_message(
        f"🎮 **ТУРНИР НАЧАТ!**\n\n"
        f"📊 Участников: {len(participants)}\n"
        f"💰 Стартовый бонус: 1.000.000 🪙 каждому\n"
        f"⏰ Начало: {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"🔔 Внимание! Турнир продлится 24 часа.\n"
        f"🏆 Победители будут определены автоматически."
    )

    await asyncio.sleep(86400)

    await finish_tournament(context)

async def finish_tournament(context: ContextTypes.DEFAULT_TYPE):
    if not chat_manager.tournament_active:
        return

    participants = UserManager.get_tournament_registrations()

    if not participants:
        return

    participants_with_balance = []
    for user_id, username in participants:
        user = UserManager.get_user(user_id)
        if user:
            participants_with_balance.append((user_id, username, user[3]))

    participants_with_balance.sort(key=lambda x: x[2], reverse=True)

    winners = participants_with_balance[:10]

    prizes = [
        (1, "3 месяца Premium"),
        (2, 100000000),
        (3, 90000000),
        (4, 80000000),
        (5, 70000000),
        (6, 50000000),
        (7, 50000000),
        (8, 50000000),
        (9, 50000000),
        (10, 50000000),
    ]

    results_text = "🏆 **РЕЗУЛЬТАТЫ ТУРНИРА** 🏆\n\n"

    for i, (position, prize) in enumerate(prizes):
        if i < len(winners):
            user_id, username, balance = winners[i]

            if position == 1:
                results_text += f"🥇 1. <a href='tg://user?id={user_id}'>{username}</a>\n"
                results_text += f"   🎁 Приз: {prize}\n"
            else:
                results_text += f"#{position}. <a href='tg://user?id={user_id}'>{username}</a>\n"
                results_text += f"   💰 Приз: {prize:,} 🪙\n"
                UserManager.add_tournament_winner(user_id, username, position, prize)

            results_text += f"   📊 Баланс: {balance:,} 🪙\n\n"

    results_text += f"\n🎯 Всего участников: {len(participants)}\n"
    results_text += f"💰 Общий призовой фонд: 650.000.000 🪙\n"
    results_text += f"⏰ Турнир завершен: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=results_text,
        parse_mode='HTML'
    )

    UserManager.clear_tournament_registrations()
    chat_manager.clear_tournament()

    chat_manager.tournament_active = False

async def handle_tournament_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    participants = UserManager.get_tournament_registrations()

    status_text = "🏆 **СТАТУС ТУРНИРА**\n\n"

    if chat_manager.tournament_active:
        status_text += "🔵 **Турнир активен**\n"
        if chat_manager.tournament_start_time:
            elapsed = datetime.now() - chat_manager.tournament_start_time
            hours_left = 24 - (elapsed.total_seconds() / 3600)
            status_text += f"⏰ Осталось: {hours_left:.1f} часов\n"
    else:
        status_text += "🔴 **Турнир не активен**\n"

    status_text += f"📊 Зарегистрировано: {len(participants)}/150\n\n"

    if participants:
        status_text += "📋 **Зарегистрированные участники:**\n"
        for i, (user_id, username) in enumerate(participants[:10], 1):
            status_text += f"{i}. {username}\n"

        if len(participants) > 10:
            status_text += f"... и еще {len(participants) - 10} участников\n"

    status_text += "\n💰 **Призовые места:**\n"
    status_text += "1️⃣ 3 месяца Premium\n"
    status_text += "2️⃣ 100.000.000 🪙\n"
    status_text += "3️⃣ 90.000.000 🪙\n"
    status_text += "4️⃣ 80.000.000 🪙\n"
    status_text += "5️⃣ 70.000.000 🪙\n"
    status_text += "6️⃣-🔟 50.000.000 🪙"

    await update.effective_chat.send_message(status_text)

async def handle_give_role_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 4:
        await update.effective_chat.send_message(
            "❌ Формат: /giverole <user_id> <role> <days>\n\n"
            "📋 Примеры:\n"
            "• /giverole 123456789 вор 30 - вор в законе на 30 дней\n"
            "• /giverole 123456789 полиция 30 - полицейский на 30 дней\n"
            "• /giverole 123456789 вор 7 - вор в законе на 7 дней"
        )
        return

    try:
        target_user_id = int(words[1])
        role_type = words[2].lower()
        days = int(words[3])

        if days <= 0:
            await update.effective_chat.send_message("❌ Количество дней должно быть положительным!")
            return

        target_user = UserManager.get_user(target_user_id)
        if not target_user:
            await update.effective_chat.send_message("❌ Пользователь не найден!")
            return

        if role_type in ["вор", "thief", "вор_в_законе"]:
            role_name = "вор_в_законе"
            role_display = "👑 Вор в законе"
            price = "4,000₽"
        elif role_type in ["полиция", "police", "полицейский"]:
            role_name = "полицейский"
            role_display = "👮 Полицейский"
            price = "2,000₽"
        else:
            await update.effective_chat.send_message("❌ Неизвестная роль! Доступные: 'вор' или 'полиция'")
            return

        UserManager.set_user_role(target_user_id, role_name, days)

        target_name = target_user[15] if target_user[15] else (target_user[1] if target_user[1] else target_user[2])

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎭 Вам выдана роль!\n\n"
                     f"📛 Роль: {role_display}\n"
                     f"⏰ Срок: {days} дней\n"
                     f"💰 Цена: {price}\n\n"
                     f"✅ Роль активирована!\n\n"
                     f"💡 Команды:\n"
                     f"• Вор в законе: ответьте на сообщение 'вор -9000'\n"
                     f"• Полицейский: 'полиция'\n"
                     f"📅 Роль автоматически снимет: через {days} дней"
            )
        except:
            pass

        await update.effective_chat.send_message(
            f"✅ Роль выдана!\n\n"
            f"👤 Пользователь: {target_name}\n"
            f"🆔 ID: {target_user_id}\n"
            f"🎭 Роль: {role_display}\n"
            f"⏰ Срок: {days} дней\n"
            f"💰 Цена: {price}\n\n"
            f"📊 Роль активирована!"
        )

    except ValueError:
        await update.effective_chat.send_message("❌ Неверный формат! Введите числа правильно.")

async def handle_remove_role_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 2:
        await update.effective_chat.send_message("❌ Формат: /removerole <user_id>")
        return

    try:
        target_user_id = int(words[1])

        target_user = UserManager.get_user(target_user_id)
        if not target_user:
            await update.effective_chat.send_message("❌ Пользователь не найден!")
            return

        role_data = UserManager.get_user_role(target_user_id)

        if not role_data:
            await update.effective_chat.send_message("❌ У этого пользователя нет роли!")
            return

        UserManager.remove_user_role(target_user_id)

        target_name = target_user[15] if target_user[15] else (target_user[1] if target_user[1] else target_user[2])

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎭 Ваша роль снята!\n\n"
                     f"📛 Роль: {role_data[0]}\n"
                     f"⚠️ Ваша роль снята администратором\n\n"
                     f"💡 Для покупки новой роли зайдите в магазин."
            )
        except:
            pass

        await update.effective_chat.send_message(
            f"✅ Роль снята!\n\n"
            f"👤 Пользователь: {target_name}\n"
            f"🆔 ID: {target_user_id}\n"
            f"🎭 Роль: {role_data[0]}\n\n"
            f"📊 Роль деактивирована!"
        )

    except ValueError:
        await update.effective_chat.send_message("❌ Неверный формат!")

async def handle_check_roles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    active_roles = UserManager.get_all_active_roles()

    if not active_roles:
        await update.effective_chat.send_message("✅ Активных ролей нет!")
        return

    roles_text = "📊 АКТИВНЫЕ РОЛИ:\n\n"

    for user_id, role, expires, username, first_name, display_name in active_roles:
        if display_name:
            name = display_name
        elif username:
            name = username
        else:
            name = first_name

        expire_date = datetime.strptime(expires, "%Y-%m-%d %H:%M:%S")
        days_left = (expire_date - datetime.now()).days

        roles_text += f"👤 {name} (ID: {user_id})\n"
        roles_text += f"🎭 Роль: {role}\n"
        roles_text += f"⏰ Истекает: {expire_date.strftime('%d.%m.%Y %H:%M')}\n"
        roles_text += f"📅 Осталось: {days_left} дней\n"
        roles_text += "─" * 30 + "\n"

    await update.effective_chat.send_message(roles_text)

async def handle_addcoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 3:
        await update.effective_chat.send_message("❌ Формат команды: /addcoins <user_id> <amount>")
        return

    try:
        target_user_id = int(words[1])
        amount = int(words[2])

        if amount <= 0:
            await update.effective_chat.send_message("❌ Сумма должна быть положительной!")
            return

        user = UserManager.get_user(target_user_id)
        if not user:
            await update.effective_chat.send_message("❌ Пользователь не найден!")
            return

        UserManager.add_coins_to_user(target_user_id, amount)

        target_name = user[15] if user[15] else (user[1] if user[1] else user[2])
        await update.effective_chat.send_message(f"✅ Пользователю {target_name} добавлено {amount} монет!\nНовый баланс: {user[3] + amount} 🪙")

    except ValueError:
        await update.effective_chat.send_message("❌ Неверный формат! Используйте: /addcoins <user_id> <amount>")

async def handle_removecoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 3:
        await update.effective_chat.send_message("❌ Формат команды: /removecoins <user_id> <amount>")
        return

    try:
        target_user_id = int(words[1])
        amount = int(words[2])

        if amount <= 0:
            await update.effective_chat.send_message("❌ Сумма должна быть положительной!")
            return

        user = UserManager.get_user(target_user_id)
        if not user:
            await update.effective_chat.send_message("❌ Пользователь не найден!")
            return

        success, removed_amount = UserManager.remove_coins_from_user(target_user_id, amount)

        if success:
            target_name = user[15] if user[15] else (user[1] if user[1] else user[2])
            await update.effective_chat.send_message(f"✅ У пользователя {target_name} убрано {removed_amount} монет!\nНовый баланс: {max(0, user[3] - removed_amount)} 🪙")
        else:
            await update.effective_chat.send_message("❌ Ошибка при удалении монет!")

    except ValueError:
        await update.effective_chat.send_message("❌ Неверный формат! Используйте: /removecoins <user_id> <amount>")

async def handle_setlimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 4:
        await update.effective_chat.send_message(
            "❌ Формат команды: /setlimit <user_id> <тип> <лимит>\n\n"
            "📋 Примеры:\n"
            "• /setlimit 123456789 transfer 50000 - установить лимит перевода 50000 монет\n"
            "• /setlimit 123456789 roulette 5000000 - установить лимит рулетки 5 млн\n\n"
            "💡 Можно установить очень большие значения:\n"
            "• /setlimit 123456789 transfer 999999999\n"
            "• /setlimit 123456789 roulette 999999999"
        )
        return

    try:
        target_user_id = int(words[1])
        limit_type = words[2].lower()
        limit = int(words[3])

        if limit <= 0:
            await update.effective_chat.send_message("❌ Лимит должен быть положительным!")
            return

        user = UserManager.get_user(target_user_id)
        if not user:
            await update.effective_chat.send_message("❌ Пользователь не найден!")
            return

        if limit_type == "roulette":
            UserManager.set_roulette_limit(target_user_id, limit)
            target_name = user[15] if user[15] else (user[1] if user[1] else user[2])
            await update.effective_chat.send_message(
                f"✅ Лимит рулетки для пользователя {target_name} (ID: {target_user_id})\n"
                f"Установлен: {limit:,} монет 🪙\n\n"
                f"Теперь он может ставить до {limit:,} монет в рулетке!"
            )
        elif limit_type == "transfer":
            UserManager.set_transfer_limit(target_user_id, limit)
            target_name = user[15] if user[15] else (user[1] if user[1] else user[2])
            await update.effective_chat.send_message(
                f"✅ Лимит перевода для пользователя {target_name} (ID: {target_user_id})\n"
                f"Установлен: {limit:,} монет 🪙 за {TRANSFER_COOLDOWN_HOURS} часов\n\n"
                f"Теперь он может переводить до {limit:,} монет каждые {TRANSFER_COOLDOWN_HOURS} часов!"
            )
        else:
            await update.effective_chat.send_message("❌ Неверный тип лимита! Используйте: roulette или transfer")

    except ValueError:
        await update.effective_chat.send_message("❌ Неверный формат! Используйте числа для ID и лимита")

async def handle_limits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 2:
        await update.effective_chat.send_message("❌ Формат: /limits <user_id>")
        return

    try:
        target_user_id = int(words[1])
        user = UserManager.get_user(target_user_id)

        if not user:
            await update.effective_chat.send_message("❌ Пользователь не найден!")
            return

        roulette_limit = user[14] if len(user) > 14 and user[14] else ROULETTE_LIMIT
        transfer_limit = user[21] if len(user) > 21 and user[21] else TRANSFER_DAILY_LIMIT

        target_name = user[15] if user[15] else (user[1] if user[1] else user[2])

        await update.effective_chat.send_message(
            f"📊 Лимиты пользователя {target_name} (ID: {target_user_id}):\n\n"
            f"🎰 Лимит рулетки: {roulette_limit:,} монет 🪙\n"
            f"🔄 Лимит перевода: {transfer_limit:,} монет 🪙 за {TRANSFER_COOLDOWN_HOURS} ч.\n\n"
            f"💰 Баланс: {user[3]:,} 🪙"
        )

    except ValueError:
        await update.effective_chat.send_message("❌ Неверный формат ID!")

async def handle_resetbalances_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    try:
        affected_users = UserManager.reduce_all_balances_above_limit(100000)

        if affected_users > 0:
            await update.effective_chat.send_message(
                f"✅ Балансы уменьшены!\n\n"
                f"📊 Результаты:\n"
                f"• Затронуто пользователей: {affected_users}\n"
                f"• Новый баланс: 100,000 🪙 (или меньше)\n\n"
                f"💎 Балансы всех пользователей уменьшены до 100к.\n"
                f"📈 Пользователи с балансом ниже 100к не изменены."
            )
        else:
            await update.effective_chat.send_message("✅ Нет пользователей с балансом выше 100к!")

    except Exception as e:
        logger.error(f"Ошибка в команде уменьшения балансов: {e}")
        await update.effective_chat.send_message(f"❌ Ошибка: {e}")

async def handle_reducebalances_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 2:
        await update.effective_chat.send_message(
            "❌ Формат: /reducebalances <лимит>\n\n"
            "📋 Примеры:\n"
            "• /reducebalances 100000 - уменьшить до 100к\n"
            "• /reducebalances 50000 - уменьшить до 50к\n"
            "• /reducebalances 5000 - уменьшить до 5к\n\n"
            "💡 Внимание: Пользователи с балансом ниже лимита не изменятся!"
        )
        return

    try:
        limit = int(words[1])

        if limit < 0:
            await update.effective_chat.send_message("❌ Лимит не может быть отрицательным!")
            return

        affected_users = UserManager.reduce_all_balances_above_limit(limit)

        if affected_users > 0:
            await update.effective_chat.send_message(
                f"✅ Балансы уменьшены!\n\n"
                f"📊 Результаты:\n"
                f"• Затронуто пользователей: {affected_users}\n"
                f"• Новый баланс: {limit:,} 🪙 (или меньше)\n\n"
                f"💎 Балансы пользователей выше {limit:,} уменьшены.\n"
                f"📈 Пользователи с балансом ниже {limit:,} не изменены."
            )
        else:
            await update.effective_chat.send_message(f"✅ Нет пользователей с балансом выше {limit:,}!")

    except ValueError:
        await update.effective_chat.send_message("❌ Неверный формат! Введите число.")
    except Exception as e:
        logger.error(f"Ошибка в команде уменьшения балансов: {e}")
        await update.effective_chat.send_message(f"❌ Ошибка: {e}")

async def handle_activate_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Эта команда только для администратора!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 3:
        await update.effective_chat.send_message(
            "❌ Формат: /activatepremium <user_id> <type>\n\n"
            "📋 Примеры:\n"
            "• /activatepremium 123456789 1 - активировать Premium 1 (100 руб)\n"
            "• /activatepremium 123456789 2 - активировать Premium 2 (200 руб)\n\n"
            "💡 Premium 1: 20.000 монет ежедневно, 10.000 бонус\n"
            "💎 Premium 2: 50.000 монет ежедневно, 20.000 бонус"
        )
        return

    try:
        target_user_id = int(words[1])
        premium_type = int(words[2])

        if premium_type not in [1, 2]:
            await update.effective_chat.send_message("❌ Неверный тип Premium! Используйте 1 или 2")
            return

        user = UserManager.get_user(target_user_id)
        if not user:
            await update.effective_chat.send_message("❌ Пользователь не найден!")
            return

        UserManager.activate_premium(target_user_id, premium_type, 30)

        target_name = user[15] if user[15] else (user[1] if user[1] else user[2])
        premium_name = "Premium 1" if premium_type == 1 else "Premium 2"
        bonus_amount = 10000 if premium_type == 1 else 20000

        await update.effective_chat.send_message(
            f"✅ Premium активирован!\n\n"
            f"👤 Пользователь: {target_name}\n"
            f"🆔 ID: {target_user_id}\n"
            f"💰 Тип: {premium_name}\n"
            f"🎁 Бонус: {bonus_amount} монет\n"
            f"⏰ Срок: 30 дней\n\n"
            f"📊 Premium успешно активирован!"
        )

    except ValueError:
        await update.effective_chat.send_message("❌ Неверный формат! Используйте числа.")

async def handle_rodnoy_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "rodnoy_main_menu":
        await show_rodnoy_main_menu(update, context)

    elif data == "rodnoy_balance_page":
        await show_rodnoy_balance_page(update, context)

    elif data == "rodnoy_bonus_page":
        await show_rodnoy_bonus_page(update, context)

    elif data == "daily_bonus":
        await handle_daily_bonus(update, context)

    elif data == "premium_1_info":
        await handle_premium_1_info(update, context)

    elif data == "premium_2_info":
        await handle_premium_2_info(update, context)

    elif data == "rodnoy_games":
        await show_rodnoy_games_menu(update, context)

    elif data == "rodnoy_roles":
        await show_rodnoy_roles_menu(update, context)

    elif data == "rodnoy_rating":
        await show_rodnoy_rating_page(update, context)

    elif data == "rodnoy_settings":
        await show_rodnoy_settings(update, context)

    elif data == "rodnoy_buy_thief":
        await handle_rodnoy_buy_thief(update, context)

    elif data == "rodnoy_buy_police":
        await handle_rodnoy_buy_police(update, context)

    elif data == "rodnoy_roulette_game":
        await Games.ruleka(update, context)

    elif data == "rodnoy_bandit_game":
        await Games.banditka(update, context)

async def handle_rodnoy_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ['group', 'supergroup']:
        return
    await show_rodnoy_main_menu(update, context)

async def handle_bonus_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ['group', 'supergroup']:
        return

    user_id = update.effective_user.id
    user = UserManager.get_user(user_id)

    if not user:
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        UserManager.create_user(user_id, username, first_name, None)
        user = UserManager.get_user(user_id)

    # Веб бонус системасына шилтеме
    webapp_bonus = InlineKeyboardButton("🎁 БОНУСЫ В MINI APP", web_app={"url": f"{WEBAPP_URL}?page=bonus"})
    
    keyboard = [
        [webapp_bonus],
        [InlineKeyboardButton("🎁 Ежедневный бонус 10.000", callback_data="daily_bonus")],
        [InlineKeyboardButton("💰 Premium 1 (100 руб)", callback_data="premium_1_info")],
        [InlineKeyboardButton("💎 Premium 2 (200 руб)", callback_data="premium_2_info")],
        [InlineKeyboardButton("◀️ Назад", callback_data="rodnoy_main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    bonus_text = "🎁 **𝗦 ○ U I D G ▲ M [] S БОНУСНАЯ СИСТЕМА**\n\n👇 Выберите бонус:"

    await update.effective_chat.send_message(bonus_text, reply_markup=reply_markup)

async def handle_donate_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ['group', 'supergroup']:
        return

    user_id = update.effective_user.id
    user = UserManager.get_user(user_id)

    if not user:
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        UserManager.create_user(user_id, username, first_name, None)
        user = UserManager.get_user(user_id)

    donate_text = (
        f"Монеты🪙\n"
        f"200.000 - 100₽\n"
        f"500.000 - 230₽\n"
        f"1.000.000 - 450₽\n"
        f"2.000.000 - 845₽\n"
        f"5.000.000 - 2.000₽\n"
        f"10.000.000 - 4.000₽\n"
        f"50.000.000 - 20000₽\n"
        f"100.000.000 - 40000₽\n\n"
        f"Telegram не сможет помочь с покупками, сделанными через нашего бота,\n"
        f"Если возникнут вопросы, Вы можете обратиться к: @SQUIIDGAMES_KASSA"
    )

    keyboard = [
        [InlineKeyboardButton("Получить бонус", url="https://t.me/mani_app_bot/app")],
        [InlineKeyboardButton("Связаться с тех. поддержкой", url="https://t.me/SQUIIDGAMES_KASSA")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_chat.send_message(donate_text, reply_markup=reply_markup)

async def handle_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ['group', 'supergroup']:
        return

    help_text = (
        "❓ ** 𝗦 ○ U I D G ▲ M [] S ПОМОЩЬ**\n\n"
        "📖 **Основные команды:**\n"
        "• /start - запустить бота\n"
        "• /SKUID - главное меню\n"
        "• /bonus - бонус система\n"
        "• /id - узнать свой ID\n"
        "• /setname - изменить отображаемое имя\n\n"
        "🎮 **Игры:**\n"
        "• Рулетка - угадайте число или цвет\n"
        "• Бандит - соберите одинаковые символы\n"
        "• Mini App - краш, дурак, бонусы\n\n"
        "👥 **Групповые команды:**\n"
        "• Б - баланс\n"
        "• ТОП - топ игроков\n"
        "• ГО - запустить рулетку\n"
        "• !лог - история рулетки\n"
        "• Ва-банк - все на одно число\n\n"
        "🎭 **Роли:**\n"
        "• Вор в законе - кража монет (4000₽)\n"
        "• Полицейский - защита от воров (2000₽)\n\n"
        "🎁 **Бонусы:**\n"
        "• Ежедневный бонус: 10.000 монет\n"
        "• Premium 1: 20.000 монет/день (100 руб)\n"
        "• Premium 2: 50.000 монет/день (200 руб)\n"
        "• Mini App: 60 каналов с бонусами\n\n"
        "🏆 **Турниры:**\n"
        "• /tournament_register - регистрация\n"
        "• /tournament_status - статус\n"
        "• (Только Premium 2)\n\n"
        "💡 **Полезное:**\n"
        "• '!бот иши' - информация о боте\n"
        "• 'вор -9000' - украсть монеты\n"
        "• 'полиция' - защититься\n"
        "• '1000 0-12' - ставка на диапазон\n"
        "• 'Ва-банк 7' - все на одно число\n"
        "• 'ставки' - показать все ставки\n"
        "• 'повторить' - повторить ставки\n"
        "• 'удвоить' - удвоить ставки\n\n"
        "🛡️ **Модерация (для админов):**\n"
        "• мут - замутить на 24 часа (ответом на сообщение)\n"
        "• размут - размутить (ответом на сообщение)\n"
        "• бан - забанить (ответом на сообщение)\n"
        "• разбан - разбанить (ответом на сообщение)\n"
        "• мут список - список мутов\n"
        "• бан список - список банов\n"
        "• мутдан - мулга түшкөндөрдүн тизмеси\n"
        "• бандан - банга түшкөндөрдүн тизмеси\n"
        "• размут @username - username боюнча размут\n"
        "• разбан @username - username боюнча разбан\n\n"
        "📞 **Поддержка:** @SQUIIDGAMES_KASSA"
    )

    await update.effective_chat.send_message(help_text)

async def rodnoy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ['group', 'supergroup']:
        return

    user_id = update.effective_user.id

    if UserManager.is_blocked(user_id):
        return

    username = update.effective_user.username
    first_name = update.effective_user.first_name

    UserManager.create_user(user_id, username, first_name, None)

    # Веб колдонмого шилтеме
    webapp_button = InlineKeyboardButton("🎮 ИГРАТЬ В MINI APP", web_app={"url": WEBAPP_URL})
    
    welcome_text = (
        f"👋 Привет, {first_name}!\n\n"
        f"✨ **🏠 𝗦 ○ U I D G ▲ M [] S** запущен!\n\n"
        f"👇 Используйте кнопки ниже или напишите /SKUID."
    )

    keyboard = [
        [webapp_button],
        [KeyboardButton("🏠 𝗦 ○ U I D G ▲ M [] S")],
        [KeyboardButton("🎁 Бонус"), KeyboardButton("💰 Пополнить баланс")],
        [KeyboardButton("❓ Помощь")]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.effective_chat.send_message(welcome_text, reply_markup=reply_markup)

async def check_expiry_job(context: ContextTypes.DEFAULT_TYPE):
    deleted_roles = UserManager.check_role_expiry()
    deleted_premium = UserManager.check_premium_expiry()

    if deleted_roles > 0:
        logger.info(f"Истекшие роли удалены: {deleted_roles}")
    if deleted_premium > 0:
        logger.info(f"Истекшие Premium удалены: {deleted_premium}")

class Games:
    @staticmethod
    async def ruleka(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id

        # Рулетканы баштоо
        chat_manager.roulette_started[chat_id] = True
        chat_manager.last_activity[chat_id] = datetime.now().timestamp()

        user_id = update.effective_user.id

        keyboard = [
            [
                InlineKeyboardButton("1-3", callback_data="bet_1_3"),
                InlineKeyboardButton("4-6", callback_data="bet_4_6"),
                InlineKeyboardButton("7-9", callback_data="bet_7_9"),
                InlineKeyboardButton("10-12", callback_data="bet_10_12")
            ],
            [
                InlineKeyboardButton("1к🔴", callback_data="bet_red"),
                InlineKeyboardButton("1к⚫️", callback_data="bet_black"),
                InlineKeyboardButton("1к💚", callback_data="bet_zero")
            ],
            [
                InlineKeyboardButton("Повторить", callback_data="repeat_bet"),
                InlineKeyboardButton("Удвоить", callback_data="double_bet"),
                InlineKeyboardButton("Крутить", callback_data="spin_roulette")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        user = UserManager.get_user(user_id)
        if not user:
            return

        roulette_layout = (
            "РУЛЕТКА\n"
            "Угадайте число из:\n"
            "0💚\n"
            "1🔴 2⚫️ 3🔴 4⚫️ 5🔴 6⚫️\n"
            "7🔴 8⚫️ 9🔴 10⚫️ 11🔴 12⚫️\n"
            "Ставки можно текстом:\n"
            "1000 на красное | 5000 на 12\n"
        )

        if update.message:
            await update.message.reply_text(roulette_layout, reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.message.reply_text(roulette_layout, reply_markup=reply_markup)

    @staticmethod
    async def handle_roulette_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, bet_type: str, bet_value: str, amount: int):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        user = UserManager.get_user(user_id)

        # Активдүүлүктү жаңыртуу
        chat_manager.last_activity[chat_id] = datetime.now().timestamp()

        # Рулетка башталганбы?
        if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
            if update.callback_query:
                await update.callback_query.answer("Рулетка не запущена, наберите Рулетка", show_alert=True)
            else:
                await update.effective_chat.send_message("Рулетка не запущена, наберите Рулетка")
            return False

        if not user:
            return False

        if amount <= 0:
            return False

        if amount < MIN_BET:
            if update.callback_query:
                await update.callback_query.answer(f"❌ Минимальная ставка: {MIN_BET} монет!", show_alert=True)
            else:
                await update.effective_chat.send_message(f"❌ Минимальная ставка: {MIN_BET} монет!")
            return False

        if user[3] < amount:
            if user[15]:
                display_name = user[15]
            elif user[1]:
                display_name = user[1]
            else:
                display_name = user[2]

            keyboard = [
                [InlineKeyboardButton("Пополнить баланс", url=DONATE_LINK)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if update.callback_query:
                await update.callback_query.message.reply_text(
                    f"{display_name}, недостаточно монет!\n\n",
                    reply_markup=reply_markup
                )
            else:
                await update.effective_chat.send_message(
                    f"{display_name}, недостаточно монет!\n\n",
                    reply_markup=reply_markup
                )
            return False

        if chat_id not in chat_manager.roulette_bets:
            chat_manager.roulette_bets[chat_id] = {}
        if user_id not in chat_manager.roulette_bets[chat_id]:
            chat_manager.roulette_bets[chat_id][user_id] = []

        if user[15]:
            username = user[15]
        elif user[1]:
            username = user[1]
        else:
            username = user[2]

        existing_bet = None
        for bet in chat_manager.roulette_bets[chat_id][user_id]:
            if bet['type'] == bet_type and bet['value'] == bet_value:
                existing_bet = bet
                break

        bet_description = ""
        if bet_type == 'number':
            bet_description = f"{bet_value}"
        elif bet_type == 'color':
            color_names = {'red': 'красное', 'black': 'чёрное', 'zero': 'зеленое'}
            bet_description = color_names.get(bet_value, bet_value)
        elif bet_type == 'range':
            range_names = {'1_3': '1-3', '4_6': '4-6', '7_9': '7-9', '10_12': '10-12'}
            bet_description = range_names.get(bet_value, bet_value)

        if existing_bet:
            existing_bet['amount'] += amount
        else:
            chat_manager.roulette_bets[chat_id][user_id].append({
                'type': bet_type,
                'value': bet_value,
                'amount': amount,
                'username': username,
                'description': bet_description
            })

        # Акыркы ставкаларды сактоо (20 мүнөткө)
        if chat_id not in chat_manager.last_bets_details:
            chat_manager.last_bets_details[chat_id] = {}
        if user_id not in chat_manager.last_bets_details[chat_id]:
            chat_manager.last_bets_details[chat_id][user_id] = []

        # Эски ставкаларды текшерүү (20 мүнөттөн эски болсо өчүрүү)
        current_time = datetime.now().timestamp()
        chat_manager.last_bets_details[chat_id][user_id] = [
            bet for bet in chat_manager.last_bets_details[chat_id][user_id]
            if bet.get('timestamp', current_time) > current_time - 1200  # 20 минут = 1200 секунд
        ]

        # Жаңы ставканы кошуу
        chat_manager.last_bets_details[chat_id][user_id].append({
            'type': bet_type,
            'value': bet_value,
            'amount': amount,
            'description': bet_description,
            'timestamp': current_time
        })

        UserManager.update_balance(user_id, -amount, f"Ставка в рулетку: {bet_description}")

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO roulette_bets (user_id, bet_type, bet_value, amount) VALUES (?, ?, ?, ?)",
            (user_id, bet_type, bet_value, amount)
        )
        conn.commit()
        conn.close()

        chat_manager.last_bet_amounts[chat_id][user_id] = amount
        chat_manager.last_bet_types[chat_id][user_id] = (bet_type, bet_value, bet_description)

        return True

    @staticmethod
    async def spin_roulette_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        if chat_id in chat_manager.roulette_spinning and chat_manager.roulette_spinning[chat_id]:
            if update.callback_query:
                await update.callback_query.answer("Рулетка уже крутится!", show_alert=True)
            return

        if chat_id not in chat_manager.roulette_bets or not chat_manager.roulette_bets[chat_id]:
            if update.callback_query:
                await update.callback_query.answer("Никто не сделал ставок! Сначала сделайте ставку.", show_alert=True)
            return

        chat_manager.roulette_spinning[chat_id] = True

        try:
            # ГО басуучунун атын алуу
            spinner_name = ""
            if update.callback_query:
                spinner_user_id = update.callback_query.from_user.id
                spinner_user = UserManager.get_user(spinner_user_id)
                if spinner_user:
                    if spinner_user[15]:
                        spinner_name = spinner_user[15]
                    elif spinner_user[1]:
                        spinner_name = spinner_user[1]
                    else:
                        spinner_name = spinner_user[2]
            else:
                spinner_user_id = update.effective_user.id
                spinner_user = UserManager.get_user(spinner_user_id)
                if spinner_user:
                    if spinner_user[15]:
                        spinner_name = spinner_user[15]
                    elif spinner_user[1]:
                        spinner_name = spinner_user[1]
                    else:
                        spinner_name = spinner_user[2]

            # Случайное время ожидания
            random_wait = random.choice([3, 5, 10, 12, 15])

            time_message = await context.bot.send_message(
                chat_id=chat_id,
                text=f"{spinner_name} крутит (через {random_wait} сек).."
            )

            await asyncio.sleep(random_wait)

            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=time_message.message_id
                )
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения: {e}")

            try:
                gif_message = await context.bot.send_animation(
                    chat_id=chat_id,
                    animation=GIF_URL,
                    caption="🎰 Рулетка вращается..."
                )

                await asyncio.sleep(3)

                try:
                    await context.bot.delete_message(
                        chat_id=chat_id,
                        message_id=gif_message.message_id
                    )
                except:
                    pass

            except Exception as e:
                logger.error(f"Ошибка отправки GIF: {e}")

            winning_number = 0
            winning_color = "💚"
            color_name = "зеленое"

            if chat_id in chat_manager.next_roulette_result and chat_manager.next_roulette_result[chat_id]:
                winning_result = chat_manager.next_roulette_result[chat_id]
                try:
                    if winning_result:
                        match = re.match(r'^(\d+)', winning_result)
                        if match:
                            winning_number = int(match.group(1))
                        else:
                            winning_number = random.randint(0, 12)

                        if "💚" in winning_result:
                            winning_color = "💚"
                            color_name = "зеленое"
                        elif "🔴" in winning_result:
                            winning_color = "🔴"
                            color_name = "красное"
                        elif "⚫️" in winning_result:
                            winning_color = "⚫️"
                            color_name = "чёрное"
                        else:
                            if winning_number == 0:
                                winning_color = "💚"
                                color_name = "зеленое"
                            elif winning_number % 2 == 1:
                                winning_color = "🔴"
                                color_name = "красное"
                            else:
                                winning_color = "⚫️"
                                color_name = "чёрное"
                    else:
                        winning_number = random.randint(0, 12)
                        if winning_number == 0:
                            winning_color = "💚"
                            color_name = "зеленое"
                        elif winning_number % 2 == 1:
                            winning_color = "🔴"
                            color_name = "красное"
                        else:
                            winning_color = "⚫️"
                            color_name = "чёрное"
                except (ValueError, AttributeError) as e:
                    logger.error(f"Ошибка обработки next_roulette_result: {e}")
                    winning_number = random.randint(0, 12)
                    if winning_number == 0:
                        winning_color = "💚"
                        color_name = "зеленое"
                    elif winning_number % 2 == 1:
                        winning_color = "🔴"
                        color_name = "красное"
                    else:
                        winning_color = "⚫️"
                        color_name = "чёрное"
            else:
                winning_number = random.randint(0, 12)
                if winning_number == 0:
                    winning_color = "💚"
                    color_name = "зеленое"
                elif winning_number % 2 == 1:
                    winning_color = "🔴"
                    color_name = "красное"
                else:
                    winning_color = "⚫️"
                    color_name = "чёрное"

            result_text = f"{winning_number}{winning_color}"

            UserManager.add_global_roulette_log(chat_id, result_text)

            if chat_id not in chat_manager.group_roulette_results:
                chat_manager.group_roulette_results[chat_id] = []

            chat_manager.group_roulette_results[chat_id].insert(0, result_text)
            if len(chat_manager.group_roulette_results[chat_id]) > 21:
                chat_manager.group_roulette_results[chat_id] = chat_manager.group_roulette_results[chat_id][:21]

            if chat_manager.roulette_bets[chat_id]:
                for user_id in chat_manager.roulette_bets[chat_id]:
                    UserManager.add_roulette_log(chat_id, user_id, result_text)

            result_message = f"Рулетка: {winning_number}{winning_color}\n"

            all_bets = []
            user_bets_map = {}

            if chat_manager.roulette_bets[chat_id]:
                for user_id, bet_info in chat_manager.roulette_bets[chat_id].items():
                    user = UserManager.get_user(user_id)
                    if not user:
                        continue

                    if user[15]:
                        username = user[15]
                    else:
                        username = user[2] or f"ID{user_id}"

                    user_bets_map[user_id] = username

                    for bet in bet_info:
                        bet_won = False
                        win_amount = 0
                        multiplier = 1
                        return_amount = 0

                        display_value = bet.get('description', '')

                        if bet['type'] == 'number':
                            if int(bet['value']) == winning_number:
                                bet_won = True
                                multiplier = 12
                                win_amount = bet['amount'] * multiplier
                                if winning_number == 0:
                                    return_amount = int(bet['amount'] * 0.5)
                                    total_win = win_amount + return_amount
                                else:
                                    total_win = win_amount

                        elif bet['type'] == 'color':
                            color_map = {'red': '🔴', 'black': '⚫️', 'zero': '💚'}
                            if bet['value'] in color_map and color_map[bet['value']] == winning_color:
                                bet_won = True
                                multiplier = 2
                                win_amount = bet['amount'] * multiplier
                                if winning_number == 0:
                                    return_amount = int(bet['amount'] * 0.5)
                                    total_win = win_amount + return_amount
                                else:
                                    total_win = win_amount

                        elif bet['type'] == 'range':
                            ranges = {
                                '1_3': (1, 3), '4_6': (4, 6),
                                '7_9': (7, 9), '10_12': (10, 12)
                            }
                            if bet['value'] in ranges:
                                start, end = ranges[bet['value']]
                                if start <= winning_number <= end:
                                    bet_won = True
                                    multiplier = 3
                                    win_amount = bet['amount'] * multiplier
                                    if winning_number == 0:
                                        return_amount = int(bet['amount'] * 0.5)
                                        total_win = win_amount + return_amount
                                    else:
                                        total_win = win_amount

                        if bet_won:
                            UserManager.update_balance(user_id, total_win, f"Выигрыш в рулетку: +{total_win}")
                            all_bets.append((user_id, bet['amount'], display_value, True, win_amount, return_amount))
                        else:
                            if winning_number == 0:
                                return_amount = int(bet['amount'] * 0.5)
                                UserManager.update_balance(user_id, return_amount, f"Возврат при 0💚: +{return_amount}")
                                all_bets.append((user_id, bet['amount'], display_value, False, 0, return_amount))
                            else:
                                all_bets.append((user_id, bet['amount'], display_value, False, 0, 0))

            # Бардык ставкаларды ак түстө чыгаруу (аты жок)
            for user_id, amount, display_value, is_winning, win_amount, return_amount in all_bets:
                username = user_bets_map.get(user_id, f"ID{user_id}")
                result_message += f"{username} {amount} на {display_value}\n"

            # Уткандарды өзүнчө көк түстө чыгаруу
            for user_id, amount, display_value, is_winning, win_amount, return_amount in all_bets:
                username = user_bets_map.get(user_id, f"ID{user_id}")
                if is_winning:
                    result_message += f"<a href='tg://user?id={user_id}'>{username}</a> выиграл {win_amount} на {display_value}\n"

            # Возвраттарды чыгаруу
            for user_id, amount, display_value, is_winning, win_amount, return_amount in all_bets:
                username = user_bets_map.get(user_id, f"ID{user_id}")
                if return_amount > 0 and not is_winning:
                    result_message += f"{username} возврат {return_amount}\n"
                elif return_amount > 0 and is_winning:
                    result_message += f"{username} +{return_amount} за 0💚\n"

            if not all_bets:
                result_message += "Никто не сделал ставок\n"

            # Акыркы оюндун ставкаларын сактап калуу
            if chat_id in chat_manager.roulette_bets:
                chat_manager.last_game_bets[chat_id] = {}
                for uid, bets in chat_manager.roulette_bets[chat_id].items():
                    chat_manager.last_game_bets[chat_id][uid] = bets.copy()

            if update.callback_query:
                try:
                    await update.callback_query.message.edit_text(result_message, parse_mode='HTML')
                except:
                    pass
                roulette_layout = (
                    "РУЛЕТКА\n"
                    "Угадайте число из:\n"
                    "0💚\n"
                    "1🔴 2⚫️ 3🔴 4⚫️ 5🔴 6⚫️\n"
                    "7🔴 8⚫️ 9🔴 10⚫️ 11🔴 12⚫️\n"
                    "Ставки можно текстом:\n"
                    "1000 на красное | 5000 на 12\n"
                )
                await context.bot.send_message(chat_id=chat_id, text=roulette_layout, reply_markup=reply_markup)
            else:
                await context.bot.send_message(chat_id=chat_id, text=result_message, parse_mode='HTML')
                roulette_layout = (
                    "РУЛЕТКА\n"
                    "Угадайте число из:\n"
                    "0💚\n"
                    "1🔴 2⚫️ 3🔴 4⚫️ 5🔴 6⚫️\n"
                    "7🔴 8⚫️ 9🔴 10⚫️ 11🔴 12⚫️\n"
                    "Ставки можно текстом:\n"
                    "1000 на красное | 5000 на 12\n"
                )
                await context.bot.send_message(chat_id=chat_id, text=roulette_layout, reply_markup=reply_markup)

        finally:
            if chat_id in chat_manager.roulette_bets:
                chat_manager.roulette_bets[chat_id] = {}
            chat_manager.roulette_spinning[chat_id] = False
            if chat_id in chat_manager.next_roulette_result:
                del chat_manager.next_roulette_result[chat_id]

    @staticmethod
    async def handle_bandit_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
        user_id = update.effective_user.id
        user = UserManager.get_user(user_id)

        if not user:
            return False

        if amount < MIN_BANDIT_BET:
            await update.effective_chat.send_message(f"Минимальная ставка в бандитку: {MIN_BANDIT_BET} монет!")
            return False

        if user[3] < amount:
            if user[15]:
                display_name = user[15]
            elif user[1]:
                display_name = user[1]
            else:
                display_name = user[2]

            keyboard = [[InlineKeyboardButton("Пополнить баланс", url=DONATE_LINK)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.effective_chat.send_message(
                f"{display_name}, недостаточно монет!\n\n",
                reply_markup=reply_markup
            )
            return False

        UserManager.update_balance(user_id, -amount, f"Ставка в бандитку: -{amount}")

        asyncio.create_task(Games._banditka_logic_with_amount(update, context, amount))
        return True

    @staticmethod
    async def banditka(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = UserManager.get_user(user_id)
        amount = MIN_BANDIT_BET

        if not user or user[3] < amount:
            keyboard = [[InlineKeyboardButton("Пополнить баланс", url=DONATE_LINK)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.effective_chat.send_message(f"Минимальная ставка: {MIN_BANDIT_BET} монет!\n\n", reply_markup=reply_markup)
            return

        UserManager.update_balance(user_id, -amount, f"Ставка в бандитку: -{amount}")

        asyncio.create_task(Games._banditka_logic_with_amount(update, context, amount))

    @staticmethod
    async def _banditka_logic_with_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
        user_id = update.effective_user.id
        user = UserManager.get_user(user_id)

        username = update.effective_user.username
        first_name = update.effective_user.first_name
        UserManager.update_user_from_tg(user_id, username, first_name)

        user = UserManager.get_user(user_id)
        if user[15]:
            display_name = user[15]
        elif user[1]:
            display_name = user[1]
        else:
            display_name = user[2]

        symbols = ["♦️", "♣️", "♥️", "♠️", "🧧", "🎴", "🀄"]
        result = [random.choice(symbols) for _ in range(5)]

        message = await update.effective_chat.send_message(f"{display_name}\n\n{result[0]}|■|■|■|■|")
        await asyncio.sleep(1.0)

        await message.edit_text(f"{display_name}\n\n{result[0]}{result[1]}|■|■|■|")
        await asyncio.sleep(1.0)

        await message.edit_text(f"{display_name}\n\n{result[0]}{result[1]}{result[2]}|■|■|")
        await asyncio.sleep(1.0)

        await message.edit_text(f"{display_name}\n\n{result[0]}{result[1]}{result[2]}{result[3]}|■|")
        await asyncio.sleep(1.0)

        final_result = "".join(result)
        unique = len(set(result))

        if unique == 1:
            win = random.randint(amount * 7, amount * 8)
        elif unique == 2:
            win = random.randint(amount * 4, amount * 5)
        elif unique == 3:
            win = random.randint(amount * 2, amount * 3)
        else:
            win = 0

        if win > 0:
            UserManager.update_balance(user_id, win, f"Выигрыш в бандитку: +{win}")
            final_message = f"{display_name}\n\n{final_result}\nВыигрыш: {win} 🪙"
        else:
            final_message = f"{display_name}\n\n{final_result}\nПроигрыш: {amount} 🪙"

        await message.edit_text(final_message)

async def handle_go_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Рулетканы текшерүү
    if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
        await update.effective_chat.send_message("Рулетка не запущена, наберите Рулетка")
        return

    if chat_id in chat_manager.go_tasks and not chat_manager.go_tasks[chat_id].done():
        await update.effective_chat.send_message("⏳ ГО уже запущен! Подождите завершения.")
        return

    task = asyncio.create_task(run_go_command(update, context, chat_id, user_id))
    chat_manager.go_tasks[chat_id] = task

    def cleanup(_):
        if chat_id in chat_manager.go_tasks:
            del chat_manager.go_tasks[chat_id]

    task.add_done_callback(cleanup)

async def run_go_command(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int):
    user = UserManager.get_user(user_id)
    if not user:
        return

    if chat_id not in chat_manager.roulette_bets or not chat_manager.roulette_bets[chat_id]:
        await update.effective_chat.send_message("Никто не сделал ставок! Сначала сделайте ставку.")
        return

    if user[15]:
        display_name = user[15]
    elif user[1]:
        display_name = user[1]
    else:
        display_name = user[2]

    random_wait = random.choice([3, 5, 10, 12, 15])

    time_message = await update.effective_chat.send_message(f"{display_name} крутит (через {random_wait} сек)..")

    await asyncio.sleep(random_wait)

    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=time_message.message_id
        )
    except Exception as e:
        logger.error(f"Ошибка удаления сообщения: {e}")

    try:
        gif_message = await update.effective_chat.send_animation(
            animation=GIF_URL,
            caption="🎰"
        )

        await asyncio.sleep(3)

        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=gif_message.message_id
            )
        except:
            pass

    except Exception as e:
        logger.error(f"Ошибка отправки GIF: {e}")

    winning_number = 0
    winning_color = "💚"
    color_name = "зеленое"

    if chat_id in chat_manager.next_roulette_result and chat_manager.next_roulette_result[chat_id]:
        winning_result = chat_manager.next_roulette_result[chat_id]
        try:
            if winning_result:
                match = re.match(r'^(\d+)', winning_result)
                if match:
                    winning_number = int(match.group(1))
                else:
                    winning_number = random.randint(0, 12)

                if "💚" in winning_result:
                    winning_color = "💚"
                    color_name = "зеленое"
                elif "🔴" in winning_result:
                    winning_color = "🔴"
                    color_name = "красное"
                elif "⚫️" in winning_result:
                    winning_color = "⚫️"
                    color_name = "чёрное"
                else:
                    if winning_number == 0:
                        winning_color = "💚"
                        color_name = "зеленое"
                    elif winning_number % 2 == 1:
                        winning_color = "🔴"
                        color_name = "красное"
                    else:
                        winning_color = "⚫️"
                        color_name = "чёрное"
            else:
                winning_number = random.randint(0, 12)
                if winning_number == 0:
                    winning_color = "💚"
                    color_name = "зеленое"
                elif winning_number % 2 == 1:
                    winning_color = "🔴"
                    color_name = "красное"
                else:
                    winning_color = "⚫️"
                    color_name = "чёрное"
        except (ValueError, AttributeError) as e:
            logger.error(f"Ошибка обработки next_roulette_result: {e}")
            winning_number = random.randint(0, 12)
            if winning_number == 0:
                winning_color = "💚"
                color_name = "зеленое"
            elif winning_number % 2 == 1:
                winning_color = "🔴"
                color_name = "красное"
            else:
                winning_color = "⚫️"
                color_name = "чёрное"
    else:
        winning_number = random.randint(0, 12)
        if winning_number == 0:
            winning_color = "💚"
            color_name = "зеленое"
        elif winning_number % 2 == 1:
            winning_color = "🔴"
            color_name = "красное"
        else:
            winning_color = "⚫️"
            color_name = "чёрное"

    result_text = f"{winning_number}{winning_color}"

    UserManager.add_global_roulette_log(chat_id, result_text)

    if chat_id not in chat_manager.group_roulette_results:
        chat_manager.group_roulette_results[chat_id] = []

    chat_manager.group_roulette_results[chat_id].insert(0, result_text)
    if len(chat_manager.group_roulette_results[chat_id]) > 21:
        chat_manager.group_roulette_results[chat_id] = chat_manager.group_roulette_results[chat_id][:21]

    if chat_manager.roulette_bets[chat_id]:
        for user_id in chat_manager.roulette_bets[chat_id]:
            UserManager.add_roulette_log(chat_id, user_id, result_text)

    result_message = f"Рулетка: {winning_number}{winning_color}\n"

    all_bets = []
    user_bets_map = {}

    if chat_manager.roulette_bets[chat_id]:
        for user_id, bet_info in chat_manager.roulette_bets[chat_id].items():
            user = UserManager.get_user(user_id)
            if not user:
                continue

            if user[15]:
                username = user[15]
            else:
                username = user[2] or f"ID{user_id}"

            user_bets_map[user_id] = username

            for bet in bet_info:
                bet_won = False
                win_amount = 0
                multiplier = 1
                return_amount = 0

                display_value = bet.get('description', '')

                if bet['type'] == 'number':
                    if int(bet['value']) == winning_number:
                        bet_won = True
                        multiplier = 12
                        win_amount = bet['amount'] * multiplier
                        if winning_number == 0:
                            return_amount = int(bet['amount'] * 0.5)
                            total_win = win_amount + return_amount
                        else:
                            total_win = win_amount

                elif bet['type'] == 'color':
                    color_map = {'red': '🔴', 'black': '⚫️', 'zero': '💚'}
                    if bet['value'] in color_map and color_map[bet['value']] == winning_color:
                        bet_won = True
                        multiplier = 2
                        win_amount = bet['amount'] * multiplier
                        if winning_number == 0:
                            return_amount = int(bet['amount'] * 0.5)
                            total_win = win_amount + return_amount
                        else:
                            total_win = win_amount

                elif bet['type'] == 'range':
                    ranges = {
                        '1_3': (1, 3), '4_6': (4, 6),
                        '7_9': (7, 9), '10_12': (10, 12)
                    }
                    if bet['value'] in ranges:
                        start, end = ranges[bet['value']]
                        if start <= winning_number <= end:
                            bet_won = True
                            multiplier = 3
                            win_amount = bet['amount'] * multiplier
                            if winning_number == 0:
                                return_amount = int(bet['amount'] * 0.5)
                                total_win = win_amount + return_amount
                            else:
                                total_win = win_amount

                if bet_won:
                    UserManager.update_balance(user_id, total_win, f"Выигрыш в рулетку: +{total_win}")
                    all_bets.append((user_id, bet['amount'], display_value, True, win_amount, return_amount))
                else:
                    if winning_number == 0:
                        return_amount = int(bet['amount'] * 0.5)
                        UserManager.update_balance(user_id, return_amount, f"Возврат при 0💚: +{return_amount}")
                        all_bets.append((user_id, bet['amount'], display_value, False, 0, return_amount))
                    else:
                        all_bets.append((user_id, bet['amount'], display_value, False, 0, 0))

    # Бардык ставкаларды ак түстө чыгаруу (аты жок)
    for user_id, amount, display_value, is_winning, win_amount, return_amount in all_bets:
        username = user_bets_map.get(user_id, f"ID{user_id}")
        result_message += f"{username} {amount} на {display_value}\n"

    # Уткандарды өзүнчө көк түстө чыгаруу
    for user_id, amount, display_value, is_winning, win_amount, return_amount in all_bets:
        username = user_bets_map.get(user_id, f"ID{user_id}")
        if is_winning:
            result_message += f"<a href='tg://user?id={user_id}'>{username}</a> выиграл {win_amount} на {display_value}\n"

    # Возвраттарды чыгаруу
    for user_id, amount, display_value, is_winning, win_amount, return_amount in all_bets:
        username = user_bets_map.get(user_id, f"ID{user_id}")
        if return_amount > 0 and not is_winning:
            result_message += f"{username} возврат {return_amount}\n"
        elif return_amount > 0 and is_winning:
            result_message += f"{username} +{return_amount} за 0💚\n"

    if not all_bets:
        result_message += "Никто не сделал ставок\n"

    # Акыркы оюндун ставкаларын сактап калуу
    if chat_id in chat_manager.roulette_bets:
        chat_manager.last_game_bets[chat_id] = {}
        for uid, bets in chat_manager.roulette_bets[chat_id].items():
            chat_manager.last_game_bets[chat_id][uid] = bets.copy()

    await update.effective_chat.send_message(result_message, parse_mode='HTML')

    keyboard = [
        [
            InlineKeyboardButton("1-3", callback_data="bet_1_3"),
            InlineKeyboardButton("4-6", callback_data="bet_4_6"),
            InlineKeyboardButton("7-9", callback_data="bet_7_9"),
            InlineKeyboardButton("10-12", callback_data="bet_10_12")
        ],
        [
            InlineKeyboardButton("1к🔴", callback_data="bet_red"),
            InlineKeyboardButton("1к⚫️", callback_data="bet_black"),
            InlineKeyboardButton("1к💚", callback_data="bet_zero")
        ],
        [
            InlineKeyboardButton("Повторить", callback_data="repeat_bet"),
            InlineKeyboardButton("Удвоить", callback_data="double_bet"),
            InlineKeyboardButton("Крутить", callback_data="spin_roulette")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    roulette_layout = (
        "РУЛЕТКА\n"
        "Угадайте число из:\n"
        "0💚\n"
        "1🔴 2⚫️ 3🔴 4⚫️ 5🔴 6⚫️\n"
        "7🔴 8⚫️ 9🔴 10⚫️ 11🔴 12⚫️\n"
        "Ставки можно текстом:\n"
        "1000 на красное | 5000 на 12\n"
    )
    await update.effective_chat.send_message(roulette_layout, reply_markup=reply_markup)

    chat_manager.reset_chat_roulette(chat_id)

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    username = update.effective_user.username
    first_name = update.effective_user.first_name
    UserManager.update_user_from_tg(user_id, username, first_name)

    if update.effective_chat.type in ['group', 'supergroup']:
        if UserManager.is_muted(user_id):
            try:
                await update.message.delete()
                return
            except Exception as e:
                logger.error(f"Ошибка при проверке мута: {e}")

        text = update.message.text or ""
        if contains_url(text):
            try:
                await update.message.delete()
                return
            except Exception as e:
                logger.error(f"Ошибка при удалении ссылки: {e}")

    user = UserManager.get_user(user_id)
    if not user:
        UserManager.create_user(user_id, username, first_name, None)
        user = UserManager.get_user(user_id)

    if not user:
        return

    text = update.message.text.strip()
    text_lower = text.lower()

    if text == "🏠 𝗦 ○ U I D G ▲ M [] S":
        await show_rodnoy_main_menu(update, context)
        return

    if text == "🎁 Бонус":
        await handle_bonus_button(update, context)
        return

    if text == "💰 Пополнить баланс":
        await handle_donate_button(update, context)
        return

    if text == "❓ Помощь":
        await handle_help_button(update, context)
        return

    if text_lower.startswith("вор"):
        await handle_thief_steal(update, context)
        return

    if text_lower == "полиция" or text_lower == "полицейский":
        await handle_police_protect(update, context)
        return

    if text_lower == "мут":
        await handle_text_mute(update, context)
        return

    if text_lower == "размут":
        await handle_text_unmute(update, context)
        return

    if text_lower == "бан":
        await handle_text_ban(update, context)
        return

    if text_lower == "разбан":
        await handle_text_unban(update, context)
        return

    if text_lower == "мут список":
        await handle_mute_list_text(update, context)
        return

    if text_lower == "бан список":
        await handle_ban_list_text(update, context)
        return

    if text_lower == "мутдан":
        await handle_mutdan_command(update, context)
        return

    if text_lower == "бандан":
        await handle_bandan_command(update, context)
        return

    if text_lower.startswith("размут"):
        await handle_razmut_username(update, context)
        return

    if text_lower.startswith("разбан"):
        await handle_razban_username(update, context)
        return

    if text_lower.startswith("дай админ"):
        await handle_dai_admin_command(update, context)
        return

    if text_lower.startswith("убери админ"):
        await handle_uberi_admin_command(update, context)
        return

    if text_lower in ["ставки", "ставка"]:
        await show_user_bets(update, context)
        return

    if text_lower in ["повторить", "повтор", "repeat"]:
        await repeat_user_bets(update, context)
        return

    if text_lower in ["удвоить", "удвой", "double"]:
        await double_user_bets(update, context)
        return

    if text.upper() == "Б":
        if user[15]:
            display_name = user[15]
        elif user[1]:
            display_name = user[1]
        else:
            display_name = user[2]

        await update.effective_chat.send_message(f"{display_name}\nМонеты: {user[3]}🪙")
        return

    if text.upper() == "ГО":
        # Рулетканы текшерүү
        if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
            await update.effective_chat.send_message("Рулетка не запущена, наберите Рулетка")
            return
        await handle_go_command(update, context)
        return

    if text.upper() == "КРУТИТЬ":
        if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
            await update.effective_chat.send_message("Рулетка не запущена, наберите Рулетка")
            return
        await handle_go_command(update, context)
        return

    if text.upper() == "!ЛОГ":
        await show_big_log(update, context)
        return

    if text.upper() == "ЛОГ":
        await show_small_log(update, context)
        return

    if text.upper() == "ТОП":
        current_user_id = update.effective_user.id
        current_user = UserManager.get_user(current_user_id)
        user_position = UserManager.get_user_position_by_balance(current_user_id)

        top_users = UserManager.get_global_top_users(10)

        if not top_users:
            top_text = "[ТОП 10 БОГАТЫХ]\n\nТоп пуст!\n\n"
            telegram_name = current_user[2] if current_user and current_user[2] else update.effective_user.first_name
            top_text += f"{telegram_name}: {user_position} место"
            await update.effective_chat.send_message(top_text)
            return

        top_text = "[ТОП 10 БОГАТЫХ]\n\n"

        for i, (top_user_id, display_name, username, first_name, balance) in enumerate(top_users, 1):
            if display_name:
                name = display_name
            elif username:
                name = username
            else:
                name = first_name

            top_text += f"{i}. {name} [{balance}]\n"

        top_text += "¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯\n"
        telegram_name = current_user[2] if current_user and current_user[2] else update.effective_user.first_name
        top_text += f"{telegram_name}: {user_position} место"

        await update.effective_chat.send_message(top_text)
        return

    if text.upper() in ["ДОНАТ", "ДОНАЦ", "DONATE", "ПОПОЛНИТЬ"]:
        user = UserManager.get_user(user_id)

        if not user:
            return

        display_name = user[15] if len(user) > 15 and user[15] else (user[1] if user[1] else user[2])

        donate_text = (
            f"Монеты🪙\n"
            f"200.000 - 100₽\n"
            f"500.000 - 230₽\n"
            f"1.000.000 - 450₽\n"
            f"2.000.000 - 845₽\n"
            f"5.000.000 - 2.000₽\n"
            f"10.000.000 - 4.000₽\n"
            f"50.000.000 - 20000₽\n"
            f"100.000.000 - 40000₽\n\n"
            f"Telegram не сможет помочь с покупками, сделанными через нашего бота,\n"
            f"Если возникнут вопросы, Вы можете обратиться к: @SQUIIDGAMES_KASSA"
        )

        keyboard = [
            [InlineKeyboardButton("Получить бонус", url="https://t.me/mani_app_bot/app")],
            [InlineKeyboardButton("Связаться с тех. поддержкой", url="https://t.me/SQUIIDGAMES_KASSA")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.effective_chat.send_message(donate_text, reply_markup=reply_markup)
        return

    if text.upper() in ["ПРОФИЛЬ", "ПРОФ", "PROFILE", "PROF"]:
        user_id = update.effective_user.id
        user = UserManager.get_user(user_id)

        if not user:
            return

        if user[15]:
            display_name = user[15]
        elif user[1]:
            display_name = user[1]
        else:
            display_name = user[2]

        profile_text = (
            f"{display_name}: ♠️♥️\n"
            f"ID: {user_id}\n"
            f"Монеты: {user[3]}🪙\n"
            f"Выиграно: {user[8]}\n"
            f"Проиграно: {user[7]}\n"
            f"Макс. выигрыш: {user[10]}\n"
            f"Макс. ставка: {user[9]}"
        )

        await update.effective_chat.send_message(profile_text)
        return

    if text_lower == "история":
        user_id = update.effective_user.id
        transactions = UserManager.get_transaction_history(user_id, 10)

        if not transactions:
            await update.effective_chat.send_message("История пуста")
            return

        history_text = ""
        for date_str, amount, ttype, description in transactions:
            time_str = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("[%H:%M:%S]")
            if amount > 0:
                history_text += f"{time_str} выигрыш в {description.lower()}: +{amount}\n"
            else:
                history_text += f"{time_str} проигрыш в {description.lower()}: {amount}\n"

        await update.effective_chat.send_message(history_text)
        return

    if text_lower == "отмена":
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        user = UserManager.get_user(user_id)
        if not user:
            return

        if user[15]:
            username = user[15]
        elif user[1]:
            username = user[1]
        else:
            username = user[2]

        if chat_id in chat_manager.roulette_bets and user_id in chat_manager.roulette_bets[chat_id]:
            bets = chat_manager.roulette_bets[chat_id][user_id]
            total_return = 0

            for bet in bets:
                total_return += bet['amount']
                UserManager.update_balance(user_id, bet['amount'], f"Возврат ставки: +{bet['amount']}")

            del chat_manager.roulette_bets[chat_id][user_id]

            if user_id in chat_manager.last_bet_amounts[chat_id]:
                del chat_manager.last_bet_amounts[chat_id][user_id]
            if user_id in chat_manager.last_bet_types[chat_id]:
                del chat_manager.last_bet_types[chat_id][user_id]
            if user_id in chat_manager.last_bets_details[chat_id]:
                del chat_manager.last_bets_details[chat_id][user_id]

            await update.effective_chat.send_message(f"Ставки {username} отменены\n💰 Возврат: {total_return} 🪙")
        else:
            await update.effective_chat.send_message(f"{username}, у вас нет ставок для отмены")
        return

    if text.upper() in ["РУЛЕТКА", "RULE", "ROULETTE"]:
        await Games.ruleka(update, context)
        return

    if text.upper() in ["БАНДИТ", "BANDIT"]:
        await Games.banditka(update, context)
        return

    if text.upper().startswith("ВА-БАНК"):
        # Рулетканы текшерүү
        if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
            await update.effective_chat.send_message("Рулетка не запущена, наберите Рулетка")
            return

        user_id = update.effective_user.id
        user = UserManager.get_user(user_id)

        if not user:
            return

        amount = user[3]

        if amount < MIN_BET:
            keyboard = [
                [InlineKeyboardButton("Пополнить баланс", url=DONATE_LINK)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.effective_chat.send_message(
                f"❌ Недостаточно монет для ставки!\n\n",
                reply_markup=reply_markup
            )
            return

        text_upper = text.upper()

        # "ВА-БАНК 0-12" форматын текшерүү
        range_match = re.search(r'ВА-БАНК\s+(\d+)-(\d+)', text_upper)
        if range_match:
            start_num = int(range_match.group(1))
            end_num = int(range_match.group(2))
            
            if start_num < 0 or end_num > 12 or start_num >= end_num:
                await update.effective_chat.send_message("❌ Неверный диапазон! Используйте числа от 0 до 12.")
                return
            
            range_count = end_num - start_num + 1
            bet_per_number = amount // range_count
            
            if bet_per_number < 1:
                await update.effective_chat.send_message("❌ Слишком маленькая сумма для диапазона!")
                return
            
            total_bet_amount = 0
            bets_made = []
            
            if user[15]:
                username = user[15]
            elif user[1]:
                username = user[1]
            else:
                username = user[2]
            
            for num in range(start_num, end_num + 1):
                success = await Games.handle_roulette_bet(update, context, "number", str(num), bet_per_number)
                if success:
                    total_bet_amount += bet_per_number
                    bets_made.append(f"{bet_per_number} на {num}")
            
            if total_bet_amount > 0:
                result_text = f"{username}\n"
                for bet_line in bets_made:
                    result_text += f"{bet_line}\n"
                await update.effective_chat.send_message(result_text)
                await update.effective_chat.send_message(f"🎰 Ва-банк! {username} поставил все {amount} на {start_num}-{end_num}")
            return

        # Бир санга текшерүү
        for num in range(0, 13):
            num_str = str(num)
            if f"ВА-БАНК {num_str}" in text_upper or text_upper == f"ВА-БАНК{num_str}":
                bet_type, bet_value, bet_description = "number", num_str, f"{num_str}"
                success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
                if success:
                    if user[15]:
                        username = user[15]
                    elif user[1]:
                        username = user[1]
                    else:
                        username = user[2]
                    await update.effective_chat.send_message(f"🎰 Ва-банк! {username} поставил все {amount} на {bet_description}")
                return

        if "ВА-БАНК К" in text_upper or "ВА-БАНК КРАС" in text_upper:
            bet_type, bet_value, bet_description = "color", "red", "красное"
            success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
        elif "ВА-БАНК Ч" in text_upper or "ВА-БАНК ЧЕР" in text_upper or "ВА-БАНК ЧЁР" in text_upper:
            bet_type, bet_value, bet_description = "color", "black", "чёрное"
            success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
        elif "ВА-БАНК З" in text_upper or "ВА-БАНК ЗЕЛ" in text_upper or "ВА-БАНК 0" in text_upper:
            bet_type, bet_value, bet_description = "number", "0", "зеленое"
            success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
        elif "ВА-БАНК 1-3" in text_upper:
            bet_type, bet_value, bet_description = "range", "1_3", "1-3"
            success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
        elif "ВА-БАНК 4-6" in text_upper:
            bet_type, bet_value, bet_description = "range", "4_6", "4-6"
            success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
        elif "ВА-БАНК 7-9" in text_upper:
            bet_type, bet_value, bet_description = "range", "7_9", "7-9"
            success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
        elif "ВА-БАНК 10-12" in text_upper:
            bet_type, bet_value, bet_description = "range", "10_12", "10-12"
            success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
        else:
            words = text.split()
            if len(words) > 1:
                bet_word = words[1].lower()
                if bet_word in ["ч", "черное", "черный", "чёрное", "чёрный"]:
                    bet_type, bet_value, bet_description = "color", "black", "чёрное"
                elif bet_word in ["к", "красное", "красный"]:
                    bet_type, bet_value, bet_description = "color", "red", "красное"
                elif bet_word in ["з", "зеленое", "зеленый", "0"]:
                    bet_type, bet_value, bet_description = "number", "0", "зеленое"
                elif "-" in bet_word:
                    if bet_word == "1-3":
                        bet_type, bet_value, bet_description = "range", "1_3", "1-3"
                    elif bet_word == "4-6":
                        bet_type, bet_value, bet_description = "range", "4_6", "4-6"
                    elif bet_word == "7-9":
                        bet_type, bet_value, bet_description = "range", "7_9", "7-9"
                    elif bet_word == "10-12":
                        bet_type, bet_value, bet_description = "range", "10_12", "10-12"
                    else:
                        await update.effective_chat.send_message("❌ Неверная команда! Используйте: Ва-банк <ставка>")
                        return
                elif bet_word.isdigit() and 0 <= int(bet_word) <= 12:
                    num = int(bet_word)
                    bet_type, bet_value, bet_description = "number", str(num), f"{num}"
                else:
                    await update.effective_chat.send_message("❌ Неверная команда! Используйте: Ва-банк <ставка>")
                    return

                success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
            else:
                await update.effective_chat.send_message("❌ Неверная команда! Используйте: Ва-банк <ставка>")
                return

        if success:
            if user[15]:
                username = user[15]
            elif user[1]:
                username = user[1]
            else:
                username = user[2]
            await update.effective_chat.send_message(f"🎰 Ва-банк! {username} поставил все {amount} на {bet_description}")
        return

    if text_lower.startswith("бандит"):
        words = text.split()

        if len(words) == 1:
            amount = MIN_BANDIT_BET
        elif len(words) == 2:
            try:
                amount = int(words[1])
                if amount < MIN_BANDIT_BET:
                    await update.effective_chat.send_message(f"❌ Минимальная ставка в бандитку: {MIN_BANDIT_BET} монет!")
                    return
            except ValueError:
                amount = MIN_BANDIT_BET
        else:
            amount = MIN_BANDIT_BET

        if user[3] < amount:
            if user[15]:
                display_name = user[15]
            elif user[1]:
                display_name = user[1]
            else:
                display_name = user[2]

            await update.effective_chat.send_message(f"{display_name}, недостаточно монет на балансе")
            return

        UserManager.update_balance(user_id, -amount, f"Ставка в бандитку: -{amount}")
        asyncio.create_task(Games._banditka_logic_with_amount(update, context, amount))
        return

    words = text.split()
    if len(words) == 2:
        try:
            amount = int(words[0])
            if amount >= MIN_BANDIT_BET and words[1].lower() == "бандит":
                if user[3] < amount:
                    if user[15]:
                        display_name = user[15]
                    elif user[1]:
                        display_name = user[1]
                    else:
                        display_name = user[2]

                    await update.effective_chat.send_message(f"{display_name}, недостаточно монет на балансе")
                    return

                UserManager.update_balance(user_id, -amount, f"Ставка в бандитку: -{amount}")
                asyncio.create_task(Games._banditka_logic_with_amount(update, context, amount))
                return
        except ValueError:
            pass

    if "+" in text:
        try:
            amount = int(text.replace("+", "").strip())
            if amount <= 0:
                return

            if user[3] < amount:
                await update.effective_chat.send_message("❌ Недостаточно монет на балансе")
                return

            can_transfer, message = UserManager.can_make_transfer(user_id, amount)
            if not can_transfer:
                await update.effective_chat.send_message(f"{message}")
                return

            if update.message.reply_to_message:
                to_user_id = update.message.reply_to_message.from_user.id
                to_user = UserManager.get_user(to_user_id)

                if to_user:
                    to_display_name = to_user[15] if len(to_user) > 15 and to_user[15] else (to_user[1] if to_user[1] else to_user[2])
                    from_display_name = user[15] if len(user) > 15 and user[15] else (user[1] if user[1] else user[2])

                    if from_display_name:
                        from_name = from_display_name
                    elif user[1]:
                        from_name = user[1]
                    else:
                        from_name = user[2]

                    if to_display_name:
                        to_name = to_display_name
                    elif to_user[1]:
                        to_name = to_user[1]
                    else:
                        to_name = to_user[2]

                    UserManager.update_balance(user_id, -amount, f"Перевод игроку {to_display_name}: -{amount}")
                    UserManager.update_balance(to_user_id, amount, f"Перевод от игрока {from_display_name}: +{amount}")

                    UserManager.update_transfer_usage(user_id, amount)

                    await update.effective_chat.send_message(
                        f"💸 <a href='tg://user?id={user_id}'>{from_name}</a> перевёл {amount}🪙 пользователю <a href='tg://user?id={to_user_id}'>{to_name}</a>",
                        parse_mode='HTML'
                    )

        except ValueError:
            return

    # Рулетка ставкаларын текшерүү
    if len(words) >= 2:
        try:
            amount = int(words[0])
            bet_part = ' '.join(words[1:]).lower()

            if amount < MIN_BET:
                await update.effective_chat.send_message(f"❌ Минимальная ставка: {MIN_BET} монет!")
                return

            # Рулетканы текшерүү
            if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
                await update.effective_chat.send_message("Рулетка не запущена, наберите Рулетка")
                return

            if user[3] < amount:
                if user[15]:
                    display_name = user[15]
                elif user[1]:
                    display_name = user[1]
                else:
                    display_name = user[2]
                keyboard = [
                    [InlineKeyboardButton("Пополнить баланс", url=DONATE_LINK)]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.effective_chat.send_message(
                    f"{display_name}, недостаточно монет!\n\n",
                    reply_markup=reply_markup
                )
                return

            # Диапазонду текшерүү (мисалы: 1000 0-5)
            range_match = re.search(r'(\d+)-(\d+)', bet_part)
            if range_match:
                start_num = int(range_match.group(1))
                end_num = int(range_match.group(2))
                
                if start_num < 0 or end_num > 12 or start_num >= end_num:
                    await update.effective_chat.send_message("❌ Неверный диапазон! Используйте числа от 0 до 12.")
                    return
                
                range_count = end_num - start_num + 1
                bet_per_number = amount // range_count
                
                if bet_per_number < 1:
                    await update.effective_chat.send_message("❌ Слишком маленькая сумма для диапазона!")
                    return
                
                total_bet_amount = 0
                bets_made = []
                
                if user[15]:
                    username = user[15]
                elif user[1]:
                    username = user[1]
                else:
                    username = user[2]
                
                for num in range(start_num, end_num + 1):
                    success = await Games.handle_roulette_bet(update, context, "number", str(num), bet_per_number)
                    if success:
                        total_bet_amount += bet_per_number
                        bets_made.append(f"{bet_per_number} на {num}")
                
                if total_bet_amount > 0:
                    result_text = f"{username}\n"
                    for bet_line in bets_made:
                        result_text += f"{bet_line}\n"
                    await update.effective_chat.send_message(result_text)
                return

            # Санды текшерүү
            if bet_part.isdigit():
                num = int(bet_part)
                if 0 <= num <= 12:
                    bet_type = "number"
                    bet_value = str(num)
                    bet_description = str(num)
                    success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
                    if success:
                        if user[15]:
                            username = user[15]
                        elif user[1]:
                            username = user[1]
                        else:
                            username = user[2]
                        await update.effective_chat.send_message(
                            f"Ставка принята: <a href='tg://user?id={user_id}'>{username}</a> {amount} на {bet_description}",
                            parse_mode='HTML'
                        )
                    return

            # Түстөрдү текшерүү
            elif bet_part in ["ч", "черное", "черный", "чёрное", "чёрный"]:
                bet_type = "color"
                bet_val = "black"
                bet_description = "чёрное"
                success = await Games.handle_roulette_bet(update, context, bet_type, bet_val, amount)
                if success:
                    if user[15]:
                        username = user[15]
                    elif user[1]:
                        username = user[1]
                    else:
                        username = user[2]
                    await update.effective_chat.send_message(
                        f"Ставка принята: <a href='tg://user?id={user_id}'>{username}</a> {amount} на {bet_description}",
                        parse_mode='HTML'
                    )
                return

            elif bet_part in ["к", "красное", "красный"]:
                bet_type = "color"
                bet_val = "red"
                bet_description = "красное"
                success = await Games.handle_roulette_bet(update, context, bet_type, bet_val, amount)
                if success:
                    if user[15]:
                        username = user[15]
                    elif user[1]:
                        username = user[1]
                    else:
                        username = user[2]
                    await update.effective_chat.send_message(
                        f"Ставка принята: <a href='tg://user?id={user_id}'>{username}</a> {amount} на {bet_description}",
                        parse_mode='HTML'
                    )
                return

            elif bet_part in ["з", "зеленое", "зеленый", "0"]:
                bet_type = "number"
                bet_val = "0"
                bet_description = "зеленое"
                success = await Games.handle_roulette_bet(update, context, bet_type, bet_val, amount)
                if success:
                    if user[15]:
                        username = user[15]
                    elif user[1]:
                        username = user[1]
                    else:
                        username = user[2]
                    await update.effective_chat.send_message(
                        f"Ставка принята: <a href='tg://user?id={user_id}'>{username}</a> {amount} на {bet_description}",
                        parse_mode='HTML'
                    )
                return

        except ValueError:
            pass

async def show_user_bets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    user = UserManager.get_user(user_id)
    if not user:
        return

    if user[15]:
        username = user[15]
    elif user[1]:
        username = user[1]
    else:
        username = user[2]

    # Акыркы ставкаларды текшерүү (20 мүнөттөн эски болсо өчүрүү)
    current_time = datetime.now().timestamp()
    if chat_id in chat_manager.last_bets_details and user_id in chat_manager.last_bets_details[chat_id]:
        chat_manager.last_bets_details[chat_id][user_id] = [
            bet for bet in chat_manager.last_bets_details[chat_id][user_id]
            if bet.get('timestamp', current_time) > current_time - 1200  # 20 минут = 1200 секунд
        ]

    if chat_id in chat_manager.last_bets_details and user_id in chat_manager.last_bets_details[chat_id]:
        last_bets = chat_manager.last_bets_details[chat_id][user_id]
        if last_bets:
            bets_text = f"{username}\n"
            total_amount = 0

            for bet in last_bets:
                amount = bet['amount']
                description = bet.get('description', '')
                total_amount += amount

                bets_text += f"{amount} на {description}\n"

            await update.effective_chat.send_message(bets_text)
        else:
            await update.effective_chat.send_message(f"{username}, у вас нет сохраненных ставок")
    else:
        await update.effective_chat.send_message(f"{username}, у вас нет ставок")

async def repeat_user_bets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    user = UserManager.get_user(user_id)
    if not user:
        return

    # Рулетканы текшерүү
    if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
        await update.effective_chat.send_message("Рулетка не запущена, наберите Рулетка")
        return

    # Акыркы оюндун ставкаларын колдонуу (ГО басканга чейинки)
    if chat_id in chat_manager.last_game_bets and user_id in chat_manager.last_game_bets[chat_id]:
        last_bets = chat_manager.last_game_bets[chat_id][user_id]
        if not last_bets:
            await update.effective_chat.send_message("Нет предыдущих ставок для повторения")
            return

        if user[15]:
            username = user[15]
        elif user[1]:
            username = user[1]
        else:
            username = user[2]

        total_amount = 0
        success_count = 0
        bets_list = []

        for bet in last_bets:
            bet_type = bet['type']
            bet_value = bet['value']
            amount = bet['amount']
            description = bet.get('description', '')

            if user[3] < amount:
                continue

            success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
            if success:
                total_amount += amount
                success_count += 1
                bets_list.append(f"{amount} на {description}")

        if success_count > 0:
            result_text = f"{username}\n"
            for bet_line in bets_list:
                result_text += f"{bet_line}\n"
            await update.effective_chat.send_message(result_text)
        else:
            await update.effective_chat.send_message("❌ Не удалось повторить ставки. Проверьте баланс")
    else:
        # Эгер акыркы оюндун ставкалары жок болсо, last_bets_details колдонуу
        if chat_id in chat_manager.last_bets_details and user_id in chat_manager.last_bets_details[chat_id]:
            last_bets = chat_manager.last_bets_details[chat_id][user_id]
            if not last_bets:
                await update.effective_chat.send_message("Нет предыдущих ставок для повторения")
                return

            # Бирдей ставкаларды бириктирүү
            bet_dict = {}
            for bet in last_bets:
                key = (bet['type'], bet['value'])
                if key in bet_dict:
                    bet_dict[key]['amount'] += bet['amount']
                else:
                    bet_dict[key] = bet.copy()

            if user[15]:
                username = user[15]
            elif user[1]:
                username = user[1]
            else:
                username = user[2]

            total_amount = 0
            success_count = 0
            bets_list = []

            for bet in bet_dict.values():
                bet_type = bet['type']
                bet_value = bet['value']
                amount = bet['amount']
                description = bet.get('description', '')

                if user[3] < amount:
                    continue

                success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
                if success:
                    total_amount += amount
                    success_count += 1
                    bets_list.append(f"{amount} на {description}")

            if success_count > 0:
                result_text = f"{username}\n"
                for bet_line in bets_list:
                    result_text += f"{bet_line}\n"
                await update.effective_chat.send_message(result_text)
            else:
                await update.effective_chat.send_message("❌ Не удалось повторить ставки. Проверьте баланс")
        else:
            await update.effective_chat.send_message("Нет предыдущих ставок для повторения")

async def double_user_bets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    user = UserManager.get_user(user_id)
    if not user:
        return

    # Рулетканы текшерүү
    if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
        await update.effective_chat.send_message("Рулетка не запущена, наберите Рулетка")
        return

    # Акыркы оюндун ставкаларын колдонуу (ГО басканга чейинки)
    if chat_id in chat_manager.last_game_bets and user_id in chat_manager.last_game_bets[chat_id]:
        last_bets = chat_manager.last_game_bets[chat_id][user_id]
        if not last_bets:
            await update.effective_chat.send_message("Нет предыдущих ставок для удвоения")
            return

        if user[15]:
            username = user[15]
        elif user[1]:
            username = user[1]
        else:
            username = user[2]

        total_amount = 0
        success_count = 0
        bets_list = []

        for bet in last_bets:
            bet_type = bet['type']
            bet_value = bet['value']
            original_amount = bet['amount']
            new_amount = original_amount * 2
            description = bet.get('description', '')

            if user[3] < new_amount:
                continue

            success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, new_amount)
            if success:
                total_amount += new_amount
                success_count += 1
                bets_list.append(f"{new_amount} на {description}")

        if success_count > 0:
            result_text = f"{username}\n"
            for bet_line in bets_list:
                result_text += f"{bet_line}\n"
            await update.effective_chat.send_message(result_text)
        else:
            await update.effective_chat.send_message("❌ Не удалось удвоить ставки. Проверьте баланс")
    else:
        # Эгер акыркы оюндун ставкалары жок болсо, last_bets_details колдонуу
        if chat_id in chat_manager.last_bets_details and user_id in chat_manager.last_bets_details[chat_id]:
            last_bets = chat_manager.last_bets_details[chat_id][user_id]
            if not last_bets:
                await update.effective_chat.send_message("Нет предыдущих ставок для удвоения")
                return

            # Бирдей ставкаларды бириктирүү
            bet_dict = {}
            for bet in last_bets:
                key = (bet['type'], bet['value'])
                if key in bet_dict:
                    bet_dict[key]['amount'] += bet['amount']
                else:
                    bet_dict[key] = bet.copy()

            if user[15]:
                username = user[15]
            elif user[1]:
                username = user[1]
            else:
                username = user[2]

            total_amount = 0
            success_count = 0
            bets_list = []

            for bet in bet_dict.values():
                bet_type = bet['type']
                bet_value = bet['value']
                original_amount = bet['amount']
                new_amount = original_amount * 2
                description = bet.get('description', '')

                if user[3] < new_amount:
                    continue

                success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, new_amount)
                if success:
                    total_amount += new_amount
                    success_count += 1
                    bets_list.append(f"{new_amount} на {description}")

            if success_count > 0:
                result_text = f"{username}\n"
                for bet_line in bets_list:
                    result_text += f"{bet_line}\n"
                await update.effective_chat.send_message(result_text)
            else:
                await update.effective_chat.send_message("❌ Не удалось удвоить ставки. Проверьте баланс")
        else:
            await update.effective_chat.send_message("Нет предыдущих ставок для удвоения")

async def show_small_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user = UserManager.get_user(user_id)

    if not user:
        return

    logs_db = UserManager.get_global_roulette_logs(chat_id, 10)
    logs = logs_db if logs_db else []

    if not logs:
        await update.effective_chat.send_message("Лог пуст")
        return

    log_text = ""
    for log in reversed(logs):
        if log:
            log_text += f"{log}\n"

    if log_text.strip():
        await update.effective_chat.send_message(log_text.strip())

        if user_id == ADMIN_ID:
            last_results = logs[:10] if len(logs) >= 10 else logs
            next_result = calculate_next_result(last_results, chat_id)

            await context.bot.send_message(
                chat_id=user_id,
                text=f"{next_result}"
            )

async def show_big_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user = UserManager.get_user(user_id)

    if not user:
        return

    logs_db = UserManager.get_global_roulette_logs_all(chat_id, 21)
    logs = logs_db if logs_db else []

    if not logs:
        await update.effective_chat.send_message("Лог пуст")
        return

    log_text = ""
    for log in reversed(logs):
        if log:
            log_text += f"{log}\n"

    if log_text.strip():
        await update.effective_chat.send_message(log_text.strip())

        if user_id == ADMIN_ID:
            last_results = logs[:10] if len(logs) >= 10 else logs
            next_result = calculate_next_result(last_results, chat_id)

            await context.bot.send_message(
                chat_id=user_id,
                text=f"{next_result}"
            )

async def handle_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
        target_name = target_user.first_name
        if target_user.username:
            target_name = target_user.username

        await update.effective_chat.send_message(f"🆔 ID пользователя {target_name}: {target_user_id}")
    else:
        user = UserManager.get_user(user_id)
        if user and user[15]:
            display_name = user[15]
        elif user and user[1]:
            display_name = user[1]
        else:
            display_name = update.effective_user.first_name

        await update.effective_chat.send_message(f"🆔 Ваш ID ({display_name}): {user_id}")

async def handle_setname_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 2:
        await update.effective_chat.send_message("❌ Укажите новое имя! Пример: /setname НовоеИмя")
        return

    new_name = ' '.join(words[1:])

    if len(new_name) > 50:
        await update.effective_chat.send_message("❌ Имя слишком длинное! Максимум 50 символов.")
        return

    UserManager.set_display_name(user_id, new_name)

    await update.effective_chat.send_message(f"✅ Ваше отображаемое имя изменено на: {new_name}")

async def handle_mute_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not update.message.reply_to_message:
        await update.effective_chat.send_message("❌ Команда должна быть ответом на сообщение пользователя!")
        return

    is_admin = await is_group_admin(context, chat_id, user_id)

    if not (user_id == ADMIN_ID or UserManager.has_permission(user_id, "mute") or is_admin):
        await update.effective_chat.send_message("❌ У вас нет прав на мутирование!")
        return

    target_user = update.message.reply_to_message.from_user
    target_id = target_user.id

    if target_id == user_id:
        await update.effective_chat.send_message("❌ Нельзя замутить самого себя!")
        return

    target_is_admin = await is_group_admin(context, chat_id, target_id)
    if target_is_admin and user_id != ADMIN_ID:
        await update.effective_chat.send_message("❌ Нельзя замутить другого администратора!")
        return

    text = update.message.text.strip()
    words = text.split()

    if len(words) < 2:
        await update.effective_chat.send_message("❌ Укажите время! Пример: /mute 60 (минут)")
        return

    try:
        minutes = int(words[1])
        if minutes <= 0:
            await update.effective_chat.send_message("❌ Время должно быть положительным!")
            return

        hours = minutes / 60
        UserManager.mute_user(target_id, hours, user_id)

        target_name = target_user.first_name
        if target_user.username:
            target_name = target_user.username

        admin_name = update.effective_user.first_name
        if update.effective_user.username:
            admin_name = update.effective_user.username

        mute_until = datetime.now() + timedelta(minutes=minutes)
        mute_until_str = mute_until.strftime("%d.%m.%Y %H:%M:%S")

        await update.effective_chat.send_message(
            f"🔇 Пользователь <a href='tg://user?id={target_id}'>{target_name}</a> замьючен до {mute_until_str}!\n"
            f"👮 Администратор: <a href='tg://user?id={user_id}'>{admin_name}</a>",
            parse_mode='HTML'
        )
    except ValueError:
        await update.effective_chat.send_message("❌ Неверный формат времени! Используйте число минут.")

async def check_roulette_inactivity(context: ContextTypes.DEFAULT_TYPE):
    """20 мүнөт эч активдүүлүк болбосо, рулетканы өчүрүү"""
    current_time = datetime.now().timestamp()
    for chat_id, last_time in list(chat_manager.last_activity.items()):
        if current_time - last_time > 1200:  # 20 минут
            if chat_id in chat_manager.roulette_started:
                chat_manager.roulette_started[chat_id] = False
                del chat_manager.last_activity[chat_id]

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    try:
        job_queue = app.job_queue
        if job_queue:
            job_queue.run_daily(check_expiry_job, time=datetime.time(hour=0, minute=0))
            job_queue.run_repeating(UserManager.reset_daily_limits, interval=43200, first=10)
            job_queue.run_repeating(check_roulette_inactivity, interval=60, first=10)  # Ар бир 60 секунд сайын текшерүү
    except:
        logger.info("JobQueue нет, автоматические задачи не будут работать")

    app.add_handler(CommandHandler("rodnoy", rodnoy_start))
    app.add_handler(CommandHandler("start", rodnoy_start))
    app.add_handler(CommandHandler("bonus", rodnoy_start))
    app.add_handler(CommandHandler("menu", rodnoy_start))
    app.add_handler(CommandHandler("SKUID", rodnoy_start))  # /SKUID командасы

    app.add_handler(CommandHandler("tournament_register", handle_tournament_register))
    app.add_handler(CommandHandler("tournament_start", handle_tournament_start))
    app.add_handler(CommandHandler("tournament_status", handle_tournament_status))

    app.add_handler(CommandHandler("giverole", handle_give_role_command))
    app.add_handler(CommandHandler("removerole", handle_remove_role_command))
    app.add_handler(CommandHandler("checkroles", handle_check_roles_command))
    app.add_handler(CommandHandler("addcoins", handle_addcoins_command))
    app.add_handler(CommandHandler("removecoins", handle_removecoins_command))
    app.add_handler(CommandHandler("setlimit", handle_setlimit_command))
    app.add_handler(CommandHandler("limits", handle_limits_command))
    app.add_handler(CommandHandler("resetbalances", handle_resetbalances_command))
    app.add_handler(CommandHandler("reducebalances", handle_reducebalances_command))
    app.add_handler(CommandHandler("activatepremium", handle_activate_premium))

    app.add_handler(CommandHandler("mute", handle_mute_time_command))
    app.add_handler(CommandHandler("unmute", handle_text_unmute))
    app.add_handler(CommandHandler("ban", handle_text_ban))
    app.add_handler(CommandHandler("unban", handle_text_unban))

    app.add_handler(CommandHandler("id", handle_id_command))
    app.add_handler(CommandHandler("setname", handle_setname_command))
    app.add_handler(CommandHandler("ruleka", Games.ruleka))
    app.add_handler(CommandHandler("roulette", Games.ruleka))
    app.add_handler(CommandHandler("banditka", Games.banditka))
    app.add_handler(CommandHandler("bandit", Games.banditka))

    app.add_handler(CallbackQueryHandler(handle_rodnoy_callbacks, pattern="^rodnoy_"))

    async def handle_roulette_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data
        chat_id = query.message.chat_id

        # Рулетканы текшерүү
        if data not in ["repeat_bet", "double_bet"] and chat_id not in chat_manager.roulette_started:
            chat_manager.roulette_started[chat_id] = True
        chat_manager.last_activity[chat_id] = datetime.now().timestamp()

        if data == "spin_roulette":
            if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
                await query.message.reply_text("Рулетка не запущена, наберите Рулетка")
                return
            await Games.spin_roulette_logic(update, context, chat_id)
        elif data.startswith("bet_"):
            if chat_id not in chat_manager.roulette_started or not chat_manager.roulette_started[chat_id]:
                await query.answer("Рулетка не запущена, наберите Рулетка", show_alert=True)
                return

            user_id = query.from_user.id

            if data == "bet_red":
                bet_type, bet_value = "color", "red"
                bet_description = "красное"
            elif data == "bet_black":
                bet_type, bet_value = "color", "black"
                bet_description = "чёрное"
            elif data == "bet_zero":
                bet_type, bet_value = "number", "0"
                bet_description = "зеленое"
            elif data == "bet_1_3":
                bet_type, bet_value = "range", "1_3"
                bet_description = "1-3"
            elif data == "bet_4_6":
                bet_type, bet_value = "range", "4_6"
                bet_description = "4-6"
            elif data == "bet_7_9":
                bet_type, bet_value = "range", "7_9"
                bet_description = "7-9"
            elif data == "bet_10_12":
                bet_type, bet_value = "range", "10_12"
                bet_description = "10-12"
            else:
                return

            user = UserManager.get_user(user_id)
            if not user:
                return

            amount = 1000

            if user[3] >= amount:
                success = await Games.handle_roulette_bet(update, context, bet_type, bet_value, amount)
                if success:
                    if user[15]:
                        username = user[15]
                    elif user[1]:
                        username = user[1]
                    else:
                        username = user[2]
                    await query.message.reply_text(
                        f"Ставка принята: <a href='tg://user?id={user_id}'>{username}</a> {amount} на {bet_description}",
                        parse_mode='HTML'
                    )
                else:
                    await query.message.reply_text("❌ Ошибка при принятии ставки!")
            else:
                keyboard = [[InlineKeyboardButton("Пополнить баланс", url=DONATE_LINK)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text("❌ Недостаточно монет!\n\n", reply_markup=reply_markup)
        elif data == "repeat_bet":
            await repeat_user_bets(update, context)
        elif data == "double_bet":
            await double_user_bets(update, context)

    app.add_handler(CallbackQueryHandler(handle_roulette_callback, pattern="^(spin_roulette|bet_|repeat_bet|double_bet)"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    print("=" * 50)
    print("🤖 **𝗦 ○ U I D G ▲ M [] S Бот запущен!**")
    print("=" * 50)
    print("🎮 Рулетка полностью работает!")
    print(f"🎰 Минимальная ставка рулетки: {MIN_BET} монет")
    print(f"🎴 Минимальная ставка бандита: {MIN_BANDIT_BET} монет")
    print("📊 !лог - 21 результат (последний результат внизу)")
    print("📊 лог - 10 результатов (последний результат внизу)")
    print("🎁 Новая бонус система:")
    print("   • Ежедневный бонус: 10.000 монет")
    print("   • Premium 1: 20.000 монет/день (100 руб)")
    print("   • Premium 2: 50.000 монет/день (200 руб)")
    print("🎮 Mini App:")
    print("   • Краш оюну (самолет)")
    print("   • Дурак оюну")
    print("   • 60 канал бонустары")
    print("   • Баланс синхрондоштуруу")
    print("🏆 Турнирная система добавлена:")
    print("   • Участие: только Premium 2")
    print("   • Призовой фонд: 650.000.000 монет")
    print("   • 10 призовых мест")
    print("🎭 Роли Вор в законе и Полицейский работают!")
    print("⚡ Админ команды работают!")
    print("📋 Новая система ставок работает!")
    print("   • 'ставки' - показывает все ваши ставки")
    print("   • 'повторить' - повторяет последние ставки (20 минут сакталат)")
    print("   • 'удвоить' - удваивает последние ставки")
    print("   • '1000 1' - ставка 1000 на число 1 (көк түстө)")
    print("   • '1000 2' - ставка 1000 на число 2")
    print("   • '1000 0-12' - ставка на диапазон")
    print("   • 'крутить' - кнопкасыз крутить")
    print("🕒 20 мүнөт эч активдүүлүк болбосо, рулетка автоматтык түрдө өчүрүлөт")
    print("=" * 50)
    print("🚀 Бот готов к работе!")
    print("=" * 50)

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
