# tkinter_app.py
import tkinter as tk
from tkinter import messagebox
import threading
from client import GRPCClient


class ChatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("gRPC Chat App")
        self.geometry("400x300")

        # Initialize the gRPC client.
        # Create a simple login form.

        self.username_entry = tk.Entry(self)
        self.username_entry.pack(pady=10)
        self.username_entry.insert(0, "Username")

        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack(pady=10)
        self.password_entry.insert(0, "Password")

        self.login_button = tk.Button(self, text="Login", command=self.login)
        self.login_button.pack(pady=10)

        # For testing echo/ping.
        self.echo_button = tk.Button(self, text="Ping Server", command=self.echo)
        self.echo_button.pack(pady=10)

        self.response_label = tk.Label(self, text="Response:")
        self.response_label.pack(pady=10)
        self.grpc_client = GRPCClient()

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        # Run the gRPC login call in a background thread.
        threading.Thread(
            target=self.do_login, args=(username, password), daemon=True
        ).start()

    def do_login(self, username, password):
        try:
            response = self.grpc_client.login(username, password)
            # Schedule the UI update on the main thread.
            self.after(0, lambda: self.handle_login_response(response))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Login Error", str(e)))

    def handle_login_response(self, response):
        # Update the UI based on the login response.
        # For example, show a message or transition to the chat screen.
        messagebox.showinfo("Login Response", f"Message: {response.message}")

    def echo(self):
        # Test echo/ping
        threading.Thread(target=self.do_echo, args=("ping",), daemon=True).start()

    def do_echo(self, message):
        try:
            response = self.grpc_client.echo(message)
            self.after(
                0,
                lambda: self.response_label.config(
                    text=f"Echo Response: {response.message}"
                ),
            )
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Echo Error", str(e)))


if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()
