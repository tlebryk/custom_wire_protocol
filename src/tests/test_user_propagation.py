# test_integration_propagation.py
import subprocess
import os
import time
import sqlite3

import grpc
import protocols_pb2
import protocols_pb2_grpc


def launch_process(script, port, db_file):
    """Launch a server process with a given script, port, and database file."""
    env = os.environ.copy()
    if os.path.exists(db_file):
        os.remove(db_file)
    env["DB_FILE"] = db_file  # Each process uses its own DB file.
    return subprocess.Popen(["python", script, "--port", str(port)], env=env)


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


def test_main():
    # Define database file paths.
    leader_db = os.path.join("tests", "test_leader.db")
    replica_db = os.path.join("tests", "test_replica.db")

    # Remove any existing test database files.
    for db in [leader_db, replica_db]:
        if os.path.exists(db):
            os.remove(db)

    # Launch the replica server on port 50052 using its own DB.
    replica_proc = launch_process("replica_server.py", 50052, replica_db)
    # Launch the leader server on port 50051 using its own DB.
    leader_proc = launch_process("server.py", 50051, leader_db)

    try:
        # Give the servers time to start up.
        time.sleep(5)

        # Create a gRPC channel and stub for the leader.
        channel = grpc.insecure_channel("localhost:50051")
        stub = protocols_pb2_grpc.MessagingServiceStub(channel)

        # ---- Test 1: Register user replication ----
        print("\nTesting Register user replication...")
        register_request = protocols_pb2.RegisterRequest(
            username="charlie", password="securepassword"
        )
        register_response = stub.Register(register_request)
        print("Leader Register response:", register_response)
        time.sleep(5)  # Wait for replication

        # Wait until the replica's 'users' table exists and then query it.
        try:
            replica_users = wait_for_table(replica_db, "users")
        except Exception as e:
            print(f"Error waiting for users table: {e}")
            replica_users = []

        leader_users = query_table(leader_db, "users")
        print("Users in leader database:", leader_users)
        print("Users in replica database:", replica_users)

        # Check if 'charlie' exists in both databases.
        leader_has_charlie = any(row[0] == "charlie" for row in leader_users)
        replica_has_charlie = any(row[0] == "charlie" for row in replica_users)
        if leader_has_charlie and replica_has_charlie:
            print(
                "Register user test passed: New user 'charlie' was replicated to both databases."
            )
        else:
            print(
                "Register user test failed: 'charlie' not found in one or both databases."
            )
        # ---- Test 2: Delete user replication ----
        print("\nTesting Delete user replication...")
        delete_request = protocols_pb2.DeleteAccountRequest(username="charlie")
        delete_response = stub.DeleteAccount(delete_request)
        print("Leader Delete response:", delete_response)
        time.sleep(5)  # Wait for replication

        # Wait until the replica's 'users' table exists and then query it.
        try:
            replica_users = wait_for_table(replica_db, "users")
        except Exception as e:
            print(f"Error waiting for users table: {e}")
            replica_users = []

        leader_users = query_table(leader_db, "users")
        print("Users in leader database:", leader_users)
        print("Users in replica database:", replica_users)

        # Check if 'charlie' is deleted from both databases.
        leader_has_charlie = any(row[0] == "charlie" for row in leader_users)
        replica_has_charlie = any(row[0] == "charlie" for row in replica_users)
        if not leader_has_charlie and not replica_has_charlie:
            print(
                "Delete user test passed: User 'charlie' was deleted from both databases."
            )
        else:
            print(
                "Delete user test failed: 'charlie' was not deleted from one or both databases."
            )
    finally:
        # Terminate both the leader and replica processes.
        leader_proc.terminate()
        replica_proc.terminate()
        leader_proc.wait()
        replica_proc.wait()


if __name__ == "__main__":
    test_main()
