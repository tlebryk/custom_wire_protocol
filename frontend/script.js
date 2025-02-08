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


window.sendRegistration = sendRegistration;
window.displayError = displayError;
window.appendChatMessage = appendChatMessage;
window.sendLogin = sendLogin;
window.sendMessage = sendMessage;

