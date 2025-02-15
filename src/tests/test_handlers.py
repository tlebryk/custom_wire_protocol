import pytest
from unittest.mock import Mock, patch, MagicMock
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
    handle_set_n_unread_messages,
    handle_unknown_action,
    handle_echo,
    handle_recent_messages,
    handle_unread_messages,
    handle_delete_message,
    handle_get_users,
    handle_delete_account,
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
    with patch("handlers.websocket") as mock_ws:
        yield mock_ws


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
            # One message to the recipient and one confirmation to sender
            assert mock_websocket.send_ws_frame.call_count == 2

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


class TestHandleSetNUnreadMessages:
    def test_missing_n_unread_messages(self, authenticated_context, mock_websocket):
        data = {"action": "set_n_unread_messages"}
        handle_set_n_unread_messages(authenticated_context, data)

        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "error"
        assert "number of unread messages is required" in sent_data["message"].lower()

    def test_set_n_unread_messages_success(self, authenticated_context, mock_websocket):
        data = {"action": "set_n_unread_messages", "n_unread_messages": 25}
        with patch("handlers.set_n_unread_messages", return_value=True) as mock_set_n:
            handle_set_n_unread_messages(authenticated_context, data)
            mock_set_n.assert_called_once_with("test_user", 25)

            mock_websocket.send_ws_frame.assert_called_once()
            sent_data = mock_websocket.send_ws_frame.call_args[0][1]
            assert sent_data["status"] == "success"
            assert sent_data["action"] == "confirm_set_n_unread_messages"
            assert "successfully" in sent_data["message"].lower()

    def test_set_n_unread_messages_failure(self, authenticated_context, mock_websocket):
        data = {"action": "set_n_unread_messages", "n_unread_messages": 10}
        with patch("handlers.set_n_unread_messages", return_value=False) as mock_set_n:
            handle_set_n_unread_messages(authenticated_context, data)
            mock_set_n.assert_called_once_with("test_user", 10)

            mock_websocket.send_ws_frame.assert_called_once()
            sent_data = mock_websocket.send_ws_frame.call_args[0][1]
            assert sent_data["status"] == "error"
            assert (
                "failed to set number of unread messages"
                in sent_data["message"].lower()
            )


class TestHandleUnknownAction:
    def test_unknown_action(self, client_context, mock_websocket):
        handle_unknown_action(client_context, "nonexistent_action")
        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "error"
        assert "unknown action" in sent_data["message"].lower()


class TestHandleEcho:
    def test_echo(self, client_context, mock_websocket):
        data = {"action": "echo", "message": "Echo this!"}
        handle_echo(client_context, data)
        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "success"
        assert sent_data["action"] == "confirm_echo"
        assert sent_data["message"] == "Echo this!"


class TestHandleRecentMessages:
    def test_recent_messages_authenticated(self, authenticated_context, mock_websocket):
        # Patch get_user_info and get_recent_messages
        fake_user_info = ("ignored", 20)  # second element is n_unread_messages
        fake_recent_msgs = [
            ("alice", "Hello", "test_user", datetime.utcnow().isoformat() + "Z", 101),
            ("bob", "Hi there", "test_user", datetime.utcnow().isoformat() + "Z", 102),
        ]
        with patch(
            "handlers.get_user_info", return_value=fake_user_info
        ) as mock_get_info, patch(
            "handlers.get_recent_messages", return_value=fake_recent_msgs
        ) as mock_get_recent:
            handle_recent_messages(
                authenticated_context, {"action": "get_recent_messages"}
            )
            mock_get_info.assert_called_once_with("test_user")
            mock_get_recent.assert_called_once_with("test_user", limit=20)
            # Check that the recent messages were sent
            mock_websocket.send_ws_frame.assert_called_once()
            sent_data = mock_websocket.send_ws_frame.call_args[0][1]
            assert sent_data["action"] == "recent_messages"
            # Verify formatted messages contain expected keys
            for msg in sent_data["messages"]:
                assert "from" in msg
                assert "message" in msg
                assert "timestamp" in msg
                assert "id" in msg

    def test_recent_messages_no_user_info(self, authenticated_context, mock_websocket):
        # If get_user_info returns None, it should default to 50 messages
        fake_recent_msgs = []
        with patch("handlers.get_user_info", return_value=None) as mock_get_info, patch(
            "handlers.get_recent_messages", return_value=fake_recent_msgs
        ) as mock_get_recent:
            handle_recent_messages(
                authenticated_context, {"action": "get_recent_messages"}
            )
            mock_get_info.assert_called_once_with("test_user")
            mock_get_recent.assert_called_once_with("test_user", limit=50)
            mock_websocket.send_ws_frame.assert_called_once()


class TestHandleUnreadMessages:
    def test_unread_messages_authenticated_with_msgs(
        self, authenticated_context, mock_websocket
    ):
        fake_user_info = ("ignored", 10)
        fake_unread_msgs = [
            (201, "charlie", "Hey!", datetime.utcnow().isoformat() + "Z"),
        ]
        with patch(
            "handlers.get_user_info", return_value=fake_user_info
        ) as mock_get_info, patch(
            "handlers.get_unread_messages", return_value=fake_unread_msgs
        ) as mock_get_unread:
            handle_unread_messages(
                authenticated_context, {"action": "get_unread_messages"}
            )
            mock_get_info.assert_called_once_with("test_user")
            mock_get_unread.assert_called_once_with("test_user", limit=10)
            mock_websocket.send_ws_frame.assert_called_once()
            sent_data = mock_websocket.send_ws_frame.call_args[0][1]
            assert sent_data["action"] == "unread_messages"
            assert len(sent_data["messages"]) == 1

    def test_unread_messages_authenticated_empty(
        self, authenticated_context, mock_websocket
    ):
        fake_user_info = ("ignored", 10)
        with patch(
            "handlers.get_user_info", return_value=fake_user_info
        ) as mock_get_info, patch(
            "handlers.get_unread_messages", return_value=[]
        ) as mock_get_unread:
            handle_unread_messages(
                authenticated_context, {"action": "get_unread_messages"}
            )
            mock_get_info.assert_called_once_with("test_user")
            mock_get_unread.assert_called_once_with("test_user", limit=10)
            mock_websocket.send_ws_frame.assert_called_once()
            sent_data = mock_websocket.send_ws_frame.call_args[0][1]
            # Should return an empty list with a message indicating no unread messages
            assert sent_data["action"] == "unread_messages"
            assert sent_data["messages"] == []


class TestHandleDeleteMessage:
    def test_delete_message_invalid_id(self, authenticated_context, mock_websocket):
        data = {"action": "delete_message", "id": "not_an_int"}
        handle_delete_message(authenticated_context, data)
        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "error"
        assert "invalid message id" in sent_data["message"].lower()

    def test_delete_message_success(self, authenticated_context, mock_websocket):
        data = {"action": "delete_message", "id": 555}
        with patch("handlers.delete_message", return_value=True) as mock_delete:
            handle_delete_message(authenticated_context, data)
            mock_delete.assert_called_once_with(555)
            mock_websocket.send_ws_frame.assert_called_once()
            sent_data = mock_websocket.send_ws_frame.call_args[0][1]
            assert sent_data["status"] == "success"
            assert sent_data["action"] == "delete_message_success"
            assert sent_data["id"] == 555


class TestHandleGetUsers:
    def test_get_users_success(self, authenticated_context, mock_websocket):
        fake_users = ["alice", "bob", "charlie"]
        with patch(
            "handlers.get_all_users_except", return_value=fake_users
        ) as mock_get_users:
            handle_get_users(authenticated_context, {"action": "get_users"})
            mock_get_users.assert_called_once_with("test_user")
            mock_websocket.send_ws_frame.assert_called_once()
            sent_data = mock_websocket.send_ws_frame.call_args[0][1]
            assert sent_data["action"] == "user_list"
            assert sent_data["users"] == fake_users


class TestHandleDeleteAccount:
    def test_delete_account_unauthenticated(self, client_context, mock_websocket):
        data = {"action": "delete_account"}
        handle_delete_account(client_context, data)
        mock_websocket.send_ws_frame.assert_called_once()
        sent_data = mock_websocket.send_ws_frame.call_args[0][1]
        assert sent_data["status"] == "error"
        assert "authentication" in sent_data["message"].lower()

    def test_delete_account_success(self, authenticated_context, mock_websocket):
        data = {"action": "delete_account"}
        with patch("handlers.delete_account", return_value=True) as mock_delete:
            # Make sure the user is in online_users for removal
            with online_users_lock:
                online_users[authenticated_context.username] = (
                    authenticated_context.conn
                )
            handle_delete_account(authenticated_context, data)
            mock_delete.assert_called_once_with("test_user")
            mock_websocket.send_ws_frame.assert_called_once()
            # After deletion, the connection should be closed and user removed from online_users
            authenticated_context.conn.close.assert_called_once()
            with online_users_lock:
                assert authenticated_context.username not in online_users


@pytest.mark.asyncio
async def test_handle_client_connection(mock_conn, mock_addr, mock_websocket):
    with patch("handlers.perform_handshake") as mock_handshake:
        mock_handshake.return_value = True
        mock_websocket.read_ws_frame.side_effect = [None]  # Simulate connection close

        handle_client_connection(mock_conn, mock_addr)

        mock_handshake.assert_called_once()
        mock_conn.close.assert_called_once()
