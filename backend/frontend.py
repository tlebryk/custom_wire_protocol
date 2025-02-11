# print python version
import sys

print(f"Python version: {sys.version}")

import tkinter as tk
from tkinter import messagebox
import json
import threading
from websocket_client import WebSocketClient  # Import the WebSocketClient class
import logging, logging.config
from pathlib import Path
import datetime
import custom_protocol
import os

# format logs to include filename and line number

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    level=logging.INFO,
)


class ChatApp(tk.Tk):
    def __init__(self, mode=None):
        super().__init__()

        self.title("WebSocket Chat - Registration and Login")
        self.geometry("800x600")
        self.resizable(False, False)

        # Initialize WebSocket client
        self.ws_client = WebSocketClient(
            url="ws://localhost:8000",  # Replace with your server URL
            on_message=self.handle_incoming_message,
            on_error=self.handle_error,
            on_close=self.handle_close,
        )
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
            mode = os.environ.get("MODE", "custom")
            self.mode = mode
        if self.mode == "json":
            self.encoder = None
            self.decoder = None
        else:
            self.encoder = custom_protocol.Encoder(custom_protocol.load_protocols())
            self.decoder = custom_protocol.Decoder(custom_protocol.load_protocols())

    def handle_incoming_message(self, message):
        """
        Handles incoming messages from the WebSocket server.
        """
        try:
            if self.mode == "json":
                data = json.loads(message)
            else:
                data = self.decoder.decode_message(message)

            status = data.get("status")
            action = data.get("action")
            logging.warning(f"Received data: {data}")
            if status == "success":
                if action == "register":
                    messagebox.showinfo(
                        "Registration Successful",
                        data.get("message", "You have registered successfully."),
                    )
                elif action == "login":
                    messagebox.showinfo(
                        "Login Successful",
                        data.get("message", "You have logged in successfully."),
                    )
                    self.n_new_messages.username = data.get("username")
                    self.chat_box.username = data.get("username")
                    self.messages_container.username = data.get("username")
                    self.delete_account_container.username = data.get("username")
                    self.switch_to_chat_screen()
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
                    self.reset_app()
                elif action == "delete_message_success":
                    # Optionally handle confirmation of message deletion
                    logging.info(f"Message {data.get('id')} deleted successfully.")
                # Handle other success actions as needed
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

    def handle_error(self, error):
        """
        Handles errors from the WebSocket client.
        """
        messagebox.showerror("WebSocket Error", error)

    def handle_close(self):
        """
        Handles the WebSocket connection closing.
        """
        messagebox.showinfo(
            "WebSocket Closed", "The connection to the server has been closed."
        )
        self.reset_app()

    def switch_to_chat_screen(self):
        """
        Transitions the UI from authentication to chat interface.
        """
        # hide all the login and register forms

        self.auth_box.login_form.pack_forget()
        self.auth_box.register_form.pack_forget()
        self.auth_box.toggle_button.pack_forget()
        self.n_new_messages.pack(pady=10)
        self.chat_box.pack(pady=10)
        self.messages_container.pack(pady=10)
        self.delete_account_container.pack(pady=10)

    def reset_app(self):
        """
        Resets the application to its initial state.
        """
        self.n_new_messages.pack_forget()
        self.chat_box.pack_forget()
        self.messages_container.pack_forget()
        self.delete_account_container.pack_forget()
        self.auth_box.show_register()
        self.auth_box.pack(pady=20)

    def send_message_via_ws(self, message_dict):
        """
        Sends a message via the WebSocket client.
        """
        if self.ws_client and self.ws_client.connected:
            if self.mode == "json":
                data = json.dumps(message_dict)
                data = data.encode("utf-8")
            else:
                logging.info("here")
                data = self.encoder.encode_message(message_dict)
                logging.warning(f"Sending data: {data}")
            self.ws_client.send(data)
        else:
            messagebox.showwarning("Connection Error", "WebSocket is not connected.")


class AuthBox(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        # Initialize with Login Form visible
        self.login_form = LoginForm(parent)
        self.register_form = RegisterForm(parent)

        self.login_form.pack(pady=10)
        self.current_form = "login"  # Track the currently displayed form

        # Toggle Button
        self.toggle_button = tk.Button(
            self,
            text="Don't have an account? Register here.",
            command=self.toggle_forms,
        )
        self.toggle_button.pack(pady=5)

    def toggle_forms(self):
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
    def __init__(self, parent):
        super().__init__(parent)

        tk.Label(self, text="Register", font=("Helvetica", 14)).pack(pady=5)

        tk.Label(self, text="Username:").pack()
        self.username_entry = tk.Entry(self)
        self.username_entry.pack(pady=5)

        tk.Label(self, text="Password:").pack()
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack(pady=5)

        tk.Button(self, text="Register", command=self.register).pack(pady=10)

    def register(self):
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

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Input Error", "Please enter both username and password."
            )
            return

        # Create the login payload
        login_payload = {"action": "login", "username": username, "password": password}

        # Send the login payload via WebSocket
        self.master.send_message_via_ws(login_payload)

        # Clear the input fields
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)


class NNewMessages(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = None

        tk.Label(self, text="Number of Unread Messages to Display").grid(
            row=0, column=0, padx=5, pady=5
        )
        self.user_input = tk.Spinbox(self, from_=1, to=100, width=5)
        self.user_input.grid(row=0, column=1, padx=5, pady=5)

        set_button = tk.Button(self, text="Set", command=self.set_unread_messages)
        set_button.grid(row=0, column=2, padx=5, pady=5)

    def set_unread_messages(self):
        number = self.user_input.get()
        # Implement logic to set number of unread messages
        set_payload = {
            "action": "set_n_unread_messages",
            "n_unread_messages": int(number),
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
        self.receiver_username = tk.Entry(receiver_frame)
        self.receiver_username.pack(side=tk.LEFT, padx=5)

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
        receiver = self.receiver_username.get().strip()
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
        self.receiver_username.delete(0, tk.END)
        self.message_text.delete(0, tk.END)

    def display_message(self, message):
        self.messages_display.config(state="normal")
        self.messages_display.insert(tk.END, message + "\n")
        self.messages_display.config(state="disabled")

    def display_error(self, message):
        self.error_box.config(text=message)
        self.error_box.pack()


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

    def add_unread_message(self, message_data):
        """
        Adds an unread message to the Unread Messages section.
        Expects message_data to be a dictionary containing at least 'id', 'from', 'timestamp', and 'message'.
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

    def read_message(self, id, frame):
        payload = {"action": "mark_as_read", "message_ids": [id]}
        self.master.send_message_via_ws(payload)
        frame.destroy()
        del self.unread_messages_dict[id]

    def add_recent_message(self, message_data):
        """
        Adds a recent message to the Recent Messages section.
        Expects message_data to be a dictionary containing at least 'id', 'from', 'timestamp', and 'message'.
        """
        id = message_data.get("id")
        sender = message_data.get("from")
        timestamp = message_data.get("timestamp")
        message = message_data.get("message")

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

    def delete_message(self, id, frame, section):
        """
        Deletes a message from the UI and notifies the server.
        :param id: Unique identifier of the message.
        :param frame: The frame widget containing the message.
        :param section: 'unread' or 'recent' indicating the message section.
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

    def mark_all_as_read(self):
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

        # Move all unread messages to recent messages
        for id, frame in list(self.unread_messages_dict.items()):
            # Extract message details from the frame's label
            msg_label = frame.winfo_children()[0]
            msg_text = msg_label.cget("text")
            # Optionally, parse the message_text to extract sender, timestamp, and message
            # Here, we assume the message_data structure is consistent
            message_data = {
                "id": id,
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

    def delete_account(self):
        # Implement account deletion logic here
        confirm = messagebox.askyesno(
            "Delete Account", "Are you sure you want to delete your account?"
        )
        if confirm:
            # Create the delete account payload
            delete_payload = {"action": "delete_account"}
            # Send the delete account request via WebSocket
            self.master.send_message_via_ws(delete_payload)
            # Inform the user and reset the app
            messagebox.showinfo("Delete Account", "Your account has been deleted.")
            self.master.reset_app()


if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()
