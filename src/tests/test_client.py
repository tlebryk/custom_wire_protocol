# test_client.py
import time
import logging
import pytest
import grpc

from client import GRPCClient, SizeLoggingClientInterceptor
import protocols_pb2
import protocols_pb2_grpc


# --- Dummy Interceptor ---
# Define a dummy subclass that implements the missing abstract methods.
class DummySizeLoggingClientInterceptor(SizeLoggingClientInterceptor):
    def intercept_stream_stream(
        self, continuation, client_call_details, request_iterator
    ):
        return continuation(client_call_details, request_iterator)

    def intercept_stream_unary(
        self, continuation, client_call_details, request_iterator
    ):
        return continuation(client_call_details, request_iterator)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        return continuation(client_call_details, request)


# --- Fake stub to simulate RPC responses ---
class FakeStub:
    def Login(self, request):
        return protocols_pb2.ConfirmLoginResponse(
            username=request.username, message="Logged in", status="success"
        )

    def Register(self, request):
        return protocols_pb2.SuccessResponse(message="Registered", status="success")

    def SendMessage(self, request, metadata=None):
        return protocols_pb2.ConfirmSendMessageResponse(
            message="Message sent", status="success", sender="sender", timestamp="now"
        )

    def GetRecentMessages(self, request):
        message = protocols_pb2.ChatMessage(
            message="Hi", timestamp="now", sender="sender", id=1
        )
        return protocols_pb2.RecentMessagesResponse(
            messages=[message], status="success"
        )

    def GetUnreadMessages(self, request):
        message = protocols_pb2.ChatMessage(
            message="Unread", timestamp="now", sender="sender", id=2
        )
        return protocols_pb2.UnreadMessagesResponse(
            messages=[message], status="success"
        )

    def MarkAsRead(self, request):
        return protocols_pb2.ConfirmMarkAsReadResponse(
            message="Marked as read", status="success"
        )

    def SetNUnreadMessages(self, request):
        return protocols_pb2.SuccessResponse(
            message="Set unread messages", status="success"
        )

    def DeleteMessage(self, request):
        return protocols_pb2.SuccessResponse(message="Deleted", status="success")

    def DeleteAccount(self, request):
        return protocols_pb2.SuccessResponse(
            message="Account deleted", status="success"
        )

    def Subscribe(self, request):
        def generator():
            for i in range(3):
                yield protocols_pb2.ReceivedMessage(
                    sender="user",
                    message=f"msg{i}",
                    timestamp="now",
                    read="false",
                    id=i,
                    username="user",
                )

        return generator()

    def GetUsers(self, request):
        return protocols_pb2.GetUsersResponse(
            usernames=["user1", "user2"], status="success", message="OK"
        )

    def SearchUsers(self, request):
        return protocols_pb2.SearchUsersResponse(
            usernames=["user3", "user4"], status="success", message="OK"
        )


# --- Fake RpcError for simulating failures ---
class FakeRpcError(grpc.RpcError):
    def __init__(self, code):
        self._code = code

    def code(self):
        return self._code


# --- Dummy future for channel readiness ---
class DummyFuture:
    def result(self, timeout):
        return True


# --- Pytest fixtures ---
@pytest.fixture
def fake_channel(monkeypatch):
    # Override grpc.channel_ready_future so it always "succeeds"
    def fake_channel_ready_future(channel):
        return DummyFuture()

    monkeypatch.setattr(grpc, "channel_ready_future", fake_channel_ready_future)


@pytest.fixture
def client(fake_channel):
    # Instantiate GRPCClient with intercept=False to avoid creating the abstract interceptor.
    c = GRPCClient(lb_addresses=["addr1:50051", "addr2:50051"], intercept=False)
    # Overwrite the channel and stub so that real network calls are not made.
    c.channel = "dummy_channel"
    c.stub = FakeStub()
    return c


# --- Tests for GRPCClient RPC methods ---


def test_login_success(client):
    response = client.login("user", "pass")
    assert response.username == "user"
    assert response.status == "success"


def test_register_success(client):
    response = client.register("user", "pass")
    assert response.message == "Registered"
    assert response.status == "success"


def test_send_message_success(client):
    client.username = "sender"
    response = client.send_message("hello", "receiver")
    assert response.message == "Message sent"
    assert response.status == "success"
    # Check that the sender in the response is what our fake stub returns.
    assert response.sender == "sender"


def test_get_recent_messages(client):
    response = client.get_recent_messages("user")
    assert response.status == "success"
    assert len(response.messages) == 1
    assert response.messages[0].message == "Hi"


def test_get_unread_messages(client):
    response = client.get_unread_messages("user")
    assert response.status == "success"
    assert len(response.messages) == 1
    assert response.messages[0].message == "Unread"


def test_mark_as_read(client):
    response = client.mark_as_read([1, 2, 3])
    assert response.message == "Marked as read"
    assert response.status == "success"


def test_set_n_unread_messages(client):
    response = client.set_n_unread_messages("user", 5)
    assert response.message == "Set unread messages"
    assert response.status == "success"


def test_delete_message(client):
    response = client.delete_message("user", 10)
    assert response.message == "Deleted"
    assert response.status == "success"


def test_delete_account(client):
    response = client.delete_account("user")
    assert response.message == "Account deleted"
    assert response.status == "success"


def test_subscribe(client):
    stream = client.subscribe("user")
    messages = list(stream)
    assert len(messages) == 3
    for i, msg in enumerate(messages):
        assert msg.message == f"msg{i}"


def test_get_users(client):
    users = client.get_users("user")
    assert users == ["user1", "user2"]


def test_search_users(client):
    users = client.search_users("query")
    assert users == ["user3", "user4"]


# --- Tests for the retry logic in perform_rpc ---


def test_perform_rpc_retry(client, monkeypatch):
    # This fake rpc function will simulate two transient UNAVAILABLE errors then succeed.
    call_count = [0]

    def fake_rpc():
        if call_count[0] < 2:
            call_count[0] += 1
            raise FakeRpcError(grpc.StatusCode.UNAVAILABLE)
        else:
            return "success"

    # Override sleep to avoid delays during testing.
    monkeypatch.setattr(time, "sleep", lambda s: None)
    result = client.perform_rpc(fake_rpc, max_retries=5, backoff=0)
    assert result == "success"
    assert call_count[0] == 2  # Two failures occurred before success


def test_perform_rpc_non_retryable(client):
    # This fake rpc function raises a non-retryable error.
    def fake_rpc():
        raise FakeRpcError(grpc.StatusCode.INVALID_ARGUMENT)

    result = client.perform_rpc(fake_rpc, max_retries=3, backoff=0)
    assert result is None


def test_perform_rpc_exhaust_retries(client, monkeypatch):
    # This fake rpc function always raises a UNAVAILABLE error.
    call_count = [0]

    def fake_rpc():
        call_count[0] += 1
        raise FakeRpcError(grpc.StatusCode.UNAVAILABLE)

    monkeypatch.setattr(time, "sleep", lambda s: None)
    result = client.perform_rpc(fake_rpc, max_retries=3, backoff=0)
    assert result is None
    assert call_count[0] == 3


# --- Test for the interceptor ---
def test_interceptor_logging(caplog):
    # Use the DummySizeLoggingClientInterceptor defined above.
    interceptor = DummySizeLoggingClientInterceptor()

    # Create a dummy request with a SerializeToString method.
    class DummyRequest:
        def SerializeToString(self):
            return b"test data"

    dummy_request = DummyRequest()
    dummy_client_call_details = None

    def dummy_continuation(call_details, req):
        return "dummy response"

    with caplog.at_level(logging.INFO):
        response = interceptor.intercept_unary_unary(
            dummy_continuation, dummy_client_call_details, dummy_request
        )
    # "test data" is 9 bytes long.
    assert "Sending unary_unary request of size: 9 bytes" in caplog.text
    assert response == "dummy response"
