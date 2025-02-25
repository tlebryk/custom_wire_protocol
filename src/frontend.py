# frontend.py
import sys
import tkinter as tk
from tkinter import messagebox
import logging
import grpc
import threading
import os

# Import the generated gRPC modules
import protocols_pb2
import protocols_pb2_grpc
from typing import Dict, Any, Optional, List, Union, Literal

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    level=logging.INFO,
)


class GRPCClient:
    """
    A simple gRPC client to interact with the MessagingService.
    """

    def __init__(self, host="localhost", port=50051):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = protocols_pb2_grpc.MessagingServiceStub(self.channel)

    def login(self, username: str, password: str):
        try:
            request = protocols_pb2.LoginRequest(username=username, password=password)
            response = self.stub.Login(request)
            return response
        except grpc.RpcError as e:
            logging.error("Login RPC failed: %s", e)
            return None

    def register(self, username: str, password: str):
        try:
            request = protocols_pb2.RegisterRequest(
                username=username, password=password
            )
            response = self.stub.Register(request)
            return response
        except grpc.RpcError as e:
            logging.error("Register RPC failed: %s", e)
            return None

    def send_message(self, message: str, receiver: str):
        try:
            request = protocols_pb2.SendMessageRequest(
                message=message, receiver=receiver
            )
            response = self.stub.SendMessage(request)
            return response
        except grpc.RpcError as e:
            logging.error("SendMessage RPC failed: %s", e)
            return None

    def get_recent_messages(self, username: str):
        try:
            request = protocols_pb2.GetRecentMessagesRequest(username=username)
            response = self.stub.GetRecentMessages(request)
            return response
        except grpc.RpcError as e:
            logging.error("GetRecentMessages RPC failed: %s", e)
            return None

    def get_unread_messages(self, username: str):
        try:
            request = protocols_pb2.GetUnreadMessagesRequest(username=username)
            response = self.stub.GetUnreadMessages(request)
            return response
        except grpc.RpcError as e:
            logging.error("GetUnreadMessages RPC failed: %s", e)
            return None

    def mark_as_read(self, message_ids: list):
        try:
            request = protocols_pb2.MarkAsReadRequest(message_ids=message_ids)
            response = self.stub.MarkAsRead(request)
            return response
        except grpc.RpcError as e:
            logging.error("MarkAsRead RPC failed: %s", e)
            return None

    def set_n_unread_messages(self, username: str, n: int):
        try:
            request = protocols_pb2.SetNUnreadMessagesRequest(
                username=username, n_unread_messages=n
            )
            response = self.stub.SetNUnreadMessages(request)
            return response
        except grpc.RpcError as e:
            logging.error("SetNUnreadMessages RPC failed: %s", e)
            return None

    def delete_message(self, username: str, message_id: int):
        try:
            request = protocols_pb2.DeleteMessageRequest(
                username=username, message_id=message_id
            )
            response = self.stub.DeleteMessage(request)
            return response
        except grpc.RpcError as e:
            logging.error("DeleteMessage RPC failed: %s", e)
            return None

    def delete_account(self, username: str):
        try:
            request = protocols_pb2.DeleteAccountRequest(username=username)
            response = self.stub.DeleteAccount(request)
            return response
        except grpc.RpcError as e:
            logging.error("DeleteAccount RPC failed: %s", e)
            return None


class ChatApp(tk.Tk):
    def __init__(self, mode: str = None):
        super().__init__()
        self.title("gRPC Chat - Registration and Login")
        self.geometry("800x800")
        self.resizable(False, False)

        # Initialize gRPC client
        self.grpc_client = GRPCClient()

        # Create Authentication Box
        self.auth_box = AuthBox(self)
        self.auth_box.pack(pady=20)

        # Initialize Chat Screen Components
        self.n_new_messages = NNewMessages(self)
        self.chat_box = ChatBox(self)
        self.messages_container = MessagesContainer(self)
        self.delete_account_container = DeleteAccountContainer(self)

        self.mode = mode if mode else os.environ.get("MODE", "grpc")

    def get_unread_messages(self):
        # Retrieve unread messages via gRPC and update the MessagesContainer
        username = self.n_new_messages.username
        if username:
            response = self.grpc_client.get_unread_messages(username)
            if response and response.status == "success":
                for msg in response.messages:
                    msg_dict = {
                        "timestamp": msg.timestamp,
                        "from": getattr(msg, "from"),
                        "message": msg.message,
                        "id": msg.id,
                    }
                    self.messages_container.add_unread_message(msg_dict)

    def get_recent_messages(self):
        # Retrieve recent messages via gRPC and update the MessagesContainer
        username = self.n_new_messages.username
        if username:
            response = self.grpc_client.get_recent_messages(username)
            if response and response.status == "success":
                for msg in response.messages:
                    msg_dict = {
                        "timestamp": msg.timestamp,
                        "from": getattr(msg, "from"),
                        "message": msg.message,
                        "id": msg.id,
                    }
                    self.messages_container.add_recent_message(msg_dict)

    def switch_to_chat_screen(self):
        """
        Transition the UI from authentication to chat interface.
        """
        # Hide authentication forms
        self.auth_box.login_form.pack_forget()
        self.auth_box.register_form.pack_forget()
        self.auth_box.toggle_button.pack_forget()

        # Show chat UI components
        self.delete_account_container.pack(pady=10)
        self.n_new_messages.pack(pady=10)
        self.chat_box.pack(pady=10)
        self.messages_container.pack(pady=10)

    def on_closing(self):
        self.destroy()


class AuthBox(tk.Frame):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        # Initialize with Login Form visible
        self.login_form = LoginForm(parent)
        self.register_form = RegisterForm(parent)

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


class RegisterForm(tk.Frame):
    def __init__(self, parent: tk.Tk) -> None:
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
        Register a new user using gRPC.
        """
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Input Error", "Please enter both username and password."
            )
            return

        # Call the gRPC register method
        response = self.master.grpc_client.register(username, password)
        if response:
            messagebox.showinfo("Registration Successful", response.message)
        else:
            messagebox.showerror(
                "Registration Failed", "An error occurred during registration."
            )

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
        Log in using the gRPC client.
        """
        username: str = self.username_entry.get().strip()
        password: str = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Input Error", "Please enter both username and password."
            )
            return

        # Call the gRPC login method
        response = self.master.grpc_client.login(username, password)
        if response and response.status == "success":
            messagebox.showinfo("Login Successful", response.message)
            # Set username and switch to chat screen
            self.master.n_new_messages.username = response.username
            self.master.chat_box.username = response.username
            self.master.messages_container.username = response.username
            self.master.delete_account_container.username = response.username
            self.master.switch_to_chat_screen()
            self.master.get_unread_messages()
            self.master.get_recent_messages()
        else:
            error_msg = (
                response.message if response else "An error occurred during login."
            )
            messagebox.showerror("Login Failed", error_msg)

        # Clear the input fields
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)


class ChatBox(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = None  # To be set upon login

        tk.Label(self, text="Chat", font=("Helvetica", 16)).pack(pady=5)

        # Receiver selection using OptionMenu
        self.receiver_var = tk.StringVar(self)
        self.receiver_var.set("Select Receiver")
        self.receiver_menu = tk.OptionMenu(self, self.receiver_var, "Select Receiver")
        self.receiver_menu.pack(pady=5)

        # Frame for message entry and send button
        self.message_frame = tk.Frame(self)
        self.message_frame.pack(pady=10)

        self.message_entry = tk.Entry(self.message_frame, width=50)
        self.message_entry.pack(side=tk.LEFT, padx=5)

        self.send_button = tk.Button(
            self.message_frame, text="Send", command=self.send_message
        )
        self.send_button.pack(side=tk.LEFT, padx=5)

    def send_message(self):
        message = self.message_entry.get().strip()
        receiver = self.receiver_var.get()
        if not message:
            messagebox.showwarning("Input Error", "Please enter a message.")
            return
        if receiver == "Select Receiver":
            messagebox.showwarning("Input Error", "Please select a receiver.")
            return
        # Call the gRPC client's send_message method
        response = self.master.grpc_client.send_message(message, receiver)
        if response is None:
            # Assume success for the placeholder implementation
            logging.info(f"Sent message to {receiver}: {message}")
            messagebox.showinfo("Message Sent", f"Message sent to {receiver}.")
        else:
            logging.info(f"Response from send_message: {response}")
        # Clear the message entry
        self.message_entry.delete(0, tk.END)

    def fetch_users(self):
        """
        Populate the receiver dropdown with a dummy list of users.
        This method can later be updated to call a gRPC method to fetch real user data.
        """
        dummy_users = ["user1", "user2", "user3"]
        menu = self.receiver_menu["menu"]
        menu.delete(0, "end")
        for user in dummy_users:
            menu.add_command(
                label=user, command=lambda value=user: self.receiver_var.set(value)
            )
        if dummy_users:
            self.receiver_var.set(dummy_users[0])


class MessagesContainer(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = None

        # Dictionaries to store messages with their IDs
        self.unread_messages_dict = {}
        self.recent_messages_dict = {}

        # Create scrollable sections for Unread and Recent Messages
        self.create_scrollable_sections()

    def create_scrollable_sections(self):
        # Unread Messages Section
        self.configure(width=600)
        unread_section = tk.LabelFrame(
            self, text="Unread Messages", padx=5, pady=5, width=600
        )
        unread_section.pack(side=tk.TOP, padx=5, pady=5, fill=tk.BOTH, expand=True)

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
            self, text="Recent Messages", padx=5, pady=5, width=600
        )
        recent_section.pack(side=tk.TOP, padx=5, pady=5, fill=tk.BOTH, expand=True)

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

    def mark_all_as_read(self) -> None:
        if not self.unread_messages_dict:
            messagebox.showinfo(
                "No Unread Messages", "There are no unread messages to mark as read."
            )
            return

        # Prepare message IDs
        message_ids: List[int] = list(self.unread_messages_dict.keys())
        response = self.master.grpc_client.mark_as_read(message_ids)
        if response:
            # Move each unread message to recent messages
            for msg_id, frame in list(self.unread_messages_dict.items()):
                # Extract text from the label (assuming first child holds the message text)
                msg_text = frame.winfo_children()[0].cget("text")
                # For simplicity, we re-use the same text for recent messages.
                message_data = {
                    "id": msg_id,
                    "from": msg_text.split(" ")[1] if " " in msg_text else "",
                    "timestamp": (
                        msg_text.split(" at ")[1].split(":")[0]
                        if " at " in msg_text
                        else ""
                    ),
                    "message": (
                        ": ".join(msg_text.split(": ")[1:])
                        if ": " in msg_text
                        else msg_text
                    ),
                }
                self.add_recent_message(message_data)
                frame.destroy()
                del self.unread_messages_dict[msg_id]
            messagebox.showinfo(
                "Messages Read", "All unread messages have been marked as read."
            )
        else:
            messagebox.showerror("Error", "Failed to mark messages as read.")

    def add_unread_message(self, message_data: Dict[str, Any]) -> None:
        msg_id = message_data.get("id")
        sender = message_data.get("from")
        timestamp = message_data.get("timestamp")
        message = message_data.get("message")
        if not msg_id:
            logging.error("Message data missing 'id'.")
            return

        # Format timestamp (assuming ISO format with microseconds and timezone)
        try:
            timestamp_obj = datetime.datetime.strptime(
                timestamp, "%Y-%m-%dT%H:%M:%S.%f%z"
            )
            timestamp_str = timestamp_obj.strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            logging.error("Timestamp parsing failed: %s", e)
            timestamp_str = timestamp

        # Avoid duplicate messages
        if msg_id in self.unread_messages_dict:
            logging.info(f"Message {msg_id} already exists in unread messages.")
            return

        msg_frame = tk.Frame(
            self.unread_messages_frame, bd=1, relief=tk.RIDGE, padx=5, pady=5
        )
        msg_frame.pack(fill=tk.X, pady=2)

        msg_label = tk.Label(
            msg_frame,
            text=f"From {sender} at {timestamp_str}: {message}",
            anchor="w",
            justify="left",
            wraplength=300,
        )
        msg_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Button to mark as read
        read_button = tk.Button(
            msg_frame,
            text="Read",
            fg="green",
            command=lambda mid=msg_id, mf=msg_frame: self.read_message(mid, mf),
        )
        read_button.pack(side=tk.RIGHT, padx=5)

        # Button to delete message
        delete_button = tk.Button(
            msg_frame,
            text="Delete",
            fg="red",
            command=lambda mid=msg_id, mf=msg_frame: self.delete_message(
                mid, mf, "unread"
            ),
        )
        delete_button.pack(side=tk.RIGHT, padx=5)

        self.unread_messages_dict[msg_id] = msg_frame

    def read_message(self, msg_id: int, frame: tk.Frame) -> None:
        response = self.master.grpc_client.mark_as_read([msg_id])
        if response:
            frame.destroy()
            del self.unread_messages_dict[msg_id]
            # Optionally, add to recent messages if desired.
        else:
            messagebox.showerror("Error", "Failed to mark message as read.")

    def add_recent_message(self, message_data: Dict[str, Any]) -> None:
        msg_id = message_data.get("id")
        sender = message_data.get("from")
        timestamp = message_data.get("timestamp")
        message = message_data.get("message")
        if not msg_id:
            logging.error("Message data missing 'id'.")
            return

        msg_frame = tk.Frame(
            self.recent_messages_frame, bd=1, relief=tk.RIDGE, padx=5, pady=5
        )
        msg_frame.pack(fill=tk.X, pady=2)

        msg_label = tk.Label(
            msg_frame,
            text=f"From {sender} at {timestamp}: {message}",
            anchor="w",
            justify="left",
            wraplength=300,
        )
        msg_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        delete_button = tk.Button(
            msg_frame,
            text="Delete",
            fg="red",
            command=lambda mid=msg_id, mf=msg_frame: self.delete_message(
                mid, mf, "recent"
            ),
        )
        delete_button.pack(side=tk.RIGHT, padx=5)

        self.recent_messages_dict[msg_id] = msg_frame

    def delete_message(
        self, msg_id: int, frame: tk.Frame, section: Literal["unread", "recent"]
    ) -> None:
        confirm = messagebox.askyesno(
            "Delete Message", "Are you sure you want to delete this message?"
        )
        if not confirm:
            return

        frame.destroy()
        if section == "unread" and msg_id in self.unread_messages_dict:
            del self.unread_messages_dict[msg_id]
        elif section == "recent" and msg_id in self.recent_messages_dict:
            del self.recent_messages_dict[msg_id]

        response = self.master.grpc_client.delete_message(
            self.master.n_new_messages.username, msg_id
        )
        if response:
            messagebox.showinfo("Delete Message", response.message)
        else:
            messagebox.showerror("Delete Message", "Failed to delete message.")


class DeleteAccountContainer(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        tk.Label(self, text="Account Settings", font=("Helvetica", 14)).pack(pady=5)
        self.delete_button = tk.Button(
            self, text="Delete Account", command=self.delete_account
        )
        self.delete_button.pack(pady=5)
        self.username = None  # To be set after login

    def delete_account(self):
        if not self.username:
            messagebox.showwarning("Warning", "No user logged in.")
            return
        if messagebox.askyesno(
            "Confirm", "Are you sure you want to delete your account?"
        ):
            response = self.master.grpc_client.delete_account(self.username)
            if response and response.status == "success":
                messagebox.showinfo("Delete Account", response.message)
            else:
                messagebox.showerror("Delete Account", "Failed to delete account.")


class NNewMessages(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = ""
        self.counter = 0
        self.label = tk.Label(self, text="New Messages: 0", font=("Helvetica", 14))
        self.label.pack(pady=5)

    def update_count(self, count):
        self.counter = count
        self.label.config(text=f"New Messages: {self.counter}")


if __name__ == "__main__":
    app = ChatApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
