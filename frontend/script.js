/* Establish WebSocket connection */
const ws = new WebSocket('ws://localhost:8000/ws');
window.isAuthenticated = false;
window.lastRegUsername = ""; // stored username from registration attempt


import {
    handleRecentMessages,
    handleLogin,
    handleSendMessage,
    handleErrorMessage,
    handleDefaultMessage,
    appendChatMessage
} from './handlers.js';

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

// Handler Functions
const handlers = {
    recent_messages: handleRecentMessages,
    login: handleLogin,
    send_message: handleSendMessage,
    // You can add more handlers here as needed
    default: handleDefaultMessage
};

// WebSocket Event Listeners
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

    const action = data.action;

    if (action && handlers[action]) {
        // log the action and the function we're calling 
        console.log("Received action:", action);
        // log which hander we're using 
        console.log("Using handler:", handlers[action]);
        handlers[action](data);
    } else if (data.from && data.message) {
        // Handle real-time incoming messages without a specific action
        appendChatMessage(data.from, data.message, "received", data.timestamp);
    } else if (data.status) {
        // Handle status messages that don't have a specific action
        if (data.status === "success" && data.message) {
            console.log("Success:", data.message);
        } else if (data.status === "error") {
            handleErrorMessage(data);
        }
    } else {
        // Fallback for unhandled messages
        handlers.default(data);
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
// function appendChatMessage(sender, text, cssClass, timestamp = null) {
//     const messagesDiv = document.getElementById('messages');
//     if (!messagesDiv) {
//         console.error("Messages element not found!");
//         return;
//     }
//     const newMessage = document.createElement('div');
//     newMessage.classList.add('message', cssClass);

//     let timeText = '';
//     if (timestamp) {
//         const date = new Date(timestamp);
//         timeText = `<span class="timestamp">[${date.toLocaleTimeString()}]</span> `;
//     }
//     newMessage.innerHTML = `<strong>${sender}:</strong> ${timeText}${text}`;
//     messagesDiv.appendChild(newMessage);
//     messagesDiv.scrollTop = messagesDiv.scrollHeight;
// }

function deleteAccount() {
    if (!isAuthenticated) {
        alert("You must be logged in to delete your account.");
        return;
    }

    const deletePayload = { action: "delete_account" };
    ws.send(JSON.stringify(deletePayload));
    alert("Account deleted. You will be logged out.");
    location.reload();
}


window.sendRegistration = sendRegistration;
window.displayError = displayError;
window.appendChatMessage = appendChatMessage;
window.sendLogin = sendLogin;
window.sendMessage = sendMessage;

