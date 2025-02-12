import pytest
from unittest.mock import Mock, patch, MagicMock
import threading
from datetime import datetime

# Import the module to test
# Note: Adjust the import path based on your project structure
from handlers import (
    ClientContext,
    handle_client_connection,
    handle_login,
    handle_register,
    handle_send_message,
    handle_mark_as_read,
    online_users,
    online_users_lock,
)


@pytest.fixture
def mock_conn():
    return Mock()


@pytest.fixture
def mock_addr():
    return ("127.0.0.1", 8000)


@pytest.fixture
def client_context(mock_conn, mock_addr):
    return ClientContext(mock_conn, mock_addr)


@pytest.fixture
def authenticated_context(client_context):
    client_context.authenticated = True
    client_context.username = "test_user"
    return client_context


@pytest.fixture
def mock_websocket():
    with patch("handlers.websocket") as mock:
        yield mock


@pytest.fixture
def mock_database():
    with patch("handlers.authenticate_user") as mock_auth, patch(
        "handlers.register_user"
    ) as mock_reg, patch("handlers.insert_message") as mock_insert, patch(
        "handlers.mark_messages_as_read"
    ) as mock_mark_read:

        mock_auth.return_value = True
        mock_reg.return_value = (True, "Registration successful")
        mock_insert.return_value = 1
        mock_mark_read.return_value = True

        yield {
            "authenticate": mock_auth,
            "register": mock_reg,
            "insert_message": mock_insert,
            "mark_read": mock_mark_read,
        }


class TestClientContext:
    def test_init(self, mock_conn, mock_addr):
        context = ClientContext(mock_conn, mock_addr)
        assert context.conn == mock_conn
        assert context.addr == mock_addr
        assert not context.authenticated
        assert context.username is None


class TestHandleLogin:
    def test_successful_login(
        self, authenticated_context, mock_websocket, mock_database
    ):
        data = {"action": "login", "username": "test_user", "password": "test_pass"}

        handle_login(authenticated_context, data)

        # Verify the success response was sent
        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "success"
        assert "test_user" in sent_data["message"]

    def test_login_missing_credentials(self, client_context, mock_websocket):
        data = {"action": "login"}

        handle_login(client_context, data)

        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "error"
        assert "required" in sent_data["message"].lower()


class TestHandleRegister:
    def test_successful_registration(
        self, client_context, mock_websocket, mock_database
    ):
        data = {"action": "register", "username": "new_user", "password": "new_pass"}

        handle_register(client_context, data)

        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "success"

    def test_registration_missing_data(self, client_context, mock_websocket):
        data = {"action": "register"}

        handle_register(client_context, data)

        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "error"
        assert "required" in sent_data["message"].lower()


class TestHandleSendMessage:
    def test_send_message_success(
        self, authenticated_context, mock_websocket, mock_database
    ):
        data = {"action": "send_message", "receiver": "recipient", "message": "Hello!"}

        with patch.dict("handlers.online_users", {"recipient": Mock()}):
            handle_send_message(authenticated_context, data)

            # Verify message was sent
            assert (
                mock_websocket.send_ws_frame.call_count == 2
            )  # One to recipient, one confirmation to sender

    def test_send_message_unauthenticated(self, client_context, mock_websocket):
        data = {"action": "send_message", "receiver": "recipient", "message": "Hello!"}

        handle_send_message(client_context, data)

        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "error"
        assert "authentication" in sent_data["message"].lower()


class TestHandleMarkAsRead:
    def test_mark_messages_read_success(
        self, authenticated_context, mock_websocket, mock_database
    ):
        data = {"action": "mark_as_read", "message_ids": [1, 2, 3]}

        handle_mark_as_read(authenticated_context, data)

        mock_database["mark_read"].assert_called_once()
        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "success"

    def test_mark_messages_invalid_ids(self, authenticated_context, mock_websocket):
        data = {"action": "mark_as_read", "message_ids": "not_a_list"}

        handle_mark_as_read(authenticated_context, data)

        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "error"
        assert "should be a list" in sent_data["message"]


@pytest.mark.asyncio
async def test_handle_client_connection(mock_conn, mock_addr, mock_websocket):
    with patch("handlers.perform_handshake") as mock_handshake:
        mock_handshake.return_value = True
        mock_websocket.read_ws_frame.side_effect = [None]  # Simulate connection close

        handle_client_connection(mock_conn, mock_addr)

        mock_handshake.assert_called_once()
        mock_conn.close.assert_called_once()
