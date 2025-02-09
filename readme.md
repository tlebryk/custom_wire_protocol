

- python 3.10 
- run `python backend/server.py` to serve the backend. 
- in the frontend directory, run `python3 -m http.server 8080` to serve the frontend.


API specs for actions 
- unread_messages
    - Backend call stack: send_unread_messages <- handle_login
    - Frontend call stack: handleUnreadMessages -> appendUnreadMessage
- recent_messages
    - Backend call stack: send_recent_messages <- handle_login 
    - Frontend call stack: handleRecentMessages -> appendRecentMessage
- login
    - Backend call stack: handle_login <- sendLogin
    - Frontend call stack: handleLogin -> unhide+auth=true
- register
    - Backend call stack:
    - Frontend call stack:
- send_message
    - Backend call stack:
    - Frontend call stack:
- mark_as_read
    - Backend call stack:
    - Frontend call stack:

TODO: typescript port

