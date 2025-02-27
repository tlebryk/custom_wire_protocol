import json

import struct
import logging
import os

from typing import Dict, Any, List, Optional, Tuple


# undo hardcode
def load_protocols(
    file_path=None,
):
    if not file_path:
        file_path = os.getenv("PROTOCOL_FILE", "configs/protocol.json")

    with open(file_path, "r") as f:
        protocols = json.load(f)
    return protocols


class Encoder:
    def __init__(self, protocols: Dict[str, Any]):
        """
        Initialize the Encoder.

        Args:
            protocols (Dict[str, Any]): A dictionary mapping protocol names to their
                specifications. The dictionary should have the following structure:

                {
                    "action_ids": {
                        "<action_name_1>": <action_id_1>,
                        "<action_name_2>": <action_id_2>,
                        ...
                    },
                    "messages": {
                        "<action_name_1>": {
                            "action": "<action_name_1>",
                            "fields": {
                                "<field_name_1>": {"type": "<field_type_1>"},
                                "<field_name_2>": {"type": "<field_type_2>"},
                                ...
                            }
                        },
                        "<action_name_2>": {
                            "action": "<action_name_2>",
                            "fields": {
                                "<field_name_1>": {"type": "<field_type_1>"},
                                "<field_name_2>": {"type": "<field_type_2>"},
                                ...
                            }
                        },
                        ...
                    }
                }

        Note: The "action_ids" dictionary maps action names to action IDs, and the
        "messages" dictionary maps action names to message specifications.
        """
        self.protocols = protocols
        self.action_ids = protocols["action_ids"]
        self.messages = protocols["messages"]

    def encode_message(self, message_obj: Dict[str, Any]) -> bytes:
        """
        Encode a message object into bytes.

        Args:
            message_obj (Dict[str, Any]): A dictionary representing the message to be
                encoded. The dictionary should have the following structure:

                {
                    "action": "<action_name>",
                    "<field_name_1>": <field_value_1>,
                    "<field_name_2>": <field_value_2>,
                    ...
                }

                where "<action_name>" is the name of the action, and "<field_name_i>" and
                "<field_value_i>" are the name and value of the i-th field, respectively.

        Returns:
            bytes: The encoded message as a sequence of bytes.

        Raises:
            ValueError: If the message object is missing a required field, or if the
                message type is unknown.
        """
        logging.warning(f"Encoding message: {message_obj}")
        message_type = message_obj.get("action")
        if not message_type:
            raise ValueError("Message object must have an 'action' field.")
        print("self.messages", self.messages.keys())
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
            elif field_type == "int":
                encoded += self.encode_int(field_value)
            elif field_type == "list":
                element_type = field_spec["element_type"]
                items_spec = field_spec.get("items")
                encoded += self.encode_list(field_value, element_type, items_spec)
            else:
                raise NotImplementedError(f"Unsupported field type: {field_type}")

        return encoded

    @staticmethod
    def encode_string(value: str) -> bytes:
        """
        Encode a string into bytes.

        Args:
            value (str): The string to encode.

        Returns:
            bytes: The encoded string as a sequence of bytes.
        """
        encoded_str = value.encode("utf-8")
        length = len(encoded_str)
        if length > 65535:
            raise ValueError("String too long to encode (max 65535 bytes).")
        # 2-byte length
        return struct.pack("!H", length) + encoded_str

    @staticmethod
    def encode_int(value: int) -> bytes:
        """
        Encode an integer into bytes.

        Args:
            value (int): The integer to encode. Must be a 4-byte signed integer.

        Returns:
            bytes: The encoded integer as a sequence of bytes.
        """
        return struct.pack("!i", value)

    def encode_list(
        self,
        value: List[Any],
        element_type: str,
        items_spec: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Encode a list into bytes.

        Args:
            value (List[Any]): The list to encode.
            element_type (str): The type of each element in the list.
            items_spec (Optional[Dict[str, Any]]): If `element_type` is 'object',
                the specification of the fields of the object. Defaults to None.

        Returns:
            bytes: The encoded list as a sequence of bytes.
        """
        encoded = b""
        length = len(value)
        if length > 65535:
            raise ValueError("List too long to encode (max 65535 elements).")
        encoded += struct.pack("!H", length)  # 2-byte length
        for item in value:
            if element_type == "string":
                encoded += self.encode_string(item)
            elif element_type == "int":
                encoded += self.encode_int(item)
            elif element_type == "object":
                if not items_spec:
                    raise ValueError(
                        "Missing 'items' specification for object in list."
                    )
                encoded += self.encode_object(item, items_spec["fields"])
            else:
                raise NotImplementedError(
                    f"Unsupported list element type: {element_type}"
                )
        return encoded

    def encode_object(self, obj: Dict[str, Any], fields_spec: Dict[str, Any]) -> bytes:
        """
        Encode a dictionary into bytes.

        Args:
            obj (Dict[str, Any]): The dictionary to encode.
            fields_spec (Dict[str, Any]): A dictionary mapping field names to
                their specifications.

        Returns:
            bytes: The encoded dictionary as a sequence of bytes.
        """
        encoded = b""
        for field_name, field_spec in fields_spec.items():
            field_value = obj.get(field_name)
            if field_value is None:
                raise ValueError(f"Missing field '{field_name}' in object.")

            field_type = field_spec["type"]
            if field_type == "string":
                encoded += self.encode_string(field_value)
            elif field_type == "int":
                encoded += self.encode_int(field_value)
            elif field_type == "list":
                encoded += self.encode_list(
                    field_value, field_spec["element_type"], field_spec.get("items")
                )
            elif field_type == "object":
                encoded += self.encode_object(field_value, field_spec["fields"])
            else:
                raise NotImplementedError(
                    f"Unsupported field type in object: {field_type}"
                )
        return encoded


class Decoder:
    def __init__(self, protocols: Dict[str, Any]) -> None:
        """
        Initialize the Decoder.

        Args:
            protocols (Dict[str, Any]): A dictionary mapping protocol names to their
                specifications. The dictionary should have the following structure:

                {
                    "action_ids": {
                        "<action_name_1>": <action_id_1>,
                        "<action_name_2>": <action_id_2>,
                        ...
                    },
                    "messages": {
                        "<action_name_1>": {
                            "action": "<action_name_1>",
                            "fields": {
                                "<field_name_1>": {"type": "<field_type_1>"},
                                "<field_name_2>": {"type": "<field_type_2>"},
                                ...
                            }
                        },
                        "<action_name_2>": {
                            "action": "<action_name_2>",
                            "fields": {
                                "<field_name_1>": {"type": "<field_type_1>"},
                                "<field_name_2>": {"type": "<field_type_2>"},
                                ...
                            }
                        },
                        ...
                    }
                }

        Note: The "action_ids" dictionary maps action names to action IDs, and the
        "messages" dictionary maps action names to message specifications.
        """
        self.protocols = protocols
        self.action_ids = protocols["action_ids"]
        self.messages = protocols["messages"]
        # Create reverse mapping from action_id to action_type
        self.id_to_action: Dict[int, str] = {v: k for k, v in self.action_ids.items()}

    def decode_message(self, data: bytes) -> Dict[str, Any]:
        """
        Decode a message from a sequence of bytes.

        Args:
            data (bytes): The sequence of bytes to decode.

        Returns:
            Dict[str, Any]: The decoded message as a dictionary.
        """
        offset = 0
        if len(data) < 1:
            raise ValueError("Data too short to contain action ID.")
        # Unpack action ID (1 byte)
        action_id: int = struct.unpack_from("!B", data, offset)[0]
        offset += 1

        action_type: str = self.id_to_action.get(action_id)
        if not action_type:
            raise ValueError(f"Unknown action ID: {action_id}")

        message_schema: Dict[str, Any] = self.messages.get(action_type)
        if not message_schema:
            raise ValueError(f"No schema defined for action type: {action_type}")

        message_obj: Dict[str, Any] = {"action": action_type}

        for field_name, field_spec in message_schema["fields"].items():
            field_type: str = field_spec["type"]
            if field_type == "string":
                field_value, bytes_consumed = self.decode_string(data, offset)
                message_obj[field_name] = field_value
                offset += bytes_consumed
            elif field_type == "int":
                field_value, bytes_consumed = self.decode_int(data, offset)
                message_obj[field_name] = field_value
                offset += bytes_consumed
            elif field_type == "list":
                field_value, bytes_consumed = self.decode_list(
                    data, offset, field_spec["element_type"], field_spec.get("items")
                )
                message_obj[field_name] = field_value
                offset += bytes_consumed
            elif field_type == "object":
                # If a field is directly an object (not within a list)
                field_value, bytes_consumed = self.decode_object(
                    data, offset, field_spec["fields"]
                )
                message_obj[field_name] = field_value
                offset += bytes_consumed
            else:
                raise NotImplementedError(f"Unsupported field type: {field_type}")

        return message_obj

    @staticmethod
    def decode_string(data: bytes, offset: int) -> (str, int):
        """
        Decode a string from the given binary data, starting from the given offset.

        Args:
            data (bytes): The binary data containing the string.
            offset (int): The starting offset of the string in the binary data.

        Returns:
            tuple: A tuple containing the decoded string and the number of bytes consumed.
        """

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

    @staticmethod
    def decode_int(data: bytes, offset: int) -> Tuple[int, int]:
        """
        Decode a 4-byte signed integer from the given binary data, starting from the given offset.

        Args:
            data (bytes): The binary data containing the integer.
            offset (int): The starting offset of the integer in the binary data.

        Returns:
            tuple: A tuple containing the decoded integer and the number of bytes consumed.
        """
        if len(data) < offset + 4:
            raise ValueError("Data too short to contain an integer.")
        int_value = struct.unpack_from("!i", data, offset)[0]
        return int_value, 4

    def decode_list(
        self,
        data: bytes,
        offset: int,
        element_type: str,
        items_spec: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Any], int]:
        """
        Decode a list from the given binary data, starting from the given offset.

        Args:
            data (bytes): The binary data containing the list.
            offset (int): The starting offset of the list in the binary data.
            element_type (str): The type of each element in the list.
            items_spec (Optional[Dict[str, Any]]): If `element_type` is 'object',
                the specification of the fields of the object. Defaults to None.

        Returns:
            tuple: A tuple containing the decoded list and the number of bytes consumed.
        """
        if len(data) < offset + 2:
            raise ValueError("Data too short to contain list length.")
        length = struct.unpack_from("!H", data, offset)[0]
        offset += 2
        bytes_consumed = 2
        items = []
        for _ in range(length):
            if element_type == "string":
                item, consumed = self.decode_string(data, offset)
            elif element_type == "int":
                item, consumed = self.decode_int(data, offset)
            elif element_type == "object":
                if not items_spec:
                    raise ValueError(
                        "Missing 'items' specification for object in list."
                    )
                item, consumed = self.decode_object(data, offset, items_spec["fields"])
            else:
                raise NotImplementedError(
                    f"Unsupported list element type: {element_type}"
                )
            items.append(item)
            offset += consumed
            bytes_consumed += consumed
        return items, bytes_consumed

    def decode_object(
        self, data: bytes, offset: int, fields_spec: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], int]:
        """
        Decode an object from the given binary data, starting from the given offset.

        Args:
            data (bytes): The binary data containing the object.
            offset (int): The starting offset of the object in the binary data.
            fields_spec (Dict[str, Any]): The specification of the fields of the object.

        Returns:
            tuple: A tuple containing the decoded object and the number of bytes consumed.
        """
        obj = {}
        total_consumed = 0
        for field_name, field_spec in fields_spec.items():
            field_type = field_spec["type"]
            if field_type == "string":
                field_value, consumed = self.decode_string(data, offset)
            elif field_type == "int":
                field_value, consumed = self.decode_int(data, offset)
            elif field_type == "list":
                field_value, consumed = self.decode_list(
                    data, offset, field_spec["element_type"], field_spec.get("items")
                )
            elif field_type == "object":
                field_value, consumed = self.decode_object(
                    data, offset, field_spec["fields"]
                )
            else:
                raise NotImplementedError(
                    f"Unsupported field type in object: {field_type}"
                )
            obj[field_name] = field_value
            offset += consumed
            total_consumed += consumed
        return obj, total_consumed
