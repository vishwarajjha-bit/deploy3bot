Deploy Bot v4.2 (Sticker Pack Auto-Fetch + Premium Emoji Suite + venv Shell + Admin Panel)
================================================================================================

1. Extract this ZIP file on your AWS EC2 Linux server or local machine.
2. Install dependencies for the Deploy Bot itself:
   pip install -r requirements.txt
3. Open main.py (or set environment variables) and set:
   - BOT_TOKEN (created via BotFather)
   - OWNER_IDS (your numeric Telegram user ID; 8710593064 is included by default)
   - STICKER_PACK_NAME (optional; default "Animals" or any public Telegram sticker set short name, e.g., from t.me/addstickers/<name>)
   - WELCOME_STICKER_ID (optional; if set, sends that exact sticker file_id)
   - PREMIUM_EMOJI_IDS (optional; custom_emoji_id strings for premium custom emojis)
4. Start the deploy bot:
   python main.py
5. Features:
   - Automatically fetches a sticker from STICKER_PACK_NAME via Telegram Bot API (getStickerSet) on /start or /panel (with safe fallback if pack is unavailable).
   - Premium Custom Emojis in messages & buttons (with clean unicode fallback).
   - PM Panel with "Add Admin" and "Manage Admins" to grant/revoke control access.
   - "venv Shell" & "/venv <bot_name> <command>" to run pip or commands inside any hosted bot's isolated virtual environment without SSH.
   - Upload .py or .zip files directly in PM to create a venv, install dependencies, and start the bot.
