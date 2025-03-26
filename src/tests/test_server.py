# test_server_functions.py
import time
import grpc
import socket
import pytest

# Import functions and globals from server.py
from server import send_heartbeats, get_external_host, EXTERNAL_HOST, SERVER_PORT
import replica_pb2_grpc
import replica_pb2

# ===== Tests for get_external_host =====


def test_get_external_host_custom():
    """
    If the host is not one of the default local addresses, the function should return it unchanged.
    """
    # When host is custom, no socket connection is attempted.
    result = get_external_host("example.com")
    assert result == "example.com"


def test_get_external_host_local(monkeypatch):
    """
    When host is a local address, the function should try to determine the external IP.
    We'll simulate a socket that returns a fake IP.
    """
    fake_ip = "192.168.1.100"

    class DummySocket:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self, address):
            # Simulate a successful connection; do nothing.
            pass

        def getsockname(self):
            return (fake_ip, 12345)

        def close(self):
            pass

    # Replace socket.socket in the server module with our DummySocket.
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: DummySocket())
    result = get_external_host("0.0.0.0")
    assert result == fake_ip


def test_get_external_host_exception(monkeypatch):
    """
    Simulate an exception during the socket connection so that get_external_host falls back to socket.gethostname().
    """
    fake_hostname = "myhostname"
    # Make gethostname return our fake hostname.
    monkeypatch.setattr(socket, "gethostname", lambda: fake_hostname)

    # Create a dummy socket that raises an exception on connect.
    def dummy_socket_fail(*args, **kwargs):
        class FailSocket:
            def connect(self, address):
                raise Exception("connection failed")

            def close(self):
                pass

            def getsockname(self):
                return ("should_not_be_used", 0)

        return FailSocket()

    monkeypatch.setattr(socket, "socket", dummy_socket_fail)
    result = get_external_host("localhost")
    assert result == fake_hostname


# ===== Tests for send_heartbeats =====


def test_send_heartbeats(monkeypatch):
    """
    Test send_heartbeats by:
      - Setting global EXTERNAL_HOST and SERVER_PORT so that the leader address is defined.
      - Providing replica addresses (including the leader's) and ensuring that the leader is skipped.
      - Replacing gRPC channel creation and heartbeat stub so that we record calls.
      - Overriding time.sleep to break the infinite loop.
    """
    # Set the globals in the server module.
    leader_addr = "192.168.0.1:50051"
    # We assign new values to these globals (they're mutable at the module level)
    import server

    server.EXTERNAL_HOST = "192.168.0.1"
    server.SERVER_PORT = "50051"
    # Prepare replica addresses: one is the leader, one is a different replica.
    replica_addresses = [leader_addr, "192.168.0.2:50051"]

    # Lists to record dummy behavior.
    heartbeat_calls = []  # records leader_id sent in heartbeat requests
    channels_created = []  # records addresses for which insecure_channel was called

    # Dummy insecure_channel: record the address and return a dummy channel.
    def dummy_insecure_channel(address):
        channels_created.append(address)

        class DummyChannel:
            def close(self):
                pass

        return DummyChannel()

    monkeypatch.setattr(grpc, "insecure_channel", dummy_insecure_channel)

    # Dummy channel_ready_future: return an object whose result method does nothing.
    class DummyFuture:
        def result(self, timeout):
            return None

    monkeypatch.setattr(grpc, "channel_ready_future", lambda channel: DummyFuture())

    # Dummy ReplicaServiceStub: record heartbeat calls.
    class DummyReplicaServiceStub:
        def __init__(self, channel):
            self.channel = channel

        def Heartbeat(self, request, timeout):
            heartbeat_calls.append(request.leader_id)
            # Return a dummy response with a 'message' attribute.
            return type("DummyResponse", (), {"message": "OK"})()

    monkeypatch.setattr(replica_pb2_grpc, "ReplicaServiceStub", DummyReplicaServiceStub)

    # Override time.sleep to break out of the infinite loop after one iteration.
    def dummy_sleep(seconds):
        raise StopIteration("Break loop after one iteration")

    monkeypatch.setattr(time, "sleep", dummy_sleep)

    # Call send_heartbeats and expect StopIteration to break the loop.
    with pytest.raises(StopIteration):
        send_heartbeats(replica_addresses)

    # Verify that the leader address was skipped.
    assert leader_addr not in channels_created
    # Verify that insecure_channel was called for the other replica.
    assert "192.168.0.2:50051" in channels_created
    # Verify that the dummy Heartbeat method was called once.
    # The heartbeat request contains leader_addr as the leader_id.
    assert len(heartbeat_calls) == 1
    assert heartbeat_calls[0] == leader_addr
