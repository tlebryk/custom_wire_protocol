# test_replication_manager.py
import pytest
from replication_manager import ReplicationManager

# --- Fake response and stub classes ---


class FakeResponse:
    def __init__(self, success, message=""):
        self.success = success
        self.message = message


class FakeStub:
    """
    A fake stub that implements the expected RPC methods.
    The responses dictionary maps method names to either:
      - a FakeResponse instance (for a static response), or
      - a callable that accepts the request and returns a response.
    """

    def __init__(self, responses):
        self.responses = responses

    def RegisterUser(self, request):
        res = self.responses.get("RegisterUser")
        return res(request) if callable(res) else res

    def DeleteAccount(self, request):
        res = self.responses.get("DeleteAccount")
        return res(request) if callable(res) else res

    def InsertMessage(self, request):
        res = self.responses.get("InsertMessage")
        return res(request) if callable(res) else res

    def MarkMessagesAsRead(self, request):
        res = self.responses.get("MarkMessagesAsRead")
        return res(request) if callable(res) else res

    def MarkMessagesDelivered(self, request):
        res = self.responses.get("MarkMessagesDelivered")
        return res(request) if callable(res) else res

    def SetNUnreadMessages(self, request):
        res = self.responses.get("SetNUnreadMessages")
        return res(request) if callable(res) else res

    def DeleteMessage(self, request):
        res = self.responses.get("DeleteMessage")
        return res(request) if callable(res) else res


# --- Tests for replicate_register_user ---


def test_replicate_register_user_all_success(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1", "replica2"])
    stubs = {
        "replica1": FakeStub({"RegisterUser": FakeResponse(True, "ok")}),
        "replica2": FakeStub({"RegisterUser": FakeResponse(True, "ok")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_register_user("user", "pass")
    assert result is True


def test_replicate_register_user_one_failure(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1", "replica2"])
    stubs = {
        "replica1": FakeStub({"RegisterUser": FakeResponse(True, "ok")}),
        "replica2": FakeStub({"RegisterUser": FakeResponse(False, "error")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_register_user("user", "pass")
    assert result is False


def test_replicate_register_user_exception(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    # Simulate an exception when creating the stub.
    manager._get_stub = lambda address: (_ for _ in ()).throw(
        Exception("connection error")
    )
    result = manager.replicate_register_user("user", "pass")
    assert result is False


# --- Tests for replicate_delete_account ---


def test_replicate_delete_account_all_success(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1", "replica2"])
    stubs = {
        "replica1": FakeStub({"DeleteAccount": FakeResponse(True, "ok")}),
        "replica2": FakeStub({"DeleteAccount": FakeResponse(True, "ok")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_delete_account("user")
    assert result is True


def test_replicate_delete_account_failure(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    stubs = {
        "replica1": FakeStub({"DeleteAccount": FakeResponse(False, "error")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_delete_account("user")
    assert result is False


def test_replicate_delete_account_exception(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    manager._get_stub = lambda address: (_ for _ in ()).throw(Exception("error"))
    result = manager.replicate_delete_account("user")
    assert result is False


# --- Tests for replicate_insert_message ---


def test_replicate_insert_message_all_success(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1", "replica2"])
    stubs = {
        "replica1": FakeStub({"InsertMessage": FakeResponse(True, "ok")}),
        "replica2": FakeStub({"InsertMessage": FakeResponse(True, "ok")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_insert_message(
        "sender", "content", "receiver", "timestamp"
    )
    assert result is True


def test_replicate_insert_message_failure(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    stubs = {
        "replica1": FakeStub({"InsertMessage": FakeResponse(False, "failed")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_insert_message(
        "sender", "content", "receiver", "timestamp"
    )
    assert result is False


def test_replicate_insert_message_exception(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    manager._get_stub = lambda address: (_ for _ in ()).throw(Exception("error"))
    result = manager.replicate_insert_message(
        "sender", "content", "receiver", "timestamp"
    )
    assert result is False


# --- Tests for replicate_mark_messages_as_read ---


def test_replicate_mark_messages_as_read_all_success(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1", "replica2"])
    stubs = {
        "replica1": FakeStub({"MarkMessagesAsRead": FakeResponse(True, "ok")}),
        "replica2": FakeStub({"MarkMessagesAsRead": FakeResponse(True, "ok")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_mark_messages_as_read([1, 2, 3])
    assert result is True


def test_replicate_mark_messages_as_read_failure(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    stubs = {
        "replica1": FakeStub({"MarkMessagesAsRead": FakeResponse(False, "failed")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_mark_messages_as_read([1, 2, 3])
    assert result is False


def test_replicate_mark_messages_as_read_exception(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    manager._get_stub = lambda address: (_ for _ in ()).throw(Exception("error"))
    result = manager.replicate_mark_messages_as_read([1, 2, 3])
    assert result is False


# --- Tests for replicate_mark_messages_delivered ---


def test_replicate_mark_messages_delivered_all_success(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1", "replica2"])
    stubs = {
        "replica1": FakeStub({"MarkMessagesDelivered": FakeResponse(True, "ok")}),
        "replica2": FakeStub({"MarkMessagesDelivered": FakeResponse(True, "ok")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_mark_messages_delivered("user_id")
    assert result is True


def test_replicate_mark_messages_delivered_failure(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    stubs = {
        "replica1": FakeStub({"MarkMessagesDelivered": FakeResponse(False, "failed")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_mark_messages_delivered("user_id")
    assert result is False


def test_replicate_mark_messages_delivered_exception(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    manager._get_stub = lambda address: (_ for _ in ()).throw(Exception("error"))
    result = manager.replicate_mark_messages_delivered("user_id")
    assert result is False


# --- Tests for replicate_set_n_unread_messages ---


def test_replicate_set_n_unread_messages_all_success(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1", "replica2"])
    stubs = {
        "replica1": FakeStub({"SetNUnreadMessages": FakeResponse(True, "ok")}),
        "replica2": FakeStub({"SetNUnreadMessages": FakeResponse(True, "ok")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_set_n_unread_messages("user", 5)
    assert result is True


def test_replicate_set_n_unread_messages_failure(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    stubs = {
        "replica1": FakeStub({"SetNUnreadMessages": FakeResponse(False, "failed")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_set_n_unread_messages("user", 5)
    assert result is False


def test_replicate_set_n_unread_messages_exception(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    manager._get_stub = lambda address: (_ for _ in ()).throw(Exception("error"))
    result = manager.replicate_set_n_unread_messages("user", 5)
    assert result is False


# --- Tests for replicate_delete_message ---


def test_replicate_delete_message_all_success(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1", "replica2"])
    stubs = {
        "replica1": FakeStub({"DeleteMessage": FakeResponse(True, "ok")}),
        "replica2": FakeStub({"DeleteMessage": FakeResponse(True, "ok")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_delete_message(10)
    assert result is True


def test_replicate_delete_message_failure(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    stubs = {
        "replica1": FakeStub({"DeleteMessage": FakeResponse(False, "failed")}),
    }
    manager._get_stub = lambda address: stubs[address]
    result = manager.replicate_delete_message(10)
    assert result is False


def test_replicate_delete_message_exception(monkeypatch):
    manager = ReplicationManager(replica_addresses=["replica1"])
    manager._get_stub = lambda address: (_ for _ in ()).throw(Exception("error"))
    result = manager.replicate_delete_message(10)
    assert result is False
