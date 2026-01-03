import os
import random
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional

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
    # Safety settings to prevent blocking legitimate queries (since we have our own blocklist)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    model = genai.GenerativeModel("gemini-pro", safety_settings=safety_settings)
else:
    model = None

# -------------------- Application client -------------------- #
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

chatai_coll = db.get_collection("chatai")
status_coll = db.get_collection("chatbot_status")
BLOCK_COLL = db.get_collection("blocked_words")

# Runtime Caches
replies_cache = []
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
    chatai_coll.delete_many({"word": word})
    global replies_cache
    replies_cache = [x for x in replies_cache if x.get("word") != word]

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
#                 AI HELPER FUNCTION (GEMINI)
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
        # We give it a personality prompt in the query
        full_prompt = (
            "You are a helpful, witty, and friendly Telegram music bot assistant. "
            "Keep your answer concise (under 50 words) and fun. "
            f"User says: {prompt}"
        )
        response = await model.generate_content_async(full_prompt)
        return response.text
    except Exception as e:
        print(f"[Gemini AI Error] {e}")
        return None

# ============================================================
#                 DATABASE REPLY HELPERS
# ============================================================
def get_reply_sync(word: str):
    global replies_cache
    if not replies_cache:
        try:
            replies_cache.extend(list(chatai_coll.find({})))
        except Exception:
            pass

    if not replies_cache:
        return None

    # Find matches
    exact = [r for r in replies_cache if r.get("word") == (word or "")]
    candidates = exact if exact else replies_cache
    
    return random.choice(candidates) if candidates else None

async def save_reply(original: Message, reply: Message):
    try:
        if not original or not original.text or not reply.text:
            return

        bl = get_blocklist()
        if any(re.search(rf"{re.escape(w)}", original.text, flags=re.IGNORECASE) for w in bl):
            return

        data = {
            "word": original.text,
            "text": reply.text,
            "kind": "text",
            "created_at": datetime.utcnow()
        }

        exists = chatai_coll.find_one({"word": data["word"], "text": data["text"]})
        if not exists:
            chatai_coll.insert_one(data)
            replies_cache.append(data)

    except Exception as e:
        print("[chatbot] save_reply ERROR:", e)

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
    
    # Check for reset
    if "reset" in message.text.lower():
         if not await is_user_admin(client, message.chat.id, message.from_user.id): return
         chatai_coll.delete_many({})
         replies_cache.clear()
         return await message.reply_text("✅ Memory reset.")

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
#               LEARNING HANDLER (GROUP 98)
# ============================================================
@app.on_message(filters.reply & (filters.group | filters.private), group=98)
async def learn_reply(client, message):
    if not message.reply_to_message or not message.text: return
    bot = await client.get_me()
    if message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot.id:
        await save_reply(message.reply_to_message, message)

# ============================================================
#               HYBRID CHATBOT HANDLER (GROUP 99)
# ============================================================
@app.on_message(
    filters.incoming & ~filters.me & (filters.group | filters.private),
    group=99
)
async def chatbot_handler(client, message: Message):
    if message.edit_date or not message.from_user or not message.text:
        return
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

    # 2. Status Check
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        s = status_coll.find_one({"chat_id": chat_id})
        if s and s.get("status") == "disabled": return

    # 3. Blocklist Check (Input)
    blocked_words = get_blocklist()
    msg_lower = message.text.lower()
    for w in blocked_words:
        if w in msg_lower: return

    # 4. Context Check (When to reply)
    should_reply = False
    if message.reply_to_message:
        bot = await client.get_me()
        if message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot.id:
            should_reply = True
    elif message.chat.type == ChatType.PRIVATE:
        should_reply = True
    elif any(k in msg_lower for k in ["chatbot", "bot", "alexa", "siri"]):
        should_reply = True

    if not should_reply:
        return

    # 5. GENERATE RESPONSE
    final_reply = None

    # A. Check Database (Cost free)
    db_reply = get_reply_sync(message.text)
    if db_reply:
        final_reply = db_reply.get("text")
    
    # B. Call AI (Costly, only if DB failed)
    if not final_reply:
        try:
            # Send typing action so user knows AI is thinking
            await client.send_chat_action(chat_id, enums.ChatAction.TYPING)
            ai_response = await get_gemini_response(message.text)
            if ai_response:
                final_reply = ai_response
        except Exception:
            pass

    # C. Fallback Safe Message (If both DB and AI failed)
    if not final_reply:
        final_reply = random.choice([
            "I'm not sure about that yet.", 
            "Thinking... 🤔", 
            "Could you say that again?",
            "I am just a music bot, but I am learning!"
        ])

    # 6. Send
    try:
        await message.reply_text(final_reply)
    except Exception:
        pass
