# client.py (modified snippet)
import logging
import grpc
import time

import protocols_pb2
import protocols_pb2_grpc


class SizeLoggingClientInterceptor(
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
    grpc.StreamUnaryClientInterceptor,
    grpc.StreamStreamClientInterceptor,
):
    # (Interceptor code remains unchanged)
    def intercept_unary_unary(self, continuation, client_call_details, request):
        data = request.SerializeToString()
        size = len(data)
        logging.info(f"Sending unary_unary request of size: {size} bytes")
        response = continuation(client_call_details, request)
        return response

    # ... (other interceptor methods)


class GRPCClient:
    """
    A gRPC client that connects to one of multiple load balancer addresses.
    If one load balancer fails, it will rotate to the next available address.
    """

    def __init__(self, lb_addresses=None, intercept=True):
        """
        Args:
            lb_addresses (list of str): List of load balancer addresses (e.g., ["host1:port", "host2:port"]).
            intercept (bool): Whether to use interceptors.
        """
        if lb_addresses is None:
            lb_addresses = ["localhost:50051"]
        self.intercept = intercept
        self.lb_addresses = lb_addresses
        self.current_lb_index = 0
        self._init_channel(self.lb_addresses[self.current_lb_index])
        self.username = None

    def _init_channel(self, address):
        if self.intercept:
            interceptors = [SizeLoggingClientInterceptor()]
        else:
            interceptors = []
        self.channel = grpc.intercept_channel(
            grpc.insecure_channel(address), *interceptors
        )
        self.stub = protocols_pb2_grpc.MessagingServiceStub(self.channel)
        logging.info("Initialized channel to %s", address)

    def perform_rpc(self, rpc_func, max_retries=5, backoff=1):
        """
        Generic RPC retry wrapper that rotates through load balancer addresses.
        """
        attempts = 0
        while attempts < max_retries:
            try:
                grpc.channel_ready_future(self.channel).result(timeout=2)
                return rpc_func()
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    attempts += 1
                    logging.error(
                        "RPC failed with UNAVAILABLE (attempt %d): %s", attempts, e
                    )
                    # Rotate to the next load balancer
                    self.current_lb_index = (self.current_lb_index + 1) % len(
                        self.lb_addresses
                    )
                    new_lb = self.lb_addresses[self.current_lb_index]
                    logging.info("Switching to backup load balancer: %s", new_lb)
                    self._init_channel(new_lb)
                    time.sleep(backoff * (2**attempts))
                else:
                    logging.error("RPC failed with non-retryable error: %s", e)
                    return None
        return None

    # RPC methods remain unchanged and use self.stub
    def login(self, username: str, password: str):
        def rpc_func():
            request = protocols_pb2.LoginRequest(username=username, password=password)
            return self.stub.Login(request)

        return self.perform_rpc(rpc_func)

    def register(self, username: str, password: str):
        def rpc_func():
            request = protocols_pb2.RegisterRequest(
                username=username, password=password
            )
            return self.stub.Register(request)

        return self.perform_rpc(rpc_func)

    def send_message(self, message: str, receiver: str):
        def rpc_func():
            request = protocols_pb2.SendMessageRequest(
                message=message, receiver=receiver
            )
            return self.stub.SendMessage(request, metadata=(("sender", self.username),))

        return self.perform_rpc(rpc_func)

    def get_recent_messages(self, username: str):
        def rpc_func():
            request = protocols_pb2.GetRecentMessagesRequest(username=username)
            return self.stub.GetRecentMessages(request)

        return self.perform_rpc(rpc_func)

    def get_unread_messages(self, username: str):
        def rpc_func():
            request = protocols_pb2.GetUnreadMessagesRequest(username=username)
            return self.stub.GetUnreadMessages(request)

        return self.perform_rpc(rpc_func)

    def mark_as_read(self, message_ids: list):
        def rpc_func():
            request = protocols_pb2.MarkAsReadRequest(message_ids=message_ids)
            return self.stub.MarkAsRead(request)

        return self.perform_rpc(rpc_func)

    def set_n_unread_messages(self, username: str, n: int):
        def rpc_func():
            request = protocols_pb2.SetNUnreadMessagesRequest(
                username=username, n_unread_messages=n
            )
            return self.stub.SetNUnreadMessages(request)

        return self.perform_rpc(rpc_func)

    def delete_message(self, username: str, message_id: int):
        def rpc_func():
            request = protocols_pb2.DeleteMessageRequest(
                username=username, message_id=message_id
            )
            return self.stub.DeleteMessage(request)

        return self.perform_rpc(rpc_func)

    def delete_account(self, username: str):
        def rpc_func():
            request = protocols_pb2.DeleteAccountRequest(username=username)
            return self.stub.DeleteAccount(request)

        return self.perform_rpc(rpc_func)

    def subscribe(self, username: str):
        def rpc_func():
            request = protocols_pb2.SubscribeRequest(username=username)
            return self.stub.Subscribe(request)

        stream = self.perform_rpc(rpc_func)
        if stream is None:
            logging.error("Subscribe RPC failed after retries.")
        return stream

    def get_users(self, username: str):
        def rpc_func():
            request = protocols_pb2.GetUsersRequest(username=username)
            return self.stub.GetUsers(request)

        response = self.perform_rpc(rpc_func)
        if response and response.status == "success":
            return list(response.usernames)
        return []

    def search_users(self, query):
        def rpc_func():
            request = protocols_pb2.SearchUsersRequest(query=query)
            return self.stub.SearchUsers(request)

        response = self.perform_rpc(rpc_func)
        if response and response.status == "success":
            return response.usernames
        return []
