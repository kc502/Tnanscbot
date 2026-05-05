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
# Render Free RAM အတွက် tiny model ကို CPU ပေါ်မှာ အသက်သာဆုံး run ပါမယ်
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
    await update.message.reply_text("👋 မင်္ဂလာပါ။ YouTube link ပေးပို့ပြီး Transcript ထုတ်ယူနိုင်ပါပြီ။ (Shorts ဗီဒီယိုများလည်း ရပါသည်)")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_url = update.message.text
    
    # YouTube Link ဟုတ်မဟုတ် စစ်ဆေးခြင်း
    if "youtube.com" not in raw_url and "youtu.be" not in raw_url:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ မှန်ကန်သော YouTube Link ကိုသာ ပေးပို့ပါ။")
        return

    # Shorts Link ဖြစ်ပါက ပုံမှန် Link အဖြစ် ပြောင်းလဲခြင်း
    url = raw_url.replace("/shorts/", "/watch?v=")
    
    status_msg = await update.message.reply_text("⏳ ဗီဒီယိုကို ဖတ်နေပါတယ်။ ခဏစောင့်ပေးပါ...")

    try:
        # yt-dlp နဲ့ ffmpeg သုံးပြီး RAM ထဲသို့ audio stream ဖတ်ခြင်း
        command = [
            'yt-dlp', '-o', '-', '-f', 'ba', '--no-playlist', url,
            '|', 
            'ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 'pipe:1'
        ]
        
        cmd_string = " ".join(command)
        process = subprocess.Popen(cmd_string, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Audio data ဖတ်ယူခြင်း
        audio_data, error_data = process.communicate()

        if not audio_data:
            error_text = error_data.decode()
            await update.message.reply_text(f"❌ Audio ဖတ်လို့ မရပါဘူး။\nError: {error_text[:100]}")
            return

        # Bytes ကို Whisper ဖတ်နိုင်သော format သို့ ပြောင်းခြင်း
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcription စတင်ခြင်း
        segments, info = model.transcribe(audio_np, beam_size=1) # beam_size=1 က ပိုမြန်ပြီး RAM သက်သာစေသည်
        
        full_text = ""
        for segment in segments:
            full_text += f"{segment.text} "

        # ရလဒ် စစ်ဆေးခြင်း
        full_text = full_text.strip()
        
        if not full_text:
            await update.message.reply_text("⚠️ ဗီဒီယိုထဲမှာ စကားပြောသံ ရှာမတွေ့ပါဘူး။")
        elif len(full_text) > 4000:
            # စာသား အရမ်းရှည်လျှင် File အနေနဲ့ ပို့ပေးမယ်
            file_path = "transcript.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            await update.message.reply_document(document=open(file_path, "rb"), caption="📝 Transcript (File)")
            os.remove(file_path)
        else:
            await update.message.reply_text(f"📝 **Transcript:**\n\n{full_text}")

    except Exception as e:
        await update.message.reply_text(f"❌ အမှားအယွင်း ဖြစ်သွားပါသည်- {str(e)}")
    
    finally:
        await status_msg.delete()

# --- Main Run ---
def main():
    # Render Port Error ကို ကျော်ရန် Thread ခွဲပြီး Server အတု Run ခြင်း
    threading.Thread(target=run_health_server, daemon=True).start()

    # Telegram Bot စတင်ခြင်း
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is starting...")
    app.run_polling()

if __name__ == '__main__':
    main()
    
