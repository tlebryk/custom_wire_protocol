# server.py
import socket
import threading
from handlers import handle_client_connection

HOST = "0.0.0.0"
PORT = 8000


def main():
    """
    Main server function:
      1. Creates a TCP socket on HOST:PORT.
      2. Accepts connections in a loop.
      3. Spawns a new thread to handle each connected client.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"[*] WebSocket server listening on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            threading.Thread(
                target=handle_client_connection, args=(conn, addr), daemon=True
            ).start()


if __name__ == "__main__":
    main()
