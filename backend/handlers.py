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


class ClientContext:
    """
    Encapsulates the state of a connected client.
    """

    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.authenticated = False
        self.username = None


def handle_register(context, data):
    reg_username = data.get("username")
    reg_password = data.get("password")
    if not reg_username or not reg_password:
        send_error(context.conn, "Username and password are required for registration.")
        return

    success, message = register_user(reg_username, reg_password)
    if success:
        send_success(context.conn, {"message": message, "action": "register"})
    else:
        send_error(context.conn, message)


def handle_login(context, data):
    login_username = data.get("username")
    login_password = data.get("password")
    if not login_username or not login_password:
        send_error(context.conn, "Username and password are required for login.")
        return

    success = authenticate_user(login_username, login_password)
    if success:
        context.authenticated = True
        context.username = login_username
        send_success(
            context.conn,
            {
                "message": f"Login successful. Welcome, {context.username}!",
                "action": "login",
            },
        )
        print(f"User '{context.username}' authenticated.")

        # Add user to online_users
        with online_users_lock:
            online_users[context.username] = context.conn
            print(f"User '{context.username}' added to online users.")

        # Retrieve and send recent messages
        recent_msgs = get_recent_messages(context.username, limit=50)
        formatted_msgs = [
            {"from": sender, "message": content, "timestamp": timestamp}
            for sender, content, receiver, timestamp in recent_msgs
        ]
        send_recent_messages(context.conn, formatted_msgs)

        # Retrieve and send undelivered messages
        undelivered_msgs = get_undelivered_messages(context.username)
        if undelivered_msgs:
            formatted_undelivered = [
                {"from": sender, "message": content, "timestamp": timestamp}
                for sender, content, timestamp in undelivered_msgs
            ]
            send_recent_messages(context.conn, formatted_undelivered)
            # Mark messages as delivered
            mark_messages_delivered(context.username)

        # Retrieve and send unread messages
        unread_msgs = get_unread_messages(context.username, limit=20)
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
            send_unread_messages(context.conn, formatted_unread)
    else:
        send_error(context.conn, "Invalid username or password.")


def handle_send_message(context, data):
    if not context.authenticated:
        send_error(context.conn, "Authentication required. Please log in first.")
        return

    receiver = data.get("receiver")
    message_text = data.get("message", "")
    if not receiver:
        send_error(context.conn, "Receiver username is required.")
        return
    if not message_text:
        send_error(context.conn, "Empty message cannot be sent.")
        return

    # Insert the message into the database
    insert_message(context.username, message_text, receiver)

    # Check if receiver is online
    with online_users_lock:
        receiver_conn = online_users.get(receiver)

    if receiver_conn:
        # Receiver is online; send the message
        message_payload = {
            "from": context.username,
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
            send_error(context.conn, f"Failed to send message to '{receiver}'.")
            return
    else:
        # Receiver is offline; message remains undelivered
        print(f"User '{receiver}' is offline. Message stored for later delivery.")

    # Echo the message back to the sender as confirmation
    response = {
        "status": "success",
        "from": context.username,
        "message": message_text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "send_message",
    }
    send_success(context.conn, response)


def handle_mark_as_read(context, data):
    if not context.authenticated:
        send_error(context.conn, "Authentication required. Please log in first.")
        return

    message_ids = data.get("message_ids", [])
    if not isinstance(message_ids, list):
        send_error(context.conn, "'message_ids' should be a list.")
        return

    # Validate that message_ids are integers
    if not all(isinstance(msg_id, int) for msg_id in message_ids):
        send_error(context.conn, "All 'message_ids' should be integers.")
        return

    # Mark messages as read in the database
    mark_messages_as_read(message_ids)

    send_success(
        context.conn,
        {"message": "Messages marked as read.", "action": "mark_as_read"},
    )


def handle_delete_account(context, data):
    if not context.authenticated:
        send_error(context.conn, "Authentication required. Please log in first.")
        return

    success = delete_account(context.username)
    if success:
        send_success(context.conn, {"message": "Account deleted successfully."})
        with online_users_lock:
            if online_users.get(context.username) == context.conn:
                del online_users[context.username]
                print(f"User '{context.username}' removed from online users.")
        context.conn.close()
    else:
        send_error(context.conn, "Failed to delete account.")


def handle_unknown_action(context, action):
    send_error(context.conn, f"Unknown action '{action}'.")


# Dispatcher mapping actions to handler functions
ACTION_HANDLERS = {
    "register": handle_register,
    "login": handle_login,
    "send_message": handle_send_message,
    "mark_as_read": handle_mark_as_read,
    "delete_account": handle_delete_account,
}


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

    # Initialize client context
    context = ClientContext(conn, addr)

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

            # Dispatch to the appropriate handler
            handler = ACTION_HANDLERS.get(action, None)
            if handler:
                handler(context, data)
            else:
                handle_unknown_action(context, action)

    except Exception as e:
        print(f"[-] Exception handling client {addr}: {e}")
    finally:
        if context.authenticated and context.username:
            with online_users_lock:
                if online_users.get(context.username) == conn:
                    del online_users[context.username]
                    print(f"User '{context.username}' removed from online users.")
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
