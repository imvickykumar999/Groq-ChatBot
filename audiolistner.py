from flask import Flask, request, Response, render_template_string, jsonify
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
    It sends the message to the Groq API for a chat completion, streams the response back,
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
            # Incrementally update the chat record in SQLite.
            update_chat(chat_id, assistant_response)
            yield content

    return Response(generate(), mimetype='text/plain')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """
    This endpoint accepts an audio file upload, sends it to the Groq audio transcription API,
    and returns the transcription result.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file.'}), 400

    # Read the file content as bytes.
    file_content = file.read()
    filename = file.filename

    transcription = client.audio.transcriptions.create(
        file=(filename, file_content),
        model="whisper-large-v3",
        response_format="verbose_json",
    )
    
    return jsonify({'transcription': transcription.text})

@app.route('/')
def index():
    """Render the chat window with chat history, an input field for text, and an audio transcription upload form."""
    chats = get_all_chats()
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Chat & Transcription Window</title>
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
            #chat-form, #transcription-form { margin-bottom: 20px; }
            #message-input { flex: 1; padding: 10px; }
            #send-btn { padding: 10px 20px; }
        </style>
    </head>
    <body>
        <h1>Chat & Transcription Window</h1>
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

        <br>
        <h2>Transcribe Audio</h2>
        <form id="transcription-form" enctype="multipart/form-data">
            <input type="file" id="audio-input" name="file" accept="audio/*" required>
            <button type="submit">Transcribe</button>
        </form>

        <script>
            // Handle chat form submission and streaming response.
            document.getElementById("chat-form").addEventListener("submit", async (e) => {
                e.preventDefault();
                const input = document.getElementById("message-input");
                const message = input.value.trim();
                if (!message) return;
                input.value = "";
                const chatHistory = document.getElementById("chat-history");

                let userEntry = document.createElement("div");
                userEntry.className = "chat-entry";
                userEntry.innerHTML = "<div class='user'><strong>User:</strong> " + message + "</div>";
                chatHistory.appendChild(userEntry);
                chatHistory.scrollTop = chatHistory.scrollHeight;

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

            // Handle transcription form submission.
            document.getElementById("transcription-form").addEventListener("submit", async (e) => {
                e.preventDefault();
                const audioInput = document.getElementById("audio-input");
                const file = audioInput.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append("file", file);

                try {
                    const response = await fetch("/transcribe", {
                        method: "POST",
                        body: formData
                    });
                    const result = await response.json();
                    document.getElementById("message-input").value = result.transcription || "No transcription available.";
                } catch (error) {
                    console.error("Error during transcription:", error);
                }
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html, chats=chats)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
