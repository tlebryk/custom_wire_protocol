def test_handle_login_success(
    mock_conn,
    mock_authenticate_user,
    mock_send_ws_frame,
    mock_get_recent_messages,
    mock_get_undelivered_messages,
    mock_get_unread_messages,
    mock_mark_messages_delivered,
    mock_online_users,
):
    """
    Test successful user login.
    """
    # Arrange
    mock_authenticate_user.return_value = True
    mock_get_recent_messages.return_value = [
        ("alice", "Hello!", "testuser", "2023-10-01T12:00:00Z")
    ]
    mock_get_undelivered_messages.return_value = [
        ("bob", "Hey there!", "2023-10-02T13:00:00Z")
    ]
    mock_get_unread_messages.return_value = [
        (1, "carol", "Good morning!", "2023-10-03T14:00:00Z")
    ]

    context = ClientContext(mock_conn, ("127.0.0.1", 12345))
    data = {"action": "login", "username": "testuser", "password": "password123"}

    # Act
    handle_login(context, data)

    # Assert
    mock_authenticate_user.assert_called_once_with("testuser", "password123")
    assert context.authenticated is True
    assert context.username == "testuser"
    assert online_users["testuser"] == mock_conn

    expected_login_payload = {
        "message": "Login successful. Welcome, testuser!",
        "action": "login",
        "status": "success",
    }
    mock_send_ws_frame.assert_any_call(mock_conn, expected_login_payload)

    expected_recent_payload = {
        "action": "recent_messages",
        "messages": [
            {"from": "alice", "message": "Hello!", "timestamp": "2023-10-01T12:00:00Z"}
        ],
    }
    mock_send_ws_frame.assert_any_call(mock_conn, expected_recent_payload)

    expected_undelivered_payload = {
        "action": "recent_messages",
        "messages": [
            {
                "from": "bob",
                "message": "Hey there!",
                "timestamp": "2023-10-02T13:00:00Z",
            }
        ],
    }
    mock_send_ws_frame.assert_any_call(mock_conn, expected_undelivered_payload)

    expected_unread_payload = {
        "action": "unread_messages",
        "messages": [
            {
                "id": 1,
                "from": "carol",
                "message": "Good morning!",
                "timestamp": "2023-10-03T14:00:00Z",
            }
        ],
    }
    mock_send_ws_frame.assert_any_call(mock_conn, expected_unread_payload)

    mock_mark_messages_delivered.assert_called_once_with("testuser")
    mock_get_unread_messages.assert_called_once_with("testuser", limit=20)


def test_handle_delete_account_success(
    mock_conn, mock_delete_account, mock_send_ws_frame, mock_online_users
):
    """
    Test successful account deletion.
    """
    # Arrange
    mock_delete_account.return_value = True
    context = ClientContext(mock_conn, ("127.0.0.1", 12345))
    context.authenticated = True
    context.username = "testuser"
    online_users["testuser"] = mock_conn

    data = {"action": "delete_account"}

    # Act
    handle_delete_account(context, data)

    # Assert
    mock_delete_account.assert_called_once_with("testuser")
    expected_payload = {
        "message": "Account deleted successfully.",
        "action": "delete_account",
        "status": "success",
    }
    mock_send_ws_frame.assert_called_once_with(mock_conn, expected_payload)
    assert "testuser" not in online_users
    mock_conn.close.assert_called_once()


def test_handle_send_message_authenticated_receiver_online(
    mock_conn, mock_send_ws_frame, mock_insert_message, mock_online_users
):
    """
    Test sending a message when the receiver is online.
    """
    # Arrange
    context = ClientContext(mock_conn, ("127.0.0.1", 12345))
    context.authenticated = True
    context.username = "sender"
    receiver_conn = MagicMock()
    online_users["receiver"] = receiver_conn

    data = {
        "action": "send_message",
        "receiver": "receiver",
        "message": "Hello, Receiver!",
    }

    # Act
    handle_send_message(context, data)

    # Assert
    mock_insert_message.assert_called_once_with(
        "sender", "Hello, Receiver!", "receiver"
    )

    # Check that send_ws_frame was called to send the message to the receiver
    expected_message_payload = {
        "from": "sender",
        "message": "Hello, Receiver!",
        "timestamp": ANY,  # Since timestamp is generated dynamically
        "read": False,
        "action": "send_message",
    }
    mock_send_ws_frame.assert_any_call(receiver_conn, expected_message_payload)

    # Check that send_success was called to confirm to sender
    expected_success_payload = {
        "status": "success",
        "from": "sender",
        "message": "Hello, Receiver!",
        "timestamp": ANY,
        "action": "send_message",
    }
    mock_send_ws_frame.assert_any_call(mock_conn, expected_success_payload)
