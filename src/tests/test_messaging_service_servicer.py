# test_messaging_service_servicer.py
import time
import threading
import pytest
import grpc

import protocols_pb2
from messaging_service_servicer import MessagingServiceServicer

# --- Dummy Implementations for Dependencies ---


class DummyUserManager:
    def authenticate_user(self, username, password):
        return username == "valid" and password == "password"

    def register_user(self, username, password):
        return (True, "User registered")

    def delete_account(self, username):
        return True


class DummyDatabase:
    def insert_message(self, sender, message, receiver):
        return 1  # dummy message id

    def search_users_in_db(self, query):
        return ["user1", "user2"]

    def get_all_users_except(self, username):
        return ["user1", "user2"] if username != "user1" else ["user2"]

    def get_recent_messages(self, username, limit):
        # Tuple: (sender, message, unused, timestamp, message_id)
        return [("user1", "hello", None, "2025-03-26T00:00:00Z", 1)]

    def get_unread_messages(self, username, limit):
        # Tuple: (id, sender, message, timestamp)
        return [(1, "user1", "unread message", "2025-03-26T00:00:00Z")]

    def mark_messages_as_read(self, message_ids):
        pass

    def set_n_unread_messages(self, username, count):
        return True

    def get_user_info(self, username):
        # Return a dummy tuple; index 1 holds unread count
        return (username, 50)

    def delete_message(self, message_id):
        return True


class DummyReplicationManager:
    def replicate_register_user(self, username, password):
        return True

    def replicate_delete_account(self, username):
        return True

    def replicate_insert_message(self, sender, message, receiver, timestamp):
        return True

    def replicate_mark_messages_as_read(self, message_ids):
        return True

    def replicate_set_n_unread_messages(self, username, count):
        return True

    def replicate_delete_message(self, message_id):
        return True


# --- Fake gRPC Context ---


class FakeContext:
    def __init__(self, metadata=None, active=True):
        self._active = active
        self._metadata = metadata or []
        self.code_val = None
        self.details_val = ""

    def invocation_metadata(self):
        return self._metadata

    def set_details(self, details):
        self.details_val = details

    def set_code(self, code):
        self.code_val = code

    def is_active(self):
        return self._active

    def deactivate(self):
        self._active = False


# A slightly customized fake context for testing the Subscribe method.
class FakeContextForSubscribe:
    def __init__(self, active_count=3):
        self.active_count = active_count
        self._metadata = []
        self.code_val = None
        self.details_val = ""

    def invocation_metadata(self):
        return self._metadata

    def set_details(self, details):
        self.details_val = details

    def set_code(self, code):
        self.code_val = code

    def is_active(self):
        if self.active_count > 0:
            self.active_count -= 1
            return True
        return False


# --- Pytest Fixtures ---


@pytest.fixture
def servicer():
    svc = MessagingServiceServicer(replica_addresses=None)
    # Inject our dummy dependencies
    svc.user_manager = DummyUserManager()
    svc.db = DummyDatabase()
    svc.replication_manager = DummyReplicationManager()
    return svc


# --- Tests for individual RPCs ---


def test_login_success(servicer):
    fake_context = FakeContext()
    req = protocols_pb2.LoginRequest(username="valid", password="password")
    response = servicer.Login(req, fake_context)
    assert response.status == "success"
    assert response.username == "valid"


def test_login_failure(servicer):
    fake_context = FakeContext()
    req = protocols_pb2.LoginRequest(username="invalid", password="wrong")
    response = servicer.Login(req, fake_context)
    assert response.status == "error"


def test_register_success(servicer):
    fake_context = FakeContext()
    req = protocols_pb2.RegisterRequest(username="new_user", password="password")
    response = servicer.Register(req, fake_context)
    assert response.status == "success"
    assert "registered" in response.message.lower()


def test_delete_account_success(servicer):
    fake_context = FakeContext()
    # Simulate that the user is online.
    servicer.online_users["user_to_delete"] = (fake_context, [])
    req = protocols_pb2.DeleteAccountRequest(username="user_to_delete")
    response = servicer.DeleteAccount(req, fake_context)
    assert response.status == "success"
    # Check that the user has been removed from the online_users dict.
    assert "user_to_delete" not in servicer.online_users


def test_send_message_success(servicer):
    # Prepare a fake context with metadata providing the sender.
    fake_context = FakeContext(metadata=[("sender", "test_sender")])
    # Ensure the receiver is online.
    receiver_context = FakeContext()
    servicer.online_users["receiver"] = (receiver_context, [])
    req = protocols_pb2.SendMessageRequest(message="Hello", receiver="receiver")
    response = servicer.SendMessage(req, fake_context)
    assert response.status == "success"
    # Verify that the receiver's message queue now has a message.
    _, queue = servicer.online_users["receiver"]
    assert len(queue) > 0
    # Optionally, check that the enqueued message has the correct text.
    enqueued_msg = queue[0]
    assert enqueued_msg.message == "Hello"


def test_get_recent_messages(servicer):
    fake_context = FakeContext()
    req = protocols_pb2.GetRecentMessagesRequest(username="user1")
    response = servicer.GetRecentMessages(req, fake_context)
    assert response.status == "success"
    assert len(response.messages) == 1
    assert response.messages[0].message == "hello"


def test_get_unread_messages(servicer):
    fake_context = FakeContext()
    req = protocols_pb2.GetUnreadMessagesRequest(username="user1")
    response = servicer.GetUnreadMessages(req, fake_context)
    assert response.status == "success"
    assert len(response.messages) == 1
    assert response.messages[0].message == "unread message"


def test_mark_as_read(servicer):
    fake_context = FakeContext()
    req = protocols_pb2.MarkAsReadRequest(message_ids=[1, 2, 3])
    response = servicer.MarkAsRead(req, fake_context)
    assert response.status == "success"


def test_delete_message(servicer):
    fake_context = FakeContext()
    req = protocols_pb2.DeleteMessageRequest(username="user1", message_id=1)
    response = servicer.DeleteMessage(req, fake_context)
    assert response.status == "success"


def test_update_unread_message_count(servicer):
    fake_context = FakeContext()

    # Create a dummy request object with attributes 'username' and 'count'
    class DummyRequest:
        username = "user1"
        count = 5

    req = DummyRequest()
    response = servicer.UpdateUnreadMessageCount(req, fake_context)
    assert response.status == "success"


def test_set_n_unread_messages(servicer):
    fake_context = FakeContext()

    # Create a dummy request with attributes 'username' and 'n_unread_messages'
    class DummyRequest:
        username = "user1"
        n_unread_messages = 3

    req = DummyRequest()
    response = servicer.SetNUnreadMessages(req, fake_context)
    assert response.status == "success"
