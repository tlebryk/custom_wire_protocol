# Custom Wire Protocol Chat Application

This repository contains a basic TCP server, a graphical client interface, and protocol testing functionality. Follow the instructions below to set up and run the project.

## Prerequisites

- [Python 3.10](https://www.python.org/downloads/) or higher
- No additional libraries beyond standard libraries for running the application.
-  To test the application, install pytest (pip install pytest).

## Installation

1. **Clone the repository.**
2. **Navigate to the project root directory.**
3. **Create and activate a virtual environment (optional but recommended):**

```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
```

### File Structure

```plaintext
src/
├── server.py          # Main server ensuring TCP connections for WebSocket communication.
├── handlers.py        # Routing to process received requests for the server.
├── users.py           # Extra password & account handling. 
├── database.py        # Persistent storage for users and messages.
├── frontend.py        # GUI application using Tkinter; supports chat functionality.
├── client.py          # Frontend WebSocket client.
├── utils.py           # Utility functions for sending data over the wire.
└── custom_protocol.py # Handles encoding & decoding with custom protocol.

```

## Running the Application

### Starting the Backend Server

Run the following command to start the backend server:

```bash
python src/server.py

```

The server will be listening on `0.0.0.0:8000` for incoming connections.

### Launching the Frontend

To launch the chat application with a graphical interface, run:

```bash
python src/frontend.py

```

The frontend uses Tkinter to provide a GUI for chat registration, login, and message handling. It connects to the backend server for real-time communication.

## Testing 
To test this code, run pytest from the src directory.

Example command: 
`python -m pytest tests/ -s -vv `

Optionally, you can specify where your config file is by prefixing your pytest command with `PROTOCOL_FILE="./configs/protocol.json" pytest ...`, but the default location is `src/configs/protocol.json`. This is helpful if you need to run the tests from the root directory or elsewhere in the project. 

### Protocol Modes

The project supports two modes for testing protocols:

#### JSON Mode

Set the environment variable to `json` to run using JSON:

```bash
export MODE='json'

```

#### Custom Protocol Mode

Set the environment variable to `custom` to run using the custom protocol:

```bash
export MODE='custom'

```

_If the `MODE` variable is not specified, the frontend will try to determine it from the system’s environment variables and default to JSON._

Performance varies based on the message being sent, but we found a 29% reduction in size of data transfered over the wire using the custom protocol compared to json with the following simple packet: 
```json
{
   "action": "login",
   "username": "a",
   "password": "a"
}
```

## Running on Multiple Devices

You can run the application on multiple machines. Follow these steps:

### Prerequisites

-   **Python 3** must be installed on all computers.
-   All computers should be on the **same Wi-Fi** or **LAN network**.
-   If connecting over the **internet**, ensure that port forwarding is configured.

### 1. Start the Server

Choose one computer to act as the **server**. This computer will run the WebSocket server and handle multiple client connections.

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
    

#### Step 2: Update `server.py` with the Server’s IP

Modify your HOST environment variable with your IP address. 

```bash
export HOST='172.11.11.1'
```

### 2. Connect Clients from Other Computers

Each client computer must connect to the server using its **local IP address**.

#### Step 1: Update `client.py` with the Server’s IP

On each **client computer**, modify the connection setup in `client.py` to connect to the server's IP:

```bash
export HOST='172.11.11.1'
```
#### Step 2: Run the Client

On each **client computer**, run:

```bash
python client.py

```
_Note: The server computer can also act as a client, and multiple clients can connect to the same server concurrently._

## Engineering notebook: 

https://docs.google.com/document/d/1JtPzRj3rhguNx7oXOzPTn3823a7jsuBHUxpW0L8DIa0/edit?usp=sharing
