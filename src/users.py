import sqlite3
import hashlib
import os
import logging


class UserManager:
    def __init__(self, db_file: str = None):
        """
        Initializes the UserManager with the given database file.

        Args:
            db_file (str, optional): Path to the SQLite database file.
                                     Defaults to "chat_app.db".
        """
        self.db_file = db_file or os.environ.get("DB_FILE", "chat_app.db")
        self.logger = logging.getLogger(__name__)

    def _hash_password(self, password: str) -> str:
        """
        Hash the given password using SHA-256.

        Args:
            password (str): The password to hash.

        Returns:
            str: The SHA-256 hash of the password.
        """
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def register_user(self, username: str, password: str) -> tuple[bool, str]:
        """
        Register a new user.

        Args:
            username (str): The username of the new user.
            password (str): The password of the new user.

        Returns:
            tuple[bool, str]: A tuple containing success (bool) and message (str).
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # Check if the username already exists
            cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return False, "Username already exists."

            # Hash the password and insert new user
            hashed_pw = self._hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hashed_pw),
            )

            conn.commit()
            return True, "Registration successful. You can now log in."
        except Exception as e:
            self.logger.error(f"Error registering user: {e}")
            return False, "Registration failed due to server error."
        finally:
            if "conn" in locals() and conn:
                conn.close()

    def authenticate_user(self, username: str, password: str) -> bool:
        """
        Authenticate a user.

        Args:
            username (str): The username to authenticate.
            password (str): The password to authenticate with.

        Returns:
            bool: True if the credentials are valid, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT password_hash FROM users WHERE username = ?", (username,)
            )
            row = cursor.fetchone()
            if not row:
                return False

            stored_hash = row[0]
            return stored_hash == self._hash_password(password)
        except Exception as e:
            self.logger.error(f"Error authenticating user: {e}")
            return False
        finally:
            if "conn" in locals() and conn:
                conn.close()

    def delete_account(self, username: str) -> bool:
        """
        Deletes a user and their messages from the database.

        Args:
            username (str): The username to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # Delete user's messages first to maintain foreign key constraints
            cursor.execute("DELETE FROM messages WHERE sender = ?", (username,))
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))

            conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error deleting user {username}: {e}")
            return False
        finally:
            if "conn" in locals() and conn:
                conn.close()
