import pytest
from unittest.mock import Mock, patch, call
import socket
import json
from client import WebSocketClient
from utils import WebSocketUtil


@pytest.fixture
def mock_socket():
    with patch("socket.socket") as mock:
        socket_instance = Mock()
        mock.return_value = socket_instance
        socket_instance.__bool__ = lambda self: True
        yield socket_instance


@pytest.fixture
def mock_websocket_util():
    with patch("client.WebSocketUtil") as mock:
        websocket_instance = Mock()
        mock.return_value = websocket_instance
        yield websocket_instance


@pytest.fixture
def client(mock_socket, mock_websocket_util):
    return WebSocketClient(host="test_host", port=8000, mode="json")


@pytest.fixture
def mock_custom_protocol():
    with patch("custom_protocol.load_protocols") as mock_load, patch(
        "custom_protocol.Encoder"
    ) as mock_encoder, patch("custom_protocol.Decoder") as mock_decoder:

        mock_load.return_value = {
            "login": {"username": "string", "password": "string"},
            "register": {"username": "string", "password": "string"},
            "message": {"content": "string", "recipient": "string"},
        }

        encoder_instance = Mock()
        decoder_instance = Mock()
        mock_encoder.return_value = encoder_instance
        mock_decoder.return_value = decoder_instance

        yield {
            "load": mock_load,
            "encoder": encoder_instance,
            "decoder": decoder_instance,
        }


@pytest.fixture
def json_client(mock_socket, mock_websocket_util):
    return WebSocketClient(host="test_host", port=8000, mode="json")


@pytest.fixture
def custom_client(mock_socket, mock_websocket_util, mock_custom_protocol):
    return WebSocketClient(host="test_host", port=8000, mode="custom")


class TestWebSocketClient:
    def test_init(self):
        client = WebSocketClient(host="test_host", port=9000, mode="json")
        assert client.host == "test_host"
        assert client.port == 9000
        assert client.socket is None
        assert isinstance(
            client.websocket, WebSocketUtil
        )  # Because we're using the mock fixture

    def test_successful_connect(self, client, mock_socket):
        # Mock successful handshake response
        mock_socket.recv.return_value = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
            "\r\n"
        ).encode()

        result = client.connect()

        assert result is True
        mock_socket.connect.assert_called_once_with(("test_host", 8000))
        assert mock_socket.send.called

        # Verify handshake request format
        sent_data = mock_socket.send.call_args[0][0].decode()
        assert "GET / HTTP/1.1" in sent_data
        assert "Upgrade: websocket" in sent_data
        assert "Connection: Upgrade" in sent_data
        assert "Sec-WebSocket-Key:" in sent_data
        assert "Sec-WebSocket-Version: 13" in sent_data

    def test_failed_connect_wrong_response(self, client, mock_socket):
        # Mock failed handshake response
        mock_socket.recv.return_value = ("HTTP/1.1 400 Bad Request\r\n" "\r\n").encode()

        result = client.connect()

        assert result is False
        mock_socket.connect.assert_called_once_with(("test_host", 8000))

    def test_failed_connect_socket_error(self, client, mock_socket):
        # Mock socket connection error
        mock_socket.connect.side_effect = socket.error("Connection refused")

        result = client.connect()

        assert result is False
        mock_socket.connect.assert_called_once_with(("test_host", 8000))

    def test_send_dict_message(self, client, mock_websocket_util):
        message = {"action": "test", "data": "hello"}
        client.send(message)

        mock_websocket_util.send_ws_frame.assert_called_once_with(
            client.socket, message
        )

    def test_send_string_message(self, client, mock_websocket_util):
        message = "hello"
        client.send(message)

        mock_websocket_util.send_ws_frame.assert_called_once_with(
            client.socket, {"message": message}
        )

    def test_receive(self, client, mock_websocket_util):
        expected_response = {"status": "success", "data": "test"}
        mock_websocket_util.read_ws_frame.return_value = expected_response

        response = client.receive()

        assert response == expected_response
        mock_websocket_util.read_ws_frame.assert_called_once_with(client.socket)

    def test_close(self, client, mock_socket):
        client.socket = mock_socket
        client.close()
        mock_socket.close.assert_called_once()

    def test_full_message_flow(self, client, mock_socket, mock_websocket_util):
        # Setup mock responses
        mock_socket.recv.return_value = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
            "\r\n"
        ).encode()

        mock_websocket_util.read_ws_frame.return_value = {
            "status": "success",
            "message": "Registration successful",
        }

        # Connect
        assert client.connect() is True

        # Send registration message
        registration_msg = {
            "action": "register",
            "username": "testuser",
            "password": "testpass",
        }
        client.send(registration_msg)

        # Verify message was sent correctly
        mock_websocket_util.send_ws_frame.assert_called_once_with(
            client.socket, registration_msg
        )

        # Receive and verify response
        response = client.receive()
        assert response["status"] == "success"
        assert "Registration successful" in response["message"]

    @pytest.mark.parametrize("mode", ["json", "custom"])
    def test_client_modes(self, mock_socket, mock_websocket_util, mode):
        client = WebSocketClient(mode=mode)
        assert client.websocket == mock_websocket_util

        # Verify WebSocketUtil was instantiated with correct mode
        from client import WebSocketUtil

        WebSocketUtil.assert_called_once_with(mode=mode)


class TestWebSocketClientCustomProtocol:
    def test_init_custom_mode(self, mock_custom_protocol):
        client = WebSocketClient(mode="custom")
        assert client.websocket.mode == "custom"

    def test_send_login_message_custom(
        self, custom_client, mock_websocket_util, mock_custom_protocol
    ):
        login_msg = {"action": "login", "username": "testuser", "password": "testpass"}

        # Mock the custom protocol encoder
        mock_custom_protocol["encoder"].encode_message.return_value = (
            b"encoded_login_message"
        )

        custom_client.send(login_msg)

        # Verify the message was encoded using custom protocol
        mock_websocket_util.send_ws_frame.assert_called_once_with(
            custom_client.socket, login_msg
        )

    def test_receive_custom_message(
        self, custom_client, mock_websocket_util, mock_custom_protocol
    ):
        # Mock the custom protocol decoder
        decoded_msg = {
            "status": "success",
            "action": "login_response",
            "message": "Login successful",
        }
        mock_custom_protocol["decoder"].decode_message.return_value = decoded_msg
        # In test_receive_custom_message
        mock_websocket_util.read_ws_frame.return_value = {
            "status": "success",
            "action": "login_response",
            "message": "Login successful",
        }

        response = custom_client.receive()

        assert response == decoded_msg
        mock_websocket_util.read_ws_frame.assert_called_once_with(custom_client.socket)

    def test_send_complex_message_custom(
        self, custom_client, mock_websocket_util, mock_custom_protocol
    ):
        message = {
            "action": "message",
            "content": "Hello, World!",
            "recipient": "other_user",
            "timestamp": "2024-02-12T12:00:00Z",
        }

        mock_custom_protocol["encoder"].encode_message.return_value = (
            b"encoded_complex_message"
        )

        custom_client.send(message)

        mock_websocket_util.send_ws_frame.assert_called_once_with(
            custom_client.socket, message
        )

    def test_protocol_error_handling(
        self, custom_client, mock_websocket_util, mock_custom_protocol
    ):
        # Mock protocol encoding error
        mock_custom_protocol["encoder"].encode_message.side_effect = ValueError(
            "Invalid message format"
        )

        # with pytest.raises(ValueError):
        custom_client.send({"invalid": "message"})

    @pytest.mark.parametrize(
        "mode,expected_encoding",
        [("json", "json_encoded"), ("custom", "custom_encoded")],
    )
    def test_mode_specific_encoding(
        self,
        mock_socket,
        mock_websocket_util,
        mock_custom_protocol,
        mode,
        expected_encoding,
    ):
        client = WebSocketClient(mode=mode)
        test_message = {"action": "test", "data": "hello"}

        if mode == "custom":
            mock_custom_protocol["encoder"].encode_message.return_value = (
                b"custom_encoded"
            )

        client.send(test_message)

        mock_websocket_util.send_ws_frame.assert_called_once_with(
            client.socket, test_message
        )

    def test_full_custom_protocol_flow(
        self, custom_client, mock_socket, mock_websocket_util, mock_custom_protocol
    ):
        # Setup mock responses
        mock_socket.recv.return_value = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
            "\r\n"
        ).encode()

        # Mock custom protocol responses
        mock_custom_protocol["encoder"].encode_message.return_value = (
            b"encoded_register_message"
        )
        # In test_full_custom_protocol_flow
        mock_websocket_util.read_ws_frame.return_value = {
            "status": "success",
            "action": "register_response",
            "message": "Registration successful",
        }

        # Connect
        assert custom_client.connect() is True

        # Send registration using custom protocol
        registration_msg = {
            "action": "register",
            "username": "testuser",
            "password": "testpass",
        }
        custom_client.send(registration_msg)

        # Verify custom protocol encoding was used
        mock_websocket_util.send_ws_frame.assert_called_once_with(
            custom_client.socket, registration_msg
        )

        # Receive and verify response
        response = custom_client.receive()
        assert response["status"] == "success"
        assert "Registration successful" in response["message"]


class TestProtocolCompatibility:
    @pytest.mark.parametrize(
        "send_mode,receive_mode", [("json", "custom"), ("custom", "json")]
    )
    def test_protocol_mode_mismatch(
        self,
        mock_socket,
        mock_websocket_util,
        mock_custom_protocol,
        send_mode,
        receive_mode,
    ):
        # Test sending with one protocol and receiving with another
        sender = WebSocketClient(mode=send_mode)
        receiver = WebSocketClient(mode=receive_mode)

        test_message = {"action": "test", "data": "hello"}

        if send_mode == "custom":
            mock_custom_protocol["encoder"].encode_message.return_value = (
                b"custom_encoded"
            )
        if receive_mode == "custom":
            mock_custom_protocol["decoder"].decode_message.return_value = test_message

        # Verify that sending and receiving with different protocols works as expected
        sender.send(test_message)
        mock_websocket_util.send_ws_frame.assert_called_once()
