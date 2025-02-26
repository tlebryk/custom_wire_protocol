# frontend.py
import sys
import tkinter as tk
from tkinter import messagebox
import logging
import grpc
import threading
import os
import datetime

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
            # Pass sender in metadata (if needed, the client can manage that)
            response = self.stub.SendMessage(
                request, metadata=(("sender", self.username),)
            )
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

    def subscribe(self, username: str):
        try:
            request = protocols_pb2.SubscribeRequest(username=username)
            return self.stub.Subscribe(request)
        except grpc.RpcError as e:
            logging.error("Subscribe RPC failed: %s", e)
            return None
    def get_users(self, username: str):
        try:
            request = protocols_pb2.GetUsersRequest(username=username)
            response = self.stub.GetUsers(request)
            if response.status == "success":
                return list(response.usernames)
            else:
                return []
        except grpc.RpcError as e:
            logging.error("GetUsers RPC failed: %s", e)
            return []



class ChatApp(tk.Tk):
    def __init__(self, mode: str = None):
        super().__init__()
        self.title("gRPC Chat - Registration and Login")
        self.geometry("800x800")
        self.resizable(False, False)

        # Initialize gRPC client
        self.grpc_client = GRPCClient()
        # We'll set the client's username after login.
        self.grpc_client.username = ""

        # Create Authentication Box
        self.auth_box = AuthBox(self)
        self.auth_box.pack(pady=20)

        # Initialize Chat Screen Components
        self.n_new_messages = NNewMessages(self)
        self.chat_box = ChatBox(self)
        self.messages_container = MessagesContainer(self)
        self.delete_account_container = DeleteAccountContainer(self)

        self.mode = mode if mode else os.environ.get("MODE", "grpc")

    def start_message_listener(self, username: str):
        """
        Starts a thread that subscribes for incoming messages and updates the UI.
        """

        def listen():
            subscribe_iter = self.grpc_client.subscribe(username)
            if subscribe_iter is None:
                logging.error("Subscribe iterator is None")
                return
            for received_msg in subscribe_iter:
                # Convert ReceivedMessage proto to dict.
                msg_dict = {
                    "timestamp": received_msg.timestamp,
                    "from": getattr(received_msg, "from"),
                    "message": received_msg.message,
                    "id": received_msg.id,
                }
                # Schedule UI update on the main thread.
                self.after(
                    0, lambda m=msg_dict: self.messages_container.add_unread_message(m)
                )

        threading.Thread(target=listen, daemon=True).start()

    def get_unread_messages(self):
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
        self.auth_box.login_form.pack_forget()
        self.auth_box.register_form.pack_forget()
        self.auth_box.toggle_button.pack_forget()
        self.delete_account_container.pack(pady=10)
        self.n_new_messages.pack(pady=10)
        self.chat_box.pack(pady=10)
        self.messages_container.pack(pady=10)

    def on_closing(self):
        self.destroy()


class AuthBox(tk.Frame):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.login_form = LoginForm(parent)
        self.register_form = RegisterForm(parent)
        self.login_form.pack(pady=10)
        self.current_form: str = "login"
        self.toggle_button: tk.Button = tk.Button(
            self,
            text="Don't have an account? Register here.",
            command=self.toggle_forms,
        )
        self.toggle_button.pack(pady=5)

    def toggle_forms(self) -> None:
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
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showwarning(
                "Input Error", "Please enter both username and password."
            )
            return
        response = self.master.grpc_client.register(username, password)
        if response and response.status == "success":
            messagebox.showinfo("Registration Succeeded", response.message)
        else:
            messagebox.showinfo("Registration Failed", response.message)
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
        username: str = self.username_entry.get().strip()
        password: str = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showwarning(
                "Input Error", "Please enter both username and password."
            )
            return
        response = self.master.grpc_client.login(username, password)
        if response and response.status == "success":
            messagebox.showinfo("Login Successful", response.message)
            self.master.n_new_messages.username = response.username
            self.master.chat_box.username = response.username
            self.master.messages_container.username = response.username
            self.master.delete_account_container.username = response.username
            self.master.grpc_client.username = response.username  # Save sender info
            self.master.switch_to_chat_screen()
            self.master.get_unread_messages()
            self.master.get_recent_messages()
            self.master.start_message_listener(response.username)
        else:
            error_msg = (
                response.message if response else "An error occurred during login."
            )
            messagebox.showerror("Login Failed", error_msg)
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)


class ChatBox(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = None
        receiver_frame = tk.Frame(self)
        receiver_frame.pack(pady=5)
        tk.Label(receiver_frame, text="Receiver Username:").pack(side=tk.LEFT, padx=5)
        self.user_list = []
        self.selected_user = tk.StringVar(self)
        self.selected_user.set("Select a user")
        self.user_dropdown = tk.OptionMenu(
            receiver_frame, self.selected_user, "Select a user", *self.user_list
        )
        self.user_dropdown.pack(side=tk.LEFT, padx=5)
        tk.Button(receiver_frame, text="Refresh", command=self.fetch_users).pack(
            side=tk.LEFT, padx=5
        )
        message_frame = tk.Frame(self)
        message_frame.pack(pady=5)
        tk.Label(message_frame, text="Message:").pack(side=tk.LEFT, padx=5)
        self.message_text = tk.Entry(message_frame, width=50)
        self.message_text.pack(side=tk.LEFT, padx=5)
        send_button = tk.Button(self, text="Send", command=self.send_message)
        send_button.pack(pady=5)
        self.error_box = tk.Label(self, text="", fg="red")
        self.error_box.pack(pady=5)
        self.error_box.pack_forget()

    def send_message(self):
        receiver = self.selected_user.get()
        message = self.message_text.get().strip()
        if not receiver or receiver == "Select a user":
            self.display_error("Receiver cannot be empty.")
            return
        if not message:
            self.display_error("Message cannot be empty.")
            return
        self.error_box.pack_forget()
        response = self.master.grpc_client.send_message(message, receiver)
        if response is None:
            logging.info(f"Sent message to {receiver}: {message}")
            messagebox.showinfo("Message Sent", f"Message sent to {receiver}.")
        else:
            logging.info(f"Response from send_message: {response}")
        self.message_text.delete(0, tk.END)
        
    def fetch_users(self):
        # Fetch users using the logged-in user's username
        users = self.master.grpc_client.get_users(self.master.grpc_client.username)
        if users:
            self.update_user_list(users)
        else:
            self.update_user_list(["No users available"])


    def display_error(self, message):
        self.error_box.config(text=message)
        self.error_box.pack()

    def update_user_list(self, users):
        if not users:
            self.selected_user.set("No users available")
            return
        self.user_list = users
        self.selected_user.set(users[0])
        menu = self.user_dropdown["menu"]
        menu.delete(0, "end")
        for user in users:
            menu.add_command(
                label=user, command=lambda value=user: self.selected_user.set(value)
            )
class MessagesContainer(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = None
        self.unread_messages_dict = {}
        self.recent_messages_dict = {}
        self.create_scrollable_sections()

    def create_scrollable_sections(self):
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
        message_ids = list(self.unread_messages_dict.keys())
        response = self.master.grpc_client.mark_as_read(message_ids)
        if response:
            for msg_id, frame in list(self.unread_messages_dict.items()):
                msg_text = frame.winfo_children()[0].cget("text")
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
        try:
            timestamp_obj = datetime.datetime.strptime(
                timestamp, "%Y-%m-%dT%H:%M:%S.%f%z"
            )
            timestamp_str = timestamp_obj.strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            logging.error("Timestamp parsing failed: %s", e)
            timestamp_str = timestamp
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
        read_button = tk.Button(
            msg_frame,
            text="Read",
            fg="green",
            command=lambda mid=msg_id, mf=msg_frame: self.read_message(mid, mf),
        )
        read_button.pack(side=tk.RIGHT, padx=5)
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
            # Extract text from the label (assumes format: "From {sender} at {timestamp}: {message}")
            try:
                msg_text = frame.winfo_children()[0].cget("text")
                # Example text: "From alice at 2025-02-11 15:30: Hello, world!"
                # First, split by " at " to separate sender and rest.
                sender_part, sep, remainder = msg_text.partition(" at ")
                sender = (
                    sender_part.split(" ")[1] if len(sender_part.split(" ")) > 1 else ""
                )
                # Now split remainder by ": " to separate timestamp and message.
                timestamp_part, sep, message_content = remainder.partition(": ")
                timestamp = timestamp_part.strip()
            except Exception as e:
                logging.error("Error parsing message text: %s", e)
                sender = ""
                timestamp = ""
                message_content = msg_text
            message_data = {
                "id": msg_id,
                "from": sender,
                "timestamp": timestamp,
                "message": message_content,
            }
            # Add the message to the recent messages section.
            self.add_recent_message(message_data)
            # Remove from unread messages UI.
            frame.destroy()
            del self.unread_messages_dict[msg_id]
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
        self.username = None

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
        # Label showing current new messages count
        # Entry for user to input a numeric value
        self.user_input = tk.Entry(self, width=10)
        self.user_input.pack(pady=5)
        # Button to set the unread messages count
        self.set_button = tk.Button(
            self, text="Set Unread Message Count", command=self.set_unread_messages
        )
        self.set_button.pack(pady=5)

    def update_count(self, count):
        self.counter = count
        # self.label.config(text=f"New Messages: {self.counter}")


class NNewMessages(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.username = ""
        self.counter = 0
        # Label showing the current unread count
        self.label = tk.Label(self, text="New Messages: 0", font=("Helvetica", 14))
        self.label.pack(pady=5)
        # Entry for the new unread messages limit
        self.user_input = tk.Entry(self, width=10)
        self.user_input.pack(pady=5)
        # Button to submit the new limit
        self.set_button = tk.Button(
            self, text="Set Unread Message Count", command=self.set_unread_messages
        )
        self.set_button.pack(pady=5)

    def update_count(self, count):
        self.counter = count
        self.label.config(text=f"New Messages: {self.counter}")

    def set_unread_messages(self) -> None:
        number = self.user_input.get().strip()
        if not number.isdigit():
            messagebox.showerror("Input Error", "Please enter a valid number.")
            return

        n_unread_messages = int(number)
        # Call the gRPC client's set_n_unread_messages method.
        response = self.master.grpc_client.set_n_unread_messages(
            self.username, n_unread_messages
        )
        if response and response.status == "success":
            messagebox.showinfo(
                "Set Unread Messages",
                f"Set to display {n_unread_messages} unread messages.",
            )
            # Now check if the current number of unread messages exceeds the new limit.
            unread_dict = self.master.messages_container.unread_messages_dict
            current_count = len(unread_dict)
            if current_count > n_unread_messages:
                # Remove the oldest messages until the count matches the new limit.
                # Assuming dictionary insertion order is preserved (Python 3.7+)
                keys_to_remove = list(unread_dict.keys())[
                    : current_count - n_unread_messages
                ]
                for key in keys_to_remove:
                    frame = unread_dict[key]
                    frame.destroy()  # Remove the UI element
                    del unread_dict[key]
        else:
            messagebox.showerror(
                "Set Unread Messages", "Failed to set unread message count."
            )


if __name__ == "__main__":
    app = ChatApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
