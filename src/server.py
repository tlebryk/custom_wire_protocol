# server.py
from concurrent import futures
import grpc
import logging
import threading
import time
from datetime import datetime


from users import authenticate_user, register_user, delete_account
from database import delete_message

import protocols_pb2
import protocols_pb2_grpc

logging.basicConfig(level=logging.INFO)

# Global dictionary to track online users.
# Key: username, Value: a tuple (context, queue) where queue is a list of messages pending delivery.
online_users = {}
online_users_lock = threading.Lock()


# In a real system you’d likely use a thread-safe queue per user.
def enqueue_message(username, message):
    with online_users_lock:
        if username in online_users:
            context, msg_queue = online_users[username]
            msg_queue.append(message)


class MessagingServiceServicer(protocols_pb2_grpc.MessagingServiceServicer):
    def Login(self, request, context):
        logging.info("Login called for user: %s", request.username)
        if authenticate_user(request.username, request.password):
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
        This streaming RPC registers a user as online.
        The client should call Subscribe (after login) and then block on the stream.
        When the server has a message for this user, it will yield it.
        """
        username = request.username
        logging.info("Subscribe called for user: %s", username)
        with online_users_lock:
            online_users[username] = (context, [])
        try:
            while context.is_active():
                with online_users_lock:
                    _, msg_queue = online_users.get(username, (None, []))
                    if msg_queue:
                        while msg_queue:
                            msg = msg_queue.pop(0)
                            yield msg
                time.sleep(0.5)
        except Exception as e:
            logging.error("Error in Subscribe for user %s: %s", username, e)
        finally:
            with online_users_lock:
                if username in online_users:
                    del online_users[username]
            logging.info("User %s unsubscribed.", username)

    def SendMessage(self, request, context):
        logging.info(
            "SendMessage called. Message: %s, Receiver: %s",
            request.message,
            request.receiver,
        )
        try:
            # Assume the sender is passed in the request metadata.
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

            # Insert the message into the database.
            message_id = insert_message(sender, request.message, request.receiver)
            logging.info(f"Message inserted with ID: {message_id}")

            # Prepare a ReceivedMessage payload using a dict and unpack it.
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

            # Check if the receiver is online.
            with online_users_lock:
                receiver_entry = online_users.get(request.receiver)

            if receiver_entry:
                enqueue_message(request.receiver, received_msg)
                logging.info(
                    f"Message enqueued for online receiver '{request.receiver}'."
                )
            else:
                logging.info(
                    f"User '{request.receiver}' is offline. Message stored for later delivery."
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
            logging.error(f"Error in SendMessage: {e}")
            context.set_details("Internal server error")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.ConfirmSendMessageResponse(
                message="Internal server error",
                status="error",
                timestamp="",
            )

    def GetRecentMessages(self, request, context):
        """
        Retrieves recent messages for the given user.
        Uses get_recent_messages(user_id, limit) from the database.
        """
        username = request.username
        try:
            recent_tuples = get_recent_messages(username, limit=50)
        except Exception as e:
            logging.error("Error fetching recent messages for %s: %s", username, e)
            context.set_details("Error fetching recent messages")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.RecentMessagesResponse(messages=[], status="error")

        chat_messages = []
        # Each tuple is (sender, content, receiver, timestamp, id)
        for tup in recent_tuples:
            sender, content, receiver, timestamp, msg_id = tup
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
        Retrieves unread (undelivered) messages for the given user.
        Uses get_undelivered_messages(user_id) from the database.
        """
        username = request.username
        try:
            unread_tuples = get_undelivered_messages(username)
        except Exception as e:
            logging.error("Error fetching unread messages for %s: %s", username, e)
            context.set_details("Error fetching unread messages")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.UnreadMessagesResponse(messages=[], status="error")

        chat_messages = []
        # Each tuple is (sender, content, timestamp, id)
        for tup in unread_tuples:
            sender, content, timestamp, msg_id = tup
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

    def DeleteMessage(self, request, context):
        """
        Handles deletion of a message.
        Expects a DeleteMessageRequest with fields 'username' and 'message_id'.
        """
        logging.info(
            "DeleteMessage called for user: %s, message_id: %d",
            request.username,
            request.message_id,
        )
        success = delete_message(request.message_id)
        if success:
            return protocols_pb2.SuccessResponse(
                message="Message deleted", status="success"
            )
        else:
            return protocols_pb2.SuccessResponse(
                message="Failed to delete message", status="error"
            )

    def DeleteAccount(self, request, context):
        """
        Handles deletion of an account.
        Expects a DeleteAccountRequest with field 'username'.
        """
        logging.info("DeleteAccount called for user: %s", request.username)
        success = delete_account(request.username)
        if success:
            return protocols_pb2.SuccessResponse(
                message="Account deleted", status="success"
            )
        else:
            return protocols_pb2.SuccessResponse(
                message="Failed to delete account", status="error"
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
