import os
import subprocess
import numpy as np
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from faster_whisper import WhisperModel

# Bot Token ကို Environment Variable ကနေယူမယ်
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Model ကို RAM သက်သာအောင် 'tiny' သုံးထားပါတယ် (Render Free အတွက်)
model = WhisperModel("tiny", device="cpu", compute_type="int8")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("YouTube Link ပို့ပေးပါ။ Transcript ထုတ်ပေးပါမယ်။")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("မှန်ကန်သော YouTube Link ပေးပါ။")
        return

    msg = await update.message.reply_text("အသံဖိုင်ကို ဖတ်နေပါတယ်။ ခဏစောင့်ပါ...")

    try:
        # Streaming Logic: yt-dlp + ffmpeg
        command = [
            'yt-dlp', '-o', '-', '-f', 'ba', url,
            '|', 
            'ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 'pipe:1'
        ]
        
        cmd_string = " ".join(command)
        process = subprocess.Popen(cmd_string, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        audio_data, _ = process.communicate()

        # Convert to numpy
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribe
        segments, _ = model.transcribe(audio_np, beam_size=5)
        text = "".join([segment.text for segment in segments])

        if len(text) > 4000:
            with open("transcript.txt", "w") as f:
                f.write(text)
            await update.message.reply_document(document=open("transcript.txt", "rb"))
        else:
            await update.message.reply_text(f"📝 Transcript:\n\n{text}")

    except Exception as e:
        await update.message.reply_text(f"Error ဖြစ်သွားပါတယ်: {str(e)}")
    finally:
        await msg.delete()

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()

