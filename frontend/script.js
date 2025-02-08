/* Establish WebSocket connection */
const ws = new WebSocket('ws://localhost:8000/ws');
let isAuthenticated = false;
let lastRegUsername = ""; // stored username from registration attempt

// Ensure all functions manipulating the DOM are defined and invoked after the DOM is ready.
document.addEventListener('DOMContentLoaded', function () {
    // Define the toggleForms function to switch between registration and login forms.
    function toggleForms() {
        document.getElementById('registerForm').classList.toggle('hidden');
        document.getElementById('loginForm').classList.toggle('hidden');
    }
    // Expose toggleForms to the global scope for HTML event handlers
    window.toggleForms = toggleForms;
});

ws.onopen = function () {
    console.log("WebSocket connection established.");
};

ws.onmessage = function (event) {
    console.log("Message from server:", event.data);
    let data;
    try {
        data = JSON.parse(event.data);
    } catch (err) {
        console.error("Failed to parse server message:", err);
        return;
    }

    if (data.action === "recent_messages") {
        const messages = data.messages;
        if (Array.isArray(messages)) {
            messages.forEach(msg => {
                appendChatMessage(msg.from, msg.message, "received", msg.timestamp);
            });
        }
    } else if (data.action === "login") {
        if (data.status === "success" && data.message && data.message.includes("Login successful")) {
            isAuthenticated = true;
            console.log("login sucessful")
            // Hide authentication and show chat box
            document.getElementById('authBox').classList.add('hidden');
            document.getElementById('chatBox').classList.remove('hidden');
        }
    } else if (data.from && data.message) {
        // Handle real-time incoming messages
        appendChatMessage(data.from, data.message, "received", data.timestamp);
    } else if (data.status === "success" && data.message) {
        // Handle other success messages if necessary
        console.log("Success:", data.message);
    } else if (data.status === "error") {
        // Check for duplicate account message, assuming the error message contains "already"
        if (data.message.toLowerCase().includes("already")) {
            // For duplicate registration error, toggle to login and pre-populate the login username field
            document.getElementById('loginUsername').value = lastRegUsername;
            // Switch forms if registration form is currently visible
            if (!document.getElementById('loginForm').classList.contains('hidden')) {
                // Already in login form, do nothing extra here
            } else {
                // Toggle to login form
                window.toggleForms();
            }
            displayError("Account already exists. Please enter your password to login.");
        } else {
            displayError(data.message);
        }
    }
};

ws.onclose = function () {
    console.log("WebSocket connection closed.");
};

ws.onerror = function (error) {
    console.error("WebSocket error:", error);
};

function sendRegistration() {
    const usernameElement = document.getElementById('regUsername');
    const passwordElement = document.getElementById('regPassword');
    const username = usernameElement.value.trim();
    const password = passwordElement.value.trim();
    if (!username || !password) {
        alert("Please enter both username and password.");
        return;
    }
    // Save the username in case we need to switch to login on error
    lastRegUsername = username;
    const regPayload = { action: "register", username, password };
    ws.send(JSON.stringify(regPayload));
    // Only clear the password field to let the username persist in the registration form 
    // in case the user needs to be switched to login form on error.
    passwordElement.value = '';
}

function sendLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value.trim();
    if (!username || !password) {
        alert("Please enter both username and password.");
        return;
    }
    const loginPayload = { action: "login", username, password };
    ws.send(JSON.stringify(loginPayload));
    // Clear the login input fields after sending the login request
    document.getElementById('loginUsername').value = '';
    document.getElementById('loginPassword').value = '';
}

function sendMessage() {
    if (!isAuthenticated) {
        alert("You must be logged in to send messages.");
        return;
    }
    const messageText = document.getElementById('messageText').value.trim();
    const receiver = document.getElementById('receiverUsername').value.trim(); // New input field for receiver
    if (!receiver) {
        alert("Please enter the receiver's username.");
        return;
    }
    if (!messageText) {
        alert("Please enter a message.");
        return;
    }
    const msgPayload = {
        action: "send_message",
        message: messageText,
        receiver: receiver
    };
    ws.send(JSON.stringify(msgPayload));
    appendChatMessage("You", messageText, "sent", new Date().toISOString());
    document.getElementById('messageText').value = "";
}


// Display error messages in the errorBox element.
function displayError(message) {
    const errorBox = document.getElementById('errorBox');
    if (errorBox) {
        errorBox.textContent = message;
        errorBox.classList.remove('hidden');
        // Optionally, hide the error message after a few seconds:
        setTimeout(() => {
            errorBox.classList.add('hidden');
        }, 5000);
    } else {
        console.error("Error element not found in DOM:", message);
    }
}

// Append chat messages to the messages display area.
function appendChatMessage(sender, text, cssClass, timestamp = null) {
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