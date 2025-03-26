# replica_server.py
import os
import argparse
from concurrent import futures
import sys
import grpc
import logging
import importlib
import threading
import time
import socket

import replica_pb2
import replica_pb2_grpc
from database import Database  # Import the Database class
from users import UserManager  # Import the UserManager class

from election_manager import ElectionManager
from logger import setup_logger

logger = setup_logger("server")

# Global variables
REPLICA_ID = None
CURRENT_LEADER_ADDRESS = None  # Full address like "10.250.164.247:50051"
SERVER = None  # Global server instance
RUNNING_MODE = "replica"  # Can be "replica" or "leader"
HEARTBEAT_THREAD = None  # Global heartbeat thread reference
LEADER_PORT = "50051"  # Default leader port, can be overridden
EXTERNAL_HOST = None  # Store external hostname/IP

# Set the replica's DB file using the environment variable (or a default).
replica_db_file = os.environ.get("DB_FILE", "replica_chat_app.db")
# Create a Database instance for the replica.
db = Database(replica_db_file)
# Create a UserManager instance for user operations
user_manager = UserManager(replica_db_file)

# Global variable to track heartbeat status
LAST_HEARTBEAT_TIME = time.time()
LEADER_TIMEOUT_SECS = 5

# Configuration for replica and leader
ALL_REPLICA_ADDRESSES = []
LOCAL_ADDRESS = None
LEADER_ADDRESS = None  # Track the leader's address when we become leader
SHOULD_KEEP_RUNNING = True  # Control flag for main loop

def send_heartbeats(replica_addresses):
    """
    Periodically send heartbeats to all replicas.
    """
    global RUNNING_MODE, LEADER_ADDRESS
    
    logger.info(f"Starting heartbeat thread. Sending to replicas: {replica_addresses}")
    
    # Keep sending heartbeats as long as we're in leader mode
    while RUNNING_MODE == "leader" and SHOULD_KEEP_RUNNING:
        for replica_addr in replica_addresses:
            # Skip self - both the replica address and the leader address
            if replica_addr == LOCAL_ADDRESS or replica_addr == LEADER_ADDRESS:
                continue
                
            channel = grpc.insecure_channel(replica_addr)
            try:
                # Wait up to 2 seconds for the channel to be ready
                grpc.channel_ready_future(channel).result(timeout=2.0)
                stub = replica_pb2_grpc.ReplicaServiceStub(channel)
                
                # Send the full leader address so replicas know where to find us
                # This is critical for client redirection
                request = replica_pb2.HeartbeatRequest(leader_id=LEADER_ADDRESS)
                
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
    
    logger.info("Heartbeat thread exiting")


class ReplicaServiceServicer(replica_pb2_grpc.ReplicaServiceServicer):
    """
    Implementation of the replica service.
    """

    def GetLeader(self, request, context):
        """
        Return the current leader's address to clients for redirection.
        This is a critical method for leader discovery by clients.
        """
        global CURRENT_LEADER_ADDRESS
        
        logger.info(f"GetLeader called, current leader is: {CURRENT_LEADER_ADDRESS}")
        
        if CURRENT_LEADER_ADDRESS:
            # If we're in leader mode, return our own address
            if RUNNING_MODE == "leader":
                logger.info(f"Returning our own leader address: {LEADER_ADDRESS}")
                return replica_pb2.GetLeaderResponse(leader_address=LEADER_ADDRESS)
            
            # Otherwise return the stored leader address
            return replica_pb2.GetLeaderResponse(leader_address=CURRENT_LEADER_ADDRESS)
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Leader not found")
            return replica_pb2.GetLeaderResponse()

    def Heartbeat(self, request, context):
        """
        Called by the leader to indicate it's alive.
        Store the leader's address for future client redirection.
        """
        global LAST_HEARTBEAT_TIME, CURRENT_LEADER_ADDRESS
        
        LAST_HEARTBEAT_TIME = time.time()  # Update global variable
        
        # The leader_id field now contains the full address
        logger.info(f"Heartbeat received from leader at {request.leader_id}")
        
        # Store the leader's address for future client redirection
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


def get_leader_port():
    """
    Determine what port to use for the leader.
    If a current leader exists, use its port, otherwise use the default.
    """
    global CURRENT_LEADER_ADDRESS, LEADER_PORT
    
    if CURRENT_LEADER_ADDRESS:
        # Try to extract port from the current leader address
        try:
            if ':' in CURRENT_LEADER_ADDRESS:
                port = CURRENT_LEADER_ADDRESS.split(':')[1]
                logger.info(f"Using previous leader's port: {port}")
                return port
        except Exception as e:
            logger.warning(f"Failed to extract port from leader address: {e}")
    
    # Default to standard leader port
    logger.info(f"Using default leader port: {LEADER_PORT}")
    return LEADER_PORT


def transition_to_leader_mode(replica_addresses):
    """
    Transition to leader mode by starting a new server instance on the leader port
    without stopping the current replica instance.
    """
    global RUNNING_MODE, HEARTBEAT_THREAD, LEADER_ADDRESS, EXTERNAL_HOST
    
    logger.info("Transitioning to leader mode")
    
    try:
        # Import the real MessagingServiceServicer from server.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        server_module = importlib.import_module("server")
        
        # Get the actual service implementation and protocol
        MessagingServiceServicer = server_module.MessagingServiceServicer
        protocols_pb2_grpc = importlib.import_module("protocols_pb2_grpc")
        
        # Create a new server for leader services
        leader_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        
        # Initialize the real MessagingServiceServicer
        # Convert replica_addresses to list if it's a string
        if isinstance(replica_addresses, str):
            replica_addrs_list = replica_addresses.split(",")
        else:
            replica_addrs_list = replica_addresses
            
        logger.info(f"Creating MessagingServiceServicer with replicas: {replica_addrs_list}")
        
        # Initialize with the same DB file we're currently using
        messaging_service = MessagingServiceServicer(
            db_file=replica_db_file,
            replica_addresses=replica_addrs_list
        )
        
        # Add service to server
        protocols_pb2_grpc.add_MessagingServiceServicer_to_server(
            messaging_service, leader_server
        )
        
        # Determine what port to use for the leader
        leader_port = get_leader_port()
        
        # IMPORTANT: Use the actual external host that clients can connect to
        leader_host = EXTERNAL_HOST
        
        # Set up the leader address with the EXTERNAL host and port
        leader_address = f"{leader_host}:{leader_port}"
        
        # Bind server to all interfaces (0.0.0.0) but advertise external IP
        bind_address = f"0.0.0.0:{leader_port}"
        leader_server.add_insecure_port(bind_address)
        
        # Store the leader address for reference and heartbeating
        # This is the address clients will use to connect
        LEADER_ADDRESS = leader_address
        
        # Set ourselves as leader for GetLeader calls
        CURRENT_LEADER_ADDRESS = leader_address
        
        logger.info(f"Starting leader server binding to {bind_address}")
        logger.info(f"Advertising leader address as {leader_address}")
        
        leader_server.start()
        
        # Update the mode to leader
        RUNNING_MODE = "leader"
        
        # Start heartbeat thread
        HEARTBEAT_THREAD = threading.Thread(
            target=send_heartbeats,
            args=(replica_addrs_list,),
            daemon=True
        )
        HEARTBEAT_THREAD.start()
        
        logger.info("Successfully transitioned to leader mode")
        
        # Wait for termination
        leader_server.wait_for_termination()
        return True
        
    except Exception as e:
        logger.error(f"Error transitioning to leader mode: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def monitor_leader(election_manager, check_interval=10):
    """
    Runs in the background to check if the leader is alive.
    If we haven't received a heartbeat for too long, we start an election.
    """
    global LAST_HEARTBEAT_TIME, RUNNING_MODE
    
    while RUNNING_MODE == "replica" and SHOULD_KEEP_RUNNING:
        elapsed = time.time() - LAST_HEARTBEAT_TIME
        if elapsed > LEADER_TIMEOUT_SECS:
            logger.warning("No heartbeat from leader. Starting leader election...")
            
            # Check if this replica should become leader
            if election_manager.elect_leader():
                logger.info("I have been elected as the new leader!")
                
                # Start leader transition in a separate thread
                leader_thread = threading.Thread(
                    target=transition_to_leader_mode,
                    args=(ALL_REPLICA_ADDRESSES,),
                    daemon=True
                )
                leader_thread.start()
                
                # Exit the monitor loop as we're transitioning to leader
                break
            else:
                logger.info("Leader election check: still not leader.")
                
            # Reset heartbeat time to avoid continuous elections
            LAST_HEARTBEAT_TIME = time.time()
            
        time.sleep(check_interval)
    
    logger.info("Monitor thread exiting")


def serve(
    host="0.0.0.0", port="50052", db_file=None, replica_id=0, replica_addresses=None,
    leader_port=None, external_host=None
):
    global REPLICA_ID, db, user_manager, ALL_REPLICA_ADDRESSES, LOCAL_ADDRESS, SERVER
    global RUNNING_MODE, SHOULD_KEEP_RUNNING, replica_db_file, LEADER_PORT, EXTERNAL_HOST
    
    # Initialize globals
    REPLICA_ID = replica_id
    RUNNING_MODE = "replica"
    SHOULD_KEEP_RUNNING = True
    LOCAL_ADDRESS = f"{host}:{port}"
    
    # Store leader port if provided
    if leader_port:
        LEADER_PORT = leader_port
    
    # Store the external host - this is how clients will find us
    # This is critical for proper client connectivity
    if external_host:
        EXTERNAL_HOST = external_host
    else:
        # Use the provided host if it's not 0.0.0.0
        if host != "0.0.0.0":
            EXTERNAL_HOST = host
        else:
            # Try to get actual hostname/IP
            try:
                # Get primary non-loopback IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Connect to any external server (doesn't actually send anything)
                s.connect(("8.8.8.8", 80))
                EXTERNAL_HOST = s.getsockname()[0]
                s.close()
            except:
                # Fallback to hostname
                EXTERNAL_HOST = socket.gethostname()
    
    logger.info(f"External host for client connections: {EXTERNAL_HOST}")
    
    # Store the DB file path
    if db_file:
        replica_db_file = db_file
        db = Database(db_file)
        user_manager = UserManager(db_file)
    
    # Store replica addresses
    if replica_addresses:
        if isinstance(replica_addresses, str):
            ALL_REPLICA_ADDRESSES = replica_addresses.split(",")
        else:
            ALL_REPLICA_ADDRESSES = replica_addresses
    else:
        ALL_REPLICA_ADDRESSES = ["localhost:50052", "localhost:50053"]
    
    # Create and start the replica server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    replica_pb2_grpc.add_ReplicaServiceServicer_to_server(
        ReplicaServiceServicer(), server
    )
    server_address = f"{host}:{port}"
    server.add_insecure_port(server_address)
    
    # Store server in global variable
    SERVER = server
    
    logger.info(f"Replica server (ID={REPLICA_ID}) running on {server_address} with DB file {db.db_file}...")
    
    # Initialize election manager
    election_manager = ElectionManager(
        replica_addresses=ALL_REPLICA_ADDRESSES,
        local_replica_id=REPLICA_ID,
    )
    
    # Start leader monitor thread
    monitor_thread = threading.Thread(
        target=monitor_leader,
        args=(election_manager,),
        daemon=True
    )
    monitor_thread.start()
    
    # Start the server
    server.start()
    
    try:
        # Keep the main thread running
        while SHOULD_KEEP_RUNNING:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down gracefully...")
        SHOULD_KEEP_RUNNING = False
        
        # Stop the server
        server.stop(1)
        
        # Wait for heartbeat thread to finish if it exists
        if HEARTBEAT_THREAD and HEARTBEAT_THREAD.is_alive():
            HEARTBEAT_THREAD.join(timeout=3)
    except Exception as e:
        logger.error(f"Error during server execution: {e}")
        server.stop(0)


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
    parser.add_argument(
        "--replicas",
        type=str,
        default="localhost:50052",
        help="Comma-separated list of replica addresses",
    )
    parser.add_argument(
        "--leader-port",
        type=str,
        default="50051",
        help="Default port for leader (used if no current leader exists)",
    )
    parser.add_argument(
        "--external-host",
        type=str,
        default=None,
        help="External hostname/IP to advertise to clients (defaults to auto-detected)",
    )
    
    args = parser.parse_args()
    replica_addresses = args.replicas.split(",") if args.replicas else ["localhost:50052"]
    
    try:
        serve(
            host=args.host,
            port=args.port,
            db_file=args.db_file,
            replica_id=args.replica_id,
            replica_addresses=replica_addresses,
            leader_port=args.leader_port,
            external_host=args.external_host
        )
    except KeyboardInterrupt:
        logger.info("Exiting due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")