# replication_manager.py
import grpc
import logging
import replica_pb2
import replica_pb2_grpc
from typing import List, Optional


class ReplicationManager:
    """
    Manages replication of write operations to replica servers.
    """

    def __init__(self, replica_addresses: Optional[List[str]] = None):
        """
        Initialize the replication manager with a list of replica server addresses.

        Args:
            replica_addresses: List of replica server addresses in format "host:port"
        """
        self.replica_addresses = replica_addresses or ["localhost:50052"]
        self.logger = logging.getLogger(__name__)

    def _get_stub(self, address: str):
        """Create a gRPC stub for a replica at the given address."""
        channel = grpc.insecure_channel(address)
        return replica_pb2_grpc.ReplicaServiceStub(channel)

    def replicate_register_user(self, username: str, password: str) -> bool:
        """
        Replicate user registration to all replicas.

        Args:
            username: The username to register
            password: The password hash or value

        Returns:
            bool: True if replication succeeded for all replicas, False otherwise
        """
        self.logger.info(f"Replicating registration for user: {username}")
        success = True

        for address in self.replica_addresses:
            try:
                stub = self._get_stub(address)
                request = replica_pb2.RegisterUserRequest(
                    username=username, password=password
                )
                response = stub.RegisterUser(request)
                if not response.success:
                    self.logger.warning(
                        f"Replica at {address} failed to register user: {response.message}"
                    )
                    success = False
                else:
                    self.logger.info(f"User registration replicated to {address}")
            except Exception as e:
                self.logger.error(
                    f"Failed to replicate user registration to {address}: {e}"
                )
                success = False

        return success

    def replicate_delete_account(self, username: str) -> bool:
        """
        Replicate account deletion to all replicas.

        Args:
            username: The username of the account to delete

        Returns:
            bool: True if replication succeeded for all replicas, False otherwise
        """
        self.logger.info(f"Replicating account deletion for user: {username}")
        success = True

        for address in self.replica_addresses:
            try:
                stub = self._get_stub(address)
                request = replica_pb2.DeleteAccountRequest(username=username)
                response = stub.DeleteAccount(request)
                if not response.success:
                    self.logger.warning(
                        f"Replica at {address} failed to delete account: {response.message}"
                    )
                    success = False
                else:
                    self.logger.info(f"Account deletion replicated to {address}")
            except Exception as e:
                self.logger.error(
                    f"Failed to replicate account deletion to {address}: {e}"
                )
                success = False

        return success

    def replicate_insert_message(
        self, sender: str, content: str, receiver: str, timestamp: str = ""
    ) -> bool:
        """
        Replicate message insertion to all replicas.

        Args:
            sender: The message sender
            content: The message content
            receiver: The message recipient
            timestamp: Optional message timestamp

        Returns:
            bool: True if replication succeeded for all replicas, False otherwise
        """
        self.logger.info(f"Replicating message from {sender} to {receiver}")
        success = True

        for address in self.replica_addresses:
            try:
                stub = self._get_stub(address)
                request = replica_pb2.InsertMessageRequest(
                    sender=sender,
                    content=content,
                    receiver=receiver,
                    timestamp=timestamp,
                )
                response = stub.InsertMessage(request)
                if not response.success:
                    self.logger.warning(
                        f"Replica at {address} failed to insert message: {response.message}"
                    )
                    success = False
                else:
                    self.logger.info(f"Message insertion replicated to {address}")
            except Exception as e:
                self.logger.error(
                    f"Failed to replicate message insertion to {address}: {e}"
                )
                success = False

        return success

    def replicate_mark_messages_as_read(self, message_ids: List[int]) -> bool:
        """
        Replicate marking messages as read to all replicas.

        Args:
            message_ids: List of message IDs to mark as read

        Returns:
            bool: True if replication succeeded for all replicas, False otherwise
        """
        self.logger.info(f"Replicating mark as read for messages: {message_ids}")
        success = True

        for address in self.replica_addresses:
            try:
                stub = self._get_stub(address)
                request = replica_pb2.MarkMessagesAsReadRequest(message_ids=message_ids)
                response = stub.MarkMessagesAsRead(request)
                if not response.success:
                    self.logger.warning(
                        f"Replica at {address} failed to mark messages as read: {response.message}"
                    )
                    success = False
                else:
                    self.logger.info(f"Mark as read replicated to {address}")
            except Exception as e:
                self.logger.error(f"Failed to replicate mark as read to {address}: {e}")
                success = False

        return success

    def replicate_mark_messages_delivered(self, user_id: str) -> bool:
        """
        Replicate marking all messages delivered for a user to all replicas.

        Args:
            user_id: The user ID whose messages should be marked as delivered

        Returns:
            bool: True if replication succeeded for all replicas, False otherwise
        """
        self.logger.info(f"Replicating mark messages delivered for user: {user_id}")
        success = True

        for address in self.replica_addresses:
            try:
                stub = self._get_stub(address)
                request = replica_pb2.MarkMessagesDeliveredRequest(user_id=user_id)
                response = stub.MarkMessagesDelivered(request)
                if not response.success:
                    self.logger.warning(
                        f"Replica at {address} failed to mark messages delivered: {response.message}"
                    )
                    success = False
                else:
                    self.logger.info(f"Mark messages delivered replicated to {address}")
            except Exception as e:
                self.logger.error(
                    f"Failed to replicate mark messages delivered to {address}: {e}"
                )
                success = False

        return success

    def replicate_set_n_unread_messages(
        self, username: str, n_unread_messages: int
    ) -> bool:
        """
        Replicate setting the number of unread messages for a user to all replicas.

        Args:
            username: The username to update
            n_unread_messages: The new number of unread messages

        Returns:
            bool: True if replication succeeded for all replicas, False otherwise
        """
        self.logger.info(f"Replicating set unread messages count for user: {username}")
        success = True

        for address in self.replica_addresses:
            try:
                stub = self._get_stub(address)
                request = replica_pb2.SetNUnreadMessagesRequest(
                    username=username, n_unread_messages=n_unread_messages
                )
                response = stub.SetNUnreadMessages(request)
                if not response.success:
                    self.logger.warning(
                        f"Replica at {address} failed to set unread messages count: {response.message}"
                    )
                    success = False
                else:
                    self.logger.info(
                        f"Set unread messages count replicated to {address}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Failed to replicate set unread messages count to {address}: {e}"
                )
                success = False

        return success

    def replicate_delete_message(self, message_id: int) -> bool:
        """
        Replicate deleting a message to all replicas.

        Args:
            message_id: The ID of the message to delete

        Returns:
            bool: True if replication succeeded for all replicas, False otherwise
        """
        self.logger.info(f"Replicating delete message: {message_id}")
        success = True

        for address in self.replica_addresses:
            try:
                stub = self._get_stub(address)
                request = replica_pb2.DeleteMessageRequest(message_id=message_id)
                response = stub.DeleteMessage(request)
                if not response.success:
                    self.logger.warning(
                        f"Replica at {address} failed to delete message: {response.message}"
                    )
                    success = False
                else:
                    self.logger.info(f"Delete message replicated to {address}")
            except Exception as e:
                self.logger.error(
                    f"Failed to replicate delete message to {address}: {e}"
                )
                success = False

        return success
