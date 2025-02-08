// Establish WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws');
let isAuthenticated = false;

ws.onopen = function () {
    console.log("WebSocket connection established.");
};

ws.onmessage = function (event) {
    console.log("Message from server:", event.data);
    let data;
    try {
        data = JSON.parse(event.data);
    } catch (err) {
        return;
    }

    if (data.action === "recent_messages") {
        const messages = data.messages;
        if (Array.isArray(messages)) {
            messages.forEach(msg => {
                appendChatMessage(msg.from, msg.message, "received", msg.timestamp);
            });
        }
    } else if (data.status === "success") {
        if (data.message && data.message.includes("Login successful")) {
            isAuthenticated = true;
            document.getElementById('authBox').classList.add('hidden');
            document.getElementById('chatBox').classList.remove('hidden');
            document.getElementById('deleteAccountBtn').classList.remove('hidden');
        } else if (data.from && data.message) {
            appendChatMessage(data.from, data.message, "received", data.timestamp);
        }
    } else if (data.status === "error") {
        console.log("Error:", data.message);
    }
};

ws.onclose = function () {
    console.log("WebSocket connection closed.");
};

ws.onerror = function (error) {
    console.error("WebSocket error:", error);
};

function toggleForms() {
    document.getElementById('registerForm').classList.toggle('hidden');
    document.getElementById('loginForm').classList.toggle('hidden');
}

function sendRegistration() {
    const username = document.getElementById('regUsername').value.trim();
    const password = document.getElementById('regPassword').value.trim();
    if (!username || !password) {
        alert("Please enter both username and password.");
        return;
    }
    const regPayload = { action: "register", username, password };
    ws.send(JSON.stringify(regPayload));
    document.getElementById('regUsername').value = '';
    document.getElementById('regPassword').value = '';
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
    document.getElementById('loginUsername').value = '';
    document.getElementById('loginPassword').value = '';
}

function sendMessage() {
    if (!isAuthenticated) {
        alert("You must be logged in to send messages.");
        return;
    }
    const messageText = document.getElementById('messageText').value.trim();
    if (!messageText) {
        alert("Please enter a message.");
        return;
    }
    const msgPayload = { action: "send_message", message: messageText };
    ws.send(JSON.stringify(msgPayload));
    appendChatMessage("You", messageText, "sent", new Date().toISOString());
    document.getElementById('messageText').value = "";
}

function appendChatMessage(sender, text, cssClass, timestamp = null) {
    const messagesDiv = document.getElementById('messages');
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

