import os
import random
import asyncio
from datetime import datetime, timedelta

# -------------------- AI IMPORTS -------------------- #
import google.generativeai as genai

from pyrogram import filters, enums
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.enums import ChatMemberStatus, ChatType
from pymongo import MongoClient

# -------------------- CONFIGURATION -------------------- #
# Get this key from https://aistudio.google.com/app/apikey
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCIFDjm0VwGqKJoFGjw6gnxlcPC-CQKCH8")

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Safety settings to prevent blocking legitimate queries
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    model = genai.GenerativeModel("gemini-pro", safety_settings=safety_settings)
else:
    model = None

# -------------------- Application Client -------------------- #
try:
    from VIPMUSIC import app
except Exception:
    try:
        from main import app
    except Exception:
        raise RuntimeError("Could not import Pyrogram Client as 'app'.")

# -------------------- MongoDB & Config setup -------------------- #
try:
    from config import MONGO_DB_URI as MONGO_URL
    from VIPMUSIC.misc import SUDOERS
except Exception:
    MONGO_URL = os.environ.get(
        "MONGO_URL",
        "mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority"
    )
    SUDOERS = []

try:
    from config import OWNER_ID
except:
    OWNER_ID = 0

# -------------------- SUDOERS SANITIZATION -------------------- #
SUDO_IDS = []
if SUDOERS:
    for item in SUDOERS:
        if isinstance(item, int):
            SUDO_IDS.append(item)
        elif hasattr(item, 'id'):
            SUDO_IDS.append(item.id)
SUDO_IDS.append(OWNER_ID)
SUDO_IDS = list(set(SUDO_IDS))

# -------------------- Database Setup -------------------- #
mongo = MongoClient(MONGO_URL)
db = mongo.get_database("vipmusic_db")

# Removed chatai_coll (Learning DB) as requested
status_coll = db.get_collection("chatbot_status")
BLOCK_COLL = db.get_collection("blocked_words")

# Runtime Caches
blocklist_users = {}
message_counts = {}

# ================= DEFAULT BLOCKED WORDS ================= #
DEFAULT_BLOCKED = [
    "sex", "porn", "nude", "boob", "boobs", "dick", "cock", "penis", "vagina",
    "nipples", "xxx", "porno", "cum", "masturbate", "erotic", "adult", "playboy",
    "hentai", "erotica", "fetish", "kink", "orgasm", "threesome", "xnxx",
    "xvideos", "xvideo", "pic", "nudepic",
    "punda", "koothi", "soothu", "sutthu", "mayiru", "olmari", "okka",
    "poolu", "olu", "sappu", "umbe", "kuththu", "thappu", "suthu", "paalu",
    "adangommala", "adangomala", "adangotha", "adangottha",
    "sunny", "call", "pm", "dm", "service", "ottha", "otta", "gommala",
    "hole", "inch", "ash", "sexchat", "onlyfans", "cams", "chatsex", "adultchat",
    "videochat", "sexting", "naked", "lingerie", "eroticvideo",
    "/start", "/help", "/play", "/vplay", "/end", "/playforce", "/vplayforce",
    "/skip", "/pause", "/seek", "/loop", "/ban", "fban", "/warn", "/mute",
    "/unban", "/unfban", "/newfed", "/chatfed", "/fedstat", "/myfeds",
    "💦", "💧", "🍑", "🍒", "🍆", "🥵", "🍌", "💋", "👅",
]

# ===================== INITIALIZE BLOCKLIST ===================== #
for w in DEFAULT_BLOCKED:
    if not BLOCK_COLL.find_one({"word": w.lower()}):
        BLOCK_COLL.insert_one({"word": w.lower()})

# ============================================================
#               BLOCKLIST & CACHE FUNCTIONS
# ============================================================
def get_blocklist():
    try:
        data = BLOCK_COLL.find({})
        words = [x["word"].lower() for x in data]
        return list(set(words + DEFAULT_BLOCKED))
    except:
        return DEFAULT_BLOCKED

def add_block_word(word: str):
    word = word.lower().strip()
    if not BLOCK_COLL.find_one({"word": word}):
        BLOCK_COLL.insert_one({"word": word})

def remove_block_word(word: str):
    word = word.lower().strip()
    BLOCK_COLL.delete_one({"word": word})

def list_block_words():
    return get_blocklist()

async def is_user_admin(client, chat_id: int, user_id: int) -> bool:
    if user_id in SUDO_IDS:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False

# ============================================================
#                  AI HELPER FUNCTION (GEMINI)
# ============================================================
async def get_gemini_response(prompt: str):
    """
    Fetches a response from Gemini Pro.
    Returns None if API fails or key is missing.
    """
    if not model:
        return None
    
    try:
        # Generate async response
        # Shortened personality prompt for faster, snappier replies
        full_prompt = (
            "You are a witty, friendly Telegram music bot. "
            "Reply to this user message. Keep it short (under 50 words). "
            f"User: {prompt}"
        )
        response = await model.generate_content_async(full_prompt)
        return response.text
    except Exception as e:
        print(f"[Gemini AI Error] {e}")
        return None

# ============================================================
#               COMMAND HANDLERS
# ============================================================
@app.on_message(filters.command("addblock", prefixes=["/", "!", "."]) & filters.user(SUDO_IDS))
async def addblock_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage:\n/addblock word1 word2 ...")
    
    text = message.text.split(None, 1)[1].strip()
    added_words = []
    
    for w in text.split():
        add_block_word(w)
        added_words.append(w)
        
    await message.reply_text(f"🚫 Added to blocklist: {', '.join(added_words)}")

@app.on_message(filters.command("rmblock", prefixes=["/", "!", "."]) & filters.user(SUDO_IDS))
async def rmblock_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /rmblock <word>")
    text = message.text.split(None, 1)[1].strip()
    remove_block_word(text)
    await message.reply_text(f"🧹 Removed from blocklist: **{text}**")

@app.on_message(filters.command("listblock", prefixes=["/", "!", "."]) & filters.user(SUDO_IDS))
async def listblock_cmd(client, message):
    words = list_block_words()
    if not words: return await message.reply_text("📭 Empty.")
    
    chunk = "🚫 **Blocked:**\n"
    for w in words:
        if len(chunk) + len(w) > 4000:
            await message.reply_text(chunk)
            chunk = ""
        chunk += f"`{w}` "
    if chunk: await message.reply_text(chunk)

# ============================================================
#               UI & SETTINGS
# ============================================================
def chatbot_keyboard(is_enabled: bool):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🍎 𝐃ɪsᴀʙʟᴇ" if is_enabled else "🍏 𝐄ɴᴀʙʟᴇ", 
                             callback_data="cb_disable" if is_enabled else "cb_enable")
    ]])

@app.on_message(filters.command(["chatbot", "chat"], prefixes=["/", "!", "", "%", ",", ".", "@", "#"]))
async def chatbot_settings(client, message):
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if not await is_user_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")
    
    doc = status_coll.find_one({"chat_id": message.chat.id})
    enabled = not doc or doc.get("status") == "enabled"
    
    await message.reply_text(
        f"**🥂 Chatbot Status:** {'🍏 Enabled' if enabled else '🍎 Disabled'}",
        reply_markup=chatbot_keyboard(enabled)
    )

@app.on_callback_query(filters.regex("^cb_(enable|disable)$"))
async def chatbot_toggle_cb(client, cq: CallbackQuery):
    chat_id = cq.message.chat.id
    if cq.message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if not await is_user_admin(client, chat_id, cq.from_user.id):
            return await cq.answer("Admins only.", show_alert=True)
            
    new_status = "enabled" if cq.data == "cb_enable" else "disabled"
    status_coll.update_one({"chat_id": chat_id}, {"$set": {"status": new_status}}, upsert=True)
    
    await cq.message.edit_text(
        f"**{'🍏 Chatbot Enabled' if new_status == 'enabled' else '🍎 Chatbot Disabled'}!**",
        reply_markup=chatbot_keyboard(new_status == "enabled")
    )
    await cq.answer(new_status.title())

# ============================================================
#                AI CHATBOT HANDLER (GROUP 99)
# ============================================================
@app.on_message(
    filters.incoming & ~filters.me & (filters.group | filters.private),
    group=99
)
async def chatbot_handler(client, message: Message):
    if message.edit_date or not message.from_user or not message.text:
        return
    # Ignore commands
    if message.text.startswith(("/", "!", ".", "#", "$")):
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    now = datetime.utcnow()
    global blocklist_users, message_counts

    # 1. Spam Protection
    blocklist_users = {u: t for u, t in blocklist_users.items() if t > now}
    if user_id in blocklist_users: return

    mc = message_counts.get(user_id)
    if not mc:
        message_counts[user_id] = {"count": 1, "last_time": now}
    else:
        diff = (now - mc["last_time"]).total_seconds()
        mc["count"] = mc["count"] + 1 if diff <= 3 else 1
        mc["last_time"] = now
        if mc["count"] >= 6:
            blocklist_users[user_id] = now + timedelta(minutes=1)
            message_counts.pop(user_id, None)
            return await message.reply_text("⛔ Spam detected. Blocked for 1 min.")

    # 2. Check if this is a direct reply to the Bot
    # We do this BEFORE checking if the chatbot is disabled.
    is_reply_to_bot = False
    bot = await client.get_me()
    
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == bot.id:
            is_reply_to_bot = True

    # 3. Status Check (Enabled/Disabled)
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        s = status_coll.find_one({"chat_id": chat_id})
        
        # If chatbot is disabled...
        if s and s.get("status") == "disabled":
            # ...ONLY stop if it is NOT a reply to the bot.
            # If it IS a reply (is_reply_to_bot is True), we bypass this return.
            if not is_reply_to_bot:
                return

    # 4. Blocklist Check (Input)
    blocked_words = get_blocklist()
    msg_lower = message.text.lower()
    for w in blocked_words:
        if w in msg_lower: return

    # 5. Context Check (When to reply)
    should_reply = False
    if is_reply_to_bot:
        should_reply = True
    elif message.chat.type == ChatType.PRIVATE:
        should_reply = True
    elif any(k in msg_lower for k in ["chatbot", "bot", "alexa", "siri", "gpt"]):
        should_reply = True

    if not should_reply:
        return

    # 6. GENERATE RESPONSE (Pure AI)
    final_reply = None

    try:
        # Send typing action so user knows AI is thinking
        await client.send_chat_action(chat_id, enums.ChatAction.TYPING)
        ai_response = await get_gemini_response(message.text)
        if ai_response:
            final_reply = ai_response
    except Exception as e:
        print(f"AI Error: {e}")

    # 7. Fallback Message (If AI fails)
    if not final_reply:
        # Simple fallbacks just in case Gemini API is down
        final_reply = random.choice([
            "I'm having trouble connecting to my brain right now.", 
            "Can you say that again?",
            "Thinking..."
        ])

    # 8. Send
    try:
        await message.reply_text(final_reply)
    except Exception:
        pass
