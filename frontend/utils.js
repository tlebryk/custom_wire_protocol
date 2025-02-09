
export function sendRegistration() {
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
    window.ws.send(JSON.stringify(regPayload));
    // Only clear the password field to let the username persist in the registration form 
    // in case the user needs to be switched to login form on error.
    passwordElement.value = '';
}

export function sendLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value.trim();
    if (!username || !password) {
        alert("Please enter both username and password.");
        return;
    }
    const loginPayload = { action: "login", username, password };
    window.ws.send(JSON.stringify(loginPayload));
    // Clear the login input fields after sending the login request
    document.getElementById('loginUsername').value = '';
    document.getElementById('loginPassword').value = '';
}

export function sendMessage() {
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
    console.log("Sending message:", msgPayload);
    window.ws.send(JSON.stringify(msgPayload));
    // figure out how to deal with sent messages at some point...
    appendRecentMessage(receiver, messageText, "recent", new Date().toISOString());
    document.getElementById('messageText').value = "";
}


// Display error messages in the errorBox element.
export function displayError(message) {
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



export function deleteAccount() {
    if (!isAuthenticated) {
        alert("You must be logged in to delete your account.");
        return;
    }

    const deletePayload = { action: "delete_account" };
    window.ws.send(JSON.stringify(deletePayload));
    alert("Account deleted. You will be logged out.");
    location.reload();
}

export function readMessages(messageIds) {
    const readPayload = { action: "mark_as_read", message_ids: messageIds };
    window.ws.send(JSON.stringify(readPayload));
}