import pytest
import grpc
import time
from unittest.mock import MagicMock, patch, call
import logging

# Import the module to test
from client import GRPCClient, SizeLoggingClientInterceptor

# Import the protocol buffers
import protocols_pb2
import protocols_pb2_grpc
import replica_pb2
import replica_pb2_grpc


@pytest.fixture
def mock_channel():
    """Fixture to create a mock channel"""
    return MagicMock(spec=grpc.Channel)


@pytest.fixture
def mock_stub():
    """Fixture to create a mock stub"""
    return MagicMock(spec=protocols_pb2_grpc.MessagingServiceStub)


@pytest.fixture
def mock_client(mock_channel, mock_stub):
    """Fixture to create a mocked client"""
    with patch("grpc.insecure_channel", return_value=mock_channel), patch(
        "grpc.intercept_channel", return_value=mock_channel
    ), patch.object(protocols_pb2_grpc, "MessagingServiceStub", return_value=mock_stub):
        client = GRPCClient(host="localhost", port=50051)
        client.username = "testuser"
        return client


class TestSizeLoggingClientInterceptor:
    """Tests for the SizeLoggingClientInterceptor class"""

    @pytest.fixture
    def interceptor(self):
        return SizeLoggingClientInterceptor()

    @pytest.fixture
    def mock_request(self):
        mock_req = MagicMock()
        mock_req.SerializeToString.return_value = b"test-data"
        return mock_req

    @pytest.fixture
    def mock_continuation(self):
        return MagicMock()

    @pytest.fixture
    def mock_client_call_details(self):
        return MagicMock()

    @patch("logging.info")
    def test_intercept_unary_unary(
        self,
        mock_log,
        interceptor,
        mock_continuation,
        mock_client_call_details,
        mock_request,
    ):
        interceptor.intercept_unary_unary(
            mock_continuation, mock_client_call_details, mock_request
        )
        mock_log.assert_called_with("Sending unary_unary request of size: 9 bytes")
        mock_continuation.assert_called_once_with(
            mock_client_call_details, mock_request
        )

    @patch("logging.info")
    def test_intercept_unary_stream(
        self,
        mock_log,
        interceptor,
        mock_continuation,
        mock_client_call_details,
        mock_request,
    ):
        interceptor.intercept_unary_stream(
            mock_continuation, mock_client_call_details, mock_request
        )
        mock_log.assert_called_with("Sending unary_stream request of size: 9 bytes")
        mock_continuation.assert_called_once_with(
            mock_client_call_details, mock_request
        )

    @patch("logging.info")
    def test_intercept_stream_unary(
        self, mock_log, interceptor, mock_continuation, mock_client_call_details
    ):
        mock_req1 = MagicMock()
        mock_req1.SerializeToString.return_value = b"data1"
        mock_req2 = MagicMock()
        mock_req2.SerializeToString.return_value = b"data2-longer"

        request_iterator = iter([mock_req1, mock_req2])

        # Need to create a new iterator for the continuation call since the first one will be consumed
        mock_continuation.return_value = "mocked response"

        with patch(
            "client.SizeLoggingClientInterceptor.intercept_stream_unary",
            wraps=interceptor.intercept_stream_unary,
        ) as wrapped_method:
            result = interceptor.intercept_stream_unary(
                mock_continuation, mock_client_call_details, request_iterator
            )

        mock_log.assert_called_with("Sending stream_unary request total size: 16 bytes")
        assert result == "mocked response"


class TestGRPCClient:
    """Tests for the GRPCClient class"""

    def test_init(self, mock_channel, mock_stub):
        """Test the initialization of GRPCClient"""
        with patch("grpc.insecure_channel", return_value=mock_channel), patch(
            "grpc.intercept_channel", return_value=mock_channel
        ), patch.object(
            protocols_pb2_grpc, "MessagingServiceStub", return_value=mock_stub
        ):

            client = GRPCClient(host="testhost", port=12345)

            assert client.current_leader == "testhost:12345"
            assert client.channel == mock_channel
            assert client.stub == mock_stub

    def test_init_with_replicas(self, mock_channel, mock_stub):
        """Test initialization with replica endpoints"""
        with patch("grpc.insecure_channel", return_value=mock_channel), patch(
            "grpc.intercept_channel", return_value=mock_channel
        ), patch.object(
            protocols_pb2_grpc, "MessagingServiceStub", return_value=mock_stub
        ):

            replicas = ["replica1:50051", "replica2:50052"]
            client = GRPCClient(host="testhost", port=12345, replica_endpoints=replicas)

            assert client.replica_endpoints == replicas

    @patch("time.sleep")
    def test_perform_rpc_success(self, mock_sleep, mock_client):
        """Test successful RPC call"""
        mock_rpc = MagicMock()
        mock_rpc.return_value = "success response"

        # Mock the channel_ready_future to return a future that's already done
        mock_future = MagicMock()
        mock_client.channel.channel_ready_future.return_value = mock_future

        result = mock_client.perform_rpc(mock_rpc)

        assert result == "success response"
        mock_rpc.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("logging.error")
    def test_perform_rpc_unavailable_with_leader_discovery(
        self, mock_log, mock_sleep, mock_client
    ):
        """Test RPC call with UNAVAILABLE error and successful leader discovery"""
        mock_rpc = MagicMock()
        mock_rpc.side_effect = [
            grpc.RpcError("Unavailable error"),  # First call fails
            "success response",  # Second call succeeds
        ]

        # Configure the RpcError to have a code method that returns UNAVAILABLE
        mock_rpc.side_effect[0].code = MagicMock(
            return_value=grpc.StatusCode.UNAVAILABLE
        )

        # Mock discover_leader to return a new leader address
        mock_client.discover_leader = MagicMock(return_value="newleader:12345")

        # Mock update_channel
        mock_client.update_channel = MagicMock()

        result = mock_client.perform_rpc(mock_rpc)

        assert result == "success response"
        assert mock_rpc.call_count == 2
        mock_client.discover_leader.assert_called_once()
        mock_client.update_channel.assert_called_once_with("newleader:12345")
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    @patch("logging.error")
    def test_perform_rpc_unavailable_no_leader(self, mock_log, mock_sleep, mock_client):
        """Test RPC call with UNAVAILABLE error and no leader discovery"""
        mock_rpc = MagicMock()
        error = grpc.RpcError("Unavailable error")
        error.code = MagicMock(return_value=grpc.StatusCode.UNAVAILABLE)
        mock_rpc.side_effect = error

        # Mock discover_leader to return None (no leader found)
        mock_client.discover_leader = MagicMock(return_value=None)

        result = mock_client.perform_rpc(mock_rpc, max_retries=3)

        assert result is None
        assert mock_rpc.call_count == 3  # Should try 3 times
        assert mock_client.discover_leader.call_count == 3
        assert mock_sleep.call_count == 3

    @patch("logging.error")
    def test_perform_rpc_non_retryable_error(self, mock_log, mock_client):
        """Test RPC call with a non-retryable error"""
        mock_rpc = MagicMock()
        error = grpc.RpcError("Permission denied")
        error.code = MagicMock(return_value=grpc.StatusCode.PERMISSION_DENIED)
        mock_rpc.side_effect = error

        result = mock_client.perform_rpc(mock_rpc)

        assert result is None
        mock_rpc.assert_called_once()
        mock_log.assert_called_once()

    def test_discover_leader_success(self, mock_client):
        """Test successful leader discovery"""
        # Mock replica endpoints
        mock_client.replica_endpoints = ["replica1:50051", "replica2:50052"]

        # Create mock for replica stub and GetLeader response
        mock_replica_stub = MagicMock()
        mock_response = MagicMock()
        mock_response.leader_address = "leader:50053"
        mock_replica_stub.GetLeader.return_value = mock_response

        with patch("grpc.insecure_channel"), patch.object(
            replica_pb2_grpc, "ReplicaServiceStub", return_value=mock_replica_stub
        ):

            result = mock_client.discover_leader()

            assert result == "leader:50053"
            # Should have called GetLeader on the first replica and returned early
            assert mock_replica_stub.GetLeader.call_count == 1

    def test_discover_leader_all_fail(self, mock_client):
        """Test leader discovery when all replicas fail"""
        # Mock replica endpoints
        mock_client.replica_endpoints = ["replica1:50051", "replica2:50052"]

        # Create mock for replica stub that raises RpcError
        mock_replica_stub = MagicMock()
        error = grpc.RpcError("Failed to connect")
        mock_replica_stub.GetLeader.side_effect = error

        with patch("grpc.insecure_channel"), patch.object(
            replica_pb2_grpc, "ReplicaServiceStub", return_value=mock_replica_stub
        ), patch("logging.error"):

            result = mock_client.discover_leader()

            assert result is None
            # Should have tried both replicas
            assert mock_replica_stub.GetLeader.call_count == 2

    def test_update_channel(self, mock_client):
        """Test updating the channel to a new leader"""
        new_address = "newleader:12345"

        with patch.object(mock_client, "_init_channel") as mock_init:
            mock_client.update_channel(new_address)

            assert mock_client.current_leader == new_address
            mock_init.assert_called_once_with(new_address)

    # Tests for RPC methods

    def test_login(self, mock_client):
        """Test login method"""
        mock_response = MagicMock()
        mock_client.stub.Login.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.login("testuser", "password123")

            assert result == mock_response
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.Login.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.LoginRequest)
            assert request.username == "testuser"
            assert request.password == "password123"

    def test_register(self, mock_client):
        """Test register method"""
        mock_response = MagicMock()
        mock_client.stub.Register.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.register("testuser", "password123")

            assert result == mock_response
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.Register.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.RegisterRequest)
            assert request.username == "testuser"
            assert request.password == "password123"

    def test_send_message(self, mock_client):
        """Test send_message method"""
        mock_response = MagicMock()
        mock_client.stub.SendMessage.return_value = mock_response
        mock_client.username = "sender"

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.send_message("Hello world", "receiver")

            assert result == mock_response
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.SendMessage.call_args
            request = call_args[0][0]
            metadata = call_args[1]["metadata"]
            assert isinstance(request, protocols_pb2.SendMessageRequest)
            assert request.message == "Hello world"
            assert request.receiver == "receiver"
            assert metadata == (("sender", "sender"),)

    def test_get_users(self, mock_client):
        """Test get_users method"""
        mock_response = MagicMock()
        mock_response.status = "success"
        mock_response.usernames = ["user1", "user2", "user3"]
        mock_client.stub.GetUsers.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.get_users("testuser")

            assert result == ["user1", "user2", "user3"]
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.GetUsers.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.GetUsersRequest)
            assert request.username == "testuser"

    def test_get_users_failure(self, mock_client):
        """Test get_users method when response is failure"""
        mock_response = MagicMock()
        mock_response.status = "error"
        mock_client.stub.GetUsers.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.get_users("testuser")

            assert result == []
            assert mock_perform.call_count == 1

    def test_search_users(self, mock_client):
        """Test search_users method"""
        mock_response = MagicMock()
        mock_response.status = "success"
        mock_response.usernames = ["user1", "user2"]
        mock_client.stub.SearchUsers.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.search_users("user")

            assert result == ["user1", "user2"]
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.SearchUsers.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.SearchUsersRequest)
            assert request.query == "user"

    def test_search_users_failure(self, mock_client):
        """Test search_users method when response is failure"""
        mock_response = MagicMock()
        mock_response.status = "error"
        mock_client.stub.SearchUsers.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.search_users("user")

            assert result == []
            assert mock_perform.call_count == 1

    def test_get_recent_messages(self, mock_client):
        """Test get_recent_messages method"""
        mock_response = MagicMock()
        mock_client.stub.GetRecentMessages.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.get_recent_messages("testuser")

            assert result == mock_response
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.GetRecentMessages.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.GetRecentMessagesRequest)
            assert request.username == "testuser"

    def test_get_unread_messages(self, mock_client):
        """Test get_unread_messages method"""
        mock_response = MagicMock()
        mock_client.stub.GetUnreadMessages.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.get_unread_messages("testuser")

            assert result == mock_response
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.GetUnreadMessages.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.GetUnreadMessagesRequest)
            assert request.username == "testuser"

    def test_mark_as_read(self, mock_client):
        """Test mark_as_read method"""
        mock_response = MagicMock()
        mock_client.stub.MarkAsRead.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.mark_as_read([1, 2, 3])

            assert result == mock_response
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.MarkAsRead.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.MarkAsReadRequest)
            assert list(request.message_ids) == [1, 2, 3]

    def test_set_n_unread_messages(self, mock_client):
        """Test set_n_unread_messages method"""
        mock_response = MagicMock()
        mock_client.stub.SetNUnreadMessages.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.set_n_unread_messages("testuser", 5)

            assert result == mock_response
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.SetNUnreadMessages.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.SetNUnreadMessagesRequest)
            assert request.username == "testuser"
            assert request.n_unread_messages == 5

    def test_delete_message(self, mock_client):
        """Test delete_message method"""
        mock_response = MagicMock()
        mock_client.stub.DeleteMessage.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.delete_message("testuser", 42)

            assert result == mock_response
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.DeleteMessage.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.DeleteMessageRequest)
            assert request.username == "testuser"
            assert request.message_id == 42

    def test_delete_account(self, mock_client):
        """Test delete_account method"""
        mock_response = MagicMock()
        mock_client.stub.DeleteAccount.return_value = mock_response

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.delete_account("testuser")

            assert result == mock_response
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.DeleteAccount.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.DeleteAccountRequest)
            assert request.username == "testuser"

    def test_subscribe(self, mock_client):
        """Test subscribe method"""
        mock_stream = MagicMock()
        mock_client.stub.Subscribe.return_value = mock_stream

        with patch.object(
            mock_client, "perform_rpc", wraps=mock_client.perform_rpc
        ) as mock_perform:
            result = mock_client.subscribe("testuser")

            assert result == mock_stream
            assert mock_perform.call_count == 1

            # Verify request was created correctly
            call_args = mock_client.stub.Subscribe.call_args
            request = call_args[0][0]
            assert isinstance(request, protocols_pb2.SubscribeRequest)
            assert request.username == "testuser"

    def test_subscribe_failure(self, mock_client):
        """Test subscribe method when perform_rpc returns None"""
        with patch.object(mock_client, "perform_rpc", return_value=None), patch(
            "logging.error"
        ) as mock_log:
            result = mock_client.subscribe("testuser")

            assert result is None
            mock_log.assert_called_once()


# Integration-style tests (still using mocks but testing multiple components together)


@patch("logging.info")
@patch("grpc.insecure_channel")
@patch("grpc.intercept_channel")
def test_client_with_interceptor(
    mock_intercept_channel, mock_insecure_channel, mock_log
):
    """Test that the client properly uses the interceptor"""
    mock_channel = MagicMock()
    mock_insecure_channel.return_value = mock_channel
    mock_intercept_channel.return_value = mock_channel

    client = GRPCClient(host="localhost", port=50051, intercept=True)

    # Verify that intercept_channel was called with SizeLoggingClientInterceptor
    mock_intercept_channel.assert_called_once()
    args, _ = mock_intercept_channel.call_args
    assert mock_channel in args
    assert isinstance(args[1], SizeLoggingClientInterceptor)


@patch("time.sleep")
@patch("grpc.insecure_channel")
def test_retry_with_leader_discovery_integration(mock_insecure_channel, mock_sleep):
    """Test the retry and leader discovery flow in an integration-style test"""
    # Set up mocks for the channels and stubs
    mock_leader_channel = MagicMock()
    mock_replica_channel = MagicMock()
    mock_new_leader_channel = MagicMock()

    # Mock leader stub that fails
    mock_leader_stub = MagicMock()
    error = grpc.RpcError("Unavailable")
    error.code = MagicMock(return_value=grpc.StatusCode.UNAVAILABLE)
    mock_leader_stub.GetUsers.side_effect = error

    # Mock replica stub that returns a leader
    mock_replica_stub = MagicMock()
    mock_leader_response = MagicMock()
    mock_leader_response.leader_address = "newleader:12345"
    mock_replica_stub.GetLeader.return_value = mock_leader_response

    # Mock new leader stub that succeeds
    mock_new_leader_stub = MagicMock()
    mock_users_response = MagicMock()
    mock_users_response.status = "success"
    mock_users_response.usernames = ["user1", "user2"]
    mock_new_leader_stub.GetUsers.return_value = mock_users_response

    # Configure the insecure_channel mock to return different channels
    # depending on the address
    def channel_side_effect(address):
        if address == "localhost:50051":
            return mock_leader_channel
        elif address == "replica:50052":
            return mock_replica_channel
        elif address == "newleader:12345":
            return mock_new_leader_channel
        else:
            return MagicMock()

    mock_insecure_channel.side_effect = channel_side_effect

    # Configure stubs for each channel
    with patch.object(
        protocols_pb2_grpc, "MessagingServiceStub"
    ) as mock_msg_stub_cls, patch.object(
        replica_pb2_grpc, "ReplicaServiceStub"
    ) as mock_replica_stub_cls:

        mock_msg_stub_cls.side_effect = [mock_leader_stub, mock_new_leader_stub]
        mock_replica_stub_cls.return_value = mock_replica_stub

        # Create client with replicas
        client = GRPCClient(
            host="localhost",
            port=50051,
            intercept=False,
            replica_endpoints=["replica:50052"],
        )

        # Test get_users which should fail on first leader, discover new leader, and succeed
        users = client.get_users("testuser")

        # Verify the flow
        assert users == ["user1", "user2"]
        assert mock_leader_stub.GetUsers.call_count == 1
        assert mock_replica_stub.GetLeader.call_count == 1
        assert mock_new_leader_stub.GetUsers.call_count == 1
        assert client.current_leader == "newleader:12345"
