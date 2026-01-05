import asyncio
import time
import random
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from pymongo import MongoClient

# ================= CONFIGURATION ================= #

API_ID = 29945235
API_HASH = "15e39599e18d844b5b731d589a5d01c2"

MONGO_DB_URI = "mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority"

OWNERS = [8399160924, 6773435708]
ADMINS = [8399160924, 6773435708, 5428992806, 8422248995]

STRING_SESSIONS = [
    "BQDMBnkAgP4mi-0bCSzgIadEuKsdDS7h4YcAgYtXTTqPWkHVe2zhB_e7hCFPkHMbnLXteG7hZs5fdBIHz7KCvUSaUTB21wPqK3kkDbs0B8bxQ4Blw_CjxJrbmHoWPevXB1_HIVOmWWvd4zldqypC_Ddj33WC6WgvOVVaFmQU2QGEAhycy4JTKSJDFU8gOxAi_TOxSYjjk9HiHYxnXo2DYqCK1UBXYF2TZC2mlyvtxS1VlHODX4gqsKzY9QpPvgcI2oXkr-Y7yjUhiL2laPFBQttyYINiVrCgWpTTxbBA_rI2iU0owZHzvgty-G-mbbke95AhYLndKoo44s3gRQLPP86hNiLQEgAAAAH2AVIjAQ", 
    # Add more sessions here if needed
]

DEFAULT_LIMIT = 3

DEFAULT_PM_MSG = (
    "<blockquote>☆ . * ● ¸ . ✦ .★° :. ★ * • ○ ° ★</blockquote>\n"
    "<blockquote>ʜᴇʏ, ɪ'ᴍ 𝐏𝐦𝐒𝐞𝐜𝐮𝐫𝐞-✗-𝐁𝐨𝐭</blockquote>\n"
    "<blockquote>➽───────────────❥</blockquote>\n"
    "<blockquote>😈 Wait until my boss comes.\n"
    "🚫 Spam = Auto Block (Limit: {limit})</blockquote>\n"
    "<blockquote>☆ . * ● ¸ . ✦ .★° :. ★ * • ○ ° ★</blockquote>"
)

DEFAULT_BLOCK_MSG = (
    "<blockquote>ʙᴇᴇᴘ ʙᴏᴏᴘ ⚠️ Spammer detected!\n"
    "Blocked successfully 🚫</blockquote>"
)

# ================= DATABASE ================= #

mongo = MongoClient(MONGO_DB_URI)
db = mongo["VIPMUSIC_PM_GUARD"]

config_db = db["config"]
approved_db = db["approved"]
users_db = db["users"]

# ================= FLOOD CACHE ================= #

FLOOD_CACHE = {}

# ================= HELPERS ================= #

def get_config(key, default):
    data = config_db.find_one({"_id": "main"})
    return data.get(key, default) if data else default

def set_config(key, value):
    config_db.update_one(
        {"_id": "main"},
        {"$set": {key: value}},
        upsert=True
    )

def is_allowed(uid):
    return uid in OWNERS or uid in ADMINS or approved_db.find_one({"user_id": uid})

def approve(uid):
    approved_db.update_one({"user_id": uid}, {"$set": {"user_id": uid}}, upsert=True)
    users_db.delete_one({"user_id": uid})

def disapprove(uid):
    approved_db.delete_one({"user_id": uid})

def add_warn(uid):
    data = users_db.find_one({"user_id": uid}) or {}
    warns = data.get("warns", 0) + 1
    users_db.update_one(
        {"user_id": uid},
        {"$set": {"warns": warns}},
        upsert=True
    )
    return warns

def reset_warn(uid):
    users_db.delete_one({"user_id": uid})

def is_flood(uid):
    now = time.time()
    FLOOD_CACHE.setdefault(uid, [])
    FLOOD_CACHE[uid] = [t for t in FLOOD_CACHE[uid] if now - t < 20]
    FLOOD_CACHE[uid].append(now)
    return len(FLOOD_CACHE[uid]) >= 6

# ================= HANDLERS (LOGIC) ================= #

async def pm_help(client, m):
    await m.reply_text(
        "**PM Security Commands**\n\n"
        ".a / .approve – Allow user\n"
        ".da / .dapprove – Disallow user\n"
        ".setlimit <n>\n"
        ".setpmmsg <text>\n"
        ".setblockmsg <text>\n"
        ".setpmimg (reply image)\n"
        ".pmtoggle\n"
        ".block"
    )

async def approve_cmd(client, m):
    if not m.reply_to_message:
        return
    approve(m.reply_to_message.from_user.id)
    await m.reply("✅ User approved")

async def disapprove_cmd(client, m):
    if not m.reply_to_message:
        return
    disapprove(m.reply_to_message.from_user.id)
    await m.reply("❌ User disapproved")

async def set_limit(client, m):
    try:
        limit = int(m.command[1])
        set_config("limit", limit)
        await m.reply(f"🔢 Warn limit set to {limit}")
    except:
        await m.reply("Usage: .setlimit 3")

async def set_pm(client, m):
    try:
        text = m.text.split(None, 1)[1]
        set_config("pm_msg", text)
        await m.reply("✅ PM message updated")
    except IndexError:
        await m.reply("Usage: .setpmmsg <text>")

async def set_block(client, m):
    try:
        text = m.text.split(None, 1)[1]
        set_config("block_msg", text)
        await m.reply("🚫 Block message updated")
    except IndexError:
        await m.reply("Usage: .setblockmsg <text>")

async def set_img(client, m):
    if not m.reply_to_message or not m.reply_to_message.photo:
        return await m.reply("Reply to image")
    set_config("pm_img", m.reply_to_message.photo.file_id)
    set_config("img_on", True)
    await m.reply("🖼️ PM image set")

async def toggle(client, m):
    status = not get_config("img_on", False)
    set_config("img_on", status)
    await m.reply(f"PM Image {'Enabled' if status else 'Disabled'}")

async def manual_block(client, m):
    if not m.reply_to_message:
        return
    uid = m.reply_to_message.from_user.id
    await client.block_user(uid)
    await m.reply("🚫 User blocked")

async def pm_guard_handler(client, m: Message):
    # Only protect private chats, ignore self and bots
    uid = m.from_user.id

    # Optimization: Don't check DB for simple cases first
    if is_allowed(uid):
        return

    # Small artificial delay to feel human
    await asyncio.sleep(random.uniform(1.5, 3.5))

    limit = get_config("limit", DEFAULT_LIMIT)
    pm_msg = get_config("pm_msg", DEFAULT_PM_MSG).format(limit=limit)
    block_msg = get_config("block_msg", DEFAULT_BLOCK_MSG)
    img_on = get_config("img_on", False)
    img_id = get_config("pm_img", None)

    if is_flood(uid):
        await m.reply_text(block_msg)
        await client.block_user(uid)
        return

    warns = add_warn(uid)

    if warns > limit:
        await m.reply_text(block_msg)
        await client.block_user(uid)
        reset_warn(uid)
        return

    warn_text = f"{pm_msg}\n\n⚠️ Warns: {warns}/{limit}"

    if img_on and img_id:
        try:
            await m.reply_photo(img_id, caption=warn_text)
            return
        except:
            pass

    await m.reply_text(warn_text)

# ================= CLIENT INITIALIZATION ================= #

async def start_pm_client(session_str, index):
    if not session_str.strip():
        return None
    
    try:
        user_bot = Client(
            name=f"VIPMUSIC_PM_{index}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_str,
            in_memory=True
        )

        await user_bot.start()

        # --- REGISTER HANDLERS MANUALLY ---
        
        # 1. Admin Commands (Allow/Disallow/Config)
        user_bot.add_handler(MessageHandler(pm_help, filters.command("pmhelp", prefixes=[".", "/"]) & filters.user(ADMINS)))
        user_bot.add_handler(MessageHandler(approve_cmd, filters.command(["a", "approve"], prefixes=[".", "/"]) & filters.user(ADMINS)))
        user_bot.add_handler(MessageHandler(disapprove_cmd, filters.command(["da", "dapprove"], prefixes=[".", "/"]) & filters.user(ADMINS)))
        user_bot.add_handler(MessageHandler(set_limit, filters.command("setlimit", prefixes=[".", "/"]) & filters.user(ADMINS)))
        user_bot.add_handler(MessageHandler(set_pm, filters.command("setpmmsg", prefixes=[".", "/"]) & filters.user(OWNERS)))
        user_bot.add_handler(MessageHandler(set_block, filters.command("setblockmsg", prefixes=[".", "/"]) & filters.user(OWNERS)))
        user_bot.add_handler(MessageHandler(set_img, filters.command("setpmimg", prefixes=[".", "/"]) & filters.user(OWNERS)))
        user_bot.add_handler(MessageHandler(toggle, filters.command("pmtoggle", prefixes=[".", "/"]) & filters.user(OWNERS)))
        user_bot.add_handler(MessageHandler(manual_block, filters.command("block", prefixes=[".", "/"]) & filters.user(ADMINS)))

        # 2. PM Guard Logic (Incoming Private Messages)
        # filters.private: Only private chats
        # ~filters.me: Don't trigger on own messages
        # ~filters.bot: Don't trigger on other bots
        # ~filters.user(ADMINS): Optional optimization, don't guard against other admins if you want
        user_bot.add_handler(MessageHandler(pm_guard_handler, filters.private & ~filters.me & ~filters.bot))

        me = await user_bot.get_me()
        print(f"🛡️ [PM GUARD] Started for: {me.first_name} ({me.id})")
        return user_bot

    except Exception as e:
        print(f"❌ [PM GUARD] Failed to start client {index}: {e}")
        return None

async def init_pm_guard():
    if not STRING_SESSIONS:
        return
    
    tasks = []
    for i, session in enumerate(STRING_SESSIONS):
        tasks.append(start_pm_client(session, i))
    
    await asyncio.gather(*tasks)

# ================= STARTUP ================= #

if STRING_SESSIONS:
    asyncio.create_task(init_pm_guard())
