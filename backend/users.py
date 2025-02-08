# users.py
import sqlite3
import hashlib
from database import initialize_database

DB_FILE = "chat_app.db"

def hash_password(password):
    """
    Hash the password using SHA-256.
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def register_user(username, password):
    """
    Register a new user.
    Returns a tuple (success: bool, message: str).
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if username already exists
        cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            return False, "Username already exists."
        
        # Insert new user
        hashed_pw = hash_password(password)
        cursor.execute('''
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
        ''', (username, hashed_pw))
        
        conn.commit()
        return True, "Registration successful. You can now log in."
    except Exception as e:
        print(f"[-] Error registering user: {e}")
        return False, "Registration failed due to server error."
    finally:
        conn.close()

def authenticate_user(username, password):
    """
    Authenticate a user.
    Returns True if credentials are valid, False otherwise.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        if not row:
            return False
        
        stored_hash = row[0]
        return stored_hash == hash_password(password)
    except Exception as e:
        print(f"[-] Error authenticating user: {e}")
        return False
    finally:
        conn.close()  


def delete_account(username, password):
    """
    Deletes a user and their messages from the database.
    Returns True if successful, False otherwise.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Delete the user's messages first (to maintain foreign key constraints)
        cursor.execute('DELETE FROM messages WHERE sender = ?', (username,))
        
        # Delete the user account
        cursor.execute('DELETE FROM users WHERE username = ?', (username,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"[-] Error deleting user {username}: {e}")
        return False
    finally:
        conn.close()
