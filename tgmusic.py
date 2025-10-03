"""
Telegram music copier — Telethon userbot with resume support (Windows-friendly)

✅ Features:
  - Forward only music/audio (skip voices)
  - Duplicate check via unique_id (seen.json)
  - Resume progress per channel after shutdown/reboot (progress.json)
  - Auto-retry on disconnects
  - FloodWaitError prompt → asks Y/N if you want to wait or stop
  - Progress & seen saved before exit
  - Logs to console + musiccopier.log
  - Bot commands: /pause, /resume, /status (owner-only)
  - START_MODE=oldest or latest in .env
  - Greeting + channel info in console
  - Telegram notification only at START and END (no spam)
"""

import os
import asyncio
import logging
import json
import sys
import time
from dotenv import load_dotenv
from telethon import TelegramClient, events, errors
from telethon.tl.types import MessageMediaDocument

# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID") or 0)
API_HASH = os.getenv("API_HASH")
SOURCE = os.getenv("SOURCE")
DEST = os.getenv("DEST")
BACKFILL = os.getenv("BACKFILL", "False").lower() in ("1", "true", "yes")
OWNER_ID = int(os.getenv("OWNER_ID") or 0)
START_MODE = os.getenv("START_MODE", "latest").lower()  # oldest or latest

if not API_ID or not API_HASH or not SOURCE or not DEST or not OWNER_ID:
    raise SystemExit("Please set API_ID, API_HASH, SOURCE, DEST, OWNER_ID in .env file")

# Logging (console + file)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("musiccopier.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# Progress & duplicates
PROGRESS_FILE = "progress.json"
SEEN_FILE = "seen.json"

def load_progress(channel_id: int) -> int:
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
                return data.get(str(channel_id), {}).get("last_id", 0)
        except Exception:
            return 0
    return 0

def save_progress(channel_id: int, last_id: int):
    data = {}
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[str(channel_id)] = {"last_id": last_id}
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning("Could not save progress: %s", e)

def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except Exception as e:
        logger.warning("Could not save seen file: %s", e)

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE) as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

# State variables
paused = False
forwarded_count = 0
seen_ids = load_seen()

# Create the client
client = TelegramClient("session", API_ID, API_HASH)

# Filter: music/audio only (skip voices)
def is_audio_message(message):
    if message is None:
        return False
    if getattr(message, "voice", None):  # skip voice
        return False
    if getattr(message, "audio", None):
        return True
    doc = getattr(message, "document", None)
    if isinstance(doc, MessageMediaDocument) or doc is not None:
        mime = getattr(doc, "mime_type", "") or ""
        if mime.startswith("audio/"):
            return True
        fname = getattr(doc, "file_name", "") or ""
        if any(fname.lower().endswith(ext) for ext in (".mp3", ".m4a", ".flac", ".ogg", ".wav", ".aac", ".amr")):
            return True
    return False

async def handle_message(msg, save_every=10):
    global forwarded_count, seen_ids, paused
    if paused:
        return
    if not is_audio_message(msg):
        return

    unique_id = None
    if msg.media and getattr(msg.media, "document", None):
        unique_id = msg.media.document.id  # Telethon's unique document id

    if unique_id and unique_id in seen_ids:
        logger.info("Skipping duplicate id=%s", msg.id)
        return

    while True:
        try:
            logger.info("Forwarding id=%s...", msg.id)
            await client.forward_messages(DEST, msg)

            forwarded_count += 1
            if unique_id:
                seen_ids.add(unique_id)

            # Save progress every batch (console log only, no Telegram spam)
            if forwarded_count % save_every == 0:
                save_progress(msg.chat_id, msg.id)
                save_seen(seen_ids)
                logger.info("Progress saved at id=%s (batch)", msg.id)
            break  # success, exit while

        except errors.FloodWaitError as fw:
            wait_time = fw.seconds
            logger.warning(f"FloodWaitError: wait {wait_time} seconds")
            choice = input(f"Do you want to wait {wait_time} seconds to continue? (Y/N): ").strip().lower()
            if choice == "y":
                logger.info(f"⏳ Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                logger.info("Resuming forwarding...")
            else:
                logger.info("👋 Bot stopped. Please run again later.")
                save_progress(msg.chat_id, msg.id)
                save_seen(seen_ids)
                sys.exit(0)
        except Exception as err:
            logger.exception("Error processing message id=%s: %s", msg.id, err)
            break

# Real-time listener
@client.on(events.NewMessage(chats=SOURCE))
async def handler(event):
    await handle_message(event.message)

# Bot commands (/pause, /resume, /status)
@client.on(events.NewMessage(pattern=r"/(pause|resume|status)"))
async def commands(event):
    global paused
    if event.sender_id != OWNER_ID:
        return
    cmd = event.raw_text.strip().lower()
    if cmd == "/pause":
        paused = True
        await event.reply("⏸️ Copier paused")
        save_progress(event.chat_id, load_progress(event.chat_id))
        save_seen(seen_ids)
    elif cmd == "/resume":
        paused = False
        await event.reply("▶️ Copier resumed")
    elif cmd == "/status":
        last_id = load_progress(event.chat_id)
        await event.reply(f"📊 Status:\nPaused: {paused}\nForwarded: {forwarded_count}\nLast ID: {last_id}")

async def backfill():
    src = await client.get_entity(SOURCE)
    last_id = load_progress(src.id)
    if START_MODE == "latest" and last_id == 0:
        logger.info("START_MODE=latest → skipping backfill, only listening for new messages.")
        return
    if START_MODE == "oldest" or last_id > 0:
        if last_id == 0:
            logger.info(f"New channel detected → starting from scratch ({src.title})")
        else:
            logger.info(f"Resuming {src.title} from id > {last_id}")
        async for message in client.iter_messages(SOURCE, reverse=True, min_id=last_id):
            await handle_message(message)
            save_progress(src.id, message.id)
        save_seen(seen_ids)
        logger.info("Backfill complete")

        # Send a single Telegram message with summary
        await client.send_message(OWNER_ID, f"✅ Backfill completed.\nForwarded {forwarded_count} music messages.")

async def main():
    await client.start()
    me = await client.get_me()
    src = await client.get_entity(SOURCE)
    dst = await client.get_entity(DEST)

    # Greet in console
    logger.info("👋 Hi %s! (id=%s)", me.username or me.first_name, me.id)
    logger.info("Forwarding from: %s (id=%s)", getattr(src, 'title', getattr(src, 'username', 'Unknown')), src.id)
    logger.info("Forwarding to:   %s (id=%s)", getattr(dst, 'title', getattr(dst, 'username', 'Unknown')), dst.id)
    logger.info("Mode: START_MODE=%s | BACKFILL=%s", START_MODE, BACKFILL)

    # Send starting notification to OWNER_ID
    await client.send_message(
        OWNER_ID,
        f"🚀 Started forwarding from {getattr(src, 'title', getattr(src, 'username', 'Unknown'))} → {getattr(dst, 'title', getattr(dst, 'username', 'Unknown'))}"
    )

    if BACKFILL:
        await backfill()

    logger.info("Listening for new messages... Press Ctrl+C to stop")
    await client.run_until_disconnected()

if __name__ == "__main__":
    while True:  # auto-retry loop
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Stopped by user")
            break
        except Exception as e:
            logger.exception("Fatal error: %s. Restarting in 30s...", e)
            time.sleep(30)
