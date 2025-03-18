# test_database_propagation.py
import subprocess
import os
import time
import sqlite3
import sys

import grpc
import protocols_pb2
import protocols_pb2_grpc


def launch_process(script, port, db_file):
    """Launch a server process with a given script, port, and database file."""
    env = os.environ.copy()
    if os.path.exists(db_file):
        os.remove(db_file)
    env["DB_FILE"] = db_file  # Each process uses its own DB file.
    return subprocess.Popen([sys.executable, script, "--port", str(port)], env=env)


def query_table(db_file, table_name):
    """Query all rows from a table in the specified SQLite database file."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    conn.close()
    return rows


def wait_for_table(db_file, table_name, timeout=15, interval=1):
    """
    Wait until the specified table exists in the given database file.
    If the table does not exist before timeout, raises an exception.
    """
    start_time = time.time()
    while True:
        try:
            rows = query_table(db_file, table_name)
            return rows
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                if time.time() - start_time > timeout:
                    raise Exception(
                        f"Table '{table_name}' not found in {db_file} after {timeout} seconds."
                    )
                time.sleep(interval)
            else:
                raise e


def print_section(title):
    """Print a section header for better test output readability."""
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)


def test_main():
    # Define database file paths
    os.makedirs("tests", exist_ok=True)
    leader_db = os.path.join("tests", "test_leader.db")
    replica_db = os.path.join("tests", "test_replica.db")

    # Remove any existing test database files
    for db in [leader_db, replica_db]:
        if os.path.exists(db):
            os.remove(db)

    # Launch the replica server on port 50052 using its own DB
    print("Starting replica server...")
    replica_proc = launch_process("replica_server.py", 50052, replica_db)

    # Launch the leader server on port 50051 using its own DB
    print("Starting leader server...")
    leader_proc = launch_process("server.py", 50051, leader_db)

    try:
        # Give the servers time to start up
        print("Waiting for servers to start...")
        time.sleep(5)

        # Create a gRPC channel and stub for the leader
        channel = grpc.insecure_channel("localhost:50051")
        stub = protocols_pb2_grpc.MessagingServiceStub(channel)

        # ============ Setup: Register test users ============
        print_section("SETUP: REGISTERING TEST USERS")
        test_users = ["alice", "bob"]
        for username in test_users:
            register_request = protocols_pb2.RegisterRequest(
                username=username, password="password123"
            )
            response = stub.Register(register_request)
            print(f"Registered user {username}: {response.status}")

        time.sleep(2)  # Wait for replication

        # Verify users were created in both databases
        leader_users = query_table(leader_db, "users")
        replica_users = query_table(replica_db, "users")

        print(f"Users in leader database: {len(leader_users)}")
        print(f"Users in replica database: {len(replica_users)}")

        if len(leader_users) == 2 and len(replica_users) == 2:
            print("User setup successful.")
        else:
            print("WARNING: Users may not have been properly created.")

        # ============ Test 1: Send Message Replication ============
        print_section("TEST 1: SEND MESSAGE REPLICATION")

        # We need to include sender in metadata for SendMessage
        metadata = [("sender", "alice")]
        send_request = protocols_pb2.SendMessageRequest(
            message="Hello, Bob! This is a test message.", receiver="bob"
        )
        send_response = stub.SendMessage(send_request, metadata=metadata)
        print(f"Send message response: {send_response.status}")

        time.sleep(2)  # Wait for replication

        # Query messages table in both databases
        leader_messages = query_table(leader_db, "messages")
        replica_messages = query_table(replica_db, "messages")

        print(f"Messages in leader database: {len(leader_messages)}")
        print(f"Messages in replica database: {len(replica_messages)}")

        # Print message details from leader
        if leader_messages:
            message_id = leader_messages[0][0]
            sender = leader_messages[0][1]
            receiver = leader_messages[0][2]
            content = leader_messages[0][3]
            print(
                f"Leader message: ID={message_id}, Sender={sender}, Receiver={receiver}, Content={content}"
            )

        # Check if message exists in both databases with the same content
        test1_passed = False
        if len(leader_messages) == 1 and len(replica_messages) == 1:
            leader_msg = leader_messages[0]
            replica_msg = replica_messages[0]

            if (
                leader_msg[1] == "alice"
                and leader_msg[2] == "bob"
                and leader_msg[3] == "Hello, Bob! This is a test message."
                and replica_msg[1] == "alice"
                and replica_msg[2] == "bob"
                and replica_msg[3] == "Hello, Bob! This is a test message."
            ):
                test1_passed = True
                message_id = leader_msg[0]  # Save message ID for later tests
                print(
                    f"TEST 1 PASSED: Message was replicated correctly to both databases."
                )
            else:
                print(
                    f"TEST 1 FAILED: Message content doesn't match between leader and replica."
                )
        else:
            print(f"TEST 1 FAILED: Expected 1 message in each database.")
            message_id = leader_messages[0][0] if leader_messages else None

        # ============ Test 2: Mark Messages as Read ============
        print_section("TEST 2: MARK MESSAGES AS READ")

        if message_id is not None:
            mark_read_request = protocols_pb2.MarkAsReadRequest(
                message_ids=[message_id]
            )
            mark_read_response = stub.MarkAsRead(mark_read_request)
            print(f"Mark as read response: {mark_read_response.status}")

            time.sleep(2)  # Wait for replication

            # Query messages table in both databases
            leader_messages = query_table(leader_db, "messages")
            replica_messages = query_table(replica_db, "messages")

            # Check read status in both databases
            # Assuming read_status is at index 5 (0-indexed)
            if (
                len(leader_messages) == 1
                and len(replica_messages) == 1
                and leader_messages[0][5] == 1
                and replica_messages[0][5] == 1
            ):
                print(f"TEST 2 PASSED: Message was marked as read in both databases.")
            else:
                leader_status = leader_messages[0][5] if leader_messages else "N/A"
                replica_status = replica_messages[0][5] if replica_messages else "N/A"
                print(
                    f"TEST 2 FAILED: Read status not updated correctly. Leader: {leader_status}, Replica: {replica_status}"
                )
        else:
            print("TEST 2 SKIPPED: No message ID available from previous test.")

        # ============ Test 3: Mark Messages Delivered ============
        print_section("TEST 3: MARK MESSAGES DELIVERED")

        # Send another message for this test
        metadata = [("sender", "bob")]
        send_request = protocols_pb2.SendMessageRequest(
            message="Hello Alice, this is a response!", receiver="alice"
        )
        stub.SendMessage(send_request, metadata=metadata)
        time.sleep(1)

        # Get unread messages for Alice which should mark them as delivered
        unread_request = protocols_pb2.GetUnreadMessagesRequest(username="alice")
        unread_response = stub.GetUnreadMessages(unread_request)
        print(f"Get unread messages response: {unread_response.status}")
        print(f"Number of unread messages: {len(unread_response.messages)}")

        time.sleep(2)  # Wait for replication

        # Query messages to check delivered status
        # Filter for messages to alice
        leader_messages = query_table(leader_db, "messages")
        replica_messages = query_table(replica_db, "messages")

        # Find the message from bob to alice
        leader_msg = next(
            (m for m in leader_messages if m[1] == "bob" and m[2] == "alice"), None
        )
        replica_msg = next(
            (m for m in replica_messages if m[1] == "bob" and m[2] == "alice"), None
        )

        if leader_msg and replica_msg:
            # Assuming delivered is at index 6 (0-indexed)
            if leader_msg[6] == 1 and replica_msg[6] == 1:
                print(
                    f"TEST 3 PASSED: Message was marked as delivered in both databases."
                )
            else:
                print(
                    f"TEST 3 FAILED: Delivered status not updated correctly. Leader: {leader_msg[6]}, Replica: {replica_msg[6]}"
                )
        else:
            print("TEST 3 FAILED: Could not find the message from bob to alice.")

        # ============ Test 4: Delete Message ============
        print_section("TEST 4: DELETE MESSAGE")

        if message_id is not None:
            # First check if we have the DeleteMessage method available
            try:
                delete_request_class = getattr(
                    protocols_pb2, "DeleteMessageRequest", None
                )
                if delete_request_class:
                    delete_request = delete_request_class(message_id=message_id)
                    delete_response = stub.DeleteMessage(delete_request)
                    print(f"Delete message response: {delete_response.message}")

                    time.sleep(2)  # Wait for replication

                    # Query to see if message was deleted
                    leader_messages = query_table(leader_db, "messages")
                    replica_messages = query_table(replica_db, "messages")

                    # Check if message with the ID is gone
                    leader_has_msg = any(
                        msg[0] == message_id for msg in leader_messages
                    )
                    replica_has_msg = any(
                        msg[0] == message_id for msg in replica_messages
                    )

                    if not leader_has_msg and not replica_has_msg:
                        print(
                            f"TEST 4 PASSED: Message was deleted from both databases."
                        )
                    else:
                        print(
                            f"TEST 4 FAILED: Message was not deleted correctly. Still in leader: {leader_has_msg}, Still in replica: {replica_has_msg}"
                        )
                else:
                    print(
                        "TEST 4 SKIPPED: DeleteMessageRequest not found in protocols_pb2."
                    )
            except (AttributeError, NotImplementedError) as e:
                print(f"TEST 4 SKIPPED: DeleteMessage method not implemented: {e}")
        else:
            print("TEST 4 SKIPPED: No message ID available from previous test.")

        # ============ Test 5: Update Unread Message Count ============
        print_section("TEST 5: UPDATE UNREAD MESSAGE COUNT")

        try:
            # Try to use UpdateUnreadMessageCount if available
            update_request_class = getattr(
                protocols_pb2, "UpdateUnreadMessageCountRequest", None
            )
            if update_request_class:
                update_request = update_request_class(username="bob", count=5)
                update_response = stub.UpdateUnreadMessageCount(update_request)
                print(f"Update unread count response: {update_response.message}")

                time.sleep(2)  # Wait for replication

                # Query users to check unread count
                leader_users = query_table(leader_db, "users")
                replica_users = query_table(replica_db, "users")

                # Find bob in each database
                leader_bob = next((u for u in leader_users if u[0] == "bob"), None)
                replica_bob = next((u for u in replica_users if u[0] == "bob"), None)

                if leader_bob and replica_bob:
                    # Assuming n_unread_messages is at index 2 (0-indexed)
                    if leader_bob[2] == 5 and replica_bob[2] == 5:
                        print(
                            f"TEST 5 PASSED: Unread count was updated in both databases."
                        )
                    else:
                        print(
                            f"TEST 5 FAILED: Unread count not updated correctly. Leader: {leader_bob[2]}, Replica: {replica_bob[2]}"
                        )
                else:
                    print("TEST 5 FAILED: Could not find bob in databases.")
            else:
                print(
                    "TEST 5 SKIPPED: UpdateUnreadMessageCountRequest not found in protocols_pb2."
                )
        except (AttributeError, NotImplementedError) as e:
            print(
                f"TEST 5 SKIPPED: UpdateUnreadMessageCount method not implemented: {e}"
            )

    except Exception as e:
        print(f"Test failed with error: {e}")
    finally:
        print("\nCleaning up...")
        # Terminate both processes
        leader_proc.terminate()
        replica_proc.terminate()
        leader_proc.wait()
        replica_proc.wait()
        print("Test completed.")


if __name__ == "__main__":
    test_main()
