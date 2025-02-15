from flask import Flask, request, Response, render_template_string
import sqlite3
from groq import Groq

app = Flask(__name__)
DATABASE = "chats.db"

def init_db():
    """Initialize the SQLite database and create the chats table if needed."""
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT,
            assistant_response TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def create_chat(user_message):
    """
    Insert a new chat record with the user's message and an empty assistant response.
    Returns the new record's id.
    """
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chats (user_message, assistant_response) VALUES (?, ?)",
        (user_message, "")
    )
    chat_id = cur.lastrowid
    conn.commit()
    conn.close()
    return chat_id

def update_chat(chat_id, assistant_response):
    """Update the assistant_response for the chat record with the given id."""
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute(
        "UPDATE chats SET assistant_response = ? WHERE id = ?",
        (assistant_response, chat_id)
    )
    conn.commit()
    conn.close()

def get_all_chats():
    """Retrieve all chats from the database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, user_message, assistant_response, created_at FROM chats ORDER BY created_at ASC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Initialize the database on startup.
init_db()

# Initialize the Groq client with your API key.
client = Groq(api_key='gsk_5rPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxw9RPf')

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    This endpoint expects a JSON payload with a "message" field.
    It sends the message to the Groq API, streams the response back,
    and incrementally updates the conversation in SQLite.
    """
    data = request.get_json() or {}
    user_message = data.get("message", "Hello, how are you?")
    messages = [{"role": "user", "content": user_message}]

    # Create a new chat record immediately with an empty assistant response.
    chat_id = create_chat(user_message)

    response = client.chat.completions.create(
        model="qwen-2.5-32b",
        messages=messages,
        temperature=0.6,
        max_tokens=4096,
        top_p=0.95,
        stream=True,
    )

    def generate():
        assistant_response = ""
        for chunk in response:
            # Use getattr because delta is a Pydantic model.
            content = getattr(chunk.choices[0].delta, "content", "")
            assistant_response += content

            # Update the chat record in SQLite with the current assistant response.
            update_chat(chat_id, assistant_response)
            yield content

    return Response(generate(), mimetype='text/plain')

@app.route('/')
def index():
    """Render the chat window with chat history and an input field."""
    chats = get_all_chats()
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Chat Window</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            #chat-history {
                border: 1px solid #ccc;
                padding: 10px;
                height: 400px;
                overflow-y: scroll;
                margin-bottom: 10px;
                background: #f9f9f9;
            }
            .chat-entry { margin-bottom: 15px; }
            .user { color: blue; }
            .assistant { color: green; }
            .timestamp { font-size: small; color: #666; }
            #chat-form { display: flex; }
            #message-input { flex: 1; padding: 10px; }
            #send-btn { padding: 10px 20px; }
        </style>
    </head>
    <body>
        <h1>Chat Window</h1>
        <div id="chat-history">
            {% for chat in chats %}
                <div class="chat-entry">
                    <div class="user"><strong>User:</strong> {{ chat.user_message }}</div>
                    <div class="assistant"><strong>Assistant:</strong> {{ chat.assistant_response }}</div>
                    <div class="timestamp">{{ chat.created_at }}</div>
                </div>
            {% endfor %}
        </div>
        <form id="chat-form">
            <input type="text" id="message-input" placeholder="Type your message here" required autocomplete="off">
            <button type="submit" id="send-btn">Send</button>
        </form>

        <script>
            // Handle form submission and chat streaming.
            document.getElementById("chat-form").addEventListener("submit", async (e) => {
                e.preventDefault();
                const input = document.getElementById("message-input");
                const message = input.value.trim();
                if (!message) return;
                input.value = "";

                // Append user message to chat history.
                const chatHistory = document.getElementById("chat-history");
                let userEntry = document.createElement("div");
                userEntry.className = "chat-entry";
                userEntry.innerHTML = "<div class='user'><strong>User:</strong> " + message + "</div>";
                chatHistory.appendChild(userEntry);
                chatHistory.scrollTop = chatHistory.scrollHeight;

                // Append a placeholder for assistant's response.
                let assistantEntry = document.createElement("div");
                assistantEntry.className = "chat-entry";
                assistantEntry.innerHTML = "<div class='assistant'><strong>Assistant:</strong> </div>";
                chatHistory.appendChild(assistantEntry);
                chatHistory.scrollTop = chatHistory.scrollHeight;

                try {
                    const response = await fetch("/webhook", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ message: message })
                    });
                    
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let assistantResponse = "";
                    
                    // Read the streamed response.
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        const chunk = decoder.decode(value);
                        assistantResponse += chunk;
                        assistantEntry.innerHTML = "<div class='assistant'><strong>Assistant:</strong> " + assistantResponse + "</div>";
                        chatHistory.scrollTop = chatHistory.scrollHeight;
                    }
                } catch (error) {
                    console.error("Error fetching assistant response:", error);
                }
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html, chats=chats)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
