import os
import re
import json
import requests
from groq import Groq
from .models import Chat
from pprint import pprint
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ngrok http --url=monkey-related-kangaroo.ngrok-free.app 8000
WEBHOOK_URL = "https://monkey-related-kangaroo.ngrok-free.app/webhook/"

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
client = Groq(api_key=GROQ_API_KEY)

def clean_filename(file_name):
    file_name = re.sub(r'\d+', '', file_name)
    file_name = re.sub(r'[^\w\s]', '', file_name)
    file_name = file_name.replace("_", " ").strip()
    return "I am feeling " + file_name

def set_webhook():
    url = f"{BASE_URL}/setWebhook"
    response = requests.post(url, json={"url": WEBHOOK_URL})
    return response.json()

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

def generate_reply(message_text):
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

def transcribe_voice(file_name, file_content):
    try:
        transcription = client.audio.transcriptions.create(
            file=(file_name, file_content),
            model="whisper-large-v3",
            response_format="verbose_json",
        )
        return transcription.text
    except Exception as e:
        return "Sorry, I'm having trouble transcribing your audio."

@csrf_exempt
def webhook(request):
    if request.method == "POST":
        update = json.loads(request.body)
        pprint(update)

        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]

            username = message["chat"].get("username", "")
            first_name = message["chat"].get("first_name", "")
            last_name = message["chat"].get("last_name", "")

            message_type = "unknown"
            message_content = ""
            reply_message = "No reply generated."
            download_url = ""

            if "voice" in message:
                voice = message["voice"]
                file_id = voice["file_id"]

                get_file_url = f"{BASE_URL}/getFile?file_id={file_id}"
                file_info_response = requests.get(get_file_url)
                file_info = file_info_response.json()

                if file_info.get("ok"):
                    file_path = file_info["result"]["file_path"]
                    download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

                    print('\n\n', download_url, '\n\n')
                    file_response = requests.get(download_url)
                    file_content = file_response.content

                    transcription_text = transcribe_voice("voice.ogg", file_content)
                    print('\n\n', transcription_text, '\n\n')

                    reply_text = generate_reply(transcription_text)
                    send_message(chat_id, reply_text)

                    message_type = "voice"
                    message_content = transcription_text
                    reply_message = reply_text
                    download_file = download_url
                else:
                    send_message(chat_id, "Sorry, could not retrieve the audio file.")

            elif "text" in message:
                message_text = message.get("text", "")
                reply_text = generate_reply(message_text)

                send_message(chat_id, reply_text)
                message_type = "text"
                message_content = message_text
                reply_message = reply_text
                download_file = download_url

            elif "sticker" in message:
                sticker_info = message["sticker"]
                emoji = sticker_info.get("emoji", "")
                reply_text = generate_reply(emoji)

                send_message(chat_id, reply_text)
                message_type = "sticker"
                message_content = message["sticker"].get("emoji", "Sticker received")
                reply_message = reply_text
                download_file = download_url

            elif "animation" in message:
                animation_info = message["animation"]
                file_name = animation_info.get("file_name", "animation.gif")
                file_name = file_name.split(".")[0]

                cleaned_name = clean_filename(file_name)
                reply_text = generate_reply(cleaned_name)
                send_message(chat_id, reply_text)

                message_type = "animation"
                message_content = cleaned_name
                reply_message = reply_text
                download_file = download_url

            elif "photo" in message:
                file_id = message["photo"][-1]["file_id"]  # Get the highest resolution photo
                file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
                
                if file_info.get("ok"):
                    file_path = file_info["result"]["file_path"]
                    download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    
                    reply_text = f"Received photo.\nFile Name: {file_path}"
                    send_message(chat_id, reply_text)
                    message_type = "photo"

                    message_content = file_path
                    reply_message = reply_text
                    download_file = download_url
                else:
                    send_message(chat_id, "Sorry, could not retrieve the photo.")

            elif "document" in message:
                file_id = message["document"]["file_id"]
                file_name = message["document"].get("file_name", "Unknown Document")
                file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
                
                if file_info.get("ok"):
                    file_path = file_info["result"]["file_path"]
                    download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    
                    reply_text = f"Received document: {file_name}"
                    send_message(chat_id, reply_text)
                    message_type = "document"

                    message_content = message["document"].get("file_name", "Document received")
                    reply_message = reply_text
                    download_file = download_url
                else:
                    send_message(chat_id, "Sorry, could not retrieve the document.")

            elif "poll" in message:
                poll = message["poll"]
                question = poll.get("question", "")

                if question:
                    reply_text = generate_reply(question)
                    send_message(chat_id, reply_text)

                    message_type = "poll"
                    message_content = question
                    reply_message = reply_text
                    download_file = download_url

            elif "venue" in message:
                venue = message["venue"]
                venue_title = venue.get("title", "")
                venue_address = venue.get("address", "")

                if venue_title or venue_address:
                    venue_info = f"Venue: {venue_title}\nAddress: {venue_address}"
                    reply_text = generate_reply(venue_info)
                    send_message(chat_id, reply_text)

                    message_type = "venue"
                    message_content = venue_info
                    reply_message = reply_text
                    download_file = download_url

            # Save to database
            Chat.objects.create(
                chat_id=chat_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                message_type=message_type,
                reply_message=reply_message,
                message_content=message_content,
                download_file=download_file,
            )

            return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "error"}, status=400)

def set_webhook_route(request):
    return JsonResponse(set_webhook())
