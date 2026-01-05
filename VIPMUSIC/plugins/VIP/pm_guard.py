# ======================================================
# VIPMUSIC PM SECURITY MODULE (STRING USERBOT ONLY)
# DO NOT USE FOR BOT TOKEN ACCOUNTS
# ======================================================

import os
import asyncio
import time
import random

from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from pyrogram import compose

# ================= CONFIGURATION ================= #

API_ID = 29945235
API_HASH = "15e39599e18d844b5b731d589a5d01c2"

MONGO_DB_URI = "mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority"

OWNERS = [8399160924, 6773435708]
ADMINS = [8399160924, 6773435708, 5428992806]

STRING_SESSIONS = [
    "STRING_SESSION_1_HERE",
    "STRING_SESSION_2_HERE",
    "STRING_SESSION_3_HERE",
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

# ================= CLIENTS ================= #

clients = []

for i, session in enumerate(STRING_SESSIONS):
    if session.strip():
        clients.append(
            Client(
                name=f"VIPMUSIC_PM_{i}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session,
                in_memory=True
            )
        )

# ================= COMMANDS ================= #

@Client.on_message(filters.command("pmhelp", prefixes=[".", "/"]) & filters.user(ADMINS))
async def pm_help(_, m):
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

@Client.on_message(filters.command(["a", "approve"], prefixes=[".", "/"]) & filters.user(ADMINS))
async def approve_cmd(_, m):
    if not m.reply_to_message:
        return
    approve(m.reply_to_message.from_user.id)
    await m.reply("✅ User approved")

@Client.on_message(filters.command(["da", "dapprove"], prefixes=[".", "/"]) & filters.user(ADMINS))
async def disapprove_cmd(_, m):
    if not m.reply_to_message:
        return
    disapprove(m.reply_to_message.from_user.id)
    await m.reply("❌ User disapproved")

@Client.on_message(filters.command("setlimit", prefixes=[".", "/"]) & filters.user(ADMINS))
async def set_limit(_, m):
    try:
        limit = int(m.command[1])
        set_config("limit", limit)
        await m.reply(f"🔢 Warn limit set to {limit}")
    except:
        await m.reply("Usage: .setlimit 3")

@Client.on_message(filters.command("setpmmsg", prefixes=[".", "/"]) & filters.user(OWNERS))
async def set_pm(_, m):
    text = m.text.split(None, 1)[1]
    set_config("pm_msg", text)
    await m.reply("✅ PM message updated")

@Client.on_message(filters.command("setblockmsg", prefixes=[".", "/"]) & filters.user(OWNERS))
async def set_block(_, m):
    text = m.text.split(None, 1)[1]
    set_config("block_msg", text)
    await m.reply("🚫 Block message updated")

@Client.on_message(filters.command("setpmimg", prefixes=[".", "/"]) & filters.user(OWNERS))
async def set_img(_, m):
    if not m.reply_to_message or not m.reply_to_message.photo:
        return await m.reply("Reply to image")
    set_config("pm_img", m.reply_to_message.photo.file_id)
    set_config("img_on", True)
    await m.reply("🖼️ PM image set")

@Client.on_message(filters.command("pmtoggle", prefixes=[".", "/"]) & filters.user(OWNERS))
async def toggle(_, m):
    status = not get_config("img_on", False)
    set_config("img_on", status)
    await m.reply(f"PM Image {'Enabled' if status else 'Disabled'}")

@Client.on_message(filters.command("block", prefixes=[".", "/"]) & filters.user(ADMINS))
async def manual_block(client, m):
    if not m.reply_to_message:
        return
    uid = m.reply_to_message.from_user.id
    await client.block_user(uid)
    await m.reply("🚫 User blocked")

# ================= PM GUARD ================= #

@Client.on_message(filters.private & ~filters.me & ~filters.bot)
async def pm_guard(client, m: Message):
    uid = m.from_user.id

    if is_allowed(uid):
        return

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
