#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from datetime import datetime

DATABASE_NAME = "rdno.db"

def init_database():
    """Базаны түзүү (эгер жок болсо)"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Колдонуучулар таблицасы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 5000,
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

    # Транзакциялар таблицасы
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

    # Турнир катталуу таблицасы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tournament_id INTEGER DEFAULT 1
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

if __name__ == "__main__":
    init_database()
