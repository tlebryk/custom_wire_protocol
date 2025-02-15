# utils.py
import sys
import hashlib
import base64
import struct
import json  # Added import for json
import logging
import custom_protocol
import traceback
import os
import socket
from typing import Dict, Any, Optional, Union

MAGIC_STRING = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WS_FIN_TEXT_FRAME = 0x81  # FIN=1, Opcode=1 (text frame)
# Opcode=1: Text frame, where the payload data is text data encoded as UTF-8
WS_PAYLOAD_LEN_8BIT_MAX = 125  # Max payload size for a single byte length
WS_PAYLOAD_LEN_16BIT = 126  # Indicator for 16-bit payload length
WS_PAYLOAD_LEN_16BIT_MAX = 65535  # Max payload size for 16-bit length
WS_PAYLOAD_LEN_64BIT = 127

# Struct format strings for big-endian encoding
WS_16BIT_LEN_FORMAT = ">H"  # Unsigned 16-bit big-endian integer
WS_64BIT_LEN_FORMAT = ">Q"  # Unsigned 64-bit big-endian integer

# WebSocket Frame Constants
WS_HEADER_SIZE = 2  # Initial header size in bytes
WS_MASK_BIT = 0x80  # Mask bit flag (1000 0000)
WS_PAYLOAD_LEN_MASK = 0x7F  # Mask to extract payload length (0111 1111)
WS_OPCODE_MASK = 0x0F  # Mask to extract opcode (0000 1111)

WS_OPCODE_CLOSE = 0x8  # Opcode for Close Frame
WS_OPCODE_TEXT = 0x1  # Opcode for Text Frame


def perform_handshake(conn: socket.socket) -> bool:
    """
    Reads the client's HTTP handshake request, parses out the Sec-WebSocket-Key,
    and responds with the appropriate 101 Switching Protocols and
    Sec-WebSocket-Accept header.

    Args:
        conn (socket.socket): The socket connection to the client.

    Returns:
        bool: True if the handshake was successful, False otherwise.
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


def generate_accept_key(key: str) -> str:
    """
    Generates Sec-WebSocket-Accept from Sec-WebSocket-Key.

    Args:
        key (str): The Sec-WebSocket-Key to generate the accept key from.

    Returns:
        str: The generated Sec-WebSocket-Accept key.
    """
    combined = key + MAGIC_STRING
    sha1 = hashlib.sha1(combined.encode("utf-8")).digest()
    return base64.b64encode(sha1).decode("utf-8")


class WebSocketUtil:
    """
    Utility class for working with WebSockets.
    """

    WS_FIN_TEXT_FRAME = 0x81  # FIN=1, Opcode=1 (text frame)
    WS_PAYLOAD_LEN_8BIT_MAX = 125  # Max payload size for a single byte length
    WS_PAYLOAD_LEN_16BIT = 126  # Indicator for 16-bit payload length
    WS_PAYLOAD_LEN_16BIT_MAX = 65535  # Max payload size for 16-bit length
    WS_PAYLOAD_LEN_64BIT = 127

    # Struct format strings for big-endian encoding
    WS_16BIT_LEN_FORMAT = ">H"  # Unsigned 16-bit big-endian integer
    WS_64BIT_LEN_FORMAT = ">Q"  # Unsigned 64-bit big-endian integer

    # WebSocket Frame Constants
    WS_HEADER_SIZE = 2  # Initial header size in bytes
    WS_MASK_BIT = 0x80  # Mask bit flag (1000 0000)
    WS_PAYLOAD_LEN_MASK = 0x7F  # Mask to extract payload length (0111 1111)
    WS_OPCODE_MASK = 0x0F  # Mask to extract opcode (0000 1111)

    WS_OPCODE_CLOSE = 0x8  # Opcode for Close Frame
    WS_OPCODE_TEXT = 0x1  # Opcode for Text Frame

    def __init__(self, mode=None):
        self.mode = mode
        if not mode:
            self.mode = os.environ.get("MODE", "json")
            logging.warning(f"Using mode: {self.mode}")
        if mode != "json":
            self.encoder = custom_protocol.Encoder(custom_protocol.load_protocols())
            self.decoder = custom_protocol.Decoder(custom_protocol.load_protocols())
        else:
            self.encoder = None
            self.decoder = None

    def handshake(self, conn: socket.socket, key: str) -> bool:
        """
        Performs the initial WebSocket handshake.

        Args:
            conn (socket.socket): The socket connection to the client.
            key (str): The Sec-WebSocket-Key to generate the accept key from.

        Returns:
            bool: True if the handshake was successful, False otherwise.
        """
        response = generate_accept_key(key)
        response += "Upgrade: websocket\r\n"
        response += "Connection: Upgrade\r\n\r\n"
        conn.sendall(response.encode("utf-8"))
        return True

    def read_ws_frame(self, conn: socket.socket) -> Dict[str, Any]:
        """
        Reads a single WebSocket frame and returns the decoded payload as a dictionary.
        Returns None if connection is closed or on error.

        Args:
            conn (socket.socket): The socket connection to the client.

        Returns:
            Dict[str, Any] or None: The decoded payload as a dictionary, or None if connection is closed or on error.
        """
        try:
            # Read the first two bytes of the frame
            header = conn.recv(self.WS_HEADER_SIZE)
            if len(header) < self.WS_HEADER_SIZE:
                return None

            b1, b2 = header
            fin = (b1 >> 7) & 1
            opcode = b1 & self.WS_OPCODE_MASK
            masked = (b2 >> 7) & 1
            payload_len = b2 & self.WS_PAYLOAD_LEN_MASK

            if payload_len == self.WS_PAYLOAD_LEN_16BIT:
                extended_payload = conn.recv(2)
                payload_len = struct.unpack(self.WS_16BIT_LEN_FORMAT, extended_payload)[
                    0
                ]
            elif payload_len == self.WS_PAYLOAD_LEN_64BIT:
                extended_payload = conn.recv(8)
                payload_len = struct.unpack(self.WS_64BIT_LEN_FORMAT, extended_payload)[
                    0
                ]

            if masked:
                masking_key = conn.recv(4)
            logging.warning(f"\n\nPayload Length: {payload_len}")
            payload_data = b""
            remaining = payload_len
            while remaining > 0:
                chunk = conn.recv(remaining)
                if not chunk:
                    break
                payload_data += chunk
                remaining -= len(chunk)

            if masked:
                payload_data = bytes(
                    b ^ masking_key[i % 4] for i, b in enumerate(payload_data)
                )

            if opcode == self.WS_OPCODE_CLOSE:
                # Close frame
                return None
            elif opcode == self.WS_OPCODE_TEXT:
                # Text frame
                if self.mode == "json":
                    message = payload_data.decode("utf-8", errors="ignore")
                    data = json.loads(message)
                else:
                    decoder = custom_protocol.Decoder(custom_protocol.load_protocols())
                    logging.warning(f"READ PAYLOAD DATA: {payload_data}")
                    data = decoder.decode_message(payload_data)
                    logging.warning(f"READ DATA: {data}")

                return data

            else:
                # For simplicity, ignore other opcodes
                return None

        except Exception as e:
            print(traceback.format_exc())
            print(f"[-] Error reading frame: {e}")
            return None

    def send_ws_frame(self, conn: socket.socket, message: Union[dict, str]) -> None:
        """
        Sends a JSON-encoded text frame to the client.

        :param conn: The socket connection to send the frame over
        :param message: The message to encode and send, either a dictionary or a string
        :return: None
        """
        try:
            logging.warning(f"Sending message: {message}")
            if self.mode == "json":
                if isinstance(message, dict):
                    payload = json.dumps(message).encode("utf-8")
                else:
                    payload = str(message).encode("utf-8")
            else:
                # TODO: handle state elsewhere
                encoder = custom_protocol.Encoder(custom_protocol.load_protocols())
                payload = encoder.encode_message(message)
                logging.warning(f"WRITE PAYLOAD DATA: {payload}")

            logging.warning(f"Sending frame: {payload}")
            payload_len = len(payload)
            logging.warning("\n\nPayload Length: " + str(payload_len))
            frame = bytearray()

            # First byte: FIN=1 and opcode=1 (text)
            frame.append(self.WS_FIN_TEXT_FRAME)

            # Determine payload length
            if payload_len < self.WS_PAYLOAD_LEN_8BIT_MAX:
                frame.append(payload_len)
            elif payload_len <= self.WS_PAYLOAD_LEN_16BIT_MAX:
                #
                frame.append(self.WS_PAYLOAD_LEN_16BIT)
                frame.extend(struct.pack(self.WS_16BIT_LEN_FORMAT, payload_len))
            else:
                frame.append(self.WS_PAYLOAD_LEN_64BIT)
                frame.extend(struct.pack(self.WS_64BIT_LEN_FORMAT, payload_len))

            # Server-to-client frames are not masked
            frame.extend(payload)
            # get size in bytes of frame

            print(f"Size of frame: {sys.getsizeof(frame)}")
            # append it to a file
            with open("frame_size.txt", "a") as f:
                f.write(f"{sys.getsizeof(frame)}\n")
            with open("frame_size.txt", "w") as f:
                f.write(str(sys.getsizeof(frame)))

            conn.sendall(frame)
        except Exception as e:
            print(f"[-] Error sending frame: {e}")
