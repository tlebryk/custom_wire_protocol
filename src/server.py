# server.py
import argparse
import logging
import os
import threading
import time
import socket
from concurrent import futures
from datetime import datetime

import grpc

import protocols_pb2
import protocols_pb2_grpc
import replica_pb2
import replica_pb2_grpc
from database import Database
from logger import setup_logger
from replication_manager import ReplicationManager  # Import the new ReplicationManager
from server_intercepter import SizeLoggingServerInterceptor
from users import UserManager


# Set up logger for the server
logger = setup_logger("server")

# Global variables for server configuration
EXTERNAL_HOST = None
SERVER_PORT = "50051"


class MessagingServiceServicer(protocols_pb2_grpc.MessagingServiceServicer):
    def __init__(self, db_file=None, replica_addresses=None):
        """
        Initializes the messaging service with a UserManager instance,
        a Database instance, and a ReplicationManager for replica servers.
        """
        self.db_file = db_file or os.environ.get("DB_FILE", "chat_app.db")
        self.user_manager = UserManager(db_file=self.db_file)
        self.db = Database(db_file=self.db_file)

        # Initialize the replication manager
        self.replication_manager = ReplicationManager(replica_addresses)

        # Dictionary to track online users: {username: (context, queue)}
        self.online_users = {}
        self.online_users_lock = threading.Lock()

    def enqueue_message(self, username, message):
        """Add a message to a user's message queue if they are online."""
        with self.online_users_lock:
            if username in self.online_users:
                _, msg_queue = self.online_users[username]
                msg_queue.append(message)

    def Login(self, request, context):
        """Authenticate a user."""
        logger.info("Login called for user: %s", request.username)
        if self.user_manager.authenticate_user(request.username, request.password):
            with self.online_users_lock:
                self.online_users[request.username] = (context, [])
            return protocols_pb2.ConfirmLoginResponse(
                username=request.username,
                message="Logged in successfully",
                status="success",
            )
        else:
            return protocols_pb2.ConfirmLoginResponse(
                username=request.username,
                message="Invalid username or password",
                status="error",
            )

    def Register(self, request, context):
        """Register a new user."""
        logger.info("Register called for user: %s", request.username)
        success, msg = self.user_manager.register_user(
            request.username, request.password
        )

        # If registration was successful, replicate to replicas
        if success:
            replication_success = self.replication_manager.replicate_register_user(
                request.username, request.password
            )
            if not replication_success:
                logger.warning(
                    f"Replication of user registration for {request.username} failed on some replicas"
                )
                # Note: We're not failing the request even if replication fails
                # This is a design decision - you might want to handle this differently

        return protocols_pb2.SuccessResponse(
            message=msg, status="success" if success else "error"
        )

    def DeleteAccount(self, request, context):
        """Delete a user's account."""
        logger.info("DeleteAccount called for user: %s", request.username)
        success = self.user_manager.delete_account(request.username)

        if success:
            # Remove user from online users
            with self.online_users_lock:
                self.online_users.pop(request.username, None)

            # Replicate the account deletion to replicas
            replication_success = self.replication_manager.replicate_delete_account(
                request.username
            )
            if not replication_success:
                logger.warning(
                    f"Replication of account deletion for {request.username} failed on some replicas"
                )
                # Again, we're continuing even if replication fails

            return protocols_pb2.SuccessResponse(
                message="Account deleted successfully.", status="success"
            )
        else:
            context.set_details("Failed to delete account.")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.SuccessResponse(
                message="Failed to delete account.", status="error"
            )

    def Subscribe(self, request, context):
        """Allow a user to receive messages."""
        logger.info("Subscribe called for user: %s", request.username)
        with self.online_users_lock:
            self.online_users[request.username] = (context, [])

        try:
            while context.is_active():
                with self.online_users_lock:
                    _, msg_queue = self.online_users.get(request.username, (None, []))
                    while msg_queue:
                        yield msg_queue.pop(0)
                time.sleep(0.5)
        except Exception as e:
            logger.error("Error in Subscribe for user %s: %s", request.username, e)
        finally:
            with self.online_users_lock:
                self.online_users.pop(request.username, None)
            logger.info("User %s unsubscribed.", request.username)

    def SendMessage(self, request, context):
        """Send a message to another user."""
        logger.info(
            "SendMessage called. Message: %s, Receiver: %s",
            request.message,
            request.receiver,
        )
        try:
            metadata = dict(context.invocation_metadata())
            sender = metadata.get("sender", "unknown_sender")

            if not request.message:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                return protocols_pb2.ConfirmSendMessageResponse(
                    message="Empty message cannot be sent", status="error"
                )

            if not request.receiver:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                return protocols_pb2.ConfirmSendMessageResponse(
                    message="Receiver username is required", status="error"
                )

            # Insert message into database
            message_id = self.db.insert_message(
                sender, request.message, request.receiver
            )
            logger.info("Message inserted with ID: %d", message_id)

            # Replicate message insertion to replicas
            timestamp = datetime.utcnow().isoformat() + "Z"
            replication_success = self.replication_manager.replicate_insert_message(
                sender, request.message, request.receiver, timestamp
            )
            if not replication_success:
                logger.warning(
                    f"Replication of message from {sender} to {request.receiver} failed on some replicas"
                )

            # **DEBUG STEP: Log the descriptor for ReceivedMessage**
            logger.info(
                "ReceivedMessage fields: %s",
                protocols_pb2.ReceivedMessage.DESCRIPTOR.fields_by_name,
            )

            # Now try constructing the ReceivedMessage
            try:
                received_msg = protocols_pb2.ReceivedMessage(
                    message=request.message,
                    sender=sender,  # this expects a field named 'sender'
                    timestamp=timestamp,
                    read="false",
                    id=message_id,
                    username=sender,
                )
            except Exception as e:
                logger.error("Failed to create ReceivedMessage: %s", e)
                raise

            with self.online_users_lock:
                receiver_entry = self.online_users.get(request.receiver)

            if receiver_entry:
                self.enqueue_message(request.receiver, received_msg)
                logger.info(
                    "Message enqueued for online receiver '%s'.", request.receiver
                )

            return protocols_pb2.ConfirmSendMessageResponse(
                message=request.message,
                status="success",
                timestamp=timestamp,
            )
        except Exception as e:
            logger.error("Error in SendMessage: %s", e)
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.ConfirmSendMessageResponse(
                message="Internal server error", status="error"
            )

    def SearchUsers(self, request, context):
        """Search for users."""
        try:
            users = self.db.search_users_in_db(request.query)
            return protocols_pb2.SearchUsersResponse(usernames=users, status="success")
        except Exception as e:
            logger.error("Error searching for users: %s", e)
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.SearchUsersResponse(usernames=[], status="error")

    def GetUsers(self, request, context):
        """Get a list of all users except the current user."""
        try:
            users = self.db.get_all_users_except(request.username)
            return protocols_pb2.GetUsersResponse(usernames=users, status="success")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.GetUsersResponse(usernames=[], status="error")

    def GetRecentMessages(self, request, context):
        """Fetch recent messages for a user."""
        try:
            recent_tuples = self.db.get_recent_messages(request.username, limit=50)
            messages = [
                protocols_pb2.ChatMessage(
                    message=t[1], timestamp=t[3], sender=t[0], id=t[4]
                )
                for t in recent_tuples
            ]
            return protocols_pb2.RecentMessagesResponse(
                messages=messages, status="success"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.RecentMessagesResponse(messages=[], status="error")

    def GetUnreadMessages(self, request, context):
        """Fetch unread messages for a user."""
        try:
            unread_tuples = self.db.get_unread_messages(request.username, limit=50)
            messages = [
                protocols_pb2.ChatMessage(
                    message=t[2], timestamp=t[3], sender=t[1], id=t[0]
                )
                for t in unread_tuples
            ]
            return protocols_pb2.UnreadMessagesResponse(
                messages=messages, status="success"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.UnreadMessagesResponse(messages=[], status="error")

    def MarkAsRead(self, request, context):
        """Mark messages as read."""
        try:
            message_ids = list(request.message_ids)
            self.db.mark_messages_as_read(message_ids)

            # Replicate mark as read to replicas
            replication_success = (
                self.replication_manager.replicate_mark_messages_as_read(message_ids)
            )
            if not replication_success:
                logger.warning(
                    f"Replication of mark as read for {message_ids} failed on some replicas"
                )

            return protocols_pb2.ConfirmMarkAsReadResponse(
                message="Messages marked as read.", status="success"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.ConfirmMarkAsReadResponse(
                message="Internal server error", status="error"
            )

    def DeleteMessage(self, request, context):
        """Delete a message."""
        try:
            message_id = request.message_id
            success = self.db.delete_message(message_id)

            if success:
                # Replicate message deletion to replicas
                replication_success = self.replication_manager.replicate_delete_message(
                    message_id
                )
                if not replication_success:
                    logger.warning(
                        f"Replication of message deletion for message {message_id} failed on some replicas"
                    )

                return protocols_pb2.SuccessResponse(
                    message="Message deleted successfully.", status="success"
                )
            else:
                context.set_details("Failed to delete message.")
                context.set_code(grpc.StatusCode.INTERNAL)
                return protocols_pb2.SuccessResponse(
                    message="Failed to delete message.", status="error"
                )
        except Exception as e:
            logger.error(f"Error in DeleteMessage: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.SuccessResponse(
                message="Internal server error", status="error"
            )

    def UpdateUnreadMessageCount(self, request, context):
        """Update unread message count for a user."""
        try:
            username = request.username
            count = request.count
            success = self.db.set_n_unread_messages(username, count)

            if success:
                # Replicate unread message count update to replicas
                replication_success = (
                    self.replication_manager.replicate_set_n_unread_messages(
                        username, count
                    )
                )
                if not replication_success:
                    logger.warning(
                        f"Replication of unread message count update for {username} failed on some replicas"
                    )

                return protocols_pb2.SuccessResponse(
                    message="Unread message count updated successfully.",
                    status="success",
                )
            else:
                context.set_details("Failed to update unread message count.")
                context.set_code(grpc.StatusCode.INTERNAL)
                return protocols_pb2.SuccessResponse(
                    message="Failed to update unread message count.", status="error"
                )
        except Exception as e:
            logger.error(f"Error in UpdateUnreadMessageCount: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.SuccessResponse(
                message="Internal server error", status="error"
            )

    def SetNUnreadMessages(self, request, context):
        """
        Set the number of unread messages for a user.

        Updates the user's unread messages count in the leader's database, enqueues
        unread messages for the user, and replicates the update to all replicas.
        """
        username = request.username
        n_unread = request.n_unread_messages

        # Retrieve current unread message count (if available)
        user_info = self.db.get_user_info(username)
        n_message_index = 1
        if user_info:
            n_unread_old = user_info[n_message_index]
            if not n_unread_old:
                n_unread_old = 50
        else:
            logger.info(f"User '{username}' not found in database.")
            n_unread_old = 50

        if not n_unread:
            context.set_details("Number of unread messages is required.")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return protocols_pb2.SuccessResponse(
                message="Number of unread messages is required.", status="error"
            )

        # Update the unread messages count in the database.
        success = self.db.set_n_unread_messages(username, n_unread)
        if success:
            try:
                unread_tuples = self.db.get_unread_messages(username, limit=n_unread)
                for tup in unread_tuples:
                    # Assume tuple order: (msg_id, sender, content, timestamp)
                    msg_id, sender, content, timestamp = tup
                    received_msg = protocols_pb2.ReceivedMessage(
                        message=content,
                        sender=sender,  # Note: use 'sender' to match the proto field name
                        timestamp=timestamp,
                        read="false",
                        id=int(msg_id),
                        username=sender,
                    )
                    self.enqueue_message(username, received_msg)
            except Exception as e:
                logger.error("Error fetching unread messages: %s", e)
            # Replicate the update to all replicas.
            replication_success = (
                self.replication_manager.replicate_set_n_unread_messages(
                    username, n_unread
                )
            )
            if not replication_success:
                logger.warning(
                    f"Replication of unread message count update for {username} failed on some replicas"
                )
            return protocols_pb2.SuccessResponse(
                message="Number of unread messages set successfully.", status="success"
            )
        else:
            context.set_details("Failed to set number of unread messages.")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.SuccessResponse(
                message="Failed to set number of unread messages.", status="error"
            )


def send_heartbeats(replica_addresses):
    """
    Periodically send heartbeats to all replicas.
    Waits for the channel to be ready before sending.
    If a replica is not ready, it logs a warning and continues.
    """
    global EXTERNAL_HOST, SERVER_PORT

    # Form the leader's complete address
    leader_address = f"{EXTERNAL_HOST}:{SERVER_PORT}"
    logger.info(f"Sending heartbeats as leader at {leader_address}")

    while True:
        for replica_addr in replica_addresses:
            # Skip self if this address is our own address
            if replica_addr == leader_address:
                continue

            channel = grpc.insecure_channel(replica_addr)
            try:
                # Wait up to 2 seconds for the channel to be ready
                grpc.channel_ready_future(channel).result(timeout=2.0)
                stub = replica_pb2_grpc.ReplicaServiceStub(channel)
                
                # Send the full leader address in the heartbeat
                request = replica_pb2.HeartbeatRequest(leader_id=leader_address)
                
                response = stub.Heartbeat(request, timeout=2.0)
                logger.info(
                    f"Sent heartbeat to replica {replica_addr}. Response: {response.message}"
                )
            except grpc.FutureTimeoutError:
                logger.warning(
                    f"Replica {replica_addr} is down and is not receiving heartbeats."
                )
            except Exception as e:
                logger.warning(
                    f"Failed to send heartbeat to replica {replica_addr}: {e}"
                )
            finally:
                channel.close()
        time.sleep(3)


def get_external_host(host):
    """Determine the external host address to use for heartbeats and client connections."""
    if host != "0.0.0.0" and host != "localhost" and host != "127.0.0.1":
        # If a specific external IP was provided, use it
        return host
    
    # Otherwise, try to determine the machine's IP address
    try:
        # This is a common way to get the local IP - connect to Google DNS and check what interface is used
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback to hostname
        return socket.gethostname()


def serve(host="0.0.0.0", port="50051", replica_addresses=None, external_host=None):
    """
    Start the gRPC server, plus start the heartbeat thread to notify replicas.

    Args:
        host (str): The host IP address to bind to. Default is "0.0.0.0" (all interfaces).
        port (str): The port to bind to. Default is "50051".
        replica_addresses (list): List of replica addresses to communicate with.
        external_host (str): External hostname/IP to advertise to clients and replicas.
    """
    global EXTERNAL_HOST, SERVER_PORT
    
    # Set the port
    SERVER_PORT = port
    
    # Determine the external host - crucial for client connectivity
    if external_host:
        EXTERNAL_HOST = external_host
    else:
        EXTERNAL_HOST = get_external_host(host)
    
    logger.info(f"Server binding to {host}:{port}")
    logger.info(f"Using external host {EXTERNAL_HOST} for client connections")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    messaging_service = MessagingServiceServicer(replica_addresses=replica_addresses)
    protocols_pb2_grpc.add_MessagingServiceServicer_to_server(messaging_service, server)
    server_address = f"{host}:{port}"
    server.add_insecure_port(server_address)

    logger.info(f"gRPC leader server running on {server_address}...")

    # Convert replica_addresses to list if it's a string
    if isinstance(replica_addresses, str):
        replica_addrs_list = replica_addresses.split(",")
    else:
        replica_addrs_list = replica_addresses
    
    # start the background heartbeat thread
    heartbeat_thread = threading.Thread(
        target=send_heartbeats, args=(replica_addrs_list,), daemon=True
    )
    heartbeat_thread.start()

    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping server...")
        server.stop(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the messaging server")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host IP address to bind to"
    )
    parser.add_argument(
        "--port", type=str, default="50051", help="Port to run the server on"
    )
    parser.add_argument(
        "--replicas",
        type=str,
        default="localhost:50052",
        help="Comma-separated list of replica addresses",
    )
    parser.add_argument(
        "--external-host",
        type=str,
        default=None,
        help="External hostname/IP to advertise to clients (defaults to auto-detected)",
    )

    args = parser.parse_args()
    replica_addresses = (
        args.replicas.split(",") if args.replicas else ["localhost:50052"]
    )
    print(f"{replica_addresses=}")
    serve(host=args.host, port=args.port, replica_addresses=replica_addresses, external_host=args.external_host)