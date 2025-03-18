# test_replica_server.py
import threading
import time
import grpc
import pytest

import replica_pb2
import replica_pb2_grpc
from replica_server import serve  # Ensure serve() accepts port parameter if needed


@pytest.fixture(scope="module")
def replica_server():
    # Start the replica server on port 50052 in a background thread.
    server_thread = threading.Thread(
        target=serve, kwargs={"port": "50052"}, daemon=True
    )
    server_thread.start()
    # Wait briefly for the server to start.
    time.sleep(1)
    yield
    # No explicit teardown is provided here; the daemon thread will exit when tests complete.


def get_stub():
    channel = grpc.insecure_channel("localhost:50052")
    return replica_pb2_grpc.ReplicaServiceStub(channel)


def test_insert_message(replica_server):
    stub = get_stub()
    request = replica_pb2.InsertMessageRequest(
        sender="alice",
        content="Hello, Replica!",
        receiver="bob",
        timestamp="2025-03-17T12:00:00Z",
    )
    response = stub.InsertMessage(request)
    assert response.success
    assert "Message inserted" in response.message


def test_register_user(replica_server):
    stub = get_stub()
    request = replica_pb2.RegisterUserRequest(username="testuser", password="password")
    response = stub.RegisterUser(request)
    assert response.success


def test_delete_account(replica_server):
    stub = get_stub()
    request = replica_pb2.DeleteAccountRequest(username="testuser")
    response = stub.DeleteAccount(request)
    assert response.success


def test_mark_messages_as_read(replica_server):
    stub = get_stub()
    request = replica_pb2.MarkMessagesAsReadRequest(message_ids=[1, 2, 3])
    response = stub.MarkMessagesAsRead(request)
    assert response.success


def test_set_n_unread_messages(replica_server):
    stub = get_stub()
    request = replica_pb2.SetNUnreadMessagesRequest(
        username="alice", n_unread_messages=10
    )
    response = stub.SetNUnreadMessages(request)
    assert response.success


def test_delete_message(replica_server):
    stub = get_stub()
    request = replica_pb2.DeleteMessageRequest(message_id=123)
    response = stub.DeleteMessage(request)
    assert response.success
