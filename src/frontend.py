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

    # Stubs for other calls (to be implemented later)
    def send_message(self, message: str, receiver: str):
        pass

    def get_recent_messages(self, username: str):
        pass

    def get_unread_messages(self, username: str):
        pass

    def mark_as_read(self, message_ids: list):
        pass

    def set_n_unread_messages(self, username: str, n: int):
        pass

    def delete_message(self, username: str, message_id: int):
        pass

    def delete_account(self, username: str):
        pass


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

        # Initialize Chat Screen Components (stubs)
        self.n_new_messages = NNewMessages(self)
        self.chat_box = ChatBox(self)
        self.messages_container = MessagesContainer(self)
        self.delete_account_container = DeleteAccountContainer(self)

        self.mode = mode if mode else os.environ.get("MODE", "grpc")

        # For gRPC, calls are synchronous so we don't need a continuous listening thread
        # Additional functionality can be added later.

    def get_unread_messages(self):
        # Stub: implement retrieval of unread messages via gRPC later
        pass

    def get_recent_messages(self):
        # Stub: implement retrieval of recent messages via gRPC later
        pass

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
        if response:
            messagebox.showinfo("Login Successful", response.message)
            # Set username in chat components
            self.master.n_new_messages.username = response.username
            self.master.chat_box.username = response.username
            self.master.messages_container.username = response.username
            self.master.delete_account_container.username = response.username
            self.master.switch_to_chat_screen()
            # Optionally, retrieve messages after login
            self.master.get_unread_messages()
            self.master.get_recent_messages()
        else:
            messagebox.showerror("Login Failed", "An error occurred during login.")

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
        # Call the gRPC client's send_message method (stubbed for now)
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
        self.recent_label = tk.Label(
            self, text="Recent Messages", font=("Helvetica", 14)
        )
        self.recent_label.pack(pady=5)
        self.recent_text = tk.Text(self, height=10, width=80)
        self.recent_text.pack(pady=5)

        self.unread_label = tk.Label(
            self, text="Unread Messages", font=("Helvetica", 14)
        )
        self.unread_label.pack(pady=5)
        self.unread_text = tk.Text(self, height=10, width=80)
        self.unread_text.pack(pady=5)

    def add_recent_message(self, msg):
        display_text = (
            f"{msg.get('timestamp')} - {msg.get('from')}: {msg.get('message')}\n"
        )
        self.recent_text.insert(tk.END, display_text)
        self.recent_text.see(tk.END)

    def add_unread_message(self, msg):
        display_text = (
            f"{msg.get('timestamp')} - {msg.get('from')}: {msg.get('message')}\n"
        )
        self.unread_text.insert(tk.END, display_text)
        self.unread_text.see(tk.END)


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
            # Replace this stub with the actual gRPC call to delete the account.
            messagebox.showinfo("Delete Account", "Account deletion requested (stub).")


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
