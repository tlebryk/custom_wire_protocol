# test_load_balancer.py
import grpc
import pytest
import logging

from load_balancer import LoadBalancerServicer
import protocols_pb2
import protocols_pb2_grpc
import replica_pb2_grpc


# --- Dummy context for simulating gRPC ServicerContext ---
class DummyContext:
    def __init__(self):
        self._code = None
        self._details = None

    def invocation_metadata(self):
        return []

    def set_code(self, code):
        self._code = code

    def set_details(self, details):
        self._details = details


# --- Fake RpcError for simulating gRPC errors ---
class FakeRpcError(grpc.RpcError):
    def __init__(self, code, details=""):
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


# --- Fake channel that stores the address ---
class FakeChannel:
    def __init__(self, addr):
        self.addr = addr

    def close(self):
        pass


# --- Fake Replica Stub for leader discovery ---
class FakeReplicaStub:
    def __init__(self, leader_address="", throw_error=False):
        self._leader_address = leader_address
        self._throw_error = throw_error

    def GetLeader(self, request, timeout):
        if self._throw_error:
            raise Exception("Fake error")
        # Return a fake response with a 'leader_address' attribute.
        return type(
            "FakeGetLeaderResponse", (), {"leader_address": self._leader_address}
        )()


# --- Fake Messaging Stub for forwarding RPCs ---
class FakeMessagingStub:
    def __init__(self, behavior=None):
        # behavior is a dict mapping RPC method names to functions.
        self.behavior = behavior or {}

    def __getattr__(self, name):
        if name in self.behavior:
            return self.behavior[name]

        # Default: return a function that returns a dummy response.
        def default_method(request, metadata):
            return "default_response"

        return default_method


# -------------------------------
# Tests for leader discovery
# -------------------------------
def test_update_leader_success(monkeypatch):
    """
    Simulate that among two replica endpoints, the second one returns a valid leader address.
    """

    # Replace grpc.insecure_channel to produce a FakeChannel storing the address.
    def fake_insecure_channel(addr):
        return FakeChannel(addr)

    monkeypatch.setattr(grpc, "insecure_channel", fake_insecure_channel)

    # Monkeypatch ReplicaServiceStub (from replica_pb2_grpc) to return our fake replica stub.
    def fake_replica_stub(channel):
        if channel.addr == "replica1":
            return FakeReplicaStub(leader_address="")  # no leader provided
        elif channel.addr == "replica2":
            return FakeReplicaStub(leader_address="leader:1234")
        return FakeReplicaStub(leader_address="")

    monkeypatch.setattr(replica_pb2_grpc, "ReplicaServiceStub", fake_replica_stub)

    lb = LoadBalancerServicer(
        replica_endpoints=["replica1", "replica2"], intercept=False
    )
    lb._update_leader()
    assert lb.current_leader == "leader:1234"


def test_update_leader_failure(monkeypatch):
    """
    Simulate that none of the replicas provide a leader address.
    """

    def fake_insecure_channel(addr):
        return FakeChannel(addr)

    monkeypatch.setattr(grpc, "insecure_channel", fake_insecure_channel)

    def fake_replica_stub(channel):
        # Always return no leader.
        return FakeReplicaStub(leader_address="")

    monkeypatch.setattr(replica_pb2_grpc, "ReplicaServiceStub", fake_replica_stub)

    lb = LoadBalancerServicer(
        replica_endpoints=["replica1", "replica2"], intercept=False
    )
    lb._update_leader()
    assert lb.current_leader is None


# -------------------------------
# Tests for _get_leader_stub
# -------------------------------
def test_get_leader_stub_success(monkeypatch):
    """
    When a leader is already known, _get_leader_stub should return a stub.
    """
    lb = LoadBalancerServicer(replica_endpoints=["replica1"], intercept=False)
    lb.current_leader = "leader:1234"

    def fake_insecure_channel(addr):
        return FakeChannel(addr)

    monkeypatch.setattr(grpc, "insecure_channel", fake_insecure_channel)

    # Replace MessagingServiceStub to return a fake messaging stub.
    def fake_messaging_stub(channel):
        return FakeMessagingStub(
            behavior={"Login": lambda req, metadata: "login_success"}
        )

    monkeypatch.setattr(protocols_pb2_grpc, "MessagingServiceStub", fake_messaging_stub)

    stub = lb._get_leader_stub()
    response = stub.Login(None, [])
    assert response == "login_success"


# -------------------------------
# Tests for forwarding RPC calls (_forward_rpc)
# -------------------------------
def test_forward_rpc_success(monkeypatch):
    """
    Test that a normal (non-streaming) RPC is forwarded successfully.
    """
    lb = LoadBalancerServicer(replica_endpoints=["replica1"], intercept=False)
    lb.current_leader = "leader:1234"

    fake_stub = FakeMessagingStub(behavior={"Login": lambda req, metadata: "login_ok"})
    monkeypatch.setattr(lb, "_get_leader_stub", lambda: fake_stub)

    dummy_context = DummyContext()
    dummy_request = protocols_pb2.LoginRequest(username="user", password="pass")
    response = lb._forward_rpc("Login", dummy_request, dummy_context)
    assert response == "login_ok"


def test_forward_rpc_retry_success(monkeypatch):
    """
    Simulate that the first attempt of an RPC call fails with UNAVAILABLE,
    then after leader update the retry succeeds.
    """
    lb = LoadBalancerServicer(replica_endpoints=["replica1"], intercept=False)
    lb.current_leader = "leader:1234"
    call_count = [0]

    def fake_login(request, metadata):
        if call_count[0] == 0:
            call_count[0] += 1
            raise FakeRpcError(grpc.StatusCode.UNAVAILABLE)
        else:
            return "retry_success"

    fake_stub = FakeMessagingStub(behavior={"Login": fake_login})
    monkeypatch.setattr(lb, "_get_leader_stub", lambda: fake_stub)
    # Monkeypatch _update_leader to do nothing (or simulate a successful update).
    monkeypatch.setattr(lb, "_update_leader", lambda: None)

    dummy_context = DummyContext()
    dummy_request = protocols_pb2.LoginRequest(username="user", password="pass")
    response = lb._forward_rpc("Login", dummy_request, dummy_context)
    assert response == "retry_success"
    assert call_count[0] == 1


def test_forward_rpc_non_retryable(monkeypatch):
    """
    Simulate a non-retryable error (e.g. INVALID_ARGUMENT) so that the RPC fails without retry.
    """
    lb = LoadBalancerServicer(replica_endpoints=["replica1"], intercept=False)
    lb.current_leader = "leader:1234"

    def fake_login(request, metadata):
        raise FakeRpcError(grpc.StatusCode.INVALID_ARGUMENT, "invalid argument")

    fake_stub = FakeMessagingStub(behavior={"Login": fake_login})
    monkeypatch.setattr(lb, "_get_leader_stub", lambda: fake_stub)

    dummy_context = DummyContext()
    dummy_request = protocols_pb2.LoginRequest(username="user", password="pass")
    response = lb._forward_rpc("Login", dummy_request, dummy_context)
    assert response is None
    assert dummy_context._code == grpc.StatusCode.INVALID_ARGUMENT
    assert dummy_context._details == "invalid argument"


def test_forward_rpc_general_exception(monkeypatch):
    """
    Simulate a general (non-gRPC) exception during RPC forwarding.
    """
    lb = LoadBalancerServicer(replica_endpoints=["replica1"], intercept=False)
    lb.current_leader = "leader:1234"

    def fake_login(request, metadata):
        raise ValueError("oops")

    fake_stub = FakeMessagingStub(behavior={"Login": fake_login})
    monkeypatch.setattr(lb, "_get_leader_stub", lambda: fake_stub)

    dummy_context = DummyContext()
    dummy_request = protocols_pb2.LoginRequest(username="user", password="pass")
    response = lb._forward_rpc("Login", dummy_request, dummy_context)
    assert response is None
    assert dummy_context._code == grpc.StatusCode.INTERNAL
    assert dummy_context._details == "Internal load balancer error"


# -------------------------------
# Test for streaming RPC forwarding (Subscribe)
# -------------------------------
def test_subscribe_success(monkeypatch):
    """
    Test that the Subscribe streaming RPC is forwarded properly.
    """
    lb = LoadBalancerServicer(replica_endpoints=["replica1"], intercept=False)
    lb.current_leader = "leader:1234"

    def fake_subscribe(request, metadata):
        # Return an iterator over fake responses.
        responses = [1, 2, 3]
        return iter(responses)

    fake_stub = FakeMessagingStub(behavior={"Subscribe": fake_subscribe})
    monkeypatch.setattr(lb, "_get_leader_stub", lambda: fake_stub)

    dummy_context = DummyContext()
    dummy_request = protocols_pb2.SubscribeRequest(username="user")
    responses = list(lb.Subscribe(dummy_request, dummy_context))
    assert responses == [1, 2, 3]
