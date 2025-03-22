# tests/test_election_manager_get_peer_ids.py
import pytest
from election_manager import ElectionManager
import replica_pb2


# A dummy stub that simulates a replica's response.
class DummyReplicaStub:
    def __init__(self, replica_id):
        self.replica_id = replica_id

    def GetReplicaID(self, request):
        response = replica_pb2.GetReplicaIDResponse()
        response.replica_id = self.replica_id
        return response


# Dummy _get_stub for success: returns a DummyReplicaStub by extracting a number from the address.
def dummy_get_stub(self, address: str):
    try:
        rid = int(address[-1])
    except ValueError:
        rid = 0
    return DummyReplicaStub(rid)


# Dummy _get_stub for failure: if the address contains the word "fail", raise an exception.
def dummy_get_stub_failure(self, address: str):
    if "fail" in address:
        raise Exception("Simulated failure")
    try:
        rid = int(address[-1])
    except ValueError:
        rid = 0
    return DummyReplicaStub(rid)


@pytest.fixture
def election_manager_success(monkeypatch):
    # For testing, simulate three peer addresses: "replica1", "replica2", "replica3".
    replica_addresses = ["replica1", "replica2", "replica3"]
    local_replica_id = 3
    em = ElectionManager(replica_addresses, local_replica_id)
    # Patch the _get_stub method so that our dummy_get_stub is used.
    monkeypatch.setattr(ElectionManager, "_get_stub", dummy_get_stub)
    return em


def test_get_peer_ids_success(election_manager_success):
    peer_ids = election_manager_success.get_peer_ids()
    # We expect IDs 1, 2, and 3 from the addresses.
    assert sorted(peer_ids) == [1, 2, 3]


@pytest.fixture
def election_manager_failure(monkeypatch):
    # Simulate two good peers and one failing peer.
    replica_addresses = ["replica1", "fail_replica", "replica3"]
    local_replica_id = 3
    em = ElectionManager(replica_addresses, local_replica_id)
    # Patch _get_stub so that the address containing "fail" raises an exception.
    monkeypatch.setattr(ElectionManager, "_get_stub", dummy_get_stub_failure)
    return em


def test_get_peer_ids_failure(election_manager_failure):
    peer_ids = election_manager_failure.get_peer_ids()
    # "replica1" yields 1, "replica3" yields 3, and "fail_replica" causes an exception and is skipped.
    assert sorted(peer_ids) == [1, 3]


@pytest.mark.parametrize(
    "peer_ids, expected",
    [
        ([1, 2], True),
        ([5, 2], False),
    ],
)
def test_elect_leader(monkeypatch, election_manager_success, peer_ids, expected):
    monkeypatch.setattr(election_manager_success, "get_peer_ids", lambda: peer_ids)
    assert election_manager_success.elect_leader() == expected
