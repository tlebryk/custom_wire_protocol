import json
import logging
import threading
from utils import read_ws_frame, send_ws_frame, perform_handshake
from users import register_user, authenticate_user, delete_account
from database import (
    insert_message,
    get_recent_messages,
    get_undelivered_messages,
    mark_messages_delivered,
    get_unread_messages,
    mark_messages_as_read,
)
from datetime import datetime

# Global dictionary to track online users
# Key: username, Value: connection object
online_users = {}
# Lock for thread-safe operations on online_users
online_users_lock = threading.Lock()


def handle_client_connection(conn, addr):
    """
    Handles a new client connection:
      1. Performs the WebSocket handshake.
      2. Manages user registration and login workflows.
      3. Processes other actions (like send_message) only if authenticated.
    """
    print(f"[+] Client connected: {addr}")
    if not perform_handshake(conn):
        conn.close()
        return  # Handshake failed, close connection

    # Track authentication state for this connection
    authenticated = False
    username = None

    try:
        while True:
            raw_msg = read_ws_frame(conn)
            if raw_msg is None:
                break  # Connection closed or error

            print(f"Received message from {addr}: {raw_msg}")

            # Attempt to parse as JSON
            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                send_error(conn, "Invalid JSON format.")
                continue

            # Check if 'action' is present
            action = data.get("action")
            if not action:
                send_error(conn, "Missing 'action' in JSON message.")
                continue

            # Handle actions
            if action == "register":
                # Handle user registration
                reg_username = data.get("username")
                reg_password = data.get("password")
                if not reg_username or not reg_password:
                    send_error(
                        conn, "Username and password are required for registration."
                    )
                    continue

                success, message = register_user(reg_username, reg_password)
                if success:
                    send_success(conn, {"message": message, action: "register"})
                else:
                    send_error(conn, message)

            elif action == "login":
                # Handle user login
                login_username = data.get("username")
                login_password = data.get("password")
                if not login_username or not login_password:
                    send_error(conn, "Username and password are required for login.")
                    continue

                success = authenticate_user(login_username, login_password)
                if success:
                    authenticated = True
                    username = login_username
                    send_success(
                        conn,
                        {
                            "message": f"Login successful. Welcome, {username}!",
                            "action": "login",
                        },
                    )
                    print(f"User '{username}' authenticated.")

                    # Add user to online_users
                    with online_users_lock:
                        online_users[username] = conn
                        print(f"User '{username}' added to online users.")

                    # Retrieve and send recent messages
                    recent_msgs = get_recent_messages(username, limit=50)
                    formatted_msgs = [
                        {"from": sender, "message": content, "timestamp": timestamp}
                        for sender, content, receiver, timestamp in recent_msgs
                    ]
                    send_recent_messages(conn, formatted_msgs)

                    # Retrieve and send undelivered messages
                    undelivered_msgs = get_undelivered_messages(username)
                    if undelivered_msgs:
                        formatted_undelivered = [
                            {"from": sender, "message": content, "timestamp": timestamp}
                            for sender, content, timestamp in undelivered_msgs
                        ]
                        send_recent_messages(conn, formatted_undelivered)
                        # Mark messages as delivered
                        mark_messages_delivered(username)

                    # Retrieve and send unread messages
                    unread_msgs = get_unread_messages(username, limit=20)
                    if unread_msgs:
                        formatted_unread = [
                            {
                                "id": msg_id,
                                "from": sender,
                                "message": content,
                                "timestamp": timestamp,
                            }
                            for msg_id, sender, content, timestamp in unread_msgs
                        ]
                        send_unread_messages(conn, formatted_unread)
                else:
                    send_error(conn, "Invalid username or password.")

            elif action == "send_message":
                # Only allow if authenticated
                if not authenticated:
                    send_error(conn, "Authentication required. Please log in first.")
                    continue
                receiver = data.get("receiver")
                message_text = data.get("message", "")
                if not receiver:
                    send_error(conn, "Receiver username is required.")
                    continue
                if not message_text:
                    send_error(conn, "Empty message cannot be sent.")
                    continue

                # Insert the message into the database
                insert_message(username, message_text, receiver)

                # Check if receiver is online
                with online_users_lock:
                    receiver_conn = online_users.get(receiver)

                if receiver_conn:
                    # Receiver is online; send the message
                    message_payload = {
                        "from": username,
                        "message": message_text,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "read": False,  # Initial read status
                        "action": "send_message",
                    }
                    try:
                        send_ws_frame(receiver_conn, message_payload)
                        print(f"Message sent to '{receiver}'.")
                        # Optionally, mark the message as delivered immediately
                        # For simplicity, assuming messages are marked as delivered on login
                    except Exception as e:
                        print(f"Failed to send message to '{receiver}': {e}")
                        send_error(conn, f"Failed to send message to '{receiver}'.")
                        continue
                else:
                    # Receiver is offline; message remains undelivered
                    print(
                        f"User '{receiver}' is offline. Message stored for later delivery."
                    )

                # Echo the message back to the sender as confirmation
                response = {
                    "status": "success",
                    "from": username,
                    "message": message_text,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "action": "send_message",
                }
                send_success(conn, response)

            elif action == "mark_as_read":
                # Only allow if authenticated
                if not authenticated:
                    send_error(conn, "Authentication required. Please log in first.")
                    continue

                message_ids = data.get("message_ids", [])
                if not isinstance(message_ids, list):
                    send_error(conn, "'message_ids' should be a list.")
                    continue

                # Validate that message_ids are integers
                if not all(isinstance(msg_id, int) for msg_id in message_ids):
                    send_error(conn, "All 'message_ids' should be integers.")
                    continue

                # Mark messages as read in the database
                mark_messages_as_read(message_ids)

                send_success(
                    conn,
                    {"message": "Messages marked as read.", "action": "mark_as_read"},
                )
            elif action == "delete_account":
                success = delete_account(username)
                if success:
                    send_success(conn, {"message": "Account deleted successfully."})
                    conn.close()
                    return  # Disconnect the user after deletion
                else:
                    send_error(conn, "Failed to delete account.")

            else:
                # Unrecognized action
                send_error(conn, f"Unknown action '{action}'.")

    except Exception as e:
        print(f"[-] Exception handling client {addr}: {e}")
    finally:
        if authenticated and username:
            with online_users_lock:
                if online_users.get(username) == conn:
                    del online_users[username]
                    print(f"User '{username}' removed from online users.")
        conn.close()
        print(f"[-] Connection closed for {addr}")


def send_success(conn, payload_dict=None):
    """
    Helper to send a JSON response with status=success.
    """
    if payload_dict is None:
        payload_dict = {}
    payload_dict["status"] = "success"
    send_ws_frame(conn, payload_dict)


def send_error(conn, message):
    """
    Helper to send a JSON response with status=error.
    """
    payload_dict = {"status": "error", "message": message}
    send_ws_frame(conn, payload_dict)


def send_recent_messages(conn, messages):
    """
    Sends recent messages to the client after successful login.
    """
    payload = {"action": "recent_messages", "messages": messages}
    send_ws_frame(conn, payload)


def send_unread_messages(conn, messages):
    """
    Sends unread messages to the client after successful login.
    """
    payload = {"action": "unread_messages", "messages": messages}
    send_ws_frame(conn, payload)
