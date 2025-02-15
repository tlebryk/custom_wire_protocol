# users.py
import sqlite3
import hashlib
from database import initialize_database

DB_FILE = "chat_app.db"


def hash_password(password: str) -> str:
    """
    Hash the given password using SHA-256.

    Args:
        password (str): The password to hash.

    Returns:
        str: The SHA-256 hash of the password.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_user(username: str, password: str) -> tuple[bool, str]:
    """
    Register a new user.

    Args:
        username (str): The username of the new user.
        password (str): The password of the new user.

    Returns:
        tuple[bool, str]: A tuple containing success (bool) and message (str).
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Check if the username already exists
        cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            # If it does, return False with an appropriate message
            return False, "Username already exists."

        # Hash the password
        hashed_pw = hash_password(password)

        # Insert new user into the database
        cursor.execute(
            """
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
        """,
            (username, hashed_pw),
        )

        # Commit the changes
        conn.commit()
        # Return True with a success message
        return True, "Registration successful. You can now log in."
    except Exception as e:
        # If an error occurs, print the error and return False with an appropriate message
        print(f"[-] Error registering user: {e}")
        return False, "Registration failed due to server error."
    finally:
        # Close the database connection
        conn.close()


def authenticate_user(username: str, password: str) -> bool:
    """
    Authenticate a user.

    Args:
        username (str): The username to authenticate.
        password (str): The password to authenticate with.

    Returns:
        bool: True if the credentials are valid, False otherwise.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        )
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


def delete_account(username: str) -> bool:
    """
    Deletes a user and their messages from the database.

    Args:
        username (str): The username to delete.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Delete the user's messages first (to maintain foreign key constraints)
        cursor.execute("DELETE FROM messages WHERE sender = ?", (username,))

        # Delete the user account
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))

        conn.commit()
        return True
    except Exception as e:
        print(f"[-] Error deleting user {username}: {e}")
        return False
    finally:
        conn.close()
