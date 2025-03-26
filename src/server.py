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
from replication_manager import ReplicationManager
from server_intercepter import SizeLoggingServerInterceptor
from users import UserManager

# Import the refactored MessagingServiceServicer
from messaging_service_servicer import MessagingServiceServicer

# Set up logger for the server
logger = setup_logger("server")

# Global variables for server configuration
EXTERNAL_HOST = None
SERVER_PORT = "50051"


def send_heartbeats(replica_addresses):
    """
    Periodically send heartbeats to all replicas.
    """
    global EXTERNAL_HOST, SERVER_PORT
    leader_address = f"{EXTERNAL_HOST}:{SERVER_PORT}"
    logger.info(f"Sending heartbeats as leader at {leader_address}")
    while True:
        for replica_addr in replica_addresses:
            if replica_addr == leader_address:
                continue
            channel = grpc.insecure_channel(replica_addr)
            try:
                grpc.channel_ready_future(channel).result(timeout=2.0)
                stub = replica_pb2_grpc.ReplicaServiceStub(channel)
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
    """
    Determine the external host address for heartbeats and client connections.
    """
    if host not in ("0.0.0.0", "localhost", "127.0.0.1"):
        return host
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostname()


def serve(host="0.0.0.0", port="50051", replica_addresses=None, external_host=None):
    """
    Start the gRPC server and the heartbeat thread.
    """
    global EXTERNAL_HOST, SERVER_PORT
    SERVER_PORT = port
    EXTERNAL_HOST = external_host if external_host else get_external_host(host)
    logger.info(f"Server binding to {host}:{port}")
    logger.info(f"Using external host {EXTERNAL_HOST} for client connections")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    messaging_service = MessagingServiceServicer(replica_addresses=replica_addresses)
    protocols_pb2_grpc.add_MessagingServiceServicer_to_server(messaging_service, server)
    server_address = f"{host}:{port}"
    server.add_insecure_port(server_address)

    logger.info(f"gRPC leader server running on {server_address}...")

    replica_addrs_list = (
        replica_addresses.split(",")
        if isinstance(replica_addresses, str)
        else replica_addresses
    )

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
    serve(
        host=args.host,
        port=args.port,
        replica_addresses=replica_addresses,
        external_host=args.external_host,
    )
