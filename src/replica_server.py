# replica_server.py
import os
import argparse
from concurrent import futures
import sys
import grpc
import logging

import replica_pb2
import replica_pb2_grpc
from database import Database  # Import the Database class
from users import UserManager  # Import the UserManager class

import threading
from election_manager import ElectionManager
from logger import setup_logger
import time

# Instead of os.execv, use subprocess.Popen which handles spaces in paths better.
import subprocess

logger = setup_logger("server")
# Global variable to store this replica's ID.
REPLICA_ID = None
CURRENT_LEADER_ADDRESS = None


# Set the replica's DB file using the environment variable (or a default).
replica_db_file = os.environ.get("DB_FILE", "replica_chat_app.db")
# Create a Database instance for the replica.
db = Database(replica_db_file)
# Create a UserManager instance for user operations
user_manager = UserManager(replica_db_file)

# Global variable to track heartbeat status
LAST_HEARTBEAT_TIME = time.time()
LEADER_TIMEOUT_SECS = 5


def transition_to_leader_mode(replica_addresses):
    """
    Transition the current replica process to leader mode:
    shuts down the replica services and starts the leader services.
    """
    logger.info(
        "Transitioning to leader mode: shutting down replica services and starting leader services."
    )

    python_executable = sys.executable
    current_dir = os.path.dirname(os.path.abspath(__file__))
    leader_script = os.path.join(current_dir, "server.py")

    new_args = [
        python_executable,
        leader_script,
        "--port",
        "50051",
        "--replicas",
        replica_addresses,
    ]

    logger.info(f"Executing leader mode with command: {new_args}")

    subprocess.Popen(new_args)
    # Exit the current process after starting the new leader.
    os._exit(0)


def monitor_leader(election_manager, check_interval=10):
    """
    Runs in the background to check if the leader is alive.
    If we haven't received a heartbeat for too long, we start an election.
    If election_manager.elect_leader() returns True, this replica becomes the leader.
    """
    global LAST_HEARTBEAT_TIME

    while True:
        elapsed = time.time() - LAST_HEARTBEAT_TIME
        if elapsed > LEADER_TIMEOUT_SECS:
            logger.warning("No heartbeat from leader. Starting leader election...")
            # election_manager.elect_leader() returns True if this replica should become leader.
            if election_manager.elect_leader():
                logger.info("I have been elected as the new leader!")
                replica_addresses_str = ",".join(ALL_REPLICA_ADDRESSES)
                transition_to_leader_mode(replica_addresses=replica_addresses_str)
                break  # Exit the monitor loop once we transition to leader mode.
            else:
                logger.info("Leader election check: still not leader.")
            # Reset LAST_HEARTBEAT_TIME so we don't keep re-triggering elections immediately.
            LAST_HEARTBEAT_TIME = time.time()
        time.sleep(check_interval)


class ReplicaServiceServicer(replica_pb2_grpc.ReplicaServiceServicer):

    def GetLeader(self, request, context):
        # Determine the current leader’s address.
        # For example, if using a global variable:
        if CURRENT_LEADER_ADDRESS:
            return replica_pb2.GetLeaderResponse(leader_address=CURRENT_LEADER_ADDRESS)
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Leader not found")
            return replica_pb2.GetLeaderResponse()

    def Heartbeat(self, request, context):
        """
        Called by the leader to indicate it's alive.
        """
        global LAST_HEARTBEAT_TIME, CURRENT_LEADER_ADDRESS
        LAST_HEARTBEAT_TIME = time.time()  # Update global variable
        logger.info(f"Heartbeat received from leader {request.leader_id}")
        CURRENT_LEADER_ADDRESS = request.leader_id
        return replica_pb2.HeartbeatResponse(message="OK")

    def RegisterUser(self, request, context):
        logger.info(f"Replica: RegisterUser called for {request.username}")
        try:
            # Use UserManager to register the user
            success, message = user_manager.register_user(
                request.username, request.password
            )

            if success:
                return replica_pb2.WriteOperationResponse(
                    success=True, message="User registered."
                )
            else:
                # If registration failed, propagate the failure
                context.set_details(message)
                context.set_code(grpc.StatusCode.INTERNAL)
                return replica_pb2.WriteOperationResponse(
                    success=False, message=message
                )
        except Exception as e:
            logger.error(f"Error in RegisterUser on replica: {e}")
            context.set_details("Error registering user in replica")
            context.set_code(grpc.StatusCode.INTERNAL)
            return replica_pb2.WriteOperationResponse(
                success=False, message="User registration failed."
            )

    def DeleteAccount(self, request, context):
        logger.info(f"Replica: DeleteAccount called for {request.username}")
        try:
            # Use UserManager to delete the account
            success = user_manager.delete_account(request.username)

            if success:
                return replica_pb2.WriteOperationResponse(
                    success=True, message="Account deleted."
                )
            else:
                context.set_details("Failed to delete account")
                context.set_code(grpc.StatusCode.INTERNAL)
                return replica_pb2.WriteOperationResponse(
                    success=False, message="Account deletion failed."
                )
        except Exception as e:
            logger.error(f"Error in DeleteAccount on replica: {e}")
            context.set_details("Error deleting account in replica")
            context.set_code(grpc.StatusCode.INTERNAL)
            return replica_pb2.WriteOperationResponse(
                success=False, message="Account deletion failed."
            )

    def InsertMessage(self, request, context):
        logger.info(f"Replica: InsertMessage called for message from {request.sender}")
        try:
            message_id = db.insert_message(
                request.sender, request.content, request.receiver
            )
            return replica_pb2.WriteOperationResponse(
                success=True, message=f"Message inserted with id {message_id}"
            )
        except Exception as e:
            logger.error(f"Error in InsertMessage on replica: {e}")
            context.set_details("Error inserting message in replica")
            context.set_code(grpc.StatusCode.INTERNAL)
            return replica_pb2.WriteOperationResponse(
                success=False, message="Message insertion failed."
            )

    def MarkMessagesDelivered(self, request, context):
        logger.info(f"Replica: MarkMessagesDelivered called for user {request.user_id}")
        try:
            db.mark_messages_delivered(request.user_id)
            return replica_pb2.WriteOperationResponse(
                success=True, message="Messages marked delivered."
            )
        except Exception as e:
            logger.error(f"Error in MarkMessagesDelivered on replica: {e}")
            context.set_details("Error marking messages delivered in replica")
            context.set_code(grpc.StatusCode.INTERNAL)
            return replica_pb2.WriteOperationResponse(
                success=False, message="Mark delivered failed."
            )

    def MarkMessagesAsRead(self, request, context):
        logger.info(
            f"Replica: MarkMessagesAsRead called for messages {request.message_ids}"
        )
        try:
            db.mark_messages_as_read(list(request.message_ids))
            return replica_pb2.WriteOperationResponse(
                success=True, message="Messages marked as read."
            )
        except Exception as e:
            logger.error(f"Error in MarkMessagesAsRead on replica: {e}")
            context.set_details("Error marking messages as read in replica")
            context.set_code(grpc.StatusCode.INTERNAL)
            return replica_pb2.WriteOperationResponse(
                success=False, message="Mark as read failed."
            )

    def SetNUnreadMessages(self, request, context):
        logger.info(f"Replica: SetNUnreadMessages called for user {request.username}")
        try:
            result = db.set_n_unread_messages(
                request.username, request.n_unread_messages
            )
            if result:
                return replica_pb2.WriteOperationResponse(
                    success=True, message="Unread messages count set."
                )
            else:
                raise Exception("Failed to update unread messages count")
        except Exception as e:
            logger.error(f"Error in SetNUnreadMessages on replica: {e}")
            context.set_details("Error setting unread messages count in replica")
            context.set_code(grpc.StatusCode.INTERNAL)
            return replica_pb2.WriteOperationResponse(
                success=False, message="Set unread messages failed."
            )

    def DeleteMessage(self, request, context):
        logger.info(
            f"Replica: DeleteMessage called for message ID {request.message_id}"
        )
        try:
            result = db.delete_message(request.message_id)
            if result:
                return replica_pb2.WriteOperationResponse(
                    success=True, message="Message deleted."
                )
            else:
                raise Exception("Deletion failed")
        except Exception as e:
            logger.error(f"Error in DeleteMessage on replica: {e}")
            context.set_details("Error deleting message in replica")
            context.set_code(grpc.StatusCode.INTERNAL)
            return replica_pb2.WriteOperationResponse(
                success=False, message="Message deletion failed."
            )

    def GetReplicaID(self, request, context):
        """Return the replica's ID."""
        global REPLICA_ID
        return replica_pb2.GetReplicaIDResponse(replica_id=REPLICA_ID)


def serve(
    host="0.0.0.0", port="50052", db_file=None, replica_id=0, replica_addresses=None
):
    global REPLICA_ID, db, user_manager, ALL_REPLICA_ADDRESSES, LOCAL_ADDRESS
    REPLICA_ID = replica_id  # Save the replica ID.

    # Set local address
    LOCAL_ADDRESS = f"{host}:{port}"

    # (Re)initialize database and user_manager if needed.
    if db_file:
        db = Database(db_file)
        user_manager = UserManager(db_file)

    # Store the list of all replicas including their IP addresses
    if replica_addresses:
        ALL_REPLICA_ADDRESSES = replica_addresses
    else:
        ALL_REPLICA_ADDRESSES = [
            "localhost:50052",
            "localhost:50053",
        ]  # Default for local testing

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    replica_pb2_grpc.add_ReplicaServiceServicer_to_server(
        ReplicaServiceServicer(), server
    )
    server_address = f"{host}:{port}"
    server.add_insecure_port(server_address)
    logger.info(
        f"Replica server (ID={REPLICA_ID}) running on {server_address} with DB file {db.db_file}..."
    )

    election_manager = ElectionManager(
        replica_addresses=ALL_REPLICA_ADDRESSES,
        local_replica_id=REPLICA_ID,
    )
    # Start a background thread to monitor the leader.
    election_thread = threading.Thread(
        target=monitor_leader, args=(election_manager,), daemon=True
    )
    election_thread.start()
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the replica server")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host IP address to bind to"
    )
    parser.add_argument(
        "--port", type=str, default="50052", help="Port to run the replica on"
    )
    parser.add_argument(
        "--db-file",
        type=str,
        default=None,
        help="Database file path (defaults to env var DB_FILE or replica_chat_app.db)",
    )
    parser.add_argument(
        "--replica-id",
        type=int,
        default=0,
        help="Unique replica ID (e.g., 1, 2, 3, etc.)",
    )
    args = parser.parse_args()
    serve(
        host=args.host, port=args.port, db_file=args.db_file, replica_id=args.replica_id
    )
