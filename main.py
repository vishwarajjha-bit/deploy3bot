import html
import os
import random
import re
import zipfile
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import database as db
import runner

# ==============================================================================
# PREMIUM CONFIGURATION, STICKER PACK AUTO-FETCH & CUSTOM EMOJI SUITE
# ==============================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
OWNER_IDS = [8710593064]

# Optional direct sticker file_id; if empty, the bot fetches a sticker from STICKER_PACK_NAME
# via Telegram's getStickerSet API automatically and caches its file_id in memory.
WELCOME_STICKER_ID = os.getenv("WELCOME_STICKER_ID", "").strip()

# Public Telegram sticker pack short names (from https://t.me/addstickers/<pack_name>)
STICKER_PACK_CANDIDATES = [
    os.getenv("STICKER_PACK_NAME", "").strip(),
    "HotCherry",
    "Animals",
]

CACHED_STICKER_IDS = []

# Optional Telegram Premium custom_emoji_id strings (falls back cleanly to Unicode emojis)
PREMIUM_EMOJI_IDS = {
    "crown": os.getenv("PE_CROWN", ""),
    "spark": os.getenv("PE_SPARK", ""),
    "rocket": os.getenv("PE_ROCKET", ""),
    "terminal": os.getenv("PE_TERMINAL", ""),
    "shield": os.getenv("PE_SHIELD", ""),
    "logs": os.getenv("PE_LOGS", ""),
    "trash": os.getenv("PE_TRASH", ""),
    "refresh": os.getenv("PE_REFRESH", ""),
    "bolt": os.getenv("PE_BOLT", ""),
    "bot": os.getenv("PE_BOT", ""),
    "check": os.getenv("PE_CHECK", ""),
    "lock": os.getenv("PE_LOCK", ""),
}

FALLBACK_EMOJIS = {
    "crown": "👑",
    "spark": "✨",
    "rocket": "🚀",
    "terminal": "💻",
    "shield": "🛡️",
    "logs": "📜",
    "trash": "🗑️",
    "refresh": "🔄",
    "bolt": "⚡",
    "bot": "🤖",
    "check": "✅",
    "lock": "🔒",
}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
db.init_db()
db.seed_owners(OWNER_IDS)

PENDING_STATES = {}


def is_owner(user_id):
    return int(user_id) in {int(x) for x in OWNER_IDS}


def is_admin(user_id):
    return db.is_authorized(user_id, OWNER_IDS)


def pe(key):
    """Returns HTML <tg-emoji> tag when custom_emoji_id is configured, else fallback emoji."""
    fb = FALLBACK_EMOJIS.get(key, "✦")
    eid = (PREMIUM_EMOJI_IDS.get(key) or "").strip()
    if eid:
        return f'<tg-emoji emoji-id="{html.escape(eid)}">{fb}</tg-emoji>'
    return fb


def get_welcome_sticker_id():
    """Resolves a sticker file_id from config or Telegram getStickerSet API."""
    if WELCOME_STICKER_ID:
        return WELCOME_STICKER_ID

    if CACHED_STICKER_IDS:
        return random.choice(CACHED_STICKER_IDS)

    for pack_name in STICKER_PACK_CANDIDATES:
        name = (pack_name or "").strip()
        if not name:
            continue
        try:
            sticker_set = bot.get_sticker_set(name)
            stickers = getattr(sticker_set, "stickers", None) or []
            ids = [s.file_id for s in stickers if getattr(s, "file_id", None)]
            if ids:
                CACHED_STICKER_IDS.extend(ids[:15])
                return random.choice(CACHED_STICKER_IDS)
        except Exception:
            continue

    return ""


def send_welcome_sticker(chat_id):
    sid = get_welcome_sticker_id()
    if not sid:
        return
    try:
        bot.send_sticker(chat_id, sid)
    except Exception:
        pass


def styled_btn(text, callback_data=None, url=None, style=None, icon_key=None):
    """
    Builds an InlineKeyboardButton with optional Telegram colored style
    ('success', 'primary', 'danger') and custom emoji icon when supported.
    """
    kwargs = {"text": text}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url

    eid = (PREMIUM_EMOJI_IDS.get(icon_key) or "").strip() if icon_key else ""
    extra_attempts = []
    if eid:
        extra_attempts.append({"icon_custom_emoji_id": eid})
    extra_attempts.append({})

    for extra in extra_attempts:
        merged = dict(kwargs)
        merged.update(extra)
        if style in {"success", "primary", "danger"}:
            try:
                return InlineKeyboardButton(style=style, **merged)
            except TypeError:
                pass
        try:
            return InlineKeyboardButton(**merged)
        except TypeError:
            continue
    return InlineKeyboardButton(**kwargs)


def pm_panel_keyboard(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        styled_btn("Hosted Bots", callback_data="panel|bots", style="primary", icon_key="bot"),
        styled_btn("Deploy Guide", callback_data="panel|guide", style="success", icon_key="bolt"),
    )
    if is_owner(user_id):
        markup.add(
            styled_btn("Add Admin", callback_data="admin|add", style="success", icon_key="crown"),
            styled_btn("Manage Admins", callback_data="admin|list", style="primary", icon_key="shield"),
        )
    markup.add(
        styled_btn("Refresh Suite", callback_data="panel|home", style="primary", icon_key="refresh"),
    )
    return markup


def bot_control_keyboard(bot_name, is_running_now):
    markup = InlineKeyboardMarkup(row_width=2)
    if is_running_now:
        markup.add(
            styled_btn("Stop", callback_data=f"stop|{bot_name}", style="danger", icon_key="lock"),
            styled_btn("Restart", callback_data=f"restart|{bot_name}", style="primary", icon_key="refresh"),
        )
    else:
        markup.add(
            styled_btn("Launch Bot", callback_data=f"start|{bot_name}", style="success", icon_key="rocket"),
        )
    markup.add(
        styled_btn("venv Shell", callback_data=f"venv|{bot_name}", style="success", icon_key="terminal"),
        styled_btn("Live Logs", callback_data=f"logs|{bot_name}", style="primary", icon_key="logs"),
    )
    markup.add(
        styled_btn("Clear Logs", callback_data=f"clearlogs|{bot_name}", style="primary", icon_key="spark"),
        styled_btn("Delete Bot", callback_data=f"delete|{bot_name}", style="danger", icon_key="trash"),
    )
    markup.add(
        styled_btn("Back to Fleet", callback_data="panel|bots", style="primary", icon_key="bot"),
    )
    return markup


def build_welcome_caption():
    return (
        f"╔══════════════════════════════╗\n"
        f"   {pe('spark')} <b>AETHER DEPLOY SUITE</b> {pe('spark')}\n"
        f"╚══════════════════════════════╝\n"
        f"<i>Signature Cloud Bot Command Deck</i>\n\n"
        f"<blockquote>“Crafted for speed, precision, and effortless control.”</blockquote>\n\n"
        f"{pe('rocket')} <b>Zero-Friction Deploy:</b> Drop any <code>.py</code> or <code>.zip</code> — isolated <code>venv</code>, auto-deps &amp; instant launch.\n"
        f"{pe('terminal')} <b>venv Command Core:</b> Run <code>pip</code> or shell commands inside a bot's <code>venv</code> without SSH.\n"
        f"{pe('crown')} <b>Admin Vault:</b> Grant or revoke co-admin control straight from PM.\n\n"
        f"{pe('bolt')} <i>Pick an option below or send a bot archive to begin.</i>"
    )


def send_styled_message(chat_id, text, reply_markup=None, reply_to_id=None):
    kwargs = {"reply_markup": reply_markup}
    if reply_to_id:
        kwargs["reply_to_message_id"] = reply_to_id
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception:
        clean_text = re.sub(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", r"\1", text)
        return bot.send_message(chat_id, clean_text, **kwargs)


def edit_styled_message(chat_id, message_id, text, reply_markup=None):
    try:
        return bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup)
    except Exception:
        clean_text = re.sub(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", r"\1", text)
        return bot.edit_message_text(clean_text, chat_id, message_id, reply_markup=reply_markup)


@bot.message_handler(commands=["start", "panel"])
def send_welcome(message):
    if not is_admin(message.from_user.id):
        return send_styled_message(
            message.chat.id,
            f"{pe('lock')} <b>Restricted Access</b>\n<i>Only authorized commanders may enter this suite.</i>",
            reply_to_id=message.message_id,
        )
    PENDING_STATES.pop(message.from_user.id, None)
    send_welcome_sticker(message.chat.id)
    send_styled_message(
        message.chat.id,
        build_welcome_caption(),
        reply_markup=pm_panel_keyboard(message.from_user.id),
    )


@bot.message_handler(commands=["addadmin"])
def cmd_add_admin(message):
    if not is_owner(message.from_user.id):
        return send_styled_message(
            message.chat.id,
            f"{pe('crown')} <b>Owner Only</b> — only primary owners can add admins.",
            reply_to_id=message.message_id,
        )
    parts = (message.text or "").strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        return send_styled_message(
            message.chat.id,
            f"{pe('spark')} <b>Usage:</b> <code>/addadmin &lt;telegram_user_id&gt;</code>\n<i>Example:</i> <code>/addadmin 123456789</code>",
            reply_to_id=message.message_id,
        )
    target_id = int(parts[1])
    db.add_admin(target_id, message.from_user.id, role="admin")
    send_styled_message(
        message.chat.id,
        f"{pe('check')} <b>Admin Authorized</b>\n<blockquote>User <code>{target_id}</code> can now deploy bots, view logs &amp; run <code>venv</code> commands.</blockquote>",
        reply_to_id=message.message_id,
    )


@bot.message_handler(commands=["bots"])
def list_bots_cmd(message):
    if not is_admin(message.from_user.id):
        return
    render_bots_list(message.chat.id)


@bot.message_handler(commands=["venv"])
def cmd_venv(message):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    parts = raw.split(maxsplit=2)
    if len(parts) < 3:
        return send_styled_message(
            message.chat.id,
            f"{pe('terminal')} <b>venv Command Syntax</b>\n"
            f"<code>/venv &lt;bot_name&gt; &lt;command&gt;</code>\n"
            f"<i>Examples:</i>\n"
            f"• <code>/venv vcBot pip install yt-dlp</code>\n"
            f"• <code>/venv vcBot pip list</code>\n"
            f"• <code>/venv vcBot python -m pip check</code>",
            reply_to_id=message.message_id,
        )
    _, bot_name, shell_cmd = parts
    if not db.get_bot(bot_name):
        return send_styled_message(
            message.chat.id,
            f"{pe('lock')} Bot <code>{html.escape(bot_name)}</code> not found.",
            reply_to_id=message.message_id,
        )

    wait_msg = send_styled_message(
        message.chat.id,
        f"{pe('bolt')} <i>Running inside <code>{html.escape(bot_name)}</code> venv...</i>\n<code>{html.escape(shell_cmd)}</code>",
        reply_to_id=message.message_id,
    )
    _, output_raw = runner.run_in_venv(bot_name, shell_cmd)
    clean_block = output_raw.replace("```", "").strip()
    edit_styled_message(
        message.chat.id,
        wait_msg.message_id,
        f"{pe('terminal')} <b>venv Output — <code>{html.escape(bot_name)}</code></b>\n"
        f"<b>Cmd:</b> <code>{html.escape(shell_cmd)}</code>\n"
        f"<pre>{html.escape(clean_block)}</pre>",
    )


def render_bots_list(chat_id, message_id=None):
    bots = db.get_all_bots()
    if not bots:
        text = (
            f"{pe('spark')} <b>Fleet Is Empty</b>\n"
            f"<blockquote>Send any <code>.py</code> or <code>.zip</code> archive to deploy your first bot.</blockquote>"
        )
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(styled_btn("Back to Suite", callback_data="panel|home", style="primary", icon_key="spark"))
    else:
        text = (
            f"╔══════════════════════════════╗\n"
            f"   {pe('bot')} <b>HOSTED BOT FLEET</b> {pe('bot')}\n"
            f"╚══════════════════════════════╝\n"
            f"<i>Select a bot to control, view logs, or run <code>venv</code> commands.</i>"
        )
        kb = InlineKeyboardMarkup(row_width=1)
        for name, _, _, pid, _ in bots:
            active = runner.is_running(name, saved_pid=pid)
            status_tag = "🟢" if active else "🔴"
            kb.add(
                styled_btn(
                    f"{status_tag} {name}",
                    callback_data=f"manage|{name}",
                    style="success" if active else "primary",
                    icon_key="rocket" if active else "bot",
                )
            )
        kb.add(styled_btn("Back to Suite", callback_data="panel|home", style="primary", icon_key="spark"))

    if message_id:
        edit_styled_message(chat_id, message_id, text, reply_markup=kb)
    else:
        send_styled_message(chat_id, text, reply_markup=kb)


def find_main_script(folder_path):
    priority = ["vcBot.py", "main.py", "bot.py", "app.py", "run.py"]
    for p in priority:
        cand = os.path.join(folder_path, p)
        if os.path.isfile(cand):
            return cand

    for item in sorted(os.listdir(folder_path)):
        sub = os.path.join(folder_path, item)
        if os.path.isdir(sub) and item != "venv":
            for p in priority:
                cand = os.path.join(sub, p)
                if os.path.isfile(cand):
                    return cand

    for root, _, files in os.walk(folder_path):
        if "venv" in root.split(os.sep):
            continue
        for f in sorted(files):
            if f.endswith(".py"):
                return os.path.join(root, f)
    return None


@bot.message_handler(content_types=["document"])
def handle_file_upload(message):
    if not is_admin(message.from_user.id):
        return

    doc = message.document
    fname = doc.file_name or "uploaded_bot.py"
    caption = (message.caption or "").strip()

    if caption.startswith("/add "):
        target_bot = caption.split(" ", 1)[1].strip()
        bot_row = db.get_bot(target_bot)
        if not bot_row:
            return send_styled_message(
                message.chat.id,
                f"{pe('lock')} Bot <code>{html.escape(target_bot)}</code> not found!",
                reply_to_id=message.message_id,
            )
        base_dir, _, _, _, _, _ = runner.get_bot_paths(target_bot)
        os.makedirs(base_dir, exist_ok=True)
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        save_path = os.path.join(base_dir, fname)
        with open(save_path, "wb") as f:
            f.write(downloaded)
        return send_styled_message(
            message.chat.id,
            f"{pe('check')} <b>Module Attached</b>\nSaved <code>{html.escape(fname)}</code> inside <code>{html.escape(target_bot)}</code>.\n<i>Restart the bot to load changes.</i>",
            reply_to_id=message.message_id,
        )

    if not (fname.endswith(".py") or fname.endswith(".zip")):
        return send_styled_message(
            message.chat.id,
            f"{pe('bolt')} Please upload a <code>.py</code> or <code>.zip</code> file.",
            reply_to_id=message.message_id,
        )

    bot_name = os.path.splitext(fname)[0]
    status_msg = send_styled_message(
        message.chat.id,
        f"{pe('rocket')} <b>Receiving Archive:</b> <code>{html.escape(fname)}</code>...",
        reply_to_id=message.message_id,
    )

    try:
        existing = db.get_bot(bot_name)
        saved_pid = existing[3] if existing else None
        runner.stop_bot(bot_name, saved_pid=saved_pid)

        base_dir, _, _, _, _, _ = runner.get_bot_paths(bot_name)
        os.makedirs(base_dir, exist_ok=True)

        file_info = bot.get_file(doc.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        if fname.endswith(".zip"):
            zip_path = os.path.join(base_dir, fname)
            with open(zip_path, "wb") as f:
                f.write(downloaded_file)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(base_dir)
            os.remove(zip_path)
            script_path = find_main_script(base_dir)
            if not script_path:
                return edit_styled_message(
                    message.chat.id,
                    status_msg.message_id,
                    f"{pe('lock')} No runnable <code>.py</code> file found inside the ZIP.",
                )
        else:
            script_path = os.path.join(base_dir, fname)
            with open(script_path, "wb") as f:
                f.write(downloaded_file)

        db.add_bot(bot_name, script_path, entry_script=script_path)

        edit_styled_message(
            message.chat.id,
            status_msg.message_id,
            f"{pe('bolt')} <b>Building Environment — <code>{html.escape(bot_name)}</code></b>\n<i>Setting up isolated <code>venv</code> &amp; installing packages...</i>",
        )
        installed, failed = runner.install_dependencies(bot_name, script_path)

        ok, msg = runner.start_bot(bot_name, script_path)
        pid_val = None
        if ok and bot_name in runner.RUNNING_PROCESSES:
            pid_val = runner.RUNNING_PROCESSES[bot_name][0].pid
        db.update_status(bot_name, "running" if ok else "stopped", pid=pid_val)

        inst_txt = ", ".join(installed) if installed else "Standard / Already Present"
        fail_txt = f"\n{pe('bolt')} <b>Failed/Skipped:</b> <code>{html.escape(', '.join(failed))}</code>" if failed else ""
        running_now = runner.is_running(bot_name, saved_pid=pid_val)

        edit_styled_message(
            message.chat.id,
            status_msg.message_id,
            f"{pe('spark')} <b>DEPLOYMENT COMPLETE</b> {pe('spark')}\n"
            f"• <b>Bot:</b> <code>{html.escape(bot_name)}</code>\n"
            f"• <b>Packages:</b> <code>{html.escape(inst_txt)}</code>{fail_txt}\n"
            f"• <b>Runtime:</b> {html.escape(msg)}",
            reply_markup=bot_control_keyboard(bot_name, running_now),
        )

    except Exception as e:
        edit_styled_message(
            message.chat.id,
            status_msg.message_id,
            f"{pe('lock')} <b>Deployment Failed</b>\n<code>{html.escape(str(e))}</code>",
        )


@bot.message_handler(func=lambda m: m.from_user and m.from_user.id in PENDING_STATES)
def handle_pending_input(message):
    uid = message.from_user.id
    state = PENDING_STATES.get(uid)
    if not state:
        return
    if not is_admin(uid):
        PENDING_STATES.pop(uid, None)
        return

    text = (message.text or "").strip()
    mode = state.get("mode")

    if mode == "add_admin":
        if not is_owner(uid):
            PENDING_STATES.pop(uid, None)
            return send_styled_message(message.chat.id, f"{pe('crown')} Owner privilege required.", reply_to_id=message.message_id)
        if not text.isdigit():
            return send_styled_message(message.chat.id, f"{pe('bolt')} Send a valid numeric Telegram User ID.", reply_to_id=message.message_id)
        target_id = int(text)
        db.add_admin(target_id, uid, role="admin")
        PENDING_STATES.pop(uid, None)
        send_styled_message(
            message.chat.id,
            f"{pe('check')} <b>New Admin Added</b>\n<blockquote>ID <code>{target_id}</code> can now deploy &amp; control bots.</blockquote>",
            reply_markup=pm_panel_keyboard(uid),
            reply_to_id=message.message_id,
        )

    elif mode == "remove_admin":
        if not is_owner(uid):
            PENDING_STATES.pop(uid, None)
            return send_styled_message(message.chat.id, f"{pe('crown')} Owner privilege required.", reply_to_id=message.message_id)
        if not text.isdigit():
            return send_styled_message(message.chat.id, f"{pe('bolt')} Send a valid numeric Telegram User ID.", reply_to_id=message.message_id)
        target_id = int(text)
        if is_owner(target_id):
            return send_styled_message(message.chat.id, f"{pe('shield')} Primary owners cannot be removed.", reply_to_id=message.message_id)
        removed = db.remove_admin(target_id)
        PENDING_STATES.pop(uid, None)
        if removed:
            send_styled_message(
                message.chat.id,
                f"{pe('trash')} <b>Admin Revoked</b>\n<blockquote>Removed <code>{target_id}</code> from admin roster.</blockquote>",
                reply_markup=pm_panel_keyboard(uid),
                reply_to_id=message.message_id,
            )
        else:
            send_styled_message(
                message.chat.id,
                f"{pe('spark')} User <code>{target_id}</code> was not in the admin list.",
                reply_markup=pm_panel_keyboard(uid),
                reply_to_id=message.message_id,
            )

    elif mode == "venv_cmd":
        bot_name = state.get("bot_name")
        PENDING_STATES.pop(uid, None)
        wait_msg = send_styled_message(
            message.chat.id,
            f"{pe('terminal')} <i>Executing in <code>{html.escape(bot_name)}</code> venv...</i>\n<code>{html.escape(text)}</code>",
            reply_to_id=message.message_id,
        )
        _, out_raw = runner.run_in_venv(bot_name, text)
        clean_block = out_raw.replace("```", "").strip()
        bot_row = db.get_bot(bot_name)
        saved_pid = bot_row[3] if bot_row else None
        running_now = runner.is_running(bot_name, saved_pid=saved_pid)
        edit_styled_message(
            message.chat.id,
            wait_msg.message_id,
            f"{pe('terminal')} <b>venv Result — <code>{html.escape(bot_name)}</code></b>\n"
            f"<b>Cmd:</b> <code>{html.escape(text)}</code>\n"
            f"<pre>{html.escape(clean_block)}</pre>",
            reply_markup=bot_control_keyboard(bot_name, running_now),
        )


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    if not is_admin(uid):
        return bot.answer_callback_query(call.id, "Access Denied!", show_alert=True)

    data = call.data or ""
    if "|" not in data:
        return bot.answer_callback_query(call.id)

    section, payload = data.split("|", 1)

    if section == "panel":
        PENDING_STATES.pop(uid, None)
        if payload == "home":
            edit_styled_message(
                call.message.chat.id,
                call.message.message_id,
                build_welcome_caption(),
                reply_markup=pm_panel_keyboard(uid),
            )
        elif payload == "bots":
            render_bots_list(call.message.chat.id, message_id=call.message.message_id)
        elif payload == "guide":
            guide_txt = (
                f"{pe('bolt')} <b>QUICK DEPLOY &amp; VENV GUIDE</b> {pe('bolt')}\n\n"
                f"1. {pe('rocket')} Send any <code>.py</code> or <code>.zip</code> in PM to deploy.\n"
                f"2. {pe('spark')} Send a file with caption <code>/add bot_name</code> to attach extra files.\n"
                f"3. {pe('terminal')} Open a bot &rarr; tap <b>venv Shell</b> or run <code>/venv bot_name pip install pkg</code>.\n"
                f"4. {pe('crown')} Tap <b>Add Admin</b> in PM to grant control rights."
            )
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(styled_btn("Back to Suite", callback_data="panel|home", style="primary", icon_key="spark"))
            edit_styled_message(call.message.chat.id, call.message.message_id, guide_txt, reply_markup=kb)
        return bot.answer_callback_query(call.id)

    if section == "admin":
        if not is_owner(uid):
            return bot.answer_callback_query(call.id, "Owner only!", show_alert=True)

        if payload == "add":
            PENDING_STATES[uid] = {"mode": "add_admin"}
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(styled_btn("Cancel", callback_data="panel|home", style="danger", icon_key="trash"))
            edit_styled_message(
                call.message.chat.id,
                call.message.message_id,
                f"{pe('crown')} <b>ADD NEW ADMIN</b>\n\n"
                f"Send the <b>numeric Telegram User ID</b> to authorize.\n"
                f"<i>They will be able to deploy bots, check logs, and run <code>venv</code> commands.</i>",
                reply_markup=kb,
            )
        elif payload == "list":
            admins = db.get_all_admins()
            lines = [f"{pe('shield')} <b>AUTHORIZED COMMANDERS</b>\n"]
            removable_ids = []
            for a_uid, _, role, _ in admins:
                tag = f"{pe('crown')} Owner" if role == "owner" else f"{pe('spark')} Admin"
                lines.append(f"• <code>{a_uid}</code> — {tag}")
                if role != "owner":
                    removable_ids.append(a_uid)

            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(styled_btn("Add Admin", callback_data="admin|add", style="success", icon_key="crown"))
            if removable_ids:
                kb.add(styled_btn("Remove Admin", callback_data="admin|remove_prompt", style="danger", icon_key="trash"))
            kb.add(styled_btn("Back to Suite", callback_data="panel|home", style="primary", icon_key="spark"))
            edit_styled_message(call.message.chat.id, call.message.message_id, "\n".join(lines), reply_markup=kb)

        elif payload == "remove_prompt":
            PENDING_STATES[uid] = {"mode": "remove_admin"}
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(styled_btn("Cancel", callback_data="admin|list", style="primary", icon_key="shield"))
            edit_styled_message(
                call.message.chat.id,
                call.message.message_id,
                f"{pe('trash')} <b>REVOKE ADMIN ACCESS</b>\n\n"
                f"Send the <b>numeric Telegram User ID</b> whose admin access should be removed.",
                reply_markup=kb,
            )
        return bot.answer_callback_query(call.id)

    bot_name = payload
    bot_data = db.get_bot(bot_name)
    if not bot_data:
        return bot.answer_callback_query(call.id, "Bot not found!", show_alert=True)

    _, script_path, _, saved_pid, _ = bot_data

    if section == "manage":
        running_now = runner.is_running(bot_name, saved_pid=saved_pid)
        status_txt = "🟢 Active" if running_now else "🔴 Stand-by"
        pid_txt = f" (<code>PID {saved_pid}</code>)" if (running_now and saved_pid) else ""
        edit_styled_message(
            call.message.chat.id,
            call.message.message_id,
            f"{pe('spark')} <b>CONSOLE: <code>{html.escape(bot_name)}</code></b> {pe('spark')}\n"
            f"• <b>Status:</b> {status_txt}{pid_txt}\n"
            f"• <b>Script:</b> <code>{html.escape(os.path.basename(script_path))}</code>",
            reply_markup=bot_control_keyboard(bot_name, running_now),
        )
        bot.answer_callback_query(call.id)

    elif section == "start":
        ok, msg = runner.start_bot(bot_name, script_path)
        pid_val = runner.RUNNING_PROCESSES[bot_name][0].pid if (ok and bot_name in runner.RUNNING_PROCESSES) else None
        if ok:
            db.update_status(bot_name, "running", pid=pid_val)
        running_now = runner.is_running(bot_name, saved_pid=pid_val)
        bot.answer_callback_query(call.id, msg)
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=bot_control_keyboard(bot_name, running_now),
        )

    elif section == "stop":
        ok, msg = runner.stop_bot(bot_name, saved_pid=saved_pid)
        db.update_status(bot_name, "stopped", pid=None)
        bot.answer_callback_query(call.id, msg)
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=bot_control_keyboard(bot_name, False),
        )

    elif section == "restart":
        runner.stop_bot(bot_name, saved_pid=saved_pid)
        ok, msg = runner.start_bot(bot_name, script_path)
        pid_val = runner.RUNNING_PROCESSES[bot_name][0].pid if (ok and bot_name in runner.RUNNING_PROCESSES) else None
        db.update_status(bot_name, "running" if ok else "stopped", pid=pid_val)
        running_now = runner.is_running(bot_name, saved_pid=pid_val)
        bot.answer_callback_query(call.id, "Bot restarted!")
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=bot_control_keyboard(bot_name, running_now),
        )

    elif section == "venv":
        PENDING_STATES[uid] = {"mode": "venv_cmd", "bot_name": bot_name}
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(styled_btn("Cancel", callback_data=f"manage|{bot_name}", style="danger", icon_key="trash"))
        edit_styled_message(
            call.message.chat.id,
            call.message.message_id,
            f"{pe('terminal')} <b>venv SHELL — <code>{html.escape(bot_name)}</code></b>\n\n"
            f"Send the <code>pip</code> or shell command to run inside <code>{html.escape(bot_name)}</code>'s <code>venv</code>:\n"
            f"• <code>pip install &lt;package&gt;</code>\n"
            f"• <code>pip uninstall -y &lt;package&gt;</code>\n"
            f"• <code>pip list</code>",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    elif section == "logs":
        logs = runner.get_logs(bot_name, lines=45)
        log_path = runner.get_log_file_path(bot_name)
        send_styled_message(
            call.message.chat.id,
            f"{pe('logs')} <b>Logs — <code>{html.escape(bot_name)}</code></b>\n<pre>{html.escape(logs[-3400:])}</pre>",
        )
        if log_path and os.path.getsize(log_path) > 0:
            try:
                with open(log_path, "rb") as lf:
                    bot.send_document(call.message.chat.id, lf, visible_file_name=f"{bot_name}_bot.log")
            except Exception:
                pass
        bot.answer_callback_query(call.id)

    elif section == "clearlogs":
        runner.clear_logs(bot_name)
        bot.answer_callback_query(call.id, "Logs cleared!")

    elif section == "delete":
        runner.delete_bot_files(bot_name, saved_pid=saved_pid)
        db.delete_bot_record(bot_name)
        bot.answer_callback_query(call.id, f"{bot_name} deleted!")
        render_bots_list(call.message.chat.id, message_id=call.message.message_id)


def auto_resume_bots():
    for name, script_path, status, saved_pid, _ in db.get_all_bots():
        if status == "running" and os.path.exists(script_path):
            if not runner.is_running(name, saved_pid=saved_pid):
                print(f"[Auto-Resume] Starting {name}...")
                ok, _ = runner.start_bot(name, script_path)
                pid_val = runner.RUNNING_PROCESSES[name][0].pid if (ok and name in runner.RUNNING_PROCESSES) else None
                db.update_status(name, "running" if ok else "stopped", pid=pid_val)


if __name__ == "__main__":
    auto_resume_bots()
    print("Aether Deploy Bot v4.2 (Sticker Pack + Premium Emoji Suite) is online...")
    bot.infinity_polling(skip_pending=True)
