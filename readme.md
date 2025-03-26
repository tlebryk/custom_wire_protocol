# gRPC Wire Protocol Chat Application

This repository contains a basic server, a graphical client interface, and to create a messaging service using gRPC. 

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
├── server.py               # Main server ensuring TCP connections for WebSocket communication.
├── users.py                # Extra password & account handling. 
├── database.py             # Persistent storage for users and messages.
├── frontend.py             # GUI application using Tkinter; supports chat functionality.
├── client.py               # Frontend gRPC client.
├── protocols_pb2_grpc.py   # Contains gRPC service definitions.
├── protocols_pb2.py        # Contains the serialized message structures.

```

## Running the Application

### Running the Backend Server

#### Option 1 (recommended): docker compose

```bash
# cd src
docker-compose up --build -d    
```
docker-compose
To test killing and individual service

```bash
# Kill a specific replica
docker-compose stop replica1
docker-compose rm -f replica1

# Kill the server
docker-compose stop server
docker-compose rm -f server

# restart the service (not functional right now)
docker-compose up -d --no-deps --build replica1

# to gracefully kill the entire backend
docker-compose down
```

#### Option 2: individual docker containers 
```bash
docker build -t chat-server src
docker run -d --name chat-server -p 50051:50051 -e DB_FILE=/data/chat_app.db -v $(pwd)/data/server:/data chat-app python server.py --port 50051 --replicas replica1:50052,replica2:50053
docker run -d --name chat-replica1 -p 50052:50052 -e DB_FILE=/data/replica1_chat_app1.db -v $(pwd)/data/replica1:/data chat-app python replica_server.py --port 50052 --replica-id 1
docker run -d --name chat-replica2 -p 50053:50053 -e DB_FILE=/data/replica2_chat_app2.db -v $(pwd)/data/replica2:/data chat-app python replica_server.py --port 50053 --replica-id 2
```

#### Option 3: running scripts
Run the following command to start the backend server:

```bash
# Then start the main server, using localhost for replica addresses
python src/load_balancer.py --lb_host 0.0.0.0 --lb_port 50051 --replica_endpoints localhost:50052,localhost:50053
python src/server.py --port 50051 --replicas localhost:50052,localhost:50053
# Start the replica servers first
python src/replica_server.py --port 50052 --db-file replica1_chat_app1.db --replica-id 1  --replicas localhost:50052,localhost:50053
python src/replica_server.py --port 50053 --db-file replica1_chat_app2.db --replica-id 2 --replicas localhost:50052,localhost:50053
# can add other replicas if needed

```


### Launching the Frontend

To launch the chat application with a graphical interface, run:

```bash
python src/frontend.py

```

The frontend uses Tkinter to provide a GUI for chat registration, login, and message handling. It connects to the backend server for real-time communication. 

### Compiling `.proto` Files into Python Code

To generate Python code from a Protocol Buffers (`.proto`) file, use the `protoc` compiler. Ensure you have the Protocol Buffers compiler installed. Run the following command from the root directory of your project:

```bash
python -m grpc_tools.protoc -I=src/configs --python_out=src --grpc_python_out=src src/configs/protocols.proto
python -m grpc_tools.protoc -I=src/configs --python_out=src --grpc_python_out=src src/configs/replica.proto
```
This will generate two files:


Ensure the generated files are placed in the correct src/ directory for use in your application.

## Testing 
To test this code, run pytest from the src directory.

Example command: 
`python -m pytest tests/ -s -vv --cov=./`

Optionally, you can specify where your config file is by prefixing your pytest command with `PROTOCOL_FILE="./configs/protocol.json" pytest ...`, but the default location is `src/configs/protocol.json`. This is helpful if you need to run the tests from the root directory or elsewhere in the project. 

## Running on Multiple Devices

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
    

#### Step 2: Run `server.py` with the Server’s IP

Run server specifying your address. Technically, this behavior should be enabled by default but specifying the IP address and port explicitly makes it clear. 

```bash
python src/server.py --host 172.11.11.1 --port 50051 --intercept
```

#### Step 3: Run `client.py` with the Server’s IP specified

On each **client computer**, run:

```bash 
python src/frontend.py --host 172.11.11.1 --port 50051 --intercept
```
Where 172.11.11.1 is the server's IP address. 

## Engineering notebook: 

https://docs.google.com/document/d/1uck1DvlR-E-yDYn41MySBpTcRAgNvV6-UusJmBGb9u4/edit?usp=sharing



python src/load_balancer.py --lb_host 0.0.0.0 --lb_port 50050 --replica_endpoints localhost:50052,localhost:50053,localhost:50056
python src/load_balancer.py --lb_host 0.0.0.0 --lb_port 50054 --replica_endpoints localhost:50052,localhost:50053,localhost:50056
python src/load_balancer.py --lb_host 0.0.0.0 --lb_port 50055 --replica_endpoints localhost:50052,localhost:50053,localhost:50056

python src/replica_server.py --port 50052 --db-file replica1_chat_app1.db --replica-id 1 --replicas localhost:50052,localhost:50053,localhost:50056
python src/replica_server.py --port 50053 --db-file replica1_chat_app2.db --replica-id 2 --replicas localhost:50052,localhost:50053,localhost:50056
python src/replica_server.py --port 50056 --db-file replica1_chat_app3.db --replica-id 3 --replicas localhost:50052,localhost:50053,localhost:50056

python src/frontend.py --lb_addresses localhost:50050,localhost:50054,localhost:50055
