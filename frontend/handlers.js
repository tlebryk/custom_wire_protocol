// handlers.js



export function handleLogin(data) {
    if (data.status === "success" && data.message && data.message.includes("Login successful")) {
        window.isAuthenticated = true;
        console.log("Login successful");
        // Hide authentication and show chat box
        document.getElementById('authBox').classList.add('hidden');
        document.getElementById('chatBox').classList.remove('hidden');
        document.getElementById('deleteAccountContainer').classList.remove('hidden');
        document.getElementById('messages-container').classList.remove('hidden');
    } else {
        // Handle unsuccessful login attempts if necessary
        displayError(data.message || "Login failed.");
    }
}

export function handleSendMessage(data) {
    // Assuming the server sends back confirmation or details about the sent message
    appendUnreadMessage(data.from, data.message, "unread", data.timestamp);
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
            // window.toggleForms();
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
        appendRecentMessage(msg.from, msg.message, "recent", msg.timestamp);
    });
}

// Handler for recent_messages action
// Handler for unread_messages action
export function handleUnreadMessages(data) {
    data.messages.forEach(msg => {
        appendUnreadMessage(msg.from, msg.message, "unread", msg.timestamp);
    });
}

// Handler for default action
export function handleDefault(data) {
    console.log("Unhandled message type:", data);
    appendRecentMessage(data.from, data.message, "recent", data.timestamp);
}

// appendChatMessage.js


export function appendRecentMessage(sender, text, cssClass, timestamp = null) {
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
    const deleteButton = document.createElement('button');
    deleteButton.textContent = 'Delete';
    deleteButton.addEventListener('click', () => {
        newMessage.remove();
    });
    newMessage.innerHTML = `<strong>${sender}:</strong> ${timeText}${text}`;
    newMessage.appendChild(deleteButton);
    messagesDiv.appendChild(newMessage);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

export function appendUnreadMessage(sender, text, cssClass, timestamp = null) {
    const containerId = 'unread-messages';

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
    const deleteButton = document.createElement('button');
    deleteButton.textContent = 'Delete';
    deleteButton.addEventListener('click', () => {
        newMessage.remove();
    });
    newMessage.innerHTML = `<strong>${sender}:</strong> ${timeText}${text}`;
    newMessage.appendChild(deleteButton);
    messagesDiv.appendChild(newMessage);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

