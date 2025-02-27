import socket
import json
from utils import perform_handshake, WebSocketUtil
from typing import Union, Dict, Any
import os


class WebSocketClient:
    def __init__(self, host=None, port=8000, mode=None):
        if not host:
            host = os.environ.get("HOST", "localhost")
        self.host = host
        self.port = port
        self.socket = None
        self.websocket = WebSocketUtil(mode=mode)
        # self.running = False

    def connect(self):
        """Establish connection and perform WebSocket handshake"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))

            # Send WebSocket handshake request
            handshake_request = (
                "GET / HTTP/1.1\r\n"
                f"Host: {self.host}:{self.port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"  # Example key
                "Sec-WebSocket-Version: 13\r\n"
                "\r\n"
            )
            self.socket.send(handshake_request.encode())

            # Receive and verify handshake response
            response = self.socket.recv(1024).decode()
            if "101 Switching Protocols" not in response:
                raise Exception("Handshake failed")
            self.connected = True
            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def send(self, message: Union[Dict, str]) -> None:
        """Send a message to the server

        Args:
            message (Union[dict, str]): The message to send. If a dict, it will be sent as a JSON-encoded text frame. If a str, it will be sent as a text frame with the string as the payload.
        """
        if isinstance(message, dict):
            self.websocket.send_ws_frame(self.socket, message)
        else:
            self.websocket.send_ws_frame(self.socket, {"message": message})

    def receive(self):
        """Receive a message from the server"""

        return self.websocket.read_ws_frame(self.socket)

    def close(self):
        """Close the WebSocket connection"""
        if self.socket:
            print("Closing connection...")
            self.socket.close()


# Example usage
if __name__ == "__main__":
    client = WebSocketClient()
    if client.connect():
        # Example: Register a new user
        client.send(
            {"action": "register", "username": "testuser", "password": "testpass"}
        )

        # Receive response
        response = client.receive()
        print(f"Received: {response}")

        client.close()
