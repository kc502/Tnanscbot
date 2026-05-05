import os
import subprocess
import numpy as np
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from faster_whisper import WhisperModel

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Render Free RAM အတွက် အသက်သာဆုံးဖြစ်အောင် tiny model ကို သုံးပါမယ်
print("Loading AI Model... Please wait.")
model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=1)

# --- Render Port Error Fix (Dummy Server) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- Bot Logic ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 မင်္ဂလာပါ။ YouTube link ပို့ပေးပါ။ Transcript ထုတ်ပေးပါမယ်။\n(Shorts များလည်း ရပါသည်)")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_url = update.message.text
    if "youtube.com" not in raw_url and "youtu.be" not in raw_url:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ မှန်ကန်သော YouTube Link ကိုသာ ပေးပို့ပါ။")
        return

    # Shorts Link ကို ပုံမှန် Link အဖြစ် ပြောင်းလဲခြင်း
    url = raw_url.replace("/shorts/", "/watch?v=")
    status_msg = await update.message.reply_text("⏳ ဗီဒီယိုကို ဖတ်နေပါတယ်။ ခဏစောင့်ပေးပါ...")

    try:
        # YouTube Block ကို ကျော်ရန် User-Agent နှင့် Referer များ ထည့်သွင်းထားသည့် Command
        cmd = (
            f'yt-dlp -o - -f ba --no-playlist --extract-audio --audio-format wav '
            f'--user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36" '
            f'--referer "https://www.google.com/" "{url}" | '
            f'ffmpeg -i pipe:0 -f s16le -acodec pcm_s16le -ar 16000 -ac 1 pipe:1'
        )
        
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        audio_data, _ = process.communicate()

        if not audio_data or len(audio_data) < 1000:
            await update.message.reply_text("❌ Audio data ဖတ်လို့မရပါဘူး။ YouTube က Block ထားတာ (သို့မဟုတ်) Link မှားနေတာ ဖြစ်နိုင်ပါတယ်။")
            return

        # Audio bytes ကို Whisper format ပြောင်းခြင်း
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcript ထုတ်ခြင်း
        segments, _ = model.transcribe(audio_np, beam_size=1)
        full_text = " ".join([segment.text for segment in segments]).strip()

        if not full_text:
            await update.message.reply_text("⚠️ ဗီဒီယိုထဲမှာ စကားပြောသံ ရှာမတွေ့ပါဘူး။")
        elif len(full_text) > 4000:
            with open("transcript.txt", "w", encoding="utf-8") as f:
                f.write(full_text)
            await update.message.reply_document(document=open("transcript.txt", "rb"), caption="📝 Transcript")
            os.remove("transcript.txt")
        else:
            await update.message.reply_text(f"📝 **Transcript:**\n\n{full_text}")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        await status_msg.delete()

# --- Main Run ---
def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is starting...")
    app.run_polling()

if __name__ == '__main__':
    main()
