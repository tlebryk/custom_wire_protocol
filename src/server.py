# server.py
from concurrent import futures
import grpc
import logging
from users import authenticate_user, register_user
from database import delete_message

import protocols_pb2
import protocols_pb2_grpc

logging.basicConfig(level=logging.INFO)


class MessagingServiceServicer(protocols_pb2_grpc.MessagingServiceServicer):
    # message is always sending success, fix this
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


    def SendMessage(self, request, context):
        logging.info(
            "SendMessage called. Message: %s, Receiver: %s",
            request.message,
            request.receiver,
        )
        # Replace with your send message logic
        return protocols_pb2.ConfirmSendMessageResponse(
            **dict(
                message="Message sent",
                status="success",
                timestamp="2025-02-23T00:00:00Z",
                # /from="server"
            )
        )

    def Echo(self, request, context):
        logging.info("Echo called with message: %s", request.message)
        # Simply echo back the received message
        return protocols_pb2.ConfirmEchoResponse(
            message=request.message, status="success"
        )

    def GetRecentMessages(self, request, context):
        logging.info("GetRecentMessages called for user: %s", request.username)
        # Replace with your logic to fetch recent messages.
        # Here we provide a dummy message for demonstration.
        dummy_message = protocols_pb2.ChatMessage(
            message="Hello, this is a recent message",
            timestamp="2025-02-23T00:00:00Z",
            # from="user1",
            id=1,
        )
        return protocols_pb2.RecentMessagesResponse(
            messages=[dummy_message], status="success"
        )

    def GetUnreadMessages(self, request, context):
        logging.info("GetUnreadMessages called for user: %s", request.username)
        # Replace with your logic to fetch unread messages.
        dummy_message = protocols_pb2.ChatMessage(
            message="This is an unread message",
            timestamp="2025-02-23T00:00:00Z",
            # from="user2",
            id=2,
        )
        return protocols_pb2.UnreadMessagesResponse(
            messages=[dummy_message], status="success"
        )

    def SetNUnreadMessages(self, request, context):
        logging.info(
            "SetNUnreadMessages called for user: %s, n_unread_messages: %d",
            request.username,
            request.n_unread_messages,
        )
        # Replace with your logic to set the unread messages count.
        return protocols_pb2.SuccessResponse(
            message="Unread message count set", status="success"
        )

    def MarkAsRead(self, request, context):
        logging.info("MarkAsRead called for message_ids: %s", request.message_ids)
        # Replace with your logic to mark messages as read.
        return protocols_pb2.ConfirmMarkAsReadResponse(
            message="Messages marked as read", status="success"
        )

    def DeleteMessage(self, request, context):
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
            logging.info("DeleteAccount called for user: %s", request.username)
            # Replace with your delete account logic.
            return protocols_pb2.SuccessResponse(
                message="Account deleted", status="success"
            )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    protocols_pb2_grpc.add_MessagingServiceServicer_to_server(
        MessagingServiceServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    logging.info("Starting gRPC server on port 50051...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
