# print python version
import sys

print(f"Python version: {sys.version}")

import tkinter as tk
from tkinter import messagebox
import json
import threading

from client import WebSocketClient  # Import the WebSocketClient class
import logging, logging.config
from pathlib import Path
import datetime
import custom_protocol
import os
from typing import Dict, Any, Optional, Union, List, Callable, Literal


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    level=logging.INFO,
)


class ChatApp(tk.Tk):
    def __init__(self, mode: str = None):
        super().__init__()

        self.title("WebSocket Chat - Registration and Login")
        self.geometry("800x800")
        self.resizable(False, False)

        # Initialize WebSocket client
        self.ws_client = WebSocketClient()
        self.ws_client.connect()

        # Create Authentication Box
        self.auth_box = AuthBox(self)
        self.auth_box.pack(pady=20)

        # Initialize Chat Screen Components (Initially hidden)
        self.n_new_messages = NNewMessages(self)
        self.chat_box = ChatBox(self)
        self.messages_container = MessagesContainer(self)
        self.delete_account_container = DeleteAccountContainer(self)
        if not mode:
            mode = os.environ.get("MODE", "json")
            self.mode = mode
            print(f"Mode: {mode}")
        if self.mode == "json":
            self.encoder = None
            self.decoder = None
        else:
            self.encoder = custom_protocol.Encoder(custom_protocol.load_protocols())
            self.decoder = custom_protocol.Decoder(custom_protocol.load_protocols())
        self.listening_thread = threading.Thread(
            target=self.listen_for_messages, daemon=True
        )
        logging.info("Starting listening thread...")
        self.listening_thread.start()

    def listen_for_messages(self):
        """
        Continuously read messages from the server in a loop.
        This runs in a separate thread so the UI remains responsive.
        """
        while True:
            try:
                message = self.ws_client.receive()
                if message is None:
                    # If receive returns None, it usually means a closed connection or error.
                    logging.info("Server closed the connection or returned None.")
                    break

                # We must not update tkinter widgets directly in a thread.
                # Instead, we schedule it on the main thread with `self.after(...)`.
                self.after(0, lambda msg=message: self.handle_incoming_message(msg))

            except Exception as e:
                logging.error(f"Error in listening thread: {e}")
                break

    def send_message_via_ws(self, message_dict: dict) -> None:
        """
        Sends a message via the WebSocket client.

        Args:
            message_dict (dict): The message to send.
        """
        if self.ws_client and self.ws_client.connected:
            self.ws_client.send(message_dict)
        else:
            messagebox.showwarning("Connection Error", "WebSocket is not connected.")

    def handle_incoming_message(self, message: dict) -> None:
        """
        Handles incoming messages from the WebSocket server.

        Args:
            message (dict): The incoming message from the WebSocket server.
        """
        try:
            data = message
            status = data.get("status")
            action = data.get("action")
            logging.warning(f"Received data: {data}")
            if status == "success":
                if action == "register":
                    messagebox.showinfo(
                        "Registration Successful",
                        data.get("message", "You have registered successfully."),
                    )
                elif action == "confirm_login":
                    messagebox.showinfo(
                        "Login Successful",
                        data.get("message", "You have logged in successfully."),
                    )
                    self.n_new_messages.username = data.get("username")
                    self.chat_box.username = data.get("username")
                    self.messages_container.username = data.get("username")
                    self.delete_account_container.username = data.get("username")
                    logging.info(f"User '{data.get('username')}' logged in.")
                    # call to get unread mesasges
                    self.get_unread_messages()
                    self.get_recent_messages()
                    self.chat_box.fetch_users()  # Fetch users after login
                    # mesage_dict
                    self.switch_to_chat_screen()
                    logging.info(f"User '{data.get('username')}' logged in.")
                elif action == "sent_message":
                    # Confirmation of sent message (Optional)
                    pass
                elif action == "received_message":
                    # Ensure id is present
                    if "id" in data:
                        incoming_message = {
                            "id": data["id"],
                            "from": data.get("from"),
                            "timestamp": data.get("timestamp"),
                            "message": data.get("message"),
                            "username": data.get("username"),
                        }
                        self.messages_container.add_unread_message(incoming_message)
                    else:
                        logging.error("Received message without 'id'.")
                elif action == "recent_messages":
                    recent_msgs = data.get("messages", [])
                    for msg in recent_msgs:
                        logging.info("Received recent message:", msg)
                        self.messages_container.add_recent_message(msg)
                elif action == "unread_messages":
                    unread_msgs = data.get("messages", [])
                    for msg in unread_msgs:
                        self.messages_container.add_unread_message(msg)
                elif action == "mark_as_read":
                    messagebox.showinfo(
                        "Messages Read", data.get("message", "Messages marked as read.")
                    )
                # self.messages_container.mark_all_as_read()
                elif action == "set_n_unread_messages":
                    messagebox.showinfo(
                        "Settings Updated",
                        data.get("message", "Settings updated successfully."),
                    )
                elif action == "delete_account_success":
                    messagebox.showinfo(
                        "Account Deleted",
                        data.get("message", "Your account has been deleted."),
                    )
                    sys.exit()  # Close the app instead of resetting

                elif action == "delete_message_success":
                    # Optionally handle confirmation of message deletion
                    logging.info(f"Message {data.get('id')} deleted successfully.")
                # Handle other success actions as needed
                elif action == "user_list":
                    self.chat_box.update_user_list(data.get("users", []))
            elif status == "error":
                error_msg = data.get("message", "An error occurred.")
                messagebox.showerror("Error", error_msg)
            else:
                # Handle other statuses or actions if necessary
                pass

        except json.JSONDecodeError:
            print("Received non-JSON message.")
        except Exception as e:
            print(f"Error handling message: {e}")

    def get_unread_messages(self):
        """
        Sends a request to the server for all unread messages of the current user.

        The server will send all unread messages back, and the messages will be
        displayed in the MessagesContainer.
        """
        message_dict = {
            "action": "get_unread_messages",
            "username": self.n_new_messages.username,
        }
        self.send_message_via_ws(message_dict)

    def get_recent_messages(self):
        """
        Sends a request to the server for the most recent messages of the current user.

        The server will send the most recent messages back, and the messages will be
        displayed in the MessagesContainer.
        """
        message_dict = {
            "action": "get_recent_messages",
            "username": self.n_new_messages.username,
        }
        self.send_message_via_ws(message_dict)

    def handle_error(self, error: str) -> None:
        """
        Handles errors from the WebSocket client.

        Shows an error message box with the error message.

        Args:
            error (str): The error message from the WebSocket client.
        """
        messagebox.showerror("WebSocket Error", error)

    def switch_to_chat_screen(self):
        """
        Transitions the UI from authentication to chat interface.

        Hides the AuthBox and its contents, and shows the chat interface.
        """
        # Hide all the login and register forms
        self.auth_box.login_form.pack_forget()
        self.auth_box.register_form.pack_forget()
        self.auth_box.toggle_button.pack_forget()

        # Show the chat interface
        self.delete_account_container.pack(pady=10)
        self.n_new_messages.pack(pady=10)
        self.chat_box.pack(pady=10)
        self.messages_container.pack(pady=10)

    def on_closing(self):
        """
        Handles the window closing event.

        If the WebSocket client is connected, it closes the connection.
        """
        # If needed, close the socket or signal the listening thread to exit
        try:
            if self.ws_client and self.ws_client.connected:
                self.ws_client.close()
        except Exception as e:
            print(f"Error closing WebSocket connection: {e}")
        finally:
            # Destroy the window
            self.destroy()


class AuthBox(tk.Frame):
    def __init__(self, parent: tk.Tk) -> None:
        """
        Initialize the AuthBox with the given parent widget.

        :param parent: The parent widget.
        :type parent: tk.Tk
        """
        super().__init__(parent)
        # Initialize with Login Form visible
        self.login_form: LoginForm = LoginForm(parent)
        self.register_form: RegisterForm = RegisterForm(parent)

        self.login_form.pack(pady=10)
        self.current_form: str = "login"  # Track the currently displayed form

        # Toggle Button
        self.toggle_button: tk.Button = tk.Button(
            self,
            text="Don't have an account? Register here.",
            command=self.toggle_forms,
        )
        self.toggle_button.pack(pady=5)

    def toggle_forms(self) -> None:
        """
        Toggle between Login and Register forms.

        If the current form is the Login form, hide it and show the Register form.
        Otherwise, hide the Register form and show the Login form.
        Update the toggle button text accordingly.
        """
        if self.current_form == "login":
            self.login_form.pack_forget()
            self.register_form.pack(pady=10)
            self.toggle_button.config(text="Already have an account? Login here.")
            self.current_form = "register"
        else:
            self.register_form.pack_forget()
            self.login_form.pack(pady=10)
            self.toggle_button.config(text="Don't have an account? Register here.")
            self.current_form = "login"

    def show_register(self):
        self.toggle_forms()


class RegisterForm(tk.Frame):
    def __init__(self, parent: tk.Tk) -> None:
        """
        Initialize the RegisterForm with the given parent widget.

        :param parent: The parent widget.
        :type parent: tk.Tk
        :return: None
        """
        super().__init__(parent)
        tk.Label(self, text="Register", font=("Helvetica", 14)).pack(pady=5)

        tk.Label(self, text="Username:").pack()
        self.username_entry: tk.Entry = tk.Entry(self)
        self.username_entry.pack(pady=5)

        tk.Label(self, text="Password:").pack()
        self.password_entry: tk.Entry = tk.Entry(self, show="*")
        self.password_entry.pack(pady=5)

        tk.Button(self, text="Register", command=self.register).pack(pady=10)

    def register(self):
        """
        Register a new user using the username and password provided in the form.

        If either the username or password is empty, show a warning message and return.
        Otherwise, create a register payload and send it via WebSocket.
        After sending the message, clear the input fields.
        """
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Input Error", "Please enter both username and password."
            )
            return

        # Create the register payload
        register_payload = {
            "action": "register",
            "username": username,
            "password": password,
        }

        # Send the register payload via WebSocket
        self.master.send_message_via_ws(register_payload)

        # Clear the input fields
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)


class LoginForm(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        tk.Label(self, text="Login", font=("Helvetica", 14)).pack(pady=5)

        tk.Label(self, text="Username:").pack()
        self.username_entry = tk.Entry(self)
        self.username_entry.pack(pady=5)

        tk.Label(self, text="Password:").pack()
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack(pady=5)

        tk.Button(self, text="Login", command=self.login).pack(pady=10)

    def login(self) -> None:
        """
        Log in using the username and password provided in the form.

        If either the username or password is empty, show a warning message and return.
        Otherwise, create a login payload and send it via WebSocket.
        After sending the message, clear the input fields.

        """
        username: str = self.username_entry.get().strip()
        password: str = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Input Error", "Please enter both username and password."
            )
            return

        # Create the login payload
        login_payload: Dict[str, str] = {
            "action": "login",
            "username": username,
            "password": password,
        }

        # Send the login payload via WebSocket
        self.master.send_message_via_ws(login_payload)

        # Clear the input fields
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)


class NNewMessages(tk.Frame):
    def __init__(self, parent: tk.Tk) -> None:
        """
        Initialize the NNewMessages frame with the given parent widget.

        :param parent: The parent widget.
        :type parent: tk.Tk
        """
        super().__init__(parent)
        self.username: str = None

        tk.Label(self, text="Number of Unread Messages to Display").grid(
            row=0, column=0, padx=5, pady=5
        )
        self.user_input: tk.Spinbox = tk.Spinbox(self, from_=1, to=100, width=5)
        self.user_input.grid(row=0, column=1, padx=5, pady=5)

        set_button: tk.Button = tk.Button(
            self, text="Set", command=self.set_unread_messages
        )
        set_button.grid(row=0, column=2, padx=5, pady=5)

    def set_unread_messages(self) -> None:
        """
        Set the number of unread messages to display in the chat box.

        Retrieves the number of unread messages from the user input field,
        creates a set payload with the action, number of unread messages, and
        the current username, and sends it via WebSocket.
        """
        number = self.user_input.get()
        set_payload = {
            "action": "set_n_unread_messages",
            "n_unread_messages": int(number),
            "username": self.username,
        }
        self.master.send_message_via_ws(set_payload)
        messagebox.showinfo(
            "Set Unread Messages", f"Set to display {number} unread messages."
        )


class ChatBox(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = None

        # Messages Display
        # self.messages_display = tk.Text(self, height=15, width=80, state="disabled")
        # self.messages_display.pack(pady=5)

        # Receiver Username
        receiver_frame = tk.Frame(self)
        receiver_frame.pack(pady=5)
        tk.Label(receiver_frame, text="Receiver Username:").pack(side=tk.LEFT, padx=5)
        self.user_list = []
        self.selected_user = tk.StringVar(self)
        self.selected_user.set("Select a user")  # Default placeholder
        self.user_dropdown = tk.OptionMenu(
            receiver_frame, self.selected_user, "Select a user", *self.user_list
        )
        self.user_dropdown.pack(side=tk.LEFT, padx=5)

        tk.Button(receiver_frame, text="Refresh", command=self.fetch_users).pack(
            side=tk.LEFT, padx=5
        )

        # Message Text
        message_frame = tk.Frame(self)
        message_frame.pack(pady=5)
        tk.Label(message_frame, text="Message:").pack(side=tk.LEFT, padx=5)
        self.message_text = tk.Entry(message_frame, width=50)
        self.message_text.pack(side=tk.LEFT, padx=5)

        # Send Button
        send_button = tk.Button(self, text="Send", command=self.send_message)
        send_button.pack(pady=5)

        # Error Message Box
        self.error_box = tk.Label(self, text="", fg="red")
        self.error_box.pack(pady=5)
        self.error_box.pack_forget()  # Initially hidden

    def send_message(self):
        receiver = self.selected_user.get()
        message = self.message_text.get().strip()
        if not receiver or not message:
            self.display_error("Receiver and message cannot be empty.")
            return
        # Create the send message payload
        send_payload = {
            "action": "send_message",
            "receiver": receiver,
            "message": message,
        }
        # Send the message via WebSocket
        self.master.send_message_via_ws(send_payload)
        # Display the sent message in the messages display
        # self.display_message(f"To {receiver}: {message}")
        # Clear input fields
        self.message_text.delete(0, tk.END)

    def display_message(self, message):
        self.messages_display.config(state="normal")
        self.messages_display.insert(tk.END, message + "\n")
        self.messages_display.config(state="disabled")

    def display_error(self, message):
        self.error_box.config(text=message)
        self.error_box.pack()

    def update_user_list(self, users):
        """
        Updates the dropdown with the latest list of users.
        """
        if not users:
            self.selected_user.set("No users available")
            return

        self.user_list = users
        self.selected_user.set(users[0])  # Set the first user as default

        menu = self.user_dropdown["menu"]
        menu.delete(0, "end")  # Clear previous entries

        for user in users:
            menu.add_command(
                label=user, command=lambda value=user: self.selected_user.set(value)
            )

    def fetch_users(self):
        """
        Sends a request to fetch all users except the logged-in user.
        """
        self.master.send_message_via_ws({"action": "get_users"})


class MessagesContainer(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = None

        # Dictionaries to store messages with their IDs
        self.unread_messages_dict = {}
        self.recent_messages_dict = {}

        # Create Scrollable Frames for Unread and Recent Messages
        self.create_scrollable_sections()

    def create_scrollable_sections(self):
        # Unread Messages Section
        self.configure(width=600)  # Increased from 400

        unread_section = tk.LabelFrame(
            self, text="Unread Messages", padx=5, pady=5, width=600
        )
        unread_section.pack(side=tk.TOP, padx=5, pady=5, fill=tk.BOTH, expand=True)

        # Canvas and Scrollbar for Unread Messages
        unread_canvas = tk.Canvas(unread_section, borderwidth=0, width=580)
        unread_scrollbar = tk.Scrollbar(
            unread_section, orient="vertical", command=unread_canvas.yview
        )
        self.unread_messages_frame = tk.Frame(unread_canvas)

        self.unread_messages_frame.bind(
            "<Configure>",
            lambda e: unread_canvas.configure(scrollregion=unread_canvas.bbox("all")),
        )

        unread_canvas.create_window(
            (0, 0), window=self.unread_messages_frame, anchor="nw"
        )
        unread_canvas.configure(yscrollcommand=unread_scrollbar.set)

        unread_canvas.pack(side="left", fill="both", expand=True)
        unread_scrollbar.pack(side="right", fill="y")

        # Recent Messages Section
        recent_section = tk.LabelFrame(
            self,
            text="Recent Messages",
            padx=5,
            pady=5,
            width=600,
        )
        recent_section.pack(side=tk.TOP, padx=5, pady=5, fill=tk.BOTH, expand=True)

        # Canvas and Scrollbar for Recent Messages
        recent_canvas = tk.Canvas(recent_section, borderwidth=0, width=580)
        recent_scrollbar = tk.Scrollbar(
            recent_section, orient="vertical", command=recent_canvas.yview
        )
        self.recent_messages_frame = tk.Frame(recent_canvas)

        self.recent_messages_frame.bind(
            "<Configure>",
            lambda e: recent_canvas.configure(scrollregion=recent_canvas.bbox("all")),
        )

        recent_canvas.create_window(
            (0, 0), window=self.recent_messages_frame, anchor="nw"
        )
        recent_canvas.configure(yscrollcommand=recent_scrollbar.set)

        recent_canvas.pack(side="left", fill="both", expand=True)
        recent_scrollbar.pack(side="right", fill="y")

    def mark_all_as_read(self):
        # Implement logic to mark all unread messages as read
        if not self.unread_messages_dict:
            messagebox.showinfo(
                "No Unread Messages", "There are no unread messages to mark as read."
            )
            return

        # Prepare message IDs to mark as read
        message_ids = list(self.unread_messages_dict.keys())

        mark_payload = {
            "action": "mark_as_read",
            "message_ids": message_ids,  # Send actual message IDs
        }
        self.master.send_message_via_ws(mark_payload)

        # Clear the unread messages display
        for msg_id, frame in self.unread_messages_dict.items():
            frame.destroy()
        self.unread_messages_dict.clear()

    def add_unread_message(self, message_data: Dict[str, Any]) -> None:
        """
        Adds an unread message to the Unread Messages section.
        Expects message_data to be a dictionary containing at least 'id', 'from', 'timestamp', and 'message'.
        :param message_data: A dictionary containing the message data.
        """
        id = message_data.get("id")
        username = message_data.get("username")
        sender = message_data.get("from")
        timestamp = message_data.get("timestamp")
        message = message_data.get("message")
        #  timestamp is in format 2025-02-11T02:25:50.374591Z
        # render just the date and time to the minute
        timestamp = datetime.datetime.strptime(
            timestamp, "%Y-%m-%dT%H:%M:%S.%f%z"
        ).strftime("%Y-%m-%d %H:%M")

        if not id:
            logging.error("Message data missing 'id'.")
            return

        # Avoid duplicate messages
        if id in self.unread_messages_dict:
            logging.info(f"Message {id} already exists in unread messages.")
            return

        # Create a frame for the message
        msg_frame = tk.Frame(
            self.unread_messages_frame, bd=1, relief=tk.RIDGE, padx=5, pady=5
        )
        msg_frame.pack(fill=tk.X, pady=2)

        # Message Label
        msg_label = tk.Label(
            msg_frame,
            text=f"From {sender} at {timestamp}: {message}",
            anchor="w",
            justify="left",
            wraplength=300,
        )
        msg_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Delete Button
        delete_button = tk.Button(
            msg_frame,
            text="Delete",
            fg="red",
            command=lambda mid=id, mf=msg_frame: self.delete_message(mid, mf, "unread"),
        )
        delete_button.pack(side=tk.RIGHT, padx=5)
        # Delete Button
        read_button = tk.Button(
            msg_frame,
            text="read",
            fg="red",
            command=lambda mid=id, mf=msg_frame: self.read_message(mid, mf),
        )
        read_button.pack(side=tk.RIGHT, padx=5)
        # Store the message frame with its ID
        self.unread_messages_dict[id] = msg_frame

    def read_message(self, id: int, frame: tk.Frame) -> None:
        """
        Handles the mark-as-read action for a message.

        Args:
            id (int): The message ID to mark as read.
            frame (tk.Frame): The frame containing the unread message to delete.

        """
        payload = {"action": "mark_as_read", "message_ids": [id]}
        self.master.send_message_via_ws(payload)
        frame.destroy()
        del self.unread_messages_dict[id]

    def add_recent_message(self, message_data: Dict[str, Any]) -> None:
        """
        Adds a recent message to the MessagesContainer from message_data.

        Args:
            message_data (Dict[str, Any]): A dictionary containing the message data.
                The required keys are 'id', 'from', 'timestamp', and 'message'.
        """
        id = message_data.get("id")
        sender = message_data.get("from")
        timestamp = message_data.get("timestamp")
        message = message_data.get("message")
        logging.info(f"Adding recent message: {message}")
        if not id:
            logging.error("Message data missing 'id'.")
            return

        # Avoid duplicate messages
        if id in self.recent_messages_dict:
            logging.info(f"Message {id} already exists in recent messages.")
            return

        # Create a frame for the message
        msg_frame = tk.Frame(
            self.recent_messages_frame, bd=1, relief=tk.RIDGE, padx=5, pady=5
        )
        msg_frame.pack(fill=tk.X, pady=2)

        # Message Label
        msg_label = tk.Label(
            msg_frame,
            text=f"From {sender} at {timestamp}: {message}",
            anchor="w",
            justify="left",
            wraplength=300,
        )
        msg_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Delete Button
        delete_button = tk.Button(
            msg_frame,
            text="Delete",
            fg="red",
            command=lambda mid=id, mf=msg_frame: self.delete_message(mid, mf, "recent"),
        )
        delete_button.pack(side=tk.RIGHT, padx=5)

        # Store the message frame with its ID
        self.recent_messages_dict[id] = msg_frame

    def delete_message(
        self, id: int, frame: tk.Frame, section: Literal["unread", "recent"]
    ) -> None:
        """
        Deletes a message from the given section and notifies the server.

        Args:
            id (int): The message ID to delete.
            frame (tk.Frame): The frame containing the message to delete.
            section (Literal["unread", "recent"]): The section of messages to delete from.

        """
        confirm = messagebox.askyesno(
            "Delete Message", "Are you sure you want to delete this message?"
        )
        if not confirm:
            return

        # Destroy the message frame
        frame.destroy()

        # Remove from the appropriate dictionary
        if section == "unread":
            del self.unread_messages_dict[id]
        elif section == "recent":
            del self.recent_messages_dict[id]

        # Notify the server about the deletion
        delete_payload = {
            "action": "delete_message",
            "id": id,
        }
        self.master.send_message_via_ws(delete_payload)

    def mark_all_as_read(self) -> None:
        """
        Marks all unread messages as read and moves them to the recent messages section.
        """
        if not self.unread_messages_dict:
            messagebox.showinfo(
                "No Unread Messages", "There are no unread messages to mark as read."
            )
            return

        # Prepare message IDs to mark as read
        message_ids: List[int] = list(self.unread_messages_dict.keys())

        mark_payload: Dict[str, Any] = {
            "action": "mark_as_read",
            "message_ids": message_ids,  # Send actual message IDs
        }
        self.master.send_message_via_ws(mark_payload)

        # Move all unread messages to recent messages
        for id, frame in list(self.unread_messages_dict.items()):
            # Extract message details from the frame's label
            msg_label: tk.Label = frame.winfo_children()[0]
            msg_text: str = msg_label.cget("text")
            # Optionally, parse the message_text to extract sender, timestamp, and message
            # Here, we assume the message_data structure is consistent
            message_data: Dict[str, str] = {
                "id": str(id),
                "from": msg_text.split(" ")[1],
                "timestamp": msg_text.split(" at ")[1].split(":")[0],
                "message": ": ".join(msg_text.split(": ")[1:]),
            }
            self.add_recent_message(message_data)
            frame.destroy()
            del self.unread_messages_dict[id]

        messagebox.showinfo(
            "Messages Read", "All unread messages have been marked as read."
        )

    # Optionally, you can add methods to handle refreshing or updating messages


class DeleteAccountContainer(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = None

        delete_button = tk.Button(
            self, text="Delete Account", fg="red", command=self.delete_account
        )
        delete_button.pack(pady=10)

    def delete_account(self) -> None:
        """
        Deletes the current user's account.

        Confirms with the user before sending a delete account request via WebSocket.
        If confirmed, sends the request and shows an information message before exiting the app.
        """
        confirm: bool = messagebox.askyesno(
            "Delete Account", "Are you sure you want to delete your account?"
        )
        if confirm:
            # Create the delete account payload
            delete_payload: Dict[str, str] = {
                "action": "delete_account",
                "username": self.username,
            }
            # Send the delete account request via WebSocket
            self.master.send_message_via_ws(delete_payload)
            # Inform the user and reset the app
            messagebox.showinfo("Delete Account", "Your account has been deleted.")
            sys.exit()


if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()
