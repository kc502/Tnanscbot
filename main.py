import os
import threading
import yt_dlp
import math
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from groq import Groq
from pydub import AudioSegment

# --- Config ---
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

# --- Utility: Split and Transcribe ---
def process_audio_in_chunks(file_path):
    audio = AudioSegment.from_file(file_path)
    ten_minutes = 10 * 60 * 1000  # 10 minutes in milliseconds
    chunks = math.ceil(len(audio) / ten_minutes)
    
    full_transcript = ""
    
    for i in range(chunks):
        start_time = i * ten_minutes
        end_time = (i + 1) * ten_minutes
        chunk = audio[start_time:end_time]
        
        chunk_name = f"chunk_{i}.mp3"
        chunk.export(chunk_name, format="mp3", bitrate="32k")
        
        with open(chunk_name, "rb") as f:
            response = client.audio.transcriptions.create(
                file=(chunk_name, f.read()),
                model="whisper-large-v3",
                response_format="text"
            )
            full_transcript += response + " "
        
        os.remove(chunk_name) # chunk ဖျက်မယ်
        
    return full_transcript

# --- Bot Handler ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not ("youtube.com" in url or "youtu.be" in url):
        return

    user_id = update.message.from_user.id
    temp_audio = f"raw_audio_{user_id}.mp3"
    status_msg = await update.message.reply_text("⏳ စတင်နေပါပြီ...")

    try:
        # 1. Download Audio
        await status_msg.edit_text("📥 Audio ဒေါင်းလုဒ်ဆွဲနေသည်...")
        ydl_opts = {
            'format': 'worstaudio/worst',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '32',
            }],
            'outtmpl': f"raw_audio_{user_id}",
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 2. Chunking & Transcription
        await status_msg.edit_text("✂️ Audio အပိုင်းခွဲပြီး Transcript ထုတ်နေသည်...")
        final_text = process_audio_in_chunks(temp_audio)

        # 3. Send back
        if len(final_text) > 4000:
            for i in range(0, len(final_text), 4000):
                await update.message.reply_text(final_text[i:i+4000])
        else:
            await update.message.reply_text(f"📝 **Transcript:**\n\n{final_text}")
            
        await status_msg.delete()

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
    finally:
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

if __name__ == '__main__':
    threading.Thread(target=run_health_check, daemon=True).start()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
    
