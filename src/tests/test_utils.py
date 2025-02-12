import pytest
from unittest.mock import Mock, patch, MagicMock
import base64
import hashlib
import struct
import json
from utils import (
    WebSocketUtil,
    perform_handshake,
    generate_accept_key,
    MAGIC_STRING,
)


@pytest.fixture
def mock_conn():
    return Mock()


@pytest.fixture
def websocket_util():
    return WebSocketUtil(mode="json")


@pytest.fixture
def sample_message():
    return {"action": "test", "data": "Hello, World!"}


def test_generate_accept_key():
    # Test with a known key and expected output
    test_key = "dGhlIHNhbXBsZSBub25jZQ=="
    expected = base64.b64encode(
        hashlib.sha1((test_key + MAGIC_STRING).encode("utf-8")).digest()
    ).decode("utf-8")

    result = generate_accept_key(test_key)
    assert result == expected


class TestHandshake:
    def test_successful_handshake(self, mock_conn):
        # Prepare mock data
        request = (
            "GET /chat HTTP/1.1\r\n"
            "Host: server.example.com\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Origin: http://example.com\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )

        mock_conn.recv.return_value = request.encode("utf-8")

        # Test handshake
        result = perform_handshake(mock_conn)

        assert result is True
        mock_conn.sendall.assert_called_once()

    def test_handshake_missing_key(self, mock_conn):
        # Request without Sec-WebSocket-Key
        request = (
            "GET /chat HTTP/1.1\r\n"
            "Host: server.example.com\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n\r\n"
        )

        mock_conn.recv.return_value = request.encode("utf-8")

        result = perform_handshake(mock_conn)
        assert result is False


class TestWebSocketUtil:
    def test_init_default_mode(self):
        ws_util = WebSocketUtil(mode="json")
        assert ws_util.mode == "json"
        assert ws_util.encoder is None
        assert ws_util.decoder is None

    def test_init_custom_mode(self):
        with patch("custom_protocol.load_protocols") as mock_load:
            mock_load.return_value = {"action_ids": {}, "messages": {}}
            ws_util = WebSocketUtil(mode="custom")
            assert ws_util.mode == "custom"
            assert ws_util.encoder is not None
            assert ws_util.decoder is not None

    def test_send_small_frame(self, websocket_util, mock_conn, sample_message):
        websocket_util.send_ws_frame(mock_conn, sample_message)

        mock_conn.sendall.assert_called_once()
        frame = mock_conn.sendall.call_args[0][0]

        # Check frame format
        assert frame[0] == WebSocketUtil.WS_FIN_TEXT_FRAME
        assert frame[1] < WebSocketUtil.WS_PAYLOAD_LEN_8BIT_MAX

    def test_send_medium_frame(self, websocket_util, mock_conn):
        # Create a message that will result in a medium-length frame
        large_message = {"data": "x" * 1000}

        websocket_util.send_ws_frame(mock_conn, large_message)

        mock_conn.sendall.assert_called_once()
        frame = mock_conn.sendall.call_args[0][0]

        # Check frame format
        assert frame[0] == WebSocketUtil.WS_FIN_TEXT_FRAME
        assert frame[1] == WebSocketUtil.WS_PAYLOAD_LEN_16BIT

    def test_read_text_frame(self, websocket_util, mock_conn):
        # Prepare a simple text frame
        message = json.dumps({"test": "data"}).encode("utf-8")
        payload_len = len(message)

        # Create frame header
        header = bytes(
            [
                WebSocketUtil.WS_FIN_TEXT_FRAME,  # FIN + Text opcode
                payload_len,  # Unmasked, small payload
            ]
        )

        # Mock the socket receives
        mock_conn.recv.side_effect = [header, message]

        result = websocket_util.read_ws_frame(mock_conn)
        assert result == {"test": "data"}

    def test_read_masked_frame(self, websocket_util, mock_conn):
        # Prepare a masked text frame
        message = json.dumps({"test": "data"}).encode("utf-8")
        payload_len = len(message)
        mask_key = b"mask"

        # Create masked payload
        masked_payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(message))

        # Create frame header
        header = bytes(
            [
                WebSocketUtil.WS_FIN_TEXT_FRAME,  # FIN + Text opcode
                WebSocketUtil.WS_MASK_BIT | payload_len,  # Masked, small payload
            ]
        )

        # Mock the socket receives
        mock_conn.recv.side_effect = [header, mask_key, masked_payload]

        result = websocket_util.read_ws_frame(mock_conn)
        assert result == {"test": "data"}

    def test_read_close_frame(self, websocket_util, mock_conn):
        # Prepare a close frame
        header = bytes([0x88, 0x00])  # FIN + Close opcode  # Unmasked, zero length

        mock_conn.recv.return_value = header

        result = websocket_util.read_ws_frame(mock_conn)
        assert result is None


def test_error_handling(websocket_util, mock_conn):
    mock_conn.recv.side_effect = Exception("Connection error")

    result = websocket_util.read_ws_frame(mock_conn)
    assert result is None
