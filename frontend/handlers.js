// handlers.js


export function handleLogin(data) {
    if (data.status === "success" && data.message && data.message.includes("Login successful")) {
        window.isAuthenticated = true;
        console.log("Login successful");
        // Hide authentication and chat interface
        document.getElementById('authBox').classList.add('hidden');
        document.getElementById('chatBox').classList.remove('hidden');
        document.getElementById('deleteAccountContainer').classList.remove('hidden');
        document.getElementById('messages-container').classList.remove('hidden');
        document.getElementById('nNewMessages').classList.remove('hidden');
    } else {
        // Handle unsuccessful login attempts if necessary
        displayError(data.message || "Login failed.");
    }
}

export function handleSentMessage(data) {
    // Assuming the server sends back confirmation or details about the sent message
    appendRecentMessage(data.from, data.message, "recent", data.timestamp, data.id);
}

export function handleReceiveMessage(data) {
    // Assuming the server sends back confirmation or details about the sent message
    appendUnreadMessage(data.from, data.message, "unread", data.timestamp, data.id);
}

export function handleErrorMessage(data) {
    // Check for duplicate account message, assuming the error message contains "already"
    if (data.message.toLowerCase().includes("already")) {
        // For duplicate registration error, toggle to login and pre-populate the login username field
        document.getElementById('loginUsername').value = window.lastRegUsername;
        // Switch forms if registration form is currently visible
        if (!document.getElementById('loginForm').classList.contains('hidden')) {
            // Already in login form, do nothing extra here
        } else {
            // Toggle to login form
            window.toggleForms();
            console.log("Toggle to login form");
        }
        displayError("Account already exists. Please enter your password to login.");
    } else {
        displayError(data.message);
    }
}

export function handleDefaultMessage(data) {
    console.log("Unhandled message type:", data);
}
export function handleRecentMessages(data) {
    data.messages.forEach(msg => {
        appendRecentMessage(msg.from, msg.message, "recent", msg.timestamp, data.id);
    });
}


export function handleUnreadMessages(data) {
    data.messages.forEach(msg => {
        appendUnreadMessage(msg.from, msg.message, "unread", msg.timestamp, msg.id);
    });
}

// Handler for default action
export function handleDefault(data) {
    // log error 
    console.error("Unhandled message type:", data);
}



export function appendRecentMessage(sender, text, cssClass = 'recent', timestamp = null, id = null) {
    const containerId = 'recent-messages';

    const messagesDiv = document.getElementById(containerId);
    if (!messagesDiv) {
        console.error(`Messages element ${containerId} not found!`);
        return;
    }

    const newMessage = document.createElement('div');
    newMessage.classList.add('message', cssClass);

    let timeText = '';
    if (timestamp) {
        const date = new Date(timestamp);
        timeText = `<span class="timestamp">[${date.toLocaleTimeString()}]</span> `;
    }
    newMessage.innerHTML = `<strong>${sender}:</strong> ${timeText}${text}`;
    addDeleteButton(newMessage);
    messagesDiv.appendChild(newMessage);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function addDeleteButton(messageDiv) {
    const deleteButton = document.createElement('button');
    deleteButton.textContent = 'Delete';
    deleteButton.addEventListener('click', () => {
        // TODO implement delete message in backend too 
        messageDiv.remove();
    });
    messageDiv.appendChild(deleteButton);
}

export function appendUnreadMessage(sender, text, cssClass = 'unread', timestamp = null, id = null) {
    const containerId = 'unread-messages';

    const messagesDiv = document.getElementById(containerId);
    if (!messagesDiv) {
        console.error(`Messages element ${containerId} not found!`);
        return;
    }

    const newMessage = document.createElement('div');
    newMessage.classList.add('message', cssClass);
    newMessage.id = id;

    let timeText = '';
    if (timestamp) {
        const date = new Date(timestamp);
        timeText = `<span class="timestamp">[${date.toLocaleTimeString()}]</span> `;
    }
    addDeleteButton(newMessage);
    const readButton = document.createElement('button');
    // give class markasreadbutton 
    readButton.classList.add('markasreadbutton');
    readButton.textContent = 'Mark as read';

    readButton.addEventListener('click', () => {
        // pass button id as well 
        window.readMessages([id]);
        // move new message to recent messages 
        const newMessage = document.getElementById(id);
        newMessage.remove();
        const recentMessages = document.getElementById('recent-messages');
        recentMessages.appendChild(newMessage);
        // remove the mark as read button from newMessage
        newMessage.removeChild(readButton);


    });
    newMessage.innerHTML = `<strong>${sender}:</strong> ${timeText}&nbsp;&nbsp;${text}&nbsp;&nbsp;`;
    // newMessage.appendChild(deleteButton);
    newMessage.appendChild(readButton);
    messagesDiv.appendChild(newMessage);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

