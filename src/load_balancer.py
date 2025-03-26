import grpc
from concurrent import futures
import time
import logging
import subprocess
import threading
import argparse

import protocols_pb2
import protocols_pb2_grpc
import replica_pb2
import replica_pb2_grpc

from election_manager import ElectionManager


# --- VIP Management Functions ---


def assign_vip(vip, interface="eth0"):
    """
    Assigns the given VIP (with /32 mask) to the specified network interface.
    Requires appropriate privileges.
    """
    try:
        subprocess.run(
            ["ip", "addr", "add", f"{vip}/32", "dev", interface],
            check=True,
        )
        logging.info("VIP %s assigned to interface %s", vip, interface)
    except Exception as e:
        logging.error("Failed to assign VIP %s on interface %s: %s", vip, interface, e)


def remove_vip(vip, interface="eth0"):
    """
    Removes the given VIP from the specified network interface.
    """
    try:
        subprocess.run(
            ["ip", "addr", "del", f"{vip}/32", "dev", interface],
            check=True,
        )
        logging.info("VIP %s removed from interface %s", vip, interface)
    except Exception as e:
        logging.error(
            "Failed to remove VIP %s from interface %s: %s", vip, interface, e
        )


# --- Load Balancer Servicer (for MessagingService RPC forwarding) ---


class LoadBalancerServicer(protocols_pb2_grpc.MessagingServiceServicer):
    """
    A load balancer that forwards client RPCs to the current leader.
    It discovers the leader by querying the configured replica endpoints.
    """

    def __init__(self, replica_endpoints, intercept=False):
        self.replica_endpoints = (
            replica_endpoints  # e.g., ["host1:port1", "host2:port2"]
        )
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
            interceptors = []
            channel = grpc.intercept_channel(channel, *interceptors)
        return protocols_pb2_grpc.MessagingServiceStub(channel)

    def _forward_rpc(self, rpc_name, request, context):
        """
        Helper to forward the RPC call to the current leader.
        On error, update leader and retry once.
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

    # Forwarding all MessagingService RPCs:
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


# --- Dummy Replica Service for LB Election (implements GetReplicaID) ---


class LoadBalancerReplicaServicer(replica_pb2_grpc.ReplicaServiceServicer):
    """
    Dummy implementation of ReplicaService for load balancer election purposes.
    Only implements GetReplicaID so that the ElectionManager can query LB endpoints.
    """

    def __init__(self, lb_id):
        self.lb_id = lb_id

    def GetReplicaID(self, request, context):
        from replica_pb2 import GetReplicaIDResponse

        logging.info(
            "Load balancer responding to GetReplicaID with lb_id: %s", self.lb_id
        )
        return GetReplicaIDResponse(replica_id=self.lb_id)

    # Optionally, you can implement other methods (like Heartbeat or GetLeader) if needed.
    # For now, they can remain unimplemented or return errors.


# --- Election Monitoring for VIP Management ---


def monitor_election(election_manager, vip, interface, poll_interval=5):
    """
    Periodically checks if this load balancer should be leader (via election_manager).
    If elected and the VIP is not assigned, assign it. If not elected and VIP is assigned, remove it.
    """
    is_vip_assigned = False
    while True:
        try:
            if election_manager.elect_leader():
                if not is_vip_assigned:
                    logging.info(
                        "This load balancer elected as leader; assigning VIP %s", vip
                    )
                    assign_vip(vip, interface)
                    is_vip_assigned = True
            else:
                if is_vip_assigned:
                    logging.info(
                        "This load balancer is no longer leader; removing VIP %s", vip
                    )
                    remove_vip(vip, interface)
                    is_vip_assigned = False
        except Exception as e:
            logging.error("Error in election monitor: %s", e)
        time.sleep(poll_interval)


# --- Main Server Setup ---


def serve_load_balancer(
    lb_host,
    lb_port,
    replica_endpoints,
    intercept,
    election_endpoints,
    lb_id,
    vip,
    vip_interface,
):
    """
    Starts the load balancer service with VIP and LB election.

    Additional parameters for VIP and election:
      - election_endpoints: list of LB addresses for election among LB nodes.
      - lb_id: this load balancer's unique numeric ID.
      - vip: the virtual IP that clients connect to.
      - vip_interface: network interface for VIP assignment.
    """
    # Create the election manager for load balancers (reuse ElectionManager)
    election_manager = ElectionManager(election_endpoints, lb_id)

    # Start the election monitor thread for VIP management.
    election_thread = threading.Thread(
        target=monitor_election,
        args=(election_manager, vip, vip_interface),
        daemon=True,
    )
    election_thread.start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add the MessagingService for RPC forwarding.
    lb_servicer = LoadBalancerServicer(replica_endpoints, intercept=intercept)
    protocols_pb2_grpc.add_MessagingServiceServicer_to_server(lb_servicer, server)

    # Also add our dummy ReplicaService so that GetReplicaID works for LB election.
    lb_replica_servicer = LoadBalancerReplicaServicer(lb_id)
    replica_pb2_grpc.add_ReplicaServiceServicer_to_server(lb_replica_servicer, server)

    server_address = f"{lb_host}:{lb_port}"
    server.add_insecure_port(server_address)
    logging.info("Load balancer running on %s", server_address)
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt detected: shutting down load balancer.")
        server.stop(0)
        # Optionally, remove VIP on shutdown
        remove_vip(vip, vip_interface)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Start the gRPC load balancer with VIP and election management"
    )
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
        help="Comma-separated list of replica addresses for leader discovery",
    )
    parser.add_argument(
        "--intercept",
        action="store_true",
        help="Enable interceptors for outgoing leader connections",
    )
    # New arguments for LB election and VIP management
    parser.add_argument(
        "--lb_id", type=int, required=True, help="Unique ID for this load balancer"
    )
    parser.add_argument(
        "--lb_election_endpoints",
        type=str,
        required=True,
        help="Comma-separated list of load balancer addresses for election",
    )
    parser.add_argument(
        "--vip", type=str, required=True, help="The virtual IP address to assign"
    )
    parser.add_argument(
        "--vip_interface",
        type=str,
        default="eth0",
        help="Network interface for VIP assignment",
    )

    args = parser.parse_args()
    replica_endpoints = args.replica_endpoints.split(",")
    lb_election_endpoints = args.lb_election_endpoints.split(",")

    serve_load_balancer(
        lb_host=args.lb_host,
        lb_port=args.lb_port,
        replica_endpoints=replica_endpoints,
        intercept=args.intercept,
        election_endpoints=lb_election_endpoints,
        lb_id=args.lb_id,
        vip=args.vip,
        vip_interface=args.vip_interface,
    )
