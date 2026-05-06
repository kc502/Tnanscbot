import os
import subprocess
import numpy as np
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from faster_whisper import WhisperModel

# Render Environment Variables ထဲမှာ TELEGRAM_TOKEN ထည့်ထားပါ
TOKEN = os.getenv("TELEGRAM_TOKEN")

# RAM 512MB အတွက် အသက်သာဆုံးဖြစ်အောင် tiny model ကို သုံးပါမယ်
print("Loading Model...")
model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Render Worker Bot Online! YouTube Link ပို့ပေးပါ။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.replace("/shorts/", "/watch?v=")
    if "youtube.com" not in url and "youtu.be" not in url: return
    
    status = await update.message.reply_text("⏳ AI က စာသားပြောင်းနေပါတယ်။ ခဏစောင့်ပါ။")
    
    try:
        # YouTube Block ကျော်ရန် User-Agent ပါသော Command
        cmd = (
            f'yt-dlp -o - -f ba --no-playlist '
            f'--user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" '
            f'"{url}" | ffmpeg -i pipe:0 -f s16le -acodec pcm_s16le -ar 16000 -ac 1 pipe:1'
        )
        
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        audio_data, _ = process.communicate()
        
        if not audio_data:
            await update.message.reply_text("❌ Audio data ဖတ်လို့မရပါ။ (YouTube Blocked)")
            return

        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = model.transcribe(audio_np, beam_size=1)
        full_text = " ".join([segment.text for segment in segments]).strip()
        
        if len(full_text) > 4000:
            with open("result.txt", "w", encoding="utf-8") as f: f.write(full_text)
            await update.message.reply_document(document=open("result.txt", "rb"))
        else:
            await update.message.reply_text(f"📝 Transcript:\n\n{full_text if full_text else 'စကားပြောသံ ရှာမတွေ့ပါ။'}")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        await status.delete()

def main():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).connect_timeout(60).read_timeout(60).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Worker is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
