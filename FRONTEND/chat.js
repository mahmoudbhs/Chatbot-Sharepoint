const chatButton = document.getElementById("chat-button");
const chatWindow = document.getElementById("chat-window");
const closeBtn = document.getElementById("close-chat");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-button");
const messagesContainer = document.getElementById("chat-messages");
const categoriesContainer = document.getElementById("categories-container");
const suggestionBtns = document.querySelectorAll(".suggestion-btn");

const tabChat = document.getElementById("tab-chat");
const tabVideos = document.getElementById("tab-videos");
const viewChat = document.getElementById("view-chat");
const viewVideos = document.getElementById("view-videos");

const sessionId = window.localStorage.getItem("chatbotSessionId") || crypto.randomUUID();
window.localStorage.setItem("chatbotSessionId", sessionId);

chatButton.addEventListener("click", () => {
    chatWindow.classList.remove("hidden");
    setTimeout(() => chatWindow.classList.add("show"), 10);
});

closeBtn.addEventListener("click", () => {
    chatWindow.classList.remove("show");
    setTimeout(() => chatWindow.classList.add("hidden"), 300);
});

tabChat.addEventListener("click", () => {
    tabChat.classList.add("active");
    tabVideos.classList.remove("active");
    viewChat.classList.remove("hidden");
    viewVideos.classList.add("hidden");
});

tabVideos.addEventListener("click", () => {
    tabVideos.classList.add("active");
    tabChat.classList.remove("active");
    viewVideos.classList.remove("hidden");
    viewChat.classList.add("hidden");
});

sendButton.addEventListener("click", sendMessage);
userInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
        sendMessage();
    }
});

suggestionBtns.forEach((button) => {
    button.addEventListener("click", () => {
        userInput.value = button.textContent;
        sendMessage();
    });
});

function sendMessage() {
    const message = userInput.value.trim();
    if (!message) {
        return;
    }

    if (categoriesContainer) {
        categoriesContainer.style.display = "none";
    }

    addMessage(message, "user");
    userInput.value = "";

    fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            message,
            session_id: sessionId,
        }),
    })
        .then((response) => response.json())
        .then((data) => {
            const botText = data.response || "Une erreur est survenue.";
            addMessage(botText, "bot");
        })
        .catch((error) => {
            console.error("Erreur:", error);
            addMessage("Desole, une erreur de connexion est survenue.", "bot");
        });
}

function addMessage(text, sender) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${sender}-message`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = text.replace(/\n/g, "<br>");

    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
