import pytest
from unittest.mock import MagicMock
from client import GRPCClient
import protocols_pb2
import protocols_pb2_grpc


@pytest.fixture
def client():
    # Create a GRPCClient instance and replace its stub with a MagicMock.
    c = GRPCClient(host="localhost", port=50051)
    c.stub = MagicMock()
    # Set a dummy username for methods that rely on self.username.
    c.username = "testuser"
    return c


def test_login_success(client):
    dummy_response = protocols_pb2.ConfirmLoginResponse(
        **{
            "username": "testuser",
            "message": "Logged in successfully",
            "status": "success",
        }
    )
    client.stub.Login.return_value = dummy_response
    response = client.login("testuser", "password")
    client.stub.Login.assert_called_once()
    assert response.username == "testuser"
    assert response.status == "success"


def test_register_success(client):
    dummy_response = protocols_pb2.SuccessResponse(
        **{"message": "Registered successfully", "status": "success"}
    )
    client.stub.Register.return_value = dummy_response
    response = client.register("testuser", "password")
    client.stub.Register.assert_called_once()
    assert response.status == "success"


def test_send_message_success(client):
    dummy_response = protocols_pb2.ConfirmSendMessageResponse(
        **{
            "message": "Hello",
            "status": "success",
            "from": "testuser",
            "timestamp": "2025-01-01T00:00:00Z",
        }
    )
    client.stub.SendMessage.return_value = dummy_response
    client.username = "testuser"
    response = client.send_message("Hello", "otheruser")
    client.stub.SendMessage.assert_called_once()
    # Verify metadata is passed by checking that the call arguments contain our sender.
    args, kwargs = client.stub.SendMessage.call_args
    assert ("sender", "testuser") in kwargs.get("metadata", ())
    assert response.status == "success"


def test_get_recent_messages(client):
    dummy_chat = protocols_pb2.ChatMessage(
        **{
            "message": "Recent",
            "timestamp": "2025-01-01T00:00:00Z",
            "from": "otheruser",
            "id": 1,
        }
    )
    dummy_response = protocols_pb2.RecentMessagesResponse(
        **{"messages": [dummy_chat], "status": "success"}
    )
    client.stub.GetRecentMessages.return_value = dummy_response
    response = client.get_recent_messages("testuser")
    client.stub.GetRecentMessages.assert_called_once()
    assert response.status == "success"
    assert len(response.messages) == 1
    assert response.messages[0].message == "Recent"


def test_get_unread_messages(client):
    dummy_chat = protocols_pb2.ChatMessage(
        **{
            "message": "Unread",
            "timestamp": "2025-01-01T00:00:00Z",
            "from": "otheruser",
            "id": 2,
        }
    )
    dummy_response = protocols_pb2.UnreadMessagesResponse(
        **{"messages": [dummy_chat], "status": "success"}
    )
    client.stub.GetUnreadMessages.return_value = dummy_response
    response = client.get_unread_messages("testuser")
    client.stub.GetUnreadMessages.assert_called_once()
    assert response.status == "success"
    assert len(response.messages) == 1
    assert response.messages[0].message == "Unread"


def test_mark_as_read(client):
    dummy_response = protocols_pb2.ConfirmMarkAsReadResponse(
        **{"message": "Marked as read", "status": "success"}
    )
    client.stub.MarkAsRead.return_value = dummy_response
    response = client.mark_as_read([1, 2, 3])
    client.stub.MarkAsRead.assert_called_once()
    assert response.status == "success"
    assert response.message == "Marked as read"


def test_set_n_unread_messages(client):
    dummy_response = protocols_pb2.SuccessResponse(
        **{"message": "Set successfully", "status": "success"}
    )
    client.stub.SetNUnreadMessages.return_value = dummy_response
    response = client.set_n_unread_messages("testuser", 10)
    client.stub.SetNUnreadMessages.assert_called_once()
    assert response.status == "success"
    assert response.message == "Set successfully"


def test_delete_message(client):
    dummy_response = protocols_pb2.SuccessResponse(
        **{"message": "Deleted successfully", "status": "success"}
    )
    client.stub.DeleteMessage.return_value = dummy_response
    response = client.delete_message("testuser", 1)
    client.stub.DeleteMessage.assert_called_once()
    assert response.status == "success"
    assert response.message == "Deleted successfully"


def test_delete_account(client):
    dummy_response = protocols_pb2.SuccessResponse(
        **{"message": "Account deleted", "status": "success"}
    )
    client.stub.DeleteAccount.return_value = dummy_response
    response = client.delete_account("testuser")
    client.stub.DeleteAccount.assert_called_once()
    assert response.status == "success"
    assert response.message == "Account deleted"


def test_subscribe(client):
    dummy_msg1 = protocols_pb2.ReceivedMessage(
        **{
            "from": "otheruser",
            "message": "Hi",
            "timestamp": "2025-01-01T00:00:00Z",
            "read": "false",
            "id": 1,
            "username": "otheruser",
        }
    )
    dummy_msg2 = protocols_pb2.ReceivedMessage(
        **{
            "from": "otheruser",
            "message": "How are you?",
            "timestamp": "2025-01-01T00:01:00Z",
            "read": "false",
            "id": 2,
            "username": "otheruser",
        }
    )
    client.stub.Subscribe.return_value = iter([dummy_msg1, dummy_msg2])
    subscribe_iter = client.subscribe("testuser")
    messages = list(subscribe_iter)
    client.stub.Subscribe.assert_called_once()
    assert len(messages) == 2
    assert messages[0].message == "Hi"
    assert messages[1].message == "How are you?"


def test_get_users(client):
    # Simulate a GetUsers method returning dummy usernames.
    dummy_response = MagicMock()
    dummy_response.status = "success"
    dummy_response.usernames = ["user1", "user2", "user3"]
    client.stub.GetUsers.return_value = dummy_response
    users = client.get_users("testuser")
    client.stub.GetUsers.assert_called_once()
    assert users == ["user1", "user2", "user3"]
