# load_balancer.py
import grpc
from concurrent import futures
import time
import logging

import protocols_pb2
import protocols_pb2_grpc
import replica_pb2
import replica_pb2_grpc


class LoadBalancerServicer(protocols_pb2_grpc.MessagingServiceServicer):
    """
    A load balancer that forwards client RPCs to the current leader.
    It discovers the leader by querying the configured replica endpoints.
    """

    def __init__(self, replica_endpoints, intercept=False):
        self.replica_endpoints = replica_endpoints  # List of replica addresses (e.g., ["host1:port1", "host2:port2"])
        self.current_leader = None
        self.intercept = intercept
        self._update_leader()

    def _update_leader(self):
        """
        Try to update the current leader by querying each replica’s GetLeader RPC.
        """
        for replica in self.replica_endpoints:
            try:
                channel = grpc.insecure_channel(replica)
                stub = replica_pb2_grpc.ReplicaServiceStub(channel)
                response = stub.GetLeader(replica_pb2.GetLeaderRequest(), timeout=2)
                if response and response.leader_address:
                    self.current_leader = response.leader_address
                    logging.info(
                        "Load balancer updated leader to: %s", self.current_leader
                    )
                    channel.close()
                    return
            except Exception as e:
                logging.error(
                    "Error contacting replica %s for leader discovery: %s", replica, e
                )
        logging.error("Load balancer could not discover leader from any replica.")

    def _get_leader_stub(self):
        """
        Returns a stub connected to the current leader. If no leader is known,
        try to update from replicas.
        """
        if not self.current_leader:
            self._update_leader()
        if not self.current_leader:
            raise Exception("No leader available")
        channel = grpc.insecure_channel(self.current_leader)
        if self.intercept:
            # If needed, add client interceptors here.
            interceptors = []
            channel = grpc.intercept_channel(channel, *interceptors)
        return protocols_pb2_grpc.MessagingServiceStub(channel)

    def _forward_rpc(self, rpc_name, request, context):
        """
        Generic helper that forwards the RPC call to the current leader.
        If an error occurs (e.g. leader unavailable), attempt to update the leader and retry once.
        """
        try:
            stub = self._get_leader_stub()
            rpc_func = getattr(stub, rpc_name)
            response = rpc_func(request, metadata=context.invocation_metadata())
            return response
        except grpc.RpcError as e:
            logging.error("Error forwarding RPC %s: %s", rpc_name, e)
            if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.INTERNAL):
                logging.info("Attempting to update leader and retry RPC %s", rpc_name)
                self._update_leader()
                try:
                    stub = self._get_leader_stub()
                    rpc_func = getattr(stub, rpc_name)
                    response = rpc_func(request, metadata=context.invocation_metadata())
                    return response
                except Exception as e2:
                    logging.error("Retry failed for RPC %s: %s", rpc_name, e2)
                    context.set_code(grpc.StatusCode.UNAVAILABLE)
                    context.set_details("Leader unavailable")
                    return None
            else:
                context.set_code(e.code())
                context.set_details(e.details())
                return None
        except Exception as e:
            logging.error("General error in forwarding RPC %s: %s", rpc_name, e)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal load balancer error")
            return None

    # Now implement (or forward) all MessagingService RPCs:
    def Login(self, request, context):
        return self._forward_rpc("Login", request, context)

    def Register(self, request, context):
        return self._forward_rpc("Register", request, context)

    def SendMessage(self, request, context):
        return self._forward_rpc("SendMessage", request, context)

    def GetRecentMessages(self, request, context):
        return self._forward_rpc("GetRecentMessages", request, context)

    def GetUnreadMessages(self, request, context):
        return self._forward_rpc("GetUnreadMessages", request, context)

    def MarkAsRead(self, request, context):
        return self._forward_rpc("MarkAsRead", request, context)

    def SetNUnreadMessages(self, request, context):
        return self._forward_rpc("SetNUnreadMessages", request, context)

    def DeleteMessage(self, request, context):
        return self._forward_rpc("DeleteMessage", request, context)

    def DeleteAccount(self, request, context):
        return self._forward_rpc("DeleteAccount", request, context)

    def Subscribe(self, request, context):
        # For streaming RPCs, forward the stream.
        try:
            stub = self._get_leader_stub()
            response_iterator = stub.Subscribe(
                request, metadata=context.invocation_metadata()
            )
            for response in response_iterator:
                yield response
        except grpc.RpcError as e:
            logging.error("Error forwarding Subscribe RPC: %s", e)
            context.set_code(e.code())
            context.set_details(e.details())
            return
        except Exception as e:
            logging.error("General error in forwarding Subscribe RPC: %s", e)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Internal load balancer error")
            return

    def GetUsers(self, request, context):
        return self._forward_rpc("GetUsers", request, context)

    def SearchUsers(self, request, context):
        return self._forward_rpc("SearchUsers", request, context)


def serve_load_balancer(
    lb_host="0.0.0.0", lb_port="50051", replica_endpoints=None, intercept=False
):
    """
    Starts the load balancer service on the given host/port.
    replica_endpoints: Comma-separated list of replica addresses (for leader discovery).
    """
    if replica_endpoints is None:
        replica_endpoints = ["localhost:50052"]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    load_balancer_servicer = LoadBalancerServicer(
        replica_endpoints, intercept=intercept
    )
    protocols_pb2_grpc.add_MessagingServiceServicer_to_server(
        load_balancer_servicer, server
    )
    server_address = f"{lb_host}:{lb_port}"
    server.add_insecure_port(server_address)
    logging.info("Load balancer running on %s", server_address)
    server.start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("Load balancer shutting down.")
        server.stop(0)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser(description="Start the gRPC load balancer")
    parser.add_argument(
        "--lb_host", type=str, default="0.0.0.0", help="Host for the load balancer"
    )
    parser.add_argument(
        "--lb_port", type=str, default="50051", help="Port for the load balancer"
    )
    parser.add_argument(
        "--replica_endpoints",
        type=str,
        default="localhost:50052",
        help="Comma-separated list of replica addresses for leader discovery (e.g., 'host1:port1,host2:port2')",
    )
    parser.add_argument(
        "--intercept",
        action="store_true",
        help="Enable interceptors for outgoing leader connections",
    )
    args = parser.parse_args()
    replica_endpoints = args.replica_endpoints.split(",")
    serve_load_balancer(
        lb_host=args.lb_host,
        lb_port=args.lb_port,
        replica_endpoints=replica_endpoints,
        intercept=args.intercept,
    )
