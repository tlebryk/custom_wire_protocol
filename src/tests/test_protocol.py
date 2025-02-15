# tests/test_protocol.py

import pytest
import struct
import sys


from custom_protocol import Encoder, load_protocols, Decoder


@pytest.fixture(scope="module")
def protocols():
    """
    Fixture to load protocols.json once for all tests.
    """
    return load_protocols()


@pytest.fixture(scope="module")
def encoder_decoder(protocols):
    """
    Fixture to instantiate Encoder and Decoder with loaded protocols.
    """
    encoder = Encoder(protocols)
    decoder = Decoder(protocols)
    return encoder, decoder


def test_encode_decode_integration(encoder_decoder):
    """
    Integration Test: Encode a message and then decode it, verifying the result matches the original message.
    """
    encoder, decoder = encoder_decoder

    original_message = {"action": "login", "username": "Bob", "password": "password456"}

    # Encode the message
    encoded_message = encoder.encode_message(original_message)

    # Decode the message
    decoded_message = decoder.decode_message(encoded_message)

    # Verify that decoded message matches the original
    assert (
        decoded_message == original_message
    ), "Decoded message does not match the original."


# Optional: Additional Tests for Error Handling and Edge Cases


def test_encode_missing_field(encoder_decoder):
    """
    Test encoding a message with a missing required field raises ValueError.
    """
    encoder, _ = encoder_decoder
    incomplete_message = {
        "action": "login",
        "username": "Charlie",
        # 'password' field is missing
    }

    with pytest.raises(ValueError, match="Missing field 'password'"):
        encoder.encode_message(incomplete_message)


def test_decode_unknown_action_id(encoder_decoder):
    """
    Test decoding a message with an unknown action ID raises ValueError.
    """
    _, decoder = encoder_decoder
    unknown_action_id = 99
    binary_data = struct.pack("!B", unknown_action_id)  # Only action ID, no fields

    with pytest.raises(ValueError, match="Unknown action ID: 99"):
        decoder.decode_message(binary_data)


def test_encode_string_too_long(encoder_decoder):
    """
    Test encoding a string that exceeds the maximum allowed length raises ValueError.
    """
    encoder, _ = encoder_decoder
    long_string = "a" * 70000  # 70,000 characters, exceeds 65535 bytes
    message = {"action": "login", "username": "Dave", "password": long_string}

    with pytest.raises(ValueError, match="String too long to encode"):
        encoder.encode_message(message)


def test_decode_incomplete_string(encoder_decoder):
    """
    Test decoding a message where the string length indicates more bytes than provided raises ValueError.
    """
    _, decoder = encoder_decoder
    action_id = 1  # 'login'
    username = "Eve"
    # Intentionally set incorrect length for 'username' (e.g., length = 10, but only 3 bytes provided)
    incorrect_length = 10
    username_encoded = struct.pack("!H", incorrect_length) + username.encode("utf-8")
    password = "password789"
    password_encoded = struct.pack(
        "!H", len(password.encode("utf-8"))
    ) + password.encode("utf-8")
    binary_data = struct.pack("!B", action_id) + username_encoded + password_encoded

    with pytest.raises(
        ValueError, match="Data too short to contain the expected string"
    ):
        decoder.decode_message(binary_data)


def test_encode_decode_message_with_int(encoder_decoder):
    """
    Integration Test: Encode and decode a message containing an integer and a list.
    """
    encoder, decoder = encoder_decoder

    # Example message with integer and list
    original_message = {
        "action": "set_n_unread_messages",
        "username": "Alice",
        "n_unread_messages": 25,
    }

    actual_encoded = encoder.encode_message(original_message)
    decoded_message = decoder.decode_message(actual_encoded)

    assert (
        decoded_message == original_message
    ), "Decoded message does not match the original."


def test_encode_decode_message_with_list(encoder_decoder):
    """
    Integration Test: Encode and decode a message containing an integer and a list.
    """
    encoder, decoder = encoder_decoder

    # Example message with integer and list
    original_message = {
        "action": "mark_as_read",
        "message_ids": [1, 2, 3],
    }

    actual_encoded = encoder.encode_message(original_message)
    decoded_message = decoder.decode_message(actual_encoded)
    assert (
        decoded_message == original_message
    ), "Decoded message does not match the original."


def test_encode_decode_message_with_object(encoder_decoder):
    """
    Integration Test: Encode and decode a message containing an integer and a list.
    """
    encoder, decoder = encoder_decoder

    # Example message with integer and list
    original_message = {
        "action": "unread_messages",
        "messages": [
            {
                "id": 1,
                "from": "bob",
                "message": "Hey!",
                "timestamp": "2023-10-02T13:00:00Z",
            },
            {
                "id": 2,
                "from": "alice",
                "message": "Hello!",
                "timestamp": "2023-10-01T12:00:00Z",
            },
        ],
        "status": "success",
    }

    actual_encoded = encoder.encode_message(original_message)
    decoded_message = decoder.decode_message(actual_encoded)
    assert (
        decoded_message == original_message
    ), "Decoded message does not match the original."


# if name == "__main__":
#     frame=bytearray(b'\x81\x87\xac:\xcf\x99\xad:\xce\xf8\xac;\xae')

#     with open("test_frame.bin", "wb") as f:
#         f.write(frame)

#     with open("test_frame.bin", "rb") as f:
#         frame_read = f.read()

#     assert frame == frame_read, "Frame written to disk not read correctly back"

#     _, decoder = encoder_decoder
#     decoded_message = decoder.decode_message(frame_read)

# assert decoded_message["action"] == "send_message", "Decoded action not correct"
# assert decoded_message["message"] == "Hello, Bob!", "Decoded message not correct"
# assert decoded_message["receiver"] == "Bob", "Decoded receiver not correct"
