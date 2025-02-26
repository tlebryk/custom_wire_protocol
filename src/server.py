# server.py
from concurrent import futures
import grpc
import logging
import threading
import time
from datetime import datetime

from users import authenticate_user, register_user, delete_account
from database import (
    insert_message,
    get_recent_messages,
    get_undelivered_messages,
    get_unread_messages,
    delete_message,
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

    def GetRecentMessages(self, request, context):
        username = request.username
        try:
            recent_tuples = get_recent_messages(username, limit=50)
        except Exception as e:
            logging.error("Error fetching recent messages for %s: %s", username, e)
            context.set_details("Error fetching recent messages")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.RecentMessagesResponse(messages=[], status="error")

        chat_messages = []
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
        username = request.username
        try:
            unread_tuples = get_unread_messages(username)
        except Exception as e:
            logging.error("Error fetching unread messages for %s: %s", username, e)
            context.set_details("Error fetching unread messages")
            context.set_code(grpc.StatusCode.INTERNAL)
            return protocols_pb2.UnreadMessagesResponse(messages=[], status="error")

        chat_messages = []
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

    def MarkAsRead(self, request, context):
        """
        Marks the messages with the provided message_ids as read.
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
