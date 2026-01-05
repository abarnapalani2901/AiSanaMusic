import asyncio
import time
import random
import logging

from pyrogram import Client, filters, enums
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from pymongo import MongoClient, ReturnDocument

# ================= CONFIG ================= #

API_ID = 29945235
API_HASH = "15e39599e18d844b5b731d589a5d01c2"

MONGO_DB_URI = "mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority"

# STRICT ROLES
OWNERS = [8399160924, 6773435708]
ADMINS = [8399160924, 6773435708, 5428992806, 8422248995]

STRING_SESSIONS = [
    "BQDMBnkAgP4mi-0bCSzgIadEuKsdDS7h4YcAgYtXTTqPWkHVe2zhB_e7hCFPkHMbnLXteG7hZs5fdBIHz7KCvUSaUTB21wPqK3kkDbs0B8bxQ4Blw_CjxJrbmHoWPevXB1_HIVOmWWvd4zldqypC_Ddj33WC6WgvOVVaFmQU2QGEAhycy4JTKSJDFU8gOxAi_TOxSYjjk9HiHYxnXo2DYqCK1UBXYF2TZC2mlyvtxS1VlHODX4gqsKzY9QpPvgcI2oXkr-Y7yjUhiL2laPFBQttyYINiVrCgWpTTxbBA_rI2iU0owZHzvgty-G-mbbke95AhYLndKoo44s3gRQLPP86hNiLQEgAAAAH2AVIjAQ",
    "BQHI7ZMAvRoC74JvkhabzOy2taIY48ninlKLfKKrH7OngNefTThsmwj_K3iwE0pK5SVydd4738nskDDrxLIBlZMv7prrOeJ-9lYrB8Z3PlNhll5niVD96zPwgb5xpmNCubmgVPbXSzLOwl0vvnkh80TVVt-Hqa2I1siibKJBT82X_NjBgGRAkvL--rwGoTjIp1uvJVug6k9msieXAIstuZepNHbbuM3pxDpcuN5t-8YlU8cg2F5V_vsSe0t1PLdGLr0-UGhDhQ_VOFlnVZ_I6QWTXl5-STcxQCnzNdh5iRPj8GGWTKy0P71XKX9gJVVBS3HpDGvyPfr-MzbjuU7xofF8qQUENgAAAAH0oQZcAA",
]

DEFAULT_LIMIT = 3

DEFAULT_PM_MSG = (
    "<blockquote>☆ . * ● ¸ . ✦ .★° :. ★ * • ○ ° ★</blockquote>\n"
    "<blockquote>ʜᴇʏ, ɪ'ᴍ 𝐏𝐦𝐒𝐞𝐜𝐮𝐫𝐢𝐭𝐲</blockquote>\n"
    "<blockquote>🚫 Spam = Auto Block</blockquote>\n"
    "<blockquote>Warn Limit : {limit}</blockquote>"
)

DEFAULT_BLOCK_MSG = (
    "<blockquote>⚠️ Spammer Detected\n"
    "🚫 Blocked Successfully</blockquote>"
)

# ================= LOG ================= #

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("VIPMUSIC_PM_SECURITY")

# ================= DATABASE ================= #

mongo = MongoClient(MONGO_DB_URI)
db = mongo["VIPMUSIC_PM_SECURITY"]

cfg = db["config"]
approved = db["approved"]
users = db["users"]

# ================= CACHE ================= #

FLOOD = {}

# ================= HELPERS ================= #

def get_cfg(k, d):
    x = cfg.find_one({"_id": "main"})
    return x.get(k, d) if x else d

def set_cfg(k, v):
    cfg.update_one({"_id": "main"}, {"$set": {k: v}}, upsert=True)

def is_approved(uid):
    if uid in OWNERS or uid in ADMINS:
        return True
    return approved.find_one({"uid": uid}) is not None

def approve(uid):
    approved.update_one({"uid": uid}, {"$set": {"uid": uid}}, upsert=True)
    users.delete_one({"uid": uid})

def disapprove(uid):
    approved.delete_one({"uid": uid})

def warn(uid):
    r = users.find_one_and_update(
        {"uid": uid},
        {"$inc": {"w": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return r.get("w", 1)

def reset(uid):
    users.delete_one({"uid": uid})

def flood(uid):
    now = time.time()
    FLOOD.setdefault(uid, [])
    FLOOD[uid] = [t for t in FLOOD[uid] if now - t < 15]
    FLOOD[uid].append(now)
    return len(FLOOD[uid]) >= 5

# ================= COMMAND FILTERS ================= #

OWNER_ONLY = filters.me | filters.user(OWNERS)
ADMIN_ONLY = filters.me | filters.user(ADMINS)

# ================= COMMANDS ================= #

async def approve_cmd(_, m):
    if m.reply_to_message:
        approve(m.reply_to_message.from_user.id)
        await m.reply("✅ Approved")

async def disapprove_cmd(_, m):
    if m.reply_to_message:
        disapprove(m.reply_to_message.from_user.id)
        await m.reply("❌ Disapproved")

async def set_limit(_, m):
    try:
        v = int(m.command[1])
        set_cfg("limit", v)
        await m.reply(f"✅ Limit set to {v}")
    except:
        await m.reply("Usage: .setlimit 3")

async def set_pm(_, m):
    set_cfg("pm", m.text.split(None, 1)[1])
    await m.reply("✅ PM message updated")

async def set_block(_, m):
    set_cfg("block", m.text.split(None, 1)[1])
    await m.reply("✅ Block message updated")

async def force_block(c, m):
    if m.reply_to_message:
        await c.block_user(m.reply_to_message.from_user.id)
        await m.reply("🚫 Blocked")

# ================= AUTO APPROVE ================= #

async def auto_approve(_, m: Message):
    if m.chat.type == enums.ChatType.PRIVATE:
        approve(m.chat.id)

# ================= PM GUARD ================= #

async def guard(c: Client, m: Message):
    if not m.from_user:
        return

    uid = m.from_user.id
    if is_approved(uid):
        return

    limit = get_cfg("limit", DEFAULT_LIMIT)
    pm_msg = get_cfg("pm", DEFAULT_PM_MSG)
    block_msg = get_cfg("block", DEFAULT_BLOCK_MSG)

    if flood(uid):
        await m.reply(block_msg)
        await c.block_user(uid)
        reset(uid)
        return

    await asyncio.sleep(random.uniform(0.4, 0.9))
    w = warn(uid)

    if w > limit:
        await m.reply(block_msg)
        await c.block_user(uid)
        reset(uid)
        return

    await m.reply(
        pm_msg.format(limit=limit) + f"\n\n⚠️ Warns: {w}/{limit}"
    )

# ================= CLIENT ================= #

async def start(session, i):
    app = Client(
        f"VIP_PM_{i}",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session,
        in_memory=True,
        parse_mode=enums.ParseMode.HTML,
    )

    await app.start()

    app.add_handler(MessageHandler(approve_cmd, filters.command("a", ".") & ADMIN_ONLY))
    app.add_handler(MessageHandler(disapprove_cmd, filters.command("da", ".") & ADMIN_ONLY))
    app.add_handler(MessageHandler(force_block, filters.command("block", ".") & ADMIN_ONLY))

    app.add_handler(MessageHandler(set_limit, filters.command("setlimit", ".") & OWNER_ONLY))
    app.add_handler(MessageHandler(set_pm, filters.command("setpmmsg", ".") & OWNER_ONLY))
    app.add_handler(MessageHandler(set_block, filters.command("setblockmsg", ".") & OWNER_ONLY))

    app.add_handler(
        MessageHandler(
            auto_approve,
            filters.private & filters.outgoing & ~filters.bot
        )
    )

    app.add_handler(
        MessageHandler(
            guard,
            filters.private
            & filters.incoming
            & ~filters.me
            & ~filters.bot
            & ~filters.service
            & ~filters.command(["a", "da", "setlimit", "setpmmsg", "setblockmsg", "block"], "."),
        )
    )

    me = await app.get_me()
    log.info(f"PM Security ON → {me.first_name} [{me.id}]")

async def main():
    await asyncio.gather(
        *[start(s, i) for i, s in enumerate(STRING_SESSIONS) if s]
    )
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
