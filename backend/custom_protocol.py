import json

# encoder.py
import struct
from typing import Dict, Any


# undo hardcode
def load_protocols(
    file_path="/home/tlebryk/262_distributed_systems/custom_wire_design/configs/protocols.json",
):
    with open(file_path, "r") as f:
        protocols = json.load(f)
    return protocols


class Encoder:
    def __init__(self, protocols: Dict[str, Any]):
        self.protocols = protocols
        self.action_ids = protocols["action_ids"]
        self.messages = protocols["messages"]

    def encode_message(self, message_obj: Dict[str, Any]) -> bytes:
        message_type = message_obj.get("action")
        if not message_type:
            raise ValueError("Message object must have an 'action' field.")

        if message_type not in self.messages:
            raise ValueError(f"Unknown message type: {message_type}")

        action_id = self.action_ids.get(message_type)
        if action_id is None:
            raise ValueError(f"No action ID defined for message type: {message_type}")

        # Start with the action ID (1 byte)
        encoded = struct.pack("!B", action_id)

        # Encode each field based on the schema
        for field_name, field_spec in self.messages[message_type]["fields"].items():
            field_value = message_obj.get(field_name)
            if field_value is None:
                raise ValueError(
                    f"Missing field '{field_name}' in message '{message_type}'."
                )

            field_type = field_spec["type"]
            if field_type == "string":
                encoded += self.encode_string(field_value)
            else:
                raise NotImplementedError(f"Unsupported field type: {field_type}")

        return encoded

    @staticmethod
    def encode_string(value: str) -> bytes:
        encoded_str = value.encode("utf-8")
        length = len(encoded_str)
        if length > 65535:
            raise ValueError("String too long to encode (max 65535 bytes).")
        return struct.pack("!H", length) + encoded_str


# decoder.py
import struct
from typing import Dict, Any


class Decoder:
    def __init__(self, protocols: Dict[str, Any]):
        self.protocols = protocols
        self.action_ids = protocols["action_ids"]
        self.messages = protocols["messages"]
        # Create reverse mapping from action_id to action_type
        self.id_to_action = {v: k for k, v in self.action_ids.items()}

    def decode_message(self, data: bytes) -> Dict[str, Any]:
        offset = 0
        if len(data) < 1:
            raise ValueError("Data too short to contain action ID.")
        print(f"Data: {data}")
        # Unpack action ID (1 byte)
        action_id = struct.unpack_from("!B", data, offset)[0]
        offset += 1

        action_type = self.id_to_action.get(action_id)
        if not action_type:
            raise ValueError(f"Unknown action ID: {action_id}")

        message_schema = self.messages.get(action_type)
        if not message_schema:
            raise ValueError(f"No schema defined for action type: {action_type}")

        message_obj = {"action": action_type}

        for field_name, field_spec in message_schema["fields"].items():
            field_type = field_spec["type"]
            if field_type == "string":
                field_value, bytes_consumed = self.decode_string(data, offset)
                message_obj[field_name] = field_value
                offset += bytes_consumed
            else:
                raise NotImplementedError(f"Unsupported field type: {field_type}")

        return message_obj

    @staticmethod
    def decode_string(data: bytes, offset: int) -> (str, int):
        if len(data) < offset + 2:
            raise ValueError("Data too short to contain string length.")

        # Unpack 2-byte length
        length = struct.unpack_from("!H", data, offset)[0]
        offset += 2

        if len(data) < offset + length:
            raise ValueError("Data too short to contain the expected string.")

        # Unpack the string bytes
        string_bytes = data[offset : offset + length]
        string_value = string_bytes.decode("utf-8")
        return string_value, 2 + length
