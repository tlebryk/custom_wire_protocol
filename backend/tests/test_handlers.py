# import pytest
# from unittest.mock import MagicMock, ANY
# from handlers import (
#     handle_register,
#     handle_login,
#     handle_send_message,
#     handle_mark_as_read,
#     handle_delete_account,
#     handle_unknown_action,
#     send_success,
#     send_error,
#     send_recent_messages,
#     send_unread_messages,
#     ClientContext,
#     online_users,
# )
# import json

# # ==============================
# # Tests for handle_register
# # ==============================


# def test_handle_register_success(mock_conn, mock_register_user, mock_send_ws_frame):
#     """
#     Test successful user registration.
#     """
#     # Arrange
#     mock_register_user.return_value = (True, "Registration successful.")
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     data = {"action": "register", "username": "testuser", "password": "password123"}

#     # Act
#     handle_register(context, data)

#     # Assert
#     mock_register_user.assert_called_once_with("testuser", "password123")
#     expected_payload = {
#         "message": "Registration successful.",
#         "action": "register",
#         "status": "success",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_register_missing_username(mock_conn, mock_send_ws_frame):
#     """
#     Test registration with missing username.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     data = {"action": "register", "password": "password123"}

#     # Act
#     handle_register(context, data)

#     # Assert
#     expected_payload = {
#         "status": "error",
#         "message": "Username and password are required for registration.",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_register_missing_password(mock_conn, mock_send_ws_frame):
#     """
#     Test registration with missing password.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     data = {"action": "register", "username": "testuser"}

#     # Act
#     handle_register(context, data)

#     # Assert
#     expected_payload = {
#         "status": "error",
#         "message": "Username and password are required for registration.",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_register_failure(mock_conn, mock_register_user, mock_send_ws_frame):
#     """
#     Test registration failure (e.g., username already exists).
#     """
#     # Arrange
#     mock_register_user.return_value = (False, "Username already exists.")
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     data = {"action": "register", "username": "existinguser", "password": "password123"}

#     # Act
#     handle_register(context, data)

#     # Assert
#     mock_register_user.assert_called_once_with("existinguser", "password123")
#     expected_payload = {"status": "error", "message": "Username already exists."}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# # ==============================
# # Tests for handle_login
# # ==============================


# def test_handle_login_failure(mock_conn, mock_authenticate_user, mock_send_ws_frame):
#     """
#     Test login failure due to invalid credentials.
#     """
#     # Arrange
#     mock_authenticate_user.return_value = False
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     data = {"action": "login", "username": "testuser", "password": "wrongpassword"}

#     # Act
#     handle_login(context, data)

#     # Assert
#     mock_authenticate_user.assert_called_once_with("testuser", "wrongpassword")
#     assert context.authenticated is False
#     assert context.username is None

#     expected_payload = {"status": "error", "message": "Invalid username or password."}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_login_missing_username(mock_conn, mock_send_ws_frame):
#     """
#     Test login with missing username.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     data = {"action": "login", "password": "password123"}

#     # Act
#     handle_login(context, data)

#     # Assert
#     expected_payload = {
#         "status": "error",
#         "message": "Username and password are required for login.",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_login_missing_password(mock_conn, mock_send_ws_frame):
#     """
#     Test login with missing password.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     data = {"action": "login", "username": "testuser"}

#     # Act
#     handle_login(context, data)

#     # Assert
#     expected_payload = {
#         "status": "error",
#         "message": "Username and password are required for login.",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# # ==============================
# # Tests for handle_send_message
# # ==============================


# def test_handle_send_message_authenticated_receiver_offline(
#     mock_conn, mock_send_ws_frame, mock_insert_message, mock_online_users
# ):
#     """
#     Test sending a message when the receiver is offline.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = True
#     context.username = "sender"
#     # Receiver is not in online_users

#     data = {
#         "action": "send_message",
#         "receiver": "offline_receiver",
#         "message": "Hello, Offline Receiver!",
#     }

#     # Act
#     handle_send_message(context, data)

#     # Assert
#     mock_insert_message.assert_called_once_with(
#         "sender", "Hello, Offline Receiver!", "offline_receiver"
#     )

#     # Since receiver is offline, send_success should still be called to confirm to sender
#     expected_success_payload = {
#         "status": "success",
#         "from": "sender",
#         "message": "Hello, Offline Receiver!",
#         "timestamp": ANY,
#         "action": "send_message",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_success_payload)


# def test_handle_send_message_not_authenticated(mock_conn, mock_send_ws_frame):
#     """
#     Test sending a message when the user is not authenticated.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = False

#     data = {"action": "send_message", "receiver": "receiver", "message": "Hello!"}

#     # Act
#     handle_send_message(context, data)

#     # Assert
#     expected_payload = {
#         "status": "error",
#         "message": "Authentication required. Please log in first.",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_send_message_missing_receiver(mock_conn, mock_send_ws_frame):
#     """
#     Test sending a message with missing receiver.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = True

#     data = {"action": "send_message", "message": "Hello!"}

#     # Act
#     handle_send_message(context, data)

#     # Assert
#     expected_payload = {"status": "error", "message": "Receiver username is required."}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_send_message_empty_message(mock_conn, mock_send_ws_frame):
#     """
#     Test sending an empty message.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = True

#     data = {"action": "send_message", "receiver": "receiver", "message": ""}

#     # Act
#     handle_send_message(context, data)

#     # Assert
#     expected_payload = {"status": "error", "message": "Empty message cannot be sent."}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# # ==============================
# # Tests for handle_mark_as_read
# # ==============================


# def test_handle_mark_as_read_success(
#     mock_conn, mock_mark_messages_as_read, mock_send_ws_frame
# ):
#     """
#     Test marking messages as read successfully.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = True
#     context.username = "testuser"

#     data = {"action": "mark_as_read", "message_ids": [1, 2, 3]}

#     # Act
#     handle_mark_as_read(context, data)

#     # Assert
#     mock_mark_messages_as_read.assert_called_once_with([1, 2, 3])
#     expected_payload = {
#         "message": "Messages marked as read.",
#         "action": "mark_as_read",
#         "status": "success",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_mark_as_read_not_authenticated(mock_conn, mock_send_ws_frame):
#     """
#     Test marking messages as read when not authenticated.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = False

#     data = {"action": "mark_as_read", "message_ids": [1, 2, 3]}

#     # Act
#     handle_mark_as_read(context, data)

#     # Assert
#     expected_payload = {
#         "status": "error",
#         "message": "Authentication required. Please log in first.",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_mark_as_read_invalid_message_ids(mock_conn, mock_send_ws_frame):
#     """
#     Test marking messages as read with invalid message_ids.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = True

#     data = {
#         "action": "mark_as_read",
#         "message_ids": ["one", "two", "three"],  # Invalid IDs
#     }

#     # Act
#     handle_mark_as_read(context, data)

#     # Assert
#     expected_payload = {
#         "status": "error",
#         "message": "All 'message_ids' should be integers.",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_handle_mark_as_read_message_ids_not_list(mock_conn, mock_send_ws_frame):
#     """
#     Test marking messages as read with message_ids not being a list.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = True

#     data = {"action": "mark_as_read", "message_ids": "1,2,3"}  # Should be a list

#     # Act
#     handle_mark_as_read(context, data)

#     # Assert
#     expected_payload = {"status": "error", "message": "'message_ids' should be a list."}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# # ==============================
# # Tests for handle_delete_account
# # ==============================


# def test_handle_delete_account_success(
#     mock_conn, mock_delete_account, mock_send_ws_frame, mock_online_users
# ):
#     """
#     Test successful account deletion.
#     """
#     # Arrange
#     mock_delete_account.return_value = True
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = True
#     context.username = "testuser"
#     online_users["testuser"] = mock_conn

#     data = {"action": "delete_account"}

#     # Act
#     handle_delete_account(context, data)

#     # Assert
#     mock_delete_account.assert_called_once_with("testuser")
#     expected_payload = {
#         "message": "Account deleted successfully.",
#         "action": "delete_account",
#         "status": "success",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)
#     assert "testuser" not in online_users
#     mock_conn.close.assert_called_once()


# def test_handle_delete_account_failure(
#     mock_conn, mock_delete_account, mock_send_ws_frame
# ):
#     """
#     Test account deletion failure.
#     """
#     # Arrange
#     mock_delete_account.return_value = False
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = True
#     context.username = "testuser"

#     data = {"action": "delete_account"}

#     # Act
#     handle_delete_account(context, data)

#     # Assert
#     mock_delete_account.assert_called_once_with("testuser")
#     expected_payload = {"status": "error", "message": "Failed to delete account."}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)
#     mock_conn.close.assert_not_called()


# def test_handle_delete_account_not_authenticated(mock_conn, mock_send_ws_frame):
#     """
#     Test account deletion when not authenticated.
#     """
#     # Arrange
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))
#     context.authenticated = False

#     data = {"action": "delete_account"}

#     # Act
#     handle_delete_account(context, data)

#     # Assert
#     expected_payload = {
#         "status": "error",
#         "message": "Authentication required. Please log in first.",
#     }
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# # ==============================
# # Tests for handle_unknown_action
# # ==============================


# def test_handle_unknown_action(mock_conn, mock_send_ws_frame):
#     """
#     Test handling of an unknown action.
#     """
#     # Arrange
#     action = "unknown_action"
#     context = ClientContext(mock_conn, ("127.0.0.1", 12345))

#     # Act
#     handle_unknown_action(context, action)

#     # Assert
#     expected_payload = {"status": "error", "message": f"Unknown action '{action}'."}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# # ==============================
# # Tests for send_success and send_error
# # ==============================


# def test_send_success(mock_conn, mock_send_ws_frame):
#     """
#     Test the send_success helper function.
#     """
#     # Arrange
#     payload = {"key": "value"}

#     # Act
#     send_success(mock_conn, payload)

#     # Assert
#     expected_payload = {"key": "value", "status": "success"}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_send_error(mock_conn, mock_send_ws_frame):
#     """
#     Test the send_error helper function.
#     """
#     # Arrange
#     message = "An error occurred."

#     # Act
#     send_error(mock_conn, message)

#     # Assert
#     expected_payload = {"status": "error", "message": message}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_send_recent_messages(mock_conn, mock_send_ws_frame):
#     """
#     Test the send_recent_messages helper function.
#     """
#     # Arrange
#     messages = [
#         {"from": "alice", "message": "Hello!", "timestamp": "2023-10-01T12:00:00Z"}
#     ]

#     # Act
#     send_recent_messages(mock_conn, messages)

#     # Assert
#     expected_payload = {"action": "recent_messages", "messages": messages}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)


# def test_send_unread_messages(mock_conn, mock_send_ws_frame):
#     """
#     Test the send_unread_messages helper function.
#     """
#     # Arrange
#     messages = [
#         {"id": 1, "from": "bob", "message": "Hey!", "timestamp": "2023-10-02T13:00:00Z"}
#     ]

#     # Act
#     send_unread_messages(mock_conn, messages)

#     # Assert
#     expected_payload = {"action": "unread_messages", "messages": messages}
#     mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)
