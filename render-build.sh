#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# ffmpeg ကို install လုပ်ခြင်း
apt-get update && apt-get install -y ffmpeg
