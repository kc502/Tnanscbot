import os
import threading
import requests
import math
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from groq import Groq
from pydub import AudioSegment

# --- Configuration ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
PORT = int(os.environ.get("PORT", 8080))

client = Groq(api_key=GROQ_API_KEY)

# --- Render Health Check ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active")

def run_health_check():
    httpd = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    httpd.serve_forever()

# --- Cobalt API: Get Audio Download Link ---
def get_cobalt_audio_url(youtube_url):
    try:
        api_url = "https://api.cobalt.tools/api/json"
        payload = {
            "url": youtube_url,
            "downloadMode": "audio",
            "audioFormat": "mp3",
            "audioBitrate": "32" # အနိမ့်ဆုံး bitrate
        }
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        response = requests.post(api_url, json=payload, headers=headers)
        return response.json().get("url")
    except Exception as e:
        print(f"Cobalt Error: {e}")
        return None

# --- Audio Chunking & Transcription ---
def process_audio_in_chunks(file_path):
    audio = AudioSegment.from_file(file_path)
    chunk_length = 10 * 60 * 1000 # 10 mins
    chunks = math.ceil(len(audio) / chunk_length)
    full_transcript = ""
    
    for i in range(chunks):
        chunk = audio[i*chunk_length : (i+1)*chunk_length]
        chunk_name = f"chunk_{i}.mp3"
        chunk.export(chunk_name, format="mp3", bitrate="32k")
        
        with open(chunk_name, "rb") as f:
            res = client.audio.transcriptions.create(
                file=(chunk_name, f.read()),
                model="whisper-large-v3",
                response_format="text"
            )
            full_transcript += res + " "
        os.remove(chunk_name)
    return full_transcript

# --- Bot Handler ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not ("youtube.com" in url or "youtu.be" in url):
        return

    status_msg = await update.message.reply_text("⏳ Processing with Cobalt API...")
    temp_file = f"audio_{update.message.from_user.id}.mp3"

    try:
        # 1. Get Direct Link from Cobalt
        audio_url = get_cobalt_audio_url(url)
        if not audio_url:
            await status_msg.edit_text("❌ YouTube Link ကို ဖတ်လို့မရပါ။")
            return

        # 2. Download from Direct Link
        await status_msg.edit_text("📥 Audio ဒေါင်းလုဒ်ဆွဲနေသည်...")
        r = requests.get(audio_url)
        with open(temp_file, 'wb') as f:
            f.write(r.content)

        # 3. Transcribe with Groq
        await status_msg.edit_text("✂️ အပိုင်းခွဲပြီး Transcript ထုတ်နေသည်...")
        final_text = process_audio_in_chunks(temp_file)

        # 4. Reply
        if len(final_text) > 4000:
            for i in range(0, len(final_text), 4000):
                await update.message.reply_text(final_text[i:i+4000])
        else:
            await update.message.reply_text(f"📝 **Transcript:**\n\n{final_text}")
        
        await status_msg.delete()

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == '__main__':
    threading.Thread(target=run_health_check, daemon=True).start()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()

