# utils.py
import socket
import hashlib
import base64
import struct
import json  # Added import for json

MAGIC_STRING = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def perform_handshake(conn):
    """
    Reads the client's HTTP handshake request, parses out the Sec-WebSocket-Key,
    and responds with the appropriate 101 Switching Protocols and
    Sec-WebSocket-Accept header.
    """
    try:
        request = conn.recv(1024).decode("utf-8", errors="ignore")
        headers = {}
        lines = request.split("\r\n")
        for line in lines[1:]:
            if ": " in line:
                key, value = line.split(": ", 1)
                headers[key.lower()] = value

        ws_key = headers.get("sec-websocket-key")
        if not ws_key:
            print("[-] WebSocket key not found.")
            return False

        accept_val = generate_accept_key(ws_key)
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_val}\r\n"
            "\r\n"
        )
        conn.sendall(response.encode("utf-8"))
        return True
    except Exception as e:
        print(f"[-] Handshake failed: {e}")
        return False

def generate_accept_key(key):
    """
    Generates Sec-WebSocket-Accept from Sec-WebSocket-Key.
    """
    combined = key + MAGIC_STRING
    sha1 = hashlib.sha1(combined.encode('utf-8')).digest()
    return base64.b64encode(sha1).decode('utf-8')

def read_ws_frame(conn):
    """
    Reads a single WebSocket frame and returns the decoded payload as a string.
    Returns None if connection is closed or on error.
    """
    try:
        # Read the first two bytes of the frame
        header = conn.recv(2)
        if len(header) < 2:
            return None

        b1, b2 = header
        fin = (b1 >> 7) & 1
        opcode = b1 & 0x0F
        masked = (b2 >> 7) & 1
        payload_len = b2 & 0x7F

        if payload_len == 126:
            extended_payload = conn.recv(2)
            payload_len = struct.unpack(">H", extended_payload)[0]
        elif payload_len == 127:
            extended_payload = conn.recv(8)
            payload_len = struct.unpack(">Q", extended_payload)[0]

        if masked:
            masking_key = conn.recv(4)

        payload_data = b""
        remaining = payload_len
        while remaining > 0:
            chunk = conn.recv(remaining)
            if not chunk:
                break
            payload_data += chunk
            remaining -= len(chunk)

        if masked:
            payload_data = bytes(b ^ masking_key[i % 4] for i, b in enumerate(payload_data))

        if opcode == 0x8:
            # Close frame
            return None
        elif opcode == 0x1:
            # Text frame
            return payload_data.decode('utf-8', errors='ignore')
        else:
            # For simplicity, ignore other opcodes
            return None

    except Exception as e:
        print(f"[-] Error reading frame: {e}")
        return None

def send_ws_frame(conn, message):
    """
    Sends a JSON-encoded text frame to the client.
    """
    try:
        if isinstance(message, dict):
            payload = json.dumps(message).encode('utf-8')
        else:
            payload = str(message).encode('utf-8')

        payload_len = len(payload)
        frame = bytearray()

        # First byte: FIN=1 and opcode=1 (text)
        frame.append(0x81)

        # Determine payload length
        if payload_len <= 125:
            frame.append(payload_len)
        elif payload_len <= 65535:
            frame.append(126)
            frame.extend(struct.pack(">H", payload_len))
        else:
            frame.append(127)
            frame.extend(struct.pack(">Q", payload_len))

        # Server-to-client frames are not masked
        frame.extend(payload)

        conn.sendall(frame)
    except Exception as e:
        print(f"[-] Error sending frame: {e}")
