from tkinter import messagebox
import logging
import grpc

# Import the generated gRPC modules
import protocols_pb2
import protocols_pb2_grpc


class GRPCClient:
    """
    A simple gRPC client to interact with the MessagingService.
    """

    def __init__(self, host="localhost", port=50051):
        """
        Initializes the gRPC client.

        Args:
            host (str): The hostname of the gRPC server.
            port (int): The port number of the gRPC server.
        """
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = protocols_pb2_grpc.MessagingServiceStub(self.channel)

    def login(self, username: str, password: str):
        """
        Logs in a user.

        Args:
            username (str): The username of the user.
            password (str): The password of the user.

        Returns:
            LoginResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.LoginRequest(username=username, password=password)
            response = self.stub.Login(request)
            return response
        except grpc.RpcError as e:
            logging.error("Login RPC failed: %s", e)
            return None

    def register(self, username: str, password: str):
        """
        Registers a new user.

        Args:
            username (str): The username to register.
            password (str): The password for the new account.

        Returns:
            RegisterResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.RegisterRequest(
                username=username, password=password
            )
            response = self.stub.Register(request)
            return response
        except grpc.RpcError as e:
            logging.error("Register RPC failed: %s", e)
            return None

    def send_message(self, message: str, receiver: str):
        """
        Sends a message to a specified receiver.

        Args:
            message (str): The message content.
            receiver (str): The recipient of the message.

        Returns:
            SendMessageResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.SendMessageRequest(
                message=message, receiver=receiver
            )
            response = self.stub.SendMessage(
                request, metadata=(("sender", self.username),)
            )
            return response
        except grpc.RpcError as e:
            logging.error("SendMessage RPC failed: %s", e)
            return None

    def get_recent_messages(self, username: str):
        """
        Retrieves recent messages for a given user.

        Args:
            username (str): The username whose messages are requested.

        Returns:
            GetRecentMessagesResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.GetRecentMessagesRequest(username=username)
            response = self.stub.GetRecentMessages(request)
            return response
        except grpc.RpcError as e:
            logging.error("GetRecentMessages RPC failed: %s", e)
            return None

    def get_unread_messages(self, username: str):
        """
        Retrieves unread messages for a given user.

        Args:
            username (str): The username whose unread messages are requested.

        Returns:
            GetUnreadMessagesResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.GetUnreadMessagesRequest(username=username)
            response = self.stub.GetUnreadMessages(request)
            return response
        except grpc.RpcError as e:
            logging.error("GetUnreadMessages RPC failed: %s", e)
            return None

    def mark_as_read(self, message_ids: list):
        """
        Marks messages as read.

        Args:
            message_ids (list): A list of message IDs to mark as read.

        Returns:
            MarkAsReadResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.MarkAsReadRequest(message_ids=message_ids)
            response = self.stub.MarkAsRead(request)
            return response
        except grpc.RpcError as e:
            logging.error("MarkAsRead RPC failed: %s", e)
            return None

    def set_n_unread_messages(self, username: str, n: int):
        """
        Sets the number of unread messages for a user.

        Args:
            username (str): The username to update.
            n (int): The number of unread messages.

        Returns:
            SetNUnreadMessagesResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.SetNUnreadMessagesRequest(
                username=username, n_unread_messages=n
            )
            response = self.stub.SetNUnreadMessages(request)
            return response
        except grpc.RpcError as e:
            logging.error("SetNUnreadMessages RPC failed: %s", e)
            return None

    def delete_message(self, username: str, message_id: int):
        """
        Deletes a specific message for a user.

        Args:
            username (str): The username owning the message.
            message_id (int): The ID of the message to delete.

        Returns:
            DeleteMessageResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.DeleteMessageRequest(
                username=username, message_id=message_id
            )
            response = self.stub.DeleteMessage(request)
            return response
        except grpc.RpcError as e:
            logging.error("DeleteMessage RPC failed: %s", e)
            return None

    def delete_account(self, username: str):
        """
        Deletes a user account.

        Args:
            username (str): The username of the account to delete.

        Returns:
            DeleteAccountResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.DeleteAccountRequest(username=username)
            response = self.stub.DeleteAccount(request)
            return response
        except grpc.RpcError as e:
            logging.error("DeleteAccount RPC failed: %s", e)
            return None

    def subscribe(self, username: str):
        """
        Subscribes to user updates.

        Args:
            username (str): The username to subscribe to.

        Returns:
            SubscribeResponse: The response from the gRPC server.
        """
        try:
            request = protocols_pb2.SubscribeRequest(username=username)
            return self.stub.Subscribe(request)
        except grpc.RpcError as e:
            logging.error("Subscribe RPC failed: %s", e)
            return None

    def get_users(self, username: str):
        """
        Retrieves a list of users.

        Args:
            username (str): The username requesting the list.

        Returns:
            list: A list of usernames.
        """
        try:
            request = protocols_pb2.GetUsersRequest(username=username)
            response = self.stub.GetUsers(request)
            if response.status == "success":
                return list(response.usernames)
            else:
                return []
        except grpc.RpcError as e:
            logging.error("GetUsers RPC failed: %s", e)
            return []
