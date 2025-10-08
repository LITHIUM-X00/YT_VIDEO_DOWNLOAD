#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, tempfile, shutil, threading
from yt_dlp import YoutubeDL
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from config import API_ID, API_HASH, BOT_TOKEN, AUDIO_FORMAT
from telethon import TelegramClient

# ---------------- Telethon Setup (for 2GB uploads) ----------------
tele_client = None
try:
    if API_ID and API_HASH:
        tele_client = TelegramClient("bot_upload", API_ID, API_HASH)
        tele_client.start()
        print("⚙️ Telethon initialized successfully.")
    else:
        print("⚠️ Telethon skipped (missing API_ID/API_HASH).")
except Exception as e:
    print("❌ Telethon init failed:", e)
    tele_client = None

# ---------------- Helper Functions ----------------
def escape_html(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def progress_hook_factory(bot, chat_id, message_id):
    def hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            done = d.get('downloaded_bytes', 0)
            pct = int(done * 100 / total) if total else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            try:
                bot.edit_message_text(f"⏬ डाउनलोड: {bar} {pct}%", chat_id, message_id)
            except:
                pass
        elif d['status'] == 'finished':
            try:
                bot.edit_message_text("✅ डाउनलोड पूरा, अब अपलोड हो रहा है...", chat_id, message_id)
            except:
                pass
    return hook

# ---------------- Instant Response ----------------
USER_STATE = {}

def start(update: Update, context: CallbackContext):
    update.message.reply_text("🙏 नमस्ते! YouTube लिंक भेजें ताकि मैं वीडियो दिखा सकूं।")

def handle_message(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    chat_id = update.message.chat.id

    if "youtube.com" not in text and "youtu.be" not in text:
        update.message.reply_text("⚠️ कृपया सही YouTube लिंक भेजें।")
        return

    USER_STATE[chat_id] = {"url": text}

    # Instant thumbnail + UI using YouTube thumbnail pattern
    try:
        video_id = text.split("v=")[-1].split("&")[0] if "v=" in text else text.split("/")[-1]
        thumb_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    except:
        thumb_url = None

    buttons = []
    rows = ["144p","240p","360p","480p","720p","1080p","1440p","2160p"]
    for i in range(0, len(rows), 2):
        buttons.append([
            InlineKeyboardButton(rows[i], callback_data=f"q|{rows[i]}"),
            InlineKeyboardButton(rows[i+1], callback_data=f"q|{rows[i+1]}"),
        ])
    buttons.append([InlineKeyboardButton("🎵 MP3", callback_data="q|mp3")])

    caption = f"🎬 <b>वीडियो लिंक मिला!</b>\n🔗 <code>{text}</code>\n\nकृपया क्वालिटी चुनें 👇"
    if thumb_url:
        update.message.reply_photo(thumb_url, caption=caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        update.message.reply_text(caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

def download_and_send(context, chat_id, url, quality):
    bot = context.bot
    msg = bot.send_message(chat_id, "📥 डाउनलोड शुरू कर रहा हूँ...")

    tmpdir = tempfile.mkdtemp()
    outtmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")

    if quality == "mp3":
        ydl_format = "bestaudio/best"
        postproc = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": AUDIO_FORMAT,
            "preferredquality": "192"
        }]
    else:
        ydl_format = f"bestvideo[height<={quality[:-1]}]+bestaudio/best"
        postproc = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]

    opts = {
        "format": ydl_format,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "progress_hooks": [progress_hook_factory(bot, chat_id, msg.message_id)],
        "postprocessors": postproc,
        "quiet": True
    }

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if quality == "mp3":
                filename = os.path.splitext(filename)[0] + f".{AUDIO_FORMAT}"
    except Exception as e:
        bot.send_message(chat_id, f"❌ डाउनलोड विफल: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        return

    caption = f"✅ डाउनलोड पूरा!\n🎬 {info.get('title')}\n📦 {quality}\n🔗 {url}"

    try:
        if tele_client:
            tele_client.send_file(int(chat_id), filename, caption=caption)
        else:
            bot.send_document(chat_id, open(filename, "rb"), caption=caption)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ अपलोड विफल: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def quality_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    quality = query.data.split("|")[1]
    chat_id = query.message.chat.id
    url = USER_STATE.get(chat_id, {}).get("url")
    if not url:
        query.message.reply_text("⚠️ पहले लिंक भेजें।")
        return
    query.message.reply_text(f"🎬 {quality} चयनित — कृपया प्रतीक्षा करें...")
    threading.Thread(target=download_and_send, args=(context, chat_id, url, quality)).start()

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(quality_callback))
    updater.start_polling()
    print("✅ Fast YouTube Bot चालू हो गया है…")
    updater.idle()

if __name__ == "__main__":
    main()
