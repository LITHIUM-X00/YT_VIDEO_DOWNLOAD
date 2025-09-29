import os
import sys
import subprocess
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ---------------- AUTO INSTALL ---------------- #
packages = [
    "aiogram==2.25.1",
    "pyrogram==2.0.106",
    "tgcrypto",
    "yt-dlp",
    "flask",
    "ffmpeg-python"
]

def install_packages():
    for package in packages:
        try:
            __import__(package.split("==")[0])
        except ImportError:
            print(f"📦 Installing: {package}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_packages()

# ---------------- FLASK SERVER ---------------- #
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7 🚀"

def run():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run).start()

# ---------------- TELEGRAM BOT ---------------- #
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Start command
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    name = message.from_user.first_name
    await message.reply(f"🙏 Namaste {name}! 👋\nSend me any YouTube link to download.")

# Handle YouTube link
@dp.message_handler(lambda message: "youtube.com" in message.text or "youtu.be" in message.text)
async def yt_link_handler(message: types.Message):
    url = message.text.strip()

    # Quality buttons (2 columns)
    keyboard = InlineKeyboardMarkup(row_width=2)
    qualities = ["144p", "240p", "360p", "480p", "720p", "1080p", "2K", "4K"]
    buttons = [InlineKeyboardButton(q, callback_data=f"quality:{q}:{url}") for q in qualities]
    keyboard.add(*buttons)

    await message.reply("✅ Select the video quality:", reply_markup=keyboard)

# Callback for quality selection
@dp.callback_query_handler(lambda c: c.data.startswith("quality:"))
async def process_quality(callback_query: types.CallbackQuery):
    _, quality, url = callback_query.data.split(":")

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "⏳ Please wait... Uploading process suru ho gaya 😊")

    # Download with yt-dlp
    out_file = f"video_{quality}.mp4"
    if "K" in quality:  # convert 2K/4K into px value
        height = "1440" if "2K" in quality else "2160"
    else:
        height = quality.replace("p", "")

    ydl_opts = {
        'format': f'bestvideo[height<={height}]+bestaudio/best',
        'outtmpl': out_file,
        'merge_output_format': 'mp4'
    }

    import yt_dlp
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except Exception as e:
            await bot.send_message(callback_query.from_user.id, f"❌ Error: {e}")
            return

    # Upload to Telegram
    try:
        await bot.send_video(callback_query.from_user.id, open(out_file, "rb"), caption=f"🎬 Your video in {quality}")
    except Exception as e:
        await bot.send_message(callback_query.from_user.id, f"❌ Upload error: {e}")
    finally:
        if os.path.exists(out_file):
            os.remove(out_file)

# ---------------- RUN BOT ---------------- #
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)