# Telegram Music Copier 🎶

A **Telethon-based userbot** that copies/forwards music and audio messages from one Telegram channel/group to another, with **resume support** and **duplicate prevention**.

---

## ✨ Features
- ✅ Forwards only **music/audio files** (skips voice messages)
- ✅ **Duplicate check** via unique file IDs (`seen.json`)
- ✅ **Resume progress** after shutdown/restart (`progress.json`)
- ✅ **Auto-retry** on disconnects
- ✅ Handles `FloodWaitError` gracefully (asks if you want to wait or exit)
- ✅ Saves progress & seen state before exit
- ✅ Logs to console and `musiccopier.log`
- ✅ Owner-only bot commands:
  - `/pause` → pause forwarding
  - `/resume` → resume forwarding
  - `/status` → check stats
- ✅ Configurable `START_MODE`:
  - `oldest` → copy everything from the beginning
  - `latest` → only new messages
- ✅ Sends start & completion notification to the bot owner
- ✅ Windows-friendly

---

## ⚙️ Setup

### 1. Clone repository
```bash
git clone https://github.com/saeidshirazi/tgmusic-copier.git
cd tgmusic-copier
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

(Minimum required: `telethon`, `python-dotenv`)

### 3. Configure `.env` file
Create a `.env` file in the root folder with the following values:

```ini
API_ID=your_api_id
API_HASH=your_api_hash
SOURCE=source_channel_or_group
DEST=destination_channel_or_group
BACKFILL=True
OWNER_ID=your_telegram_user_id
START_MODE=oldest   # oldest | latest
```

- **API_ID / API_HASH** → get from [my.telegram.org](https://my.telegram.org/apps)
- **SOURCE** → source chat username or ID
- **DEST** → destination chat username or ID
- **OWNER_ID** → your own Telegram user ID
- **BACKFILL** → `True` = copy past messages, `False` = only new ones
- **START_MODE** → `oldest` or `latest`

---

## 🚀 Run

```bash
python tgmusic.py
```

- First run will prompt for Telegram login (saved as `session.session`)
- Use `/pause`, `/resume`, `/status` commands in Telegram (owner only)

---

## 📂 Files generated
- `musiccopier.log` → runtime logs
- `progress.json` → stores last processed message ID per channel
- `seen.json` → keeps track of forwarded files to avoid duplicates
- `session.session` → Telethon session file

---

## 🛑 Stop
Press `Ctrl + C` to stop safely. Progress and seen state are saved automatically.
