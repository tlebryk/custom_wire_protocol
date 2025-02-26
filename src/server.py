# server.py
from concurrent import futures
import grpc
import logging
import threading
import time
from datetime import datetime

from users import authenticate_user, register_user, delete_account
from database import (
    get_all_users_except,
    insert_message,
    get_recent_messages,
    get_undelivered_messages,
    get_unread_messages,
    delete_message,
    set_n_unread_messages,
    get_user_info,
    mark_messages_as_read,  # Newly imported function
)

import protocols_pb2
import protocols_pb2_grpc

logging.basicConfig(level=logging.INFO)

# Global dictionary to track online users.
# Key: username, Value: a tuple (context, queue) where queue is a list of ReceivedMessage messages.
online_users = {}
online_users_lock = threading.Lock()


def enqueue_message(username, message):
    with online_users_lock:
        if username in online_users:
            user_context, msg_queue = online_users[username]
            msg_queue.append(message)


class MessagingServiceServicer(protocols_pb2_grpc.MessagingServiceServicer):
    def Login(self, request, context):
        """
        Authenticate a user.

        Args:
            request: A LoginRequest with the username and password.
            context: The context of the gRPC request.

        Returns:
            A ConfirmLoginResponse with a status of "success" if the credentials are valid, or "error" if they are not.
        """
        logging.info("Login called for user: %s", request.username)
        if authenticate_user(request.username, request.password):
            with online_users_lock:
                online_users[request.username] = (context, [])
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
        """
        Register a new user.

        Args:
            request: A RegisterRequest with the username and password.
            context: The context of the gRPC request.

        Returns:
            A SuccessResponse with a status of "success" if the registration is successful, or "error" if it is not.
        """
        logging.info("Register called for user: %s", request.username)
        success, msg = register_user(request.username, request.password)
        if success:
            return protocols_pb2.SuccessResponse(
                message=msg,
                status="success",
            )
        else:
            return protocols_pb2.SuccessResponse(
                message=msg,
                status="error",
            )

    def Subscribe(self, request, context):
        """
        Subscribe to receive messages for a user.

        Args:
            request: A SubscribeRequest with the username.
            context: The context of the gRPC request.

        Yields:
            ReceivedMessage messages that are sent to the user while they are subscribed.

        Notes:
            The user is automatically unsubscribed if there is an error in the stream or if the gRPC request is cancelled.
        """
        logging.info("Subscribe called for user: %s", request.username)
        with online_users_lock:
            online_users[request.username] = (context, [])
        try:
            while context.is_active():
                with online_users_lock:
                    _, msg_queue = online_users.get(request.username, (None, []))
                    if msg_queue:
                        while msg_queue:
                            msg = msg_queue.pop(0)
                            yield msg
                time.sleep(0.5)
        except Exception as e:
            logging.error("Error in Subscribe for user %s: %s", request.username, e)
        finally:
            with online_users_lock:
                if request.username in online_users:
                    del online_users[request.username]
            logging.info("User %s unsubscribed.", request.username)

    def SendMessage(self, request, context):
        """
        Send a message to another user.

        Args:
            request: A SendMessageRequest with the message and receiver username.
            context: The context of the gRPC request.

        Returns:
            A ConfirmSendMessageResponse with a status of "success" if the message is sent, or "error" if it is not.
        """
        logging.info(
            "SendMessage called. Message: %s, Receiver: %s",
            request.message,
            request.receiver,
        )
        try:
            metadata = dict(context.invocation_metadata())
            sender = metadata.get("sender", "unknown_sender")

            if not request.message:
                context.set_details("Empty message cannot be sent.")
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                return protocols_pb2.ConfirmSendMessageResponse(
                    message="Empty message cannot be sent",
                    status="error",
                    timestamp="",
                )
            if not request.receiver:
                context.set_details("Receiver username is required.")
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                return protocols_pb2.ConfirmSendMessageResponse(
                    message="Receiver username is required",
                    status="error",
                    timestamp="",
                )

            message_id = insert_message(sender, request.message, request.receiver)
            logging.info("Message inserted with ID: %d", message_id)

            received_msg = protocols_pb2.ReceivedMessage(
                **{
                    "message": request.message,
                    "from": sender,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "read": "false",
                    "id": message_id,
                    "username": sender,
                }
            )

            with online_users_lock:
                logging.info("ONLINE USERS: %s", online_users)
                receiver_entry = online_users.get(request.receiver)

            if receiver_entry:
                enqueue_message(request.receiver, received_msg)
                logging.info(
                    "Message enqueued for online receiver '%s'.", request.receiver
                )
            else:
                logging.info(
                    "User '%s' is offline. Message stored for later delivery.",
                    request.receiver,
                )

            response_payload = {
                "status": "success",
                "from": sender,
                "message": request.message,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "confirm_send_message",
            }
            return protocols_pb2.ConfirmSendMessageResponse(
                message=response_payload["message"],
                status=response_payload["status"],
                timestamp=response_payload["timestamp"],
            )
        except Exception as e:
            logging.error("Error in SendMessage: %s", e)
            context.set_details("Internal server error")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.ConfirmSendMessageResponse(
                message="Internal server error",
                status="error",
                timestamp="",
            )

    def GetUsers(self, request, context):
        """
        Get a list of all users except the current user.

        Args:
            request: A GetUsersRequest with the current user's username.
            context: The context of the gRPC request.

        Returns:
            A GetUsersResponse with a status of "success" if the user list is fetched, or "error" if it is not.
        """

        try:
            # get users and exclude the current user from the list
            users = get_all_users_except(request.username)
            return protocols_pb2.GetUsersResponse(
                usernames=users,
                status="success",
                message="User list fetched successfully.",
            )
        except Exception as e:
            context.set_details("Error fetching user list")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.GetUsersResponse(
                usernames=[], status="error", message=str(e)
            )

    def GetRecentMessages(self, request, context):
        """
        Get the recent messages for a user.

        Args:
            request: A GetRecentMessagesRequest with the username.
            context: The context of the gRPC request.

        Returns:
            A RecentMessagesResponse with a status of "success" if the messages are fetched, or "error" if they are not.
        """
        username = request.username
        # get user info
        user_info = get_user_info(username)
        n_message_index = 1
        if user_info:
            n_unread_messages = user_info[n_message_index]
            if not n_unread_messages:
                n_unread_messages = 50

        else:
            logging.info(f"User '{context.username}' not found in database.")
            n_unread_messages = 50
        try:
            recent_tuples = get_recent_messages(username, limit=n_unread_messages)
        except Exception as e:
            logging.error("Error fetching recent messages for %s: %s", username, e)
            context.set_details("Error fetching recent messages")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.RecentMessagesResponse(messages=[], status="error")

        chat_messages = []
        for tup in recent_tuples:
            # sender, content, receiver, timestamp, msg_id = tup
            (
                sender,
                content,
                receiver,
                timestamp,
                msg_id,
            ) = tup
            chat_msg = protocols_pb2.ChatMessage(
                **{
                    "message": content,
                    "timestamp": timestamp,
                    "from": sender,
                    "id": msg_id,
                }
            )
            chat_messages.append(chat_msg)

        return protocols_pb2.RecentMessagesResponse(
            messages=chat_messages, status="success"
        )

    def GetUnreadMessages(self, request, context):
        """
        Get the unread messages for a user.

        Args:
            request: A GetUnreadMessagesRequest with the username.
            context: The context of the gRPC request.

        Returns:
            An UnreadMessagesResponse with a status of "success" if the messages are fetched, or "error" if they are not.
        """
        username = request.username
        user_info = get_user_info(username)
        n_message_index = 1
        if user_info:
            n_unread_messages = user_info[n_message_index]
            if not n_unread_messages:
                n_unread_messages = 50

        else:
            logging.info(f"User '{context.username}' not found in database.")
            n_unread_messages = 50
        try:
            unread_tuples = get_unread_messages(username, limit=n_unread_messages)
        except Exception as e:
            logging.error("Error fetching unread messages for %s: %s", username, e)
            context.set_details("Error fetching unread messages")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.UnreadMessagesResponse(messages=[], status="error")

        chat_messages = []
        for tup in unread_tuples:
            msg_id, sender, content, timestamp = tup
            print(
                f"sender: {sender}, content: {content}, timestamp: {timestamp}, msg_id: {msg_id}"
            )
            print("types: ", type(sender), type(content), type(timestamp), type(msg_id))
            chat_msg = protocols_pb2.ChatMessage(
                **{
                    "message": content,
                    "timestamp": timestamp,
                    "from": sender,
                    "id": msg_id,
                }
            )
            chat_messages.append(chat_msg)

        return protocols_pb2.UnreadMessagesResponse(
            messages=chat_messages, status="success"
        )

    def MarkAsRead(self, request, context):
        """
        Mark a list of messages as read.

        Args:
            request: A MarkAsReadRequest with the message IDs to mark as read.
            context: The context of the gRPC request.

        Returns:
            A ConfirmMarkAsReadResponse with a status of "success" if the messages are marked as read, or "error" if they are not.
        """

        try:
            # request.message_ids is a repeated field of int32
            mark_messages_as_read(request.message_ids)
            return protocols_pb2.ConfirmMarkAsReadResponse(
                message="Messages marked as read.",
                status="success",
            )
        except Exception as e:
            logging.error("Error in MarkAsRead: %s", e)
            context.set_details("Internal server error while marking messages as read")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.ConfirmMarkAsReadResponse(
                message="Internal server error",
                status="error",
            )

    def DeleteMessage(self, request, context):
        """
        Delete a message.

        Args:
            request: A DeleteMessageRequest with the username and message_id of the message to delete.
            context: The context of the gRPC request.

        Returns:
            A SuccessResponse with a status of "success" if the message is deleted, or "error" if it is not.
        """

        logging.info(
            "DeleteMessage called for user: %s, message_id: %d",
            request.username,
            request.message_id,
        )
        try:
            success = delete_message(request.message_id)
            if success:
                return protocols_pb2.SuccessResponse(
                    message="Message deleted successfully.",
                    status="success",
                )
            else:
                context.set_details("Failed to delete message.")
                context.set_code(grpc.StatusCode.INTERNAL)
                return protocols_pb2.SuccessResponse(
                    message="Failed to delete message.",
                    status="error",
                )
        except Exception as e:
            logging.error("Error in DeleteMessage: %s", e)
            context.set_details("Internal server error during message deletion")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.SuccessResponse(
                message="Internal server error",
                status="error",
            )

    def DeleteAccount(self, request, context):
        """
        Delete the account of a user.

        Args:
            request: A DeleteAccountRequest with the username.
            context: The context of the gRPC request.

        Returns:
            A SuccessResponse with a status of "success" if the account is deleted, or "error" if it is not.
        """
        logging.info("DeleteAccount called for user: %s", request.username)
        try:
            success = delete_account(request.username)
            if success:
                with online_users_lock:
                    if request.username in online_users:
                        del online_users[request.username]
                return protocols_pb2.SuccessResponse(
                    message="Account deleted successfully.",
                    status="success",
                )
            else:
                context.set_details("Failed to delete account.")
                context.set_code(grpc.StatusCode.INTERNAL)
                return protocols_pb2.SuccessResponse(
                    message="Failed to delete account.",
                    status="error",
                )
        except Exception as e:
            logging.error("Error in DeleteAccount: %s", e)
            context.set_details("Internal server error during account deletion")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.SuccessResponse(
                message="Internal server error",
                status="error",
            )

    def SetNUnreadMessages(self, request, context):
        """
        Set the number of unread messages for a user.

        Args:
            request: A SetNUnreadMessagesRequest with the username and number of unread messages.
            context: The context of the gRPC request.

        Returns:
            A SuccessResponse with a status of "success" if the unread messages count is set, or "error" if it is not.

        Notes:
            If the user is not found in the database, the unread messages count is set to 50.
            If the user is found but the unread messages count is not set in the request, an error is returned.
            If the unread messages count is set, the server will fetch the unread messages from the database and enqueue
            them for the user.
        """

        username = request.username
        n_unread = request.n_unread_messages

        # Get old unread messages count from the database (assume get_user_info returns a tuple)
        user_info = get_user_info(username)
        n_message_index = 1
        if user_info:
            n_unread_old = user_info[n_message_index]
            if not n_unread_old:
                n_unread_old = 50
        else:
            logging.info(f"User '{username}' not found in database.")
            n_unread_old = 50

        if not n_unread:
            context.set_details("Number of unread messages is required.")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return protocols_pb2.SuccessResponse(
                message="Number of unread messages is required.", status="error"
            )

        # Update the unread messages count in the database.
        success = set_n_unread_messages(username, n_unread)
        if success:
            try:
                unread_tuples = get_unread_messages(username, limit=n_unread)
                # Assume corrected tuple order: (msg_id, sender, content, timestamp)
                for tup in unread_tuples:
                    msg_id, sender, content, timestamp = tup
                    received_msg = protocols_pb2.ReceivedMessage(
                        **{
                            "message": content,
                            "from": sender,
                            "timestamp": timestamp,
                            "read": "false",
                            "id": int(msg_id),
                            "username": sender,
                        }
                    )
                    enqueue_message(username, received_msg)
            except Exception as e:
                logging.error("Error fetching unread messages: %s", e)
            return protocols_pb2.SuccessResponse(
                message="Number of unread messages set successfully.", status="success"
            )
        else:
            context.set_details("Failed to set number of unread messages.")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.SuccessResponse(
                message="Failed to set number of unread messages.", status="error"
            )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    protocols_pb2_grpc.add_MessagingServiceServicer_to_server(
        MessagingServiceServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    logging.info("gRPC server is running on port 50051...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
