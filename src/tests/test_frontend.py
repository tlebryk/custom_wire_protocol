import pytest
from unittest.mock import MagicMock, patch
import tkinter as tk
import json
from frontend import (
    ChatApp,
    AuthBox,
    LoginForm,
    RegisterForm,
    MessagesContainer,
    ChatBox,
    NNewMessages,
    DeleteAccountContainer,
)


@pytest.fixture
def mock_websocket_client():
    """Create a mock WebSocket client."""
    mock_client = MagicMock()
    mock_client.connected = True
    return mock_client


@pytest.fixture
def app(monkeypatch, mock_websocket_client):
    """Create a ChatApp instance with mocked WebSocket."""
    with patch("frontend.WebSocketClient") as MockWebSocketClient:
        MockWebSocketClient.return_value = mock_websocket_client
        app = ChatApp()
        yield app
        app.destroy()


@pytest.fixture
def messages_container(app):
    """Create a MessagesContainer instance."""
    container = MessagesContainer(app)
    container.username = "test_user"
    return container


@pytest.fixture
def chat_box(app):
    """Create a ChatBox instance."""
    box = ChatBox(app)
    box.username = "test_user"
    return box


class TestChatApp:
    def test_init(self, app):
        """Test ChatApp initialization."""
        assert isinstance(app, tk.Tk)
        assert app.title() == "WebSocket Chat - Registration and Login"
        assert hasattr(app, "ws_client")
        assert hasattr(app, "auth_box")

    def test_send_message_via_ws(self, app, mock_websocket_client):
        """Test sending message via WebSocket."""
        test_message = {"action": "test", "data": "test_data"}
        app.send_message_via_ws(test_message)
        mock_websocket_client.send.assert_called_once_with(test_message)

    def test_handle_incoming_message_login_success(self, app):
        """Test handling successful login message."""
        test_message = {
            "status": "success",
            "action": "confirm_login",
            "username": "test_user",
            "message": "Login successful",
        }

        with patch("tkinter.messagebox.showinfo") as mock_showinfo:
            app.handle_incoming_message(test_message)
            mock_showinfo.assert_called_once()
            assert app.n_new_messages.username == "test_user"
            assert app.chat_box.username == "test_user"

    def test_handle_incoming_message_error(self, app):
        """Test handling error message."""
        test_message = {"status": "error", "message": "Test error message"}

        with patch("tkinter.messagebox.showerror") as mock_showerror:
            app.handle_incoming_message(test_message)
            mock_showerror.assert_called_once_with("Error", "Test error message")


class TestLoginForm:
    def test_login_validation(self, app):
        """Test login form validation."""
        login_form = LoginForm(app)

        with patch("tkinter.messagebox.showwarning") as mock_warning:
            # Test empty fields
            login_form.login()
            mock_warning.assert_called_once_with(
                "Input Error", "Please enter both username and password."
            )

        # Test valid login attempt
        login_form.username_entry.insert(0, "test_user")
        login_form.password_entry.insert(0, "test_pass")

        with patch.object(app, "send_message_via_ws") as mock_send:
            login_form.login()
            mock_send.assert_called_once_with(
                {"action": "login", "username": "test_user", "password": "test_pass"}
            )


class TestMessagesContainer:
    def test_add_unread_message(self, messages_container):
        """Test adding unread message."""
        test_message = {
            "id": "123",
            "from": "sender",
            "timestamp": "2025-02-11T02:25:50.374591Z",
            "message": "Test message",
        }

        messages_container.add_unread_message(test_message)
        assert "123" in messages_container.unread_messages_dict

    def test_delete_message(self, messages_container):
        """Test message deletion."""
        test_message = {
            "id": "123",
            "from": "sender",
            "timestamp": "2025-02-11T02:25:50.374591Z",
            "message": "Test message",
        }

        messages_container.add_unread_message(test_message)

        with patch("tkinter.messagebox.askyesno", return_value=True), patch.object(
            messages_container.master, "send_message_via_ws"
        ) as mock_send:
            messages_container.delete_message(
                "123", messages_container.unread_messages_dict["123"], "unread"
            )
            assert "123" not in messages_container.unread_messages_dict
            mock_send.assert_called_once_with({"action": "delete_message", "id": "123"})


class TestChatBox:

    def test_update_user_list(self, chat_box):
        """Test updating user list."""
        test_users = ["user1", "user2", "user3"]
        chat_box.update_user_list(test_users)
        assert chat_box.selected_user.get() == "user1"
