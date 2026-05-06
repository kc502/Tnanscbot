FROM python:3.10-slim

# FFmpeg သွင်းခြင်း (Audio အပိုင်းခွဲဖို့ မရှိမဖြစ် လိုအပ်ပါတယ်)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bot ကို စတင် run မယ့် command
CMD ["python", "main.py"]

