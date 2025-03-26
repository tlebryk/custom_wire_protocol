# test_election_manager.py
import grpc
import pytest

from election_manager import ElectionManager

# --- Helpers for faking gRPC responses ---


class FakeRpcError(grpc.RpcError):
    def __init__(self, code):
        self._code = code

    def code(self):
        return self._code


class DummyChannel:
    def close(self):
        pass


class FakeReplicaStub:
    def __init__(
        self, replica_id=None, throw_error=False, error_code=grpc.StatusCode.UNKNOWN
    ):
        self.replica_id = replica_id
        self.throw_error = throw_error
        self.error_code = error_code

    def GetReplicaID(self, request, timeout):
        if self.throw_error:
            raise FakeRpcError(self.error_code)
        # Return a dummy response object with a 'replica_id' attribute.
        return type("DummyResponse", (object,), {"replica_id": self.replica_id})()


# --- Tests for ElectionManager ---


def test_get_peer_ids_all_success(monkeypatch):
    # Mapping addresses to fake stubs with valid replica IDs.
    mapping = {
        "addr1": FakeReplicaStub(replica_id=1),
        "addr2": FakeReplicaStub(replica_id=2),
    }

    def fake_get_stub(self, addr):
        stub = mapping[addr]
        return stub, DummyChannel()

    monkeypatch.setattr(ElectionManager, "_get_stub", fake_get_stub)
    # local_replica_id is 2, so expect local_address to be set to "addr2".
    em = ElectionManager(replica_addresses=["addr1", "addr2"], local_replica_id=2)
    peer_ids = em.get_peer_ids()
    assert peer_ids == {"addr1": 1, "addr2": 2}
    assert em.local_address == "addr2"


def test_get_peer_ids_with_error(monkeypatch):
    # Simulate addr1 succeeds and addr2 times out.
    mapping = {
        "addr1": FakeReplicaStub(replica_id=1),
        "addr2": FakeReplicaStub(
            throw_error=True, error_code=grpc.StatusCode.DEADLINE_EXCEEDED
        ),
    }

    def fake_get_stub(self, addr):
        stub = mapping[addr]
        return stub, DummyChannel()

    monkeypatch.setattr(ElectionManager, "_get_stub", fake_get_stub)
    em = ElectionManager(replica_addresses=["addr1", "addr2"], local_replica_id=1)
    peer_ids = em.get_peer_ids()
    # Only addr1 returns a valid ID.
    assert peer_ids == {"addr1": 1}
    assert em.local_address == "addr1"


def test_elect_leader_is_leader(monkeypatch):
    # Two replicas: addr1 returns 1, addr2 returns 2; local replica ID is 2.
    mapping = {
        "addr1": FakeReplicaStub(replica_id=1),
        "addr2": FakeReplicaStub(replica_id=2),
    }

    def fake_get_stub(self, addr):
        stub = mapping[addr]
        return stub, DummyChannel()

    monkeypatch.setattr(ElectionManager, "_get_stub", fake_get_stub)
    em = ElectionManager(replica_addresses=["addr1", "addr2"], local_replica_id=2)
    # elect_leader calls get_peer_ids internally.
    is_leader = em.elect_leader()
    assert is_leader is True


def test_elect_leader_not_leader(monkeypatch):
    # Two replicas: addr1 returns 1, addr2 returns 3; local replica ID is 2.
    mapping = {
        "addr1": FakeReplicaStub(replica_id=1),
        "addr2": FakeReplicaStub(replica_id=3),
    }

    def fake_get_stub(self, addr):
        stub = mapping[addr]
        return stub, DummyChannel()

    monkeypatch.setattr(ElectionManager, "_get_stub", fake_get_stub)
    em = ElectionManager(replica_addresses=["addr1", "addr2"], local_replica_id=2)
    is_leader = em.elect_leader()
    assert is_leader is False


def test_notify_election_result_not_winner(monkeypatch):
    # When not the winner, no notifications should be sent.
    fake_notify_calls = {"addr1": 0, "addr2": 0}

    class FakeReplicaStubNotify(FakeReplicaStub):
        def __init__(
            self, replica_id, throw_error=False, error_code=grpc.StatusCode.UNKNOWN
        ):
            super().__init__(
                replica_id=replica_id, throw_error=throw_error, error_code=error_code
            )
            self.address = None

        def NotifyElectionResult(self, request, timeout):
            fake_notify_calls[self.address] += 1
            return type(
                "DummyNotifyResponse",
                (object,),
                {"success": True, "message": "Notified"},
            )()

    mapping = {
        "addr1": FakeReplicaStubNotify(replica_id=1),
        "addr2": FakeReplicaStubNotify(replica_id=2),
    }

    def fake_get_stub(self, addr):
        stub = mapping[addr]
        stub.address = addr
        return stub, DummyChannel()

    monkeypatch.setattr(ElectionManager, "_get_stub", fake_get_stub)
    em = ElectionManager(replica_addresses=["addr1", "addr2"], local_replica_id=2)
    em.local_address = "addr2"
    # When not winning, notify_election_result should return immediately without notifying.
    em.notify_election_result(won=False)
    assert fake_notify_calls["addr1"] == 0
    assert fake_notify_calls["addr2"] == 0
