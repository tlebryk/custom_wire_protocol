# database.py
import sqlite3
import os
from datetime import datetime

DB_FILE = "chat_app.db"

def initialize_database():
    """
    Initializes the database by creating necessary tables if they don't exist.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create users table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Create messages table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (sender) REFERENCES users(username)
        )
    ''')
    
    conn.commit()
    conn.close()

def insert_message(sender, content):
    """
    Inserts a new message into the messages table.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    timestamp = datetime.utcnow().isoformat() + 'Z'  # UTC time in ISO format
    cursor.execute('''
        INSERT INTO messages (sender, content, timestamp)
        VALUES (?, ?, ?)
    ''', (sender, content, timestamp))
    
    conn.commit()
    conn.close()

def get_recent_messages(limit=50):
    """
    Retrieves the most recent messages from the messages table.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT sender, content, timestamp
        FROM messages
        ORDER BY id DESC
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Reverse to have oldest messages first
    return rows[::-1]

# Initialize the database when the module is imported
initialize_database()
