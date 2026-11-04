window.addEventListener('load', () => {
    console.log("Chat script loaded!");

    const chatBtn = document.getElementById('ai-chat-btn');
    const chatWindow = document.getElementById('ai-chat-window');
    const closeBtn = document.getElementById('close-chat-btn');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const history = document.getElementById('chat-history');

    if (!chatBtn || !chatWindow) {
        console.error("Could not find the chat button or window in the HTML!");
        return;
    }

    // Toggle Chat Window
    chatBtn.addEventListener('click', (e) => {
        e.preventDefault();
        console.log("Chat button clicked!");
        chatWindow.classList.toggle('open');
        if (chatWindow.classList.contains('open')) {
            chatInput.focus();
            history.scrollTop = history.scrollHeight;
        }
    });

    closeBtn.addEventListener('click', () => {
        chatWindow.classList.remove('open');
    });

    // Handle Form Submit
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = chatInput.value.trim();
        if (!question) return;

        console.log("Sending question:", question);

        // Add user message
        const userBubble = document.createElement('div');
        userBubble.className = 'chat-bubble user-bubble';
        userBubble.textContent = question;
        history.appendChild(userBubble);

        chatInput.value = '';
        sendBtn.disabled = true;
        sendBtn.textContent = '...';

        // Add loading bubble
        const loadingBubble = document.createElement('div');
        loadingBubble.className = 'chat-bubble ai-bubble loading';
        loadingBubble.textContent = 'Thinking...';
        history.appendChild(loadingBubble);
        history.scrollTop = history.scrollHeight;

        try {
            const csrfToken = chatForm.querySelector('input[name="csrf_token"]').value;
            
            const res = await fetch('/api/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ question: question })
            });
            
            const data = await res.json();
            console.log("AI Response:", data);
            
            if (data.error) {
                loadingBubble.textContent = "Error: " + data.error;
                loadingBubble.style.color = "var(--danger)";
            } else {
                loadingBubble.textContent = data.answer;
                loadingBubble.classList.remove('loading');
            }
        } catch (err) {
            console.error("Fetch error:", err);
            loadingBubble.textContent = "Failed to connect to the AI.";
            loadingBubble.style.color = "var(--danger)";
        }

        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
        history.scrollTop = history.scrollHeight;
    });
});