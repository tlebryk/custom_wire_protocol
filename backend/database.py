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
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    """
    )

    # Create messages table if it doesn't exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            read_status INTEGER NOT NULL DEFAULT 0,
            delivered INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (sender) REFERENCES users(username),
            FOREIGN KEY (receiver) REFERENCES users(username)
        )
    """
    )

    conn.commit()
    conn.close()


def insert_message(sender, content, receiver):
    """
    Inserts a new message into the messages table.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    timestamp = datetime.utcnow().isoformat() + "Z"  # UTC time in ISO format
    cursor.execute(
        """
        INSERT INTO messages (sender, content, receiver, timestamp, read_status, delivered)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (sender, content, receiver, timestamp, 0, 0),
    )

    conn.commit()
    conn.close()


def get_recent_messages(user_id, limit=50):
    """
    Retrieves the most recent messages from the messages table.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT sender, content, receiver, timestamp
        FROM messages
        WHERE (receiver = ? OR sender = ?)
        ORDER BY id DESC
        LIMIT ?
    """,
        (
            user_id,
            user_id,
            limit,
        ),
    )

    rows = cursor.fetchall()
    conn.close()

    # Reverse to have oldest messages first
    return rows[::-1]


def get_undelivered_messages(user_id):
    """
    Retrieves all undelivered messages for a user.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT sender, content, timestamp
        FROM messages
        WHERE receiver = ? AND delivered = 0
        ORDER BY id ASC
    """,
        (user_id,),
    )

    messages = cursor.fetchall()
    conn.close()

    return messages


def mark_messages_delivered(user_id):
    """
    Marks all undelivered messages for a user as delivered.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE messages
        SET delivered = 1
        WHERE receiver = ? AND delivered = 0
    """,
        (user_id,),
    )

    conn.commit()
    conn.close()


def get_unread_messages(user_id, limit=20):
    """
    Retrieves the first 'limit' unread messages for a user.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, sender, content, timestamp
        FROM messages
        WHERE receiver = ? AND read_status = 0
        ORDER BY id ASC
        LIMIT ?
    """,
        (user_id, limit),
    )

    messages = cursor.fetchall()
    conn.close()

    return messages


def mark_messages_as_read(message_ids):
    """
    Marks specified messages as read.
    """
    if not message_ids:
        return  # No messages to mark

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Use parameter substitution to prevent SQL injection
    placeholders = ",".join(["?"] * len(message_ids))
    query = f"UPDATE messages SET read_status = 1 WHERE id IN ({placeholders})"
    cursor.execute(query, message_ids)

    conn.commit()
    conn.close()


# Initialize the database when the module is imported
initialize_database()
