// handlers.js

export function handleRecentMessages(data) {
    const messages = data.messages;
    if (Array.isArray(messages)) {
        messages.forEach(msg => {
            appendChatMessage(msg.from, msg.message, "received", msg.timestamp);
        });
    }
}

export function handleLogin(data) {
    if (data.status === "success" && data.message && data.message.includes("Login successful")) {
        window.isAuthenticated = true;
        console.log("Login successful");
        // Hide authentication and show chat box
        document.getElementById('authBox').classList.add('hidden');
        document.getElementById('chatBox').classList.remove('hidden');
    } else {
        // Handle unsuccessful login attempts if necessary
        displayError(data.message || "Login failed.");
    }
}

export function handleSendMessage(data) {
    // Assuming the server sends back confirmation or details about the sent message
    if (data.status === "success") {
        console.log("Message sent successfully.");
    } else if (data.status === "error") {
        displayError(data.message || "Failed to send message.");
    }
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


// Append chat messages to the messages display area.
export function appendChatMessage(sender, text, cssClass, timestamp = null) {
    const messagesDiv = document.getElementById('messages');
    if (!messagesDiv) {
        console.error("Messages element not found!");
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
    messagesDiv.appendChild(newMessage);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
