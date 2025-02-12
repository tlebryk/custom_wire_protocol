

- python 3.10 
- run `python backend/server.py` to serve the backend. 
- frontend: `backend/frontend.py `
- To test protocols: 
- Set MODE="json" in the environment to run with json
    `export MODE='json'
- set MODE="custom" in environment to run with custom



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

   Directory Structure
backend/
├── server.py         # Main server ensuring TCP connections for WebSocket communication.
├── frontend.py       # GUI application using Tkinter; supports chat functionality.
├── client.py         # WebSocket client to establish and test backend communication.
├── pyproject.toml    # Project configuration and dependencies.
└── README.md         # This file.
Copy
Insert

Running the Application
Starting the Backend Server
To start the backend server, run:

python backend/server.py
Copy
Insert

The server will be listening on 0.0.0.0:8000 for incoming connections.

Launching the Frontend
To launch the frontend chat application, run:

python backend/frontend.py
Copy
Insert

The frontend uses Tkinter to provide a GUI for chat registration, login, and message handling. It connects to the backend server for real-time communication.

Protocol Modes
The project supports two modes for testing protocols:

JSON Mode
Set the environment variable to json to run using JSON.
export MODE='json'
Copy
Insert

Custom Protocol Mode
Set the environment variable to custom to run using custom protocols implemented in the project.
export MODE='custom'
Copy
Insert

If the MODE variable is not specified, the frontend will try to determine it from the system’s environment variables.

Logging
The project is configured to log essential events:

The backend server logs information to stdout.
The frontend logs events, including connection status and potential errors, with details on file location and line numbers.
Additional Information
For further customization or debugging, review the server and client code to understand the internal handling of WebSocket connections and protocol encoding/decoding.
This backend is built using built-in libraries and custom modules tailored for real-time messaging and protocol testing.
Contributions
Contributions are welcome. Please ensure that any changes remain consistent with the existing code patterns and project configuration.

License
MIT License

Enjoy using the App backend!