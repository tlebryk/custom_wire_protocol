# test_frontend.py
import pytest
import tkinter as tk
from types import SimpleNamespace

# Import the module to test.
import frontend

# --- Create fake response and fake GRPC client ---


class FakeResponse:
    def __init__(
        self, status="success", message="ok", username="testuser", messages=None
    ):
        self.status = status
        self.message = message
        self.username = username
        self.messages = messages or []


class FakeGRPCClient:
    def __init__(self):
        self.username = ""

    def login(self, username, password):
        if username == "valid" and password == "valid":
            return FakeResponse(
                status="success", message="Login Successful", username=username
            )
        return FakeResponse(status="failure", message="Invalid credentials")

    def register(self, username, password):
        if username and password:
            return FakeResponse(status="success", message="Registration Succeeded")
        return FakeResponse(status="failure", message="Registration Failed")

    def send_message(self, message, receiver):
        # Return None so that the frontend shows the info message.
        return None

    def get_recent_messages(self, username):
        # Return a dummy recent message
        msg = SimpleNamespace(
            timestamp="2025-02-25T12:00:00.000000+0000",
            **{"from": "alice", "message": "hello", "id": 1},
        )

        class Dummy:
            status = "success"
            messages = [msg]

        return Dummy()

    def get_unread_messages(self, username):
        msg = SimpleNamespace(
            timestamp="2025-02-25T12:00:00.000000+0000",
            **{"from": "bob", "message": "hi", "id": 2},
        )

        class Dummy:
            status = "success"
            messages = [msg]

        return Dummy()

    def mark_as_read(self, message_ids):
        return FakeResponse(status="success", message="Messages marked as read")

    def set_n_unread_messages(self, username, n):
        return FakeResponse(
            status="success", message=f"Set to display {n} unread messages"
        )

    def delete_message(self, username, message_id):
        return FakeResponse(status="success", message="Message Deleted")

    def delete_account(self, username):
        return FakeResponse(status="success", message="Account Deleted")

    def subscribe(self, username):
        # Return an empty iterator for testing
        return iter([])

    def get_users(self, username):
        return ["user1", "user2", "user3"]


# --- Fixtures to create the app and patch messagebox functions ---


@pytest.fixture
def app(monkeypatch):
    # Replace the GRPCClient in the frontend module with our fake
    monkeypatch.setattr(frontend, "GRPCClient", FakeGRPCClient)
    # Create the ChatApp instance
    app = frontend.ChatApp()
    yield app
    # Clean up the Tk instance
    app.destroy()


@pytest.fixture
def fake_messagebox(monkeypatch):
    calls = []

    def fake_showinfo(title, message):
        calls.append(("info", title, message))

    def fake_showerror(title, message):
        calls.append(("error", title, message))

    def fake_showwarning(title, message):
        calls.append(("warning", title, message))

    monkeypatch.setattr(frontend.messagebox, "showinfo", fake_showinfo)
    monkeypatch.setattr(frontend.messagebox, "showerror", fake_showerror)
    monkeypatch.setattr(frontend.messagebox, "showwarning", fake_showwarning)
    return calls


# --- Tests ---


def test_register_success(app, fake_messagebox):
    # Access the register form
    reg_form = app.auth_box.register_form
    reg_form.username_entry.insert(0, "newuser")
    reg_form.password_entry.insert(0, "newpass")
    # Call the register command
    reg_form.register()

    # Check that the info messagebox was called with a success message
    messages = fake_messagebox
    assert any("Registration Succeeded" in msg for typ, _, msg in messages)


def test_login_success(app, fake_messagebox):
    login_form = app.auth_box.login_form
    login_form.username_entry.insert(0, "valid")
    login_form.password_entry.insert(0, "valid")
    # Call the login command
    login_form.login()

    # Process pending UI events.
    app.update()

    # After a successful login, the ChatApp should switch to the chat screen.
    # We can check that certain UI components are now visible.
    assert not app.auth_box.login_form.winfo_ismapped()
    assert app.chat_box.winfo_ismapped()

    # Check that an info messagebox with success message was shown.
    messages = fake_messagebox
    assert any("Login Successful" in msg for typ, _, msg in messages)

    # Also verify that the fake client’s username was set.
    assert app.grpc_client.username == "valid"


def test_login_failure(app, fake_messagebox):
    login_form = app.auth_box.login_form
    login_form.username_entry.insert(0, "invalid")
    login_form.password_entry.insert(0, "wrong")
    login_form.login()

    messages = fake_messagebox
    # In failure, an error messagebox is expected.
    assert any("Invalid credentials" in msg for typ, _, msg in messages)


def test_send_message(app, fake_messagebox):
    # Simulate that the user is already logged in.
    app.grpc_client.username = "valid"
    app.chat_box.username = "valid"

    # Set up the OptionMenu to select a receiver.
    app.chat_box.user_list = ["user1", "user2"]
    app.chat_box.selected_user.set("user1")
    # Insert a message.
    app.chat_box.message_text.insert(0, "Hello there!")

    # Call send_message
    app.chat_box.send_message()

    messages = fake_messagebox
    # Check that an info messagebox with the send confirmation was shown.
    assert any("Message sent to user1" in msg for typ, _, msg in messages)

    # Also verify that the message entry was cleared.
    assert app.chat_box.message_text.get() == ""


def test_fetch_users(app):
    # Simulate fetching users
    app.chat_box.fetch_users()
    # After fetching, the OptionMenu should be updated.
    menu = app.chat_box.user_dropdown["menu"]
    # Get all menu entries by iterating over the menu
    options = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]
    # Check that our fake client returned the expected users.
    assert options == ["user1", "user2", "user3"]


def test_set_unread_messages(app, fake_messagebox):
    # Set a fake username in NNewMessages
    app.n_new_messages.username = "valid"
    # Insert a valid number into the user input.
    app.n_new_messages.user_input.insert(0, "3")
    # Call the method
    app.n_new_messages.set_unread_messages()

    messages = fake_messagebox
    # Check that an info messagebox was shown indicating the new limit.
    assert any("display 3 unread messages" in msg for typ, _, msg in messages)


def test_mark_message_as_read(app, fake_messagebox):
    # Simulate that the user is logged in.
    app.grpc_client.username = "valid"

    # Create a dummy unread message and add it to the messages container.
    dummy_msg = {
        "timestamp": "2025-02-25T12:00:00.000000+0000",
        "from": "bob",
        "message": "Test unread message",
        "id": 999,
    }
    # Call add_unread_message which creates a frame in the unread section.
    app.messages_container.add_unread_message(dummy_msg)
    # Retrieve the frame corresponding to the dummy message.
    msg_frame = app.messages_container.unread_messages_dict.get(999)
    assert msg_frame is not None

    # Now call read_message directly to simulate the user clicking "Read".
    app.messages_container.read_message(999, msg_frame)

    # The unread message should be removed.
    assert 999 not in app.messages_container.unread_messages_dict


def test_delete_account(app, fake_messagebox, monkeypatch):
    # Simulate a logged-in user.
    app.grpc_client.username = "valid"
    app.delete_account_container.username = "valid"

    # Monkey-patch messagebox.askyesno to automatically return True (simulate confirmation).
    monkeypatch.setattr(frontend.messagebox, "askyesno", lambda title, msg: True)

    # Call delete_account.
    app.delete_account_container.delete_account()

    messages = fake_messagebox
    # Check that an info messagebox was shown indicating account deletion.
    assert any("Account Deleted" in msg for typ, _, msg in messages)
