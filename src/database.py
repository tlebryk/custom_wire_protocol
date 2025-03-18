# database.py
import sqlite3
import os
from datetime import datetime
import logging
from typing import List, Tuple, Optional


class Database:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.initialize_database()

    def _connect(self):
        return sqlite3.connect(self.db_file)

    def initialize_database(self):
        """
        Initializes the database by creating necessary tables if they don't exist.
        """
        conn = self._connect()
        cursor = conn.cursor()
        # Create users table if it doesn't exist.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                n_unread_messages INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Create messages table if it doesn't exist.
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

    # @write_operation
    def insert_message(self, sender: str, content: str, receiver: str) -> int:
        """
        Inserts a new message into the messages table.

        Args:
            sender (str): The username of the user sending the message.
            content (str): The content of the message.
            receiver (str): The username of the user receiving the message.

        Returns:
            int: The ID of the newly inserted message.
        """
        conn = self._connect()
        cursor = conn.cursor()
        timestamp = datetime.utcnow().isoformat() + "Z"  # UTC time in ISO format
        cursor.execute(
            """
            INSERT INTO messages (sender, content, receiver, timestamp, read_status, delivered)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sender, content, receiver, timestamp, 0, 0),
        )
        cursor.execute("SELECT last_insert_rowid()")
        message_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return message_id

    def get_recent_messages(
        self, user_id: str, limit: int = 50
    ) -> List[Tuple[str, str, str, str, int]]:
        """
        Retrieves the most recent messages from the messages table.

        Args:
            user_id (str): The user ID of the user whose messages to retrieve.
            limit (int): The maximum number of messages to retrieve. Defaults to 50.

        Returns:
            List[Tuple[str, str, str, str, int]]: A list of tuples, each containing the sender, content, receiver, timestamp, and id of a message, sorted from oldest to newest.
        """
        conn = self._connect()
        cursor = conn.cursor()
        query = """
            SELECT sender, content, receiver, timestamp, id
            FROM messages
            WHERE (receiver = ? OR sender = ?)
            AND read_status = 1
            ORDER BY id DESC
            LIMIT ?
        """
        logging.info(f"recent messages query: {query}")
        logging.info(f"recent messages user_id: {user_id}")
        logging.info(f"recent messages limit: {limit}")
        cursor.execute(query, (user_id, user_id, limit))
        rows = cursor.fetchall()
        logging.info(f"recent messages rows: {rows}")
        conn.close()
        return rows[::-1]

    def get_undelivered_messages(self, user_id: str) -> List[Tuple[str, str, str, int]]:
        """
        Retrieves all undelivered messages for a user.

        Args:
            user_id (str): The user ID of the user whose undelivered messages to retrieve.

        Returns:
            List[Tuple[str, str, str, int]]: A list of tuples, each containing the sender, content, timestamp, and id of an undelivered message, sorted from oldest to newest.
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sender, content, timestamp, id
            FROM messages
            WHERE receiver = ? AND delivered = 0
            ORDER BY id ASC
            """,
            (user_id,),
        )
        messages = cursor.fetchall()
        conn.close()
        return messages

    # @write_operation
    def mark_messages_delivered(self, user_id: str) -> None:
        """
        Marks all undelivered messages for a user as delivered.

        Args:
            user_id (str): The user ID of the user whose undelivered messages to mark as delivered.

        Returns:
            None
        """
        conn = self._connect()
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

    def get_unread_messages(
        self, user_id: str, limit: int = 20
    ) -> List[Tuple[int, str, str, str]]:
        """
        Retrieves the first 'limit' unread messages for a user.

        Args:
            user_id (str): The user ID of the user whose unread messages to retrieve.
            limit (int): The maximum number of messages to retrieve. Defaults to 20.

        Returns:
            List[Tuple[int, str, str, str]]: A list of tuples, each containing the ID, sender, content, and timestamp of an unread message, sorted from oldest to newest.
        """
        conn = self._connect()
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

    # @write_operation
    def mark_messages_as_read(self, message_ids: List[int]) -> None:
        """
        Marks specified messages as read.

        Args:
            message_ids (List[int]): A list of message IDs to mark as read.

        Returns:
            None
        """
        if not message_ids:
            return
        conn = self._connect()
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(message_ids))
        query = f"UPDATE messages SET read_status = 1 WHERE id IN ({placeholders})"
        logging.info(f"mark_messages_as_read query: {query}")
        logging.info(f"mark_messages_as_read message_ids: {message_ids}")
        cursor.execute(query, message_ids)
        conn.commit()
        conn.close()

    def get_user_info(self, username: str) -> Optional[Tuple[str, int]]:
        """
        Retrieves user information, specifically the username and the number of unread messages.

        Args:
            username (str): The username to retrieve information for.

        Returns:
            Optional[Tuple[str, int]]: A tuple of the username and the number of unread messages, or None if the user does not exist.
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username, n_unread_messages FROM users WHERE username = ?",
            (username,),
        )
        user_info = cursor.fetchone()
        conn.close()
        return user_info

    # @write_operation
    def set_n_unread_messages(self, username: str, n_unread_messages: int) -> bool:
        """
        Updates the number of unread messages for a user.

        Args:
            username (str): The username to update.
            n_unread_messages (int): The new number of unread messages for the user.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        conn = self._connect()
        cursor = conn.cursor()
        logging.info(
            "set_n_unread_messages query: %s for user: %s", n_unread_messages, username
        )
        cursor.execute(
            "UPDATE users SET n_unread_messages = ? WHERE username = ?",
            (n_unread_messages, username),
        )
        conn.commit()
        conn.close()
        return True

    # @write_operation
    def delete_message(self, message_id: int) -> bool:
        """
        Deletes a message from the database.

        Args:
            message_id (int): The ID of the message to delete.

        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Error deleting message {message_id}: {e}")
            return False
        finally:
            conn.close()

    def get_all_users_except(self, username: str) -> List[str]:
        """
        Retrieves all usernames except the given username.

        Args:
            username (str): The username to exclude.

        Returns:
            List[str]: A list of all usernames except the given username.
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE username != ?", (username,))
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users

    def search_users_in_db(self, query: str) -> List[str]:
        """
        Searches for users whose usernames start with the given query string.

        Args:
            query (str): The prefix string to search for.

        Returns:
            List[str]: A list of matching usernames.
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username FROM users WHERE username LIKE ?", (query + "%",)
        )
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users
