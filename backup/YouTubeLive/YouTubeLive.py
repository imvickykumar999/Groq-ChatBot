import os
import time
import requests
from flask import Flask, request, jsonify
from groq import Groq
from googleapiclient.discovery import build

app = Flask(__name__)

# Set environment variables for security
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', 'YOUR_YOUTUBE_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', 'YOUR_GROQ_API_KEY')
VIDEO_ID = os.getenv('YOUTUBE_VIDEO_ID', 'Mvr4NQF0IuQ')

if not YOUTUBE_API_KEY or not GROQ_API_KEY:
    raise ValueError("API keys not found! Set YOUTUBE_API_KEY and GROQ_API_KEY.")

# Initialize API clients
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
client = Groq(api_key=GROQ_API_KEY)

def get_live_chat_id(video_id):
    """Fetches the live chat ID from the given video."""
    response = youtube.videos().list(part='liveStreamingDetails', id=video_id).execute()
    return response['items'][0]['liveStreamingDetails'].get('activeLiveChatId')

def get_live_chat_messages(live_chat_id):
    """Fetches only the latest live chat message."""
    chat_response = youtube.liveChatMessages().list(
        liveChatId=live_chat_id, part='snippet,authorDetails', maxResults=1
    ).execute()
    
    if not chat_response['items']:
        return None, None

    item = chat_response['items'][-1]  # Get the last message
    author = item['authorDetails']['displayName']
    message = item['snippet']['displayMessage']
    return author, message

def generate_reply(message_text):
    """Generates a reply using Groq's AI."""
    try:
        completion = client.chat.completions.create(
            model="llama-3.2-1b-preview",
            messages=[{"role": "user", "content": message_text}],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=False,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return "Sorry, I'm having trouble processing your request."

@app.route("/", methods=["GET"])
def fetch_and_reply():
    """Fetches the last YouTube live chat message, processes it, and generates a response."""
    live_chat_id = get_live_chat_id(VIDEO_ID)
    if not live_chat_id:
        return jsonify({"error": "Live chat not available for this video."})
    
    author, message = get_live_chat_messages(live_chat_id)
    if not message:
        return jsonify({"error": "No messages found."})

    reply = generate_reply(message)
    return jsonify({"author": author, "message": message, "reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
