# tests/test_websocket.py
import pytest
import json
from client import WebSocketClient


@pytest.mark.usefixtures("websocket_server")
class TestWebSocketClientServer:
    @pytest.fixture
    def client(self):
        """
        Fixture to create a WebSocket client instance.
        """
        return WebSocketClient(host="localhost", port=8000, mode="json")

    @pytest.mark.timeout(10)  # Sets a 5-second timeout for the test
    def test_handshake_success(self, client):
        """
        Test that the client can successfully perform a handshake with the server.
        """
        assert client.connect(), "Handshake should succeed"

    @pytest.mark.timeout(10)  # Sets a 5-second timeout for the test
    def test_send_receive_message(self, client):
        """
        Test sending a message to the server and receiving a response.
        """
        assert client.connect(), "Handshake should succeed"

        test_message = {"action": "echo", "message": "Hello, Server!"}
        client.send(test_message)

        response = client.receive()
        assert response is not None, "Should receive a response from the server"
        assert response.get("status") == "success", "Response status should be success"
        assert (
            response.get("message") == "Hello, Server!"
        ), "Echoed message should match"

    @pytest.mark.timeout(10)  # Sets a 5-second timeout for the test
    def test_invalid_action(self, client):
        """
        Test sending an invalid action and expecting an error response.
        """
        assert client.connect(), "Handshake should succeed"

        invalid_message = {"action": "invalid_action", "data": "Test"}
        client.send(invalid_message)

        response = client.receive()
        assert response is not None, "Should receive a response from the server"
        assert response.get("status") == "error", "Response status should be error"
        assert "Unknown action" in response.get(
            "message", ""
        ), "Error message should indicate unknown action"

    def test_missing_action_field(self, client):
        """
        Test sending a message without the 'action' field and expecting an error.
        """
        assert client.connect(), "Handshake should succeed"

        invalid_message = {"action": "login", "username": "testuser"}
        client.send(invalid_message)

        response = client.receive()
        assert response is not None, "Should receive a response from the server"
        assert response.get("status") == "error", "Response status should be error"
        assert "Username and password are required" in response.get(
            "message", ""
        ), "Error message should indicate missing password"

    @pytest.mark.timeout(10)  # Sets a 5-second timeout for the test
    def test_close_connection(self, client):
        """
        Test that the client can gracefully close the connection.
        """
        assert client.connect(), "Handshake should succeed"

        client.close()

        # Attempt to send a message after closing should fail
        client.send({"action": "echo", "message": "Should fail"})
        response = client.receive()
        # TODO: fix this to throw exeption??
        assert response is None, "Should not receive a response from the server"


@pytest.mark.usefixtures("websocket_server")
class TestWebSocketClientServerCustom(TestWebSocketClientServer):
    @pytest.fixture
    def client(self):
        """
        Fixture to create a WebSocket client instance.
        """
        return WebSocketClient(host="localhost", port=8000, mode="custom")


if __name__ == "__main__":
    pytest.main()
