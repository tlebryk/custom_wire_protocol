/* Establish WebSocket connection */
const ws = new WebSocket('ws://localhost:8000/ws');
window.ws = ws;
window.isAuthenticated = false;
window.lastRegUsername = ""; // stored username from registration attempt


import {
    handleRecentMessages,
    handleUnreadMessages,
    handleLogin,
    handleSendMessage,
    handleErrorMessage,
    handleDefaultMessage,
    appendChatMessage
} from './handlers.js';

import {
    sendRegistration,
    displayError,
    sendLogin,
    deleteAccount,
    sendMessage
} from './utils.js';

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
    recent_messages: handleRecentMessages,
    unread_messages: handleUnreadMessages,
    // You can add more handlers here as needed
    default: handleDefaultMessage
};

// WebSocket Event Listeners
window.ws.onopen = function () {
    console.log("WebSocket connection established.");
};
window.ws.onmessage = function (event) {
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
        // Log the action and the function we're calling 
        console.log("Received action:", action);
        console.log("Using handler:", handlers[action].name);
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
        if (handlers.default) {
            handlers.default(data);
        } else {
            console.warn("No handler found for message:", data);
        }
    }
};

window.ws.onclose = function () {
    console.log("WebSocket connection closed.");
};

window.ws.onerror = function (error) {
    console.error("WebSocket error:", error);
};


window.sendRegistration = sendRegistration;
window.displayError = displayError;
window.appendChatMessage = appendChatMessage;
window.sendLogin = sendLogin;
window.sendMessage = sendMessage;
window.deleteAccount = deleteAccount;

