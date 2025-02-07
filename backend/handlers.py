import json
from utils import read_ws_frame, send_ws_frame, perform_handshake
from users import register_user, authenticate_user
from database import insert_message, get_recent_messages
from datetime import datetime 

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
                    send_error(conn, "Username and password are required for registration.")
                    continue

                success, message = register_user(reg_username, reg_password)
                if success:
                    send_success(conn, {"message": message})
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
                    send_success(conn, {"message": f"Login successful. Welcome, {username}!"})
                    
                    # Retrieve recent messages and send to the user
                    recent_msgs = get_recent_messages(limit=50)
                    formatted_msgs = [
                        {
                            "from": sender,
                            "message": content,
                            "timestamp": timestamp
                        }
                        for sender, content, timestamp in recent_msgs
                    ]
                    send_recent_messages(conn, formatted_msgs)
                else:
                    send_error(conn, "Invalid username or password.")

            elif action == "send_message":
                # Only allow if authenticated
                if not authenticated:
                    send_error(conn, "Authentication required. Please log in first.")
                    continue

                message_text = data.get("message", "")
                if not message_text:
                    send_error(conn, "Empty message cannot be sent.")
                    continue

                # Insert the message into the database
                insert_message(username, message_text)

                # For demonstration, we'll echo the message back
                response = {
                    "status": "success",
                    "from": username,
                    "message": message_text,
                    "timestamp": datetime.utcnow().isoformat() + 'Z'
                }
                send_ws_frame(conn, response)

            else:
                # Unrecognized action
                send_error(conn, f"Unknown action '{action}'.")

    except Exception as e:
        print(f"[-] Exception handling client {addr}: {e}")
    finally:
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
    payload = {
        "action": "recent_messages",
        "messages": messages
    }
    send_ws_frame(conn, payload)
