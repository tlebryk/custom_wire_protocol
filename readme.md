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

The server will be listening on `0.0.0.0:8000` for incoming connections by default.

You can add additional command line flags to specify the address/port and whether to measure packet size. See server.py for more information. 


### Launching the Frontend

To launch the chat application with a graphical interface, run:

```bash
python src/frontend.py

```

The frontend uses Tkinter to provide a GUI for chat registration, login, and message handling. It connects to the backend server for real-time communication. 
The client by default looks for a server on `0.0.0.0:8000`, but you can specify the host, port and whether to track package size using command line flags. For instance: 



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

https://docs.google.com/document/d/1JtPzRj3rhguNx7oXOzPTn3823a7jsuBHUxpW0L8DIa0/edit?usp=sharing
