# client.py
import logging
import grpc
import time

# Import the generated gRPC modules for the leader service
import protocols_pb2
import protocols_pb2_grpc

# Also import the replica modules (for GetLeader RPC)
import replica_pb2
import replica_pb2_grpc


class SizeLoggingClientInterceptor(
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
    grpc.StreamUnaryClientInterceptor,
    grpc.StreamStreamClientInterceptor,
):
    def intercept_unary_unary(self, continuation, client_call_details, request):
        data = request.SerializeToString()
        size = len(data)
        logging.info(f"Sending unary_unary request of size: {size} bytes")
        response = continuation(client_call_details, request)
        return response

    def intercept_unary_stream(self, continuation, client_call_details, request):
        data = request.SerializeToString()
        size = len(data)
        logging.info(f"Sending unary_stream request of size: {size} bytes")
        response_it = continuation(client_call_details, request)
        return response_it

    def intercept_stream_unary(
        self, continuation, client_call_details, request_iterator
    ):
        total = 0
        for req in request_iterator:
            total += len(req.SerializeToString())
        logging.info(f"Sending stream_unary request total size: {total} bytes")
        return continuation(client_call_details, request_iterator)

    def intercept_stream_stream(
        self, continuation, client_call_details, request_iterator
    ):
        total = 0
        for req in request_iterator:
            total += len(req.SerializeToString())
        logging.info(f"Sending stream_stream request total size: {total} bytes")
        return continuation(client_call_details, request_iterator)


class GRPCClient:
    """
    A simple gRPC client to interact with the MessagingService,
    with automatic retries and leader discovery.
    """

    def __init__(
        self, host="localhost", port=50051, intercept=True, replica_endpoints=None
    ):
        """
        Initializes the gRPC client.

        Args:
            host (str): The hostname of the current leader.
            port (int): The port number of the current leader.
            intercept (bool): Whether to use interceptors.
            replica_endpoints (list of str): A list of "host:port" strings for replica endpoints,
                                             used for leader discovery.
        """
        self.intercept = intercept
        self.replica_endpoints = replica_endpoints or []
        self.current_leader = f"{host}:{port}"
        self._init_channel(self.current_leader)
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
        Generic RPC retry wrapper.
        Args:
            rpc_func (callable): A zero-argument function that calls an RPC.
            max_retries (int): Number of retries.
            backoff (int): Base seconds for exponential backoff.
        Returns:
            The RPC response if successful, or None if all attempts fail.
        """
        attempts = 0
        while attempts < max_retries:
            try:
                # Optionally, wait for the channel to be ready.
                grpc.channel_ready_future(self.channel).result(timeout=2)
                return rpc_func()
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    attempts += 1
                    logging.error(
                        "RPC failed with UNAVAILABLE (attempt %d): %s", attempts, e
                    )
                    new_leader = self.discover_leader()
                    if new_leader:
                        self.update_channel(new_leader)
                        logging.info("Updated leader address to: %s", new_leader)
                    time.sleep(backoff * (2**attempts))
                else:
                    logging.error("RPC failed with non-retryable error: %s", e)
                    return None
        return None

    def discover_leader(self):
        """
        Try to discover the new leader by querying the replica endpoints.
        Returns:
            The leader address as a string (e.g., "hostname:port") if discovered, else None.
        """
        for replica in self.replica_endpoints:
            try:
                temp_channel = grpc.insecure_channel(replica)
                temp_stub = replica_pb2_grpc.ReplicaServiceStub(temp_channel)
                response = temp_stub.GetLeader(
                    replica_pb2.GetLeaderRequest(), timeout=2
                )
                if response and response.leader_address:
                    logging.info(
                        "Discovered leader %s from replica %s",
                        response.leader_address,
                        replica,
                    )
                    return response.leader_address
            except grpc.RpcError as ex:
                logging.error("Failed to get leader from %s: %s", replica, ex)
        return None

    def update_channel(self, leader_address):
        """
        Reinitialize the channel and stub with the new leader's address.
        """
        self.current_leader = leader_address
        self._init_channel(leader_address)

    # Now update RPC methods to use perform_rpc:

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
        """
        Subscribes to user updates. For streaming RPCs, you may want to handle
        reconnection separately if needed.
        """

        def rpc_func():
            request = protocols_pb2.SubscribeRequest(username=username)
            return self.stub.Subscribe(request)

        # For simplicity, we wrap the initial subscribe call with perform_rpc.
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
