import json
import logging
import threading
from utils import perform_handshake, WebSocketUtil
from users import register_user, authenticate_user, delete_account
from database import (
    insert_message,
    get_recent_messages,
    get_undelivered_messages,
    mark_messages_delivered,
    get_unread_messages,
    mark_messages_as_read,
    get_user_info,
    set_n_unread_messages,
    delete_message,
    get_all_users_except
)
from datetime import datetime
from pathlib import Path
import traceback
import custom_protocol

# Global dictionary to track online users
# Key: username, Value: connection object
online_users = {}
# Lock for thread-safe operations on online_users
online_users_lock = threading.Lock()

# TODO get rid of global state
websocket = WebSocketUtil()


class ClientContext:
    """
    Encapsulates the state of a connected client.
    """

    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.authenticated = False
        self.username = None


def handle_client_connection(conn, addr):
    """
    Handles a new client connection:
      1. Performs the WebSocket handshake.
      2. Manages user registration and login workflows.
      3. Processes other actions (like send_message) only if authenticated.
    """
    logging.info(f"[+] Client connected: {addr}")
    if not perform_handshake(conn):
        conn.close()
        return  # Handshake failed, close connection

    # Initialize client context
    context = ClientContext(conn, addr)
    try:
        while True:
            data = websocket.read_ws_frame(conn)
            if data is None:
                break  # Connection closed or error

            logging.info(f"Received message from {addr}: {data}")

            # Check if 'action' is present
            action = data.get("action")
            if not action:
                send_error(conn, "Missing 'action' in JSON message.")
                continue

            # Dispatch to the appropriate handler
            handler = ACTION_HANDLERS.get(action, None)
            if handler:
                logging.info(f"Received action: {action}")
                handler(context, data)
            else:
                logging.warning(f"Unknown action: {action}")
                handle_unknown_action(context, action)

    except Exception as e:
        logging.error(f"Exception handling client {addr}: {e}", exc_info=True)
    finally:
        if context.authenticated and context.username:
            with online_users_lock:
                if online_users.get(context.username) == conn:
                    del online_users[context.username]
                    logging.info(
                        f"User '{context.username}' removed from online users."
                    )
        conn.close()
        logging.info(f"[-] Connection closed for {addr}")


def send_success(conn, payload_dict=None):
    """
    Helper to send a JSON response with status=success.
    """
    # TODO: make this less flexible
    if payload_dict is None:
        payload_dict = {}
    payload_dict["status"] = "success"
    # payload_dict["action"] = "success"
    websocket.send_ws_frame(conn, payload_dict)


def send_error(conn, message):
    """
    Helper to send a JSON response with status=error.
    """
    payload_dict = {"status": "error", "message": message, "action": "error"}
    websocket.send_ws_frame(conn, payload_dict)


def send_recent_messages(conn, messages):
    """
    Sends recent messages to the client after successful login.
    """
    logging.warning(f"Sending recent messages: {messages}")
    payload = {"action": "recent_messages", "messages": messages}
    send_success(conn, payload)


def send_unread_messages(conn, messages):
    """
    Sends unread messages to the client after successful login.
    """
    logging.warning(f"Sending unread messages: {messages}")

    payload = {"action": "unread_messages", "messages": messages}
    send_success(conn, payload)


# TODO: add codes to all responses


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


def handle_set_n_unread_messages(context, data):
    n_unread_messages = data.get("n_unread_messages")
    username = context.username

    if not n_unread_messages:
        send_error(context.conn, "Number of unread messages is required.")
        return

    success = set_n_unread_messages(username, n_unread_messages)
    if success:
        send_success(
            context.conn,
            {
                "message": "Number of unread messages set successfully.",
                "action": "confirm_set_n_unread_messages",
            },
        )
    else:
        send_error(context.conn, "Failed to set number of unread messages.")


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
                "action": "confirm_login",
                "username": context.username,
            },
        )
        logging.warning(f"User '{context.username}' authenticated.")

        # Add user to online_users
        with online_users_lock:
            online_users[context.username] = context.conn
            logging.warning(f"User '{context.username}' added to online users.")

        # Retrieve and send undelivered messages
        # undelivered_msgs = get_undelivered_messages(context.username)
        # logging.warning(
        #     f"Undelivered messages for '{context.username}': {undelivered_msgs}"
        # )

        # if undelivered_msgs:
        #     formatted_undelivered = [
        #         {"from": sender, "message": content, "timestamp": timestamp}
        #         for sender, content, timestamp, id in undelivered_msgs
        #     ]
        #     send_recent_messages(context.conn, formatted_undelivered)
        #     # Mark messages as delivered
        #     mark_messages_delivered(context.username)

        # # Retrieve and send unread messages
        # unread_msgs = get_unread_messages(context.username, limit=20)
        # logging.warning(f"unread messages for '{context.username}': {unread_msgs}")
        # if unread_msgs:
        #     formatted_unread = [
        #         {
        #             "id": msg_id,
        #             "from": sender,
        #             "message": content,
        #             "timestamp": timestamp,
        #         }
        #         for msg_id, sender, content, timestamp in unread_msgs
        #     ]
        #     send_unread_messages(context.conn, formatted_unread)
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
    id = insert_message(context.username, message_text, receiver)
    logging.info(f"Message inserted with ID: {id}")
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
            "action": "received_message",
            "id": id,
            "username": context.username,
        }
        try:
            send_success(receiver_conn, message_payload)
            logging.info(f"Message sent to '{receiver}'.")
            # Optionally, mark the message as delivered immediately
            # For simplicity, assuming messages are marked as delivered on login
        except Exception as e:
            logging.info(f"Failed to send message to '{receiver}': {e}")
            send_error(context.conn, f"Failed to send message to '{receiver}'.")
            return
    else:
        # Receiver is offline; message remains undelivered
        logging.info(
            f"User '{receiver}' is offline. Message stored for later delivery."
        )

    # Echo the message back to the sender as confirmation
    response = {
        "status": "success",
        "from": context.username,
        "message": message_text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "confirm_send_message",
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
        {"message": "Messages marked as read.", "action": "confirm_mark_as_read"},
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
                logging.info(f"User '{context.username}' removed from online users.")
        context.conn.close()
    else:
        send_error(context.conn, "Failed to delete account.")


def handle_unknown_action(context, action):
    send_error(context.conn, f"Unknown action '{action}'.")


# handlers.py (Add the echo handler)
def handle_echo(context, data):
    message = data.get("message", "")
    response = {"status": "success", "message": message}
    send_success(context.conn, response)


# Dispatcher mapping actions to handler functions


def handle_recent_messages(context, data):
    if not context.authenticated:
        send_error(context.conn, "Authentication required. Please log in first.")
        return

    # Retrieve and send recent messages

    # get number of messages the user wants to display
    user_info = get_user_info(context.username)
    n_message_index = 1
    if user_info:
        n_unread_messages = user_info[n_message_index]
        if not n_unread_messages:
            n_unread_messages = 50

    else:
        logging.info(f"User '{context.username}' not found in database.")
        n_unread_messages = 50

    # Retrieve and send recent messages
    recent_msgs = get_recent_messages(context.username, limit=n_unread_messages)
    logging.info(f"Recent messages for '{context.username}': {recent_msgs}")
    formatted_msgs = [
        {"from": sender, "message": content, "timestamp": timestamp, "id": id}
        for sender, content, receiver, timestamp, id in recent_msgs
    ]
    send_recent_messages(context.conn, formatted_msgs)


def handle_unread_messages(context, data):
    if not context.authenticated:
        send_error(context.conn, "Authentication required. Please log in first.")
        return
    # TODO: set the limit based on user information
    # Retrieve and send unread messages
    user_info = get_user_info(context.username)
    n_message_index = 1
    if user_info:
        n_unread_messages = user_info[n_message_index]
        if not n_unread_messages:
            n_unread_messages = 50

    else:
        logging.info(f"User '{context.username}' not found in database.")
        n_unread_messages = 50
    unread_msgs = get_unread_messages(context.username, limit=n_unread_messages)
    logging.info(f"Undelivered messages for '{context.username}': {unread_msgs}")
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

def handle_delete_message(context, data):
    if not context.authenticated:
        send_error(context.conn, "Authentication required. Please log in first.")
        return

    message_id = data.get("id")
    if not isinstance(message_id, int):
        send_error(context.conn, "Invalid message ID format.")
        return

    success = delete_message(message_id)
    if success:
        send_success(context.conn, {"message": "Message deleted successfully.", "action": "delete_message_success", "id": message_id})
    else:
        send_error(context.conn, "Failed to delete message.")

def handle_get_users(context, data):
    if not context.authenticated:
        send_error(context.conn, "Authentication required. Please log in first.")
        return

    users = get_all_users_except(context.username)
    send_success(context.conn, {"action": "user_list", "users": users})



# # Retrieve and send undelivered messages
# undelivered_msgs = get_undelivered_messages(context.username)
# logging.info(
#     f"Undelivered messages for '{context.username}': {undelivered_msgs}"
# )

# if undelivered_msgs:
#     formatted_undelivered = [
#         {"from": sender, "message": content, "timestamp": timestamp}
#         for sender, content, timestamp, id in undelivered_msgs
#     ]
#     send_recent_messages(context.conn, formatted_undelivered)
#     # Mark messages as delivered
#     mark_messages_delivered(context.username)

# # Retrieve and send unread messages
# unread_msgs = get_unread_messages(context.username, limit=20)
# logging.info(f"Undelivered messages for '{context.username}': {unread_msgs}")
# if unread_msgs:
#     formatted_unread = [
#         {
#             "id": msg_id,
#             "from": sender,
#             "message": content,
#             "timestamp": timestamp,
#         }
#         for msg_id, sender, content, timestamp in unread_msgs
#     ]
#     send_unread_messages(context.conn, formatted_unread)
ACTION_HANDLERS = {
    "register": handle_register,
    "login": handle_login,
    "send_message": handle_send_message,
    "mark_as_read": handle_mark_as_read,
    "delete_account": handle_delete_account,
    "set_n_unread_messages": handle_set_n_unread_messages,
    # "get_user_info": handle_get_user_info,
    "echo": handle_echo,
    "get_unread_messages": handle_unread_messages,
    "get_recent_messages": handle_recent_messages,
    "delete_message": handle_delete_message,
    "get_users": handle_get_users,
}
