# gRPC Wire Protocol Chat Application

This repository contains code for a simple messaging service using gRPC. This includes a graphical client interface/client, load balancer, and persistent backend system. A frontend client connects to a load balancer who tracks a "leader" server. The leader server has replicas it propogates "writes" to. Should the replicas detect leader failure, they initiate leader election and one assumes the new leadership role. The client only connects with the load balancer. Should the load balancer fail, a backup load balancer takes its place and connects with the client and begins routing to the leader.

## Installation


1. **Clone the repository.**
2. **Navigate to the project root directory.**
3. **Create and activate a virtual environment (optional but recommended):**

### Prerequisites

- [Python 3.10](https://www.python.org/downloads/) or higher

```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
```

### File Structure

```plaintext
src/
├── server.py                       # Main server ensuring TCP connections for WebSocket communication
├── replica_server.py               # Server implementation for replicas in the distributed system
├── users.py                        # Extra password & account handling
├── database.py                     # Persistent storage for users and messages
├── frontend.py                     # GUI application using Tkinter; supports chat functionality
├── client.py                       # Frontend gRPC client
├── load_balancer.py                # Distributes client requests across multiple server replicas
├── replication_manager.py          # Manages data replication between primary and replica servers
├── election_manager.py             # Handles leader election among replicas when primary fails
├── messaging_service_servicer.py   # Implements the gRPC service for messaging functionality
├── server_intercepter.py           # Intercepts gRPC calls for additional processing
├── logger.py                       # Logging utility for the application
├── clearport.py                    # Utility script to clear ports that might be in use
├── protocols_pb2_grpc.py           # Contains gRPC service definitions (generated)
├── protocols_pb2.py                # Contains the serialized message structures (generated)
├── replica_pb2_grpc.py             # Contains gRPC service definitions for replicas (generated)
├── replica_pb2.py                  # Contains the serialized message structures for replicas (generated)
├── configs/                        # Directory containing configuration files
│   ├── protocols.proto             # Protocol Buffer definition for main service
│   └── replica.proto               # Protocol Buffer definition for replica communication

```

## Running the Application

You can run the application on multiple machines. Follow these steps:

### Prerequisites

-   **Python 3** must be installed on all computers.
-   All computers should be on the **same Wi-Fi** or **LAN network**.
-   If connecting over the **internet**, ensure that port forwarding is configured.


#### Step 1: Find the Server’s Local IP Address

On the **server computer**, open **Command Prompt (Windows)** or **Terminal (Mac/Linux)** and run:

-   **Windows:**
    
    ```bash
    ipconfig
    
    ```
    
    Look for the IPv4 Address under the active network.
    
-   **Mac/Linux:**
    
    ```bash
    ifconfig | grep "inet "
    
    ```
    
### Step 2: Running the Backend Server

Here's an example two machine set up to test two fault tolerance. Replace 10.111.111.111 and 10.222.22.222 with your two ip addresses as described below. For each line, run in a separate terminal. 

Machine 1
```bash
python src/load_balancer.py --lb_host 10.222.22.222 --lb_port 50055 --replica_endpoints 10.111.111.111:50052,10.111.111.111:50053,10.222.22.222:50056
python src/replica_server.py --port 50056 --db-file replica_chat_app3.db --replica-id 3 --replicas 10.111.111.111:50052,10.111.111.111:50053,10.222.22.222:50056 --external-host 10.222.22.222

```

Machine 2: 
```bash
python src/load_balancer.py --lb_host 10.111.111.111 --lb_port 50050 --replica_endpoints 10.111.111.111:50052,10.111.111.111:50053,10.222.22.222:50056
python src/load_balancer.py --lb_host 10.111.111.111 --lb_port 50054 --replica_endpoints 10.111.111.111:50052,10.111.111.111:50053,10.222.22.222:50056
python src/replica_server.py --port 50052 --db-file replica_chat_app1.db --replica-id 1 --replicas 10.111.111.111:50052,10.111.111.111:50053,10.222.22.222:50056 --external-host 10.111.111.111
python src/replica_server.py --port 50053 --db-file replica_chat_app2.db --replica-id 2 --replicas 10.111.111.111:50052,10.111.111.111:50053,10.222.22.222:50056 --external-host 10.111.111.111
```

### Step 3: Spin up the front end

Run the frontend on either machine like so:
```bash
python src/frontend.py --lb_addresses 10.111.111.111:50050,10.111.111.111:50054,10.222.22.222:50055
```

The frontend uses Tkinter to provide a GUI for chat registration, login, and message handling. It connects to the backend server for real-time communication. 

### Compiling `.proto` Files into Python Code

To generate Python code from a Protocol Buffers (`.proto`) file, use the `protoc` compiler. Ensure you have the Protocol Buffers compiler installed. Run the following command from the root directory of your project:

```bash
python -m grpc_tools.protoc -I=src/configs --python_out=src --grpc_python_out=src src/configs/protocols.proto
python -m grpc_tools.protoc -I=src/configs --python_out=src --grpc_python_out=src src/configs/replica.proto
```

## Testing 
To test this code, run pytest from the src directory.

Example command: 
`python -m pytest tests/ -s -vv --cov=./`

## Engineering notebook: 

https://docs.google.com/document/d/1XtN9PWlmSSK0f0TxztJz-o9uITRXeMGyJY-8FtfzTec/edit?usp=sharing

