// Éléments du DOM
const chatButton = document.getElementById('chat-button');
const chatWindow = document.getElementById('chat-window');
const closeBtn = document.getElementById('close-chat');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const messagesContainer = document.getElementById('chat-messages');
const categoriesContainer = document.getElementById('categories-container');
const suggestionBtns = document.querySelectorAll('.suggestion-btn');

// Éléments des onglets
const tabChat = document.getElementById('tab-chat');
const tabVideos = document.getElementById('tab-videos');
const viewChat = document.getElementById('view-chat');
const viewVideos = document.getElementById('view-videos');

// --- OUVRIR / FERMER LE CHAT ---
chatButton.addEventListener('click', () => {
    chatWindow.classList.remove('hidden');
    setTimeout(() => chatWindow.classList.add('show'), 10);
});

closeBtn.addEventListener('click', () => {
    chatWindow.classList.remove('show');
    setTimeout(() => chatWindow.classList.add('hidden'), 300);
});

// --- GESTION DES ONGLETS ---
tabChat.addEventListener('click', () => {
    tabChat.classList.add('active');
    tabVideos.classList.remove('active');
    viewChat.classList.remove('hidden');
    viewVideos.classList.add('hidden');
});

tabVideos.addEventListener('click', () => {
    tabVideos.classList.add('active');
    tabChat.classList.remove('active');
    viewVideos.classList.remove('hidden');
    viewChat.classList.add('hidden');
});

// --- GESTION DES MESSAGES ---
sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// Clic sur une question catégorisée
suggestionBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        userInput.value = btn.textContent;
        sendMessage();
    });
});

function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Masquer les catégories dès le premier message pour faire de la place
    if (categoriesContainer) {
        categoriesContainer.style.display = 'none';
    }

    addMessage(message, 'user');
    userInput.value = '';

    fetch('http://localhost:5000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        addMessage(data.response, 'bot');
    })
    .catch(error => {
        console.error('Erreur:', error);
        addMessage('Désolé, une erreur de connexion est survenue. 🔌', 'bot');
    });
}

function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    // Convertit les sauts de ligne texte en vrais sauts de ligne HTML
    bubble.innerHTML = text.replace(/\n/g, '<br>');
    
    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll automatique
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}