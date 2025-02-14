
# App Backend

This repository contains the backend components for the App project. It provides a basic TCP server, a graphical client interface, and protocol testing functionality. Please follow the instructions below to set up and run this project.

## Prerequisites

- [Python 3.10](https://www.python.org/downloads/) or higher

## Installation

1. Clone the repository.
2. Navigate to the project root directory.
3. Create and activate a virtual environment (optional but recommended):

   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows use: venv\Scripts\activatepip install -e .

src/
```
├── server.py           Main server ensuring TCP connections for WebSocket communication.
├── handlers.py         Routing to process received request for server
├── database.py         Perisistent storage for users and messages 
├── frontend.py         GUI application using Tkinter; supports chat functionality.
├── client.py           frontend websocket .
├── utils.py            utility fns for sending data over wire
├── custom_protocol.py  Handles encoding & decoding with custom protocol
```



# Running the Application
## Starting the Backend Server
To start the backend server, run:

python src/server.py

The server will be listening on 0.0.0.0:8000 for incoming connections.

Launching the Frontend
To launch the frontend chat application, run:

python src/frontend.py

The frontend uses Tkinter to provide a GUI for chat registration, login, and message handling. It connects to the backend server for real-time communication.

## Protocol Modes
The project supports two modes for testing protocols:

### JSON Mode
Set the environment variable to json to run using JSON.
export MODE='json'
Copy
Insert

### Custom Protocol Mode
Set the environment variable to custom to run using custom protocols implemented in the project.
export MODE='custom'

If the MODE variable is not specified, the frontend will try to determine it from the system’s environment variables and use json.
