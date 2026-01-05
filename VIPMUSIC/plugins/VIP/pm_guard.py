import asyncio
import time
import random
import logging
from pyrogram import Client, filters, enums
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from pymongo import MongoClient, ReturnDocument

# ================= CONFIGURATION ================= #

API_ID = 29945235
API_HASH = "15e39599e18d844b5b731d589a5d01c2"

MONGO_DB_URI = "mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority"

# Permissions
# IDs of people who control the bot (You + Trusted)
OWNERS = [8399160924, 6773435708]
ADMINS = [8399160924, 6773435708, 5428992806, 8422248995]

STRING_SESSIONS = [
    "BQDMBnkAgP4mi-0bCSzgIadEuKsdDS7h4YcAgYtXTTqPWkHVe2zhB_e7hCFPkHMbnLXteG7hZs5fdBIHz7KCvUSaUTB21wPqK3kkDbs0B8bxQ4Blw_CjxJrbmHoWPevXB1_HIVOmWWvd4zldqypC_Ddj33WC6WgvOVVaFmQU2QGEAhycy4JTKSJDFU8gOxAi_TOxSYjjk9HiHYxnXo2DYqCK1UBXYF2TZC2mlyvtxS1VlHODX4gqsKzY9QpPvgcI2oXkr-Y7yjUhiL2laPFBQttyYINiVrCgWpTTxbBA_rI2iU0owZHzvgty-G-mbbke95AhYLndKoo44s3gRQLPP86hNiLQEgAAAAH2AVIjAQ", #bot
    "BQHI7ZMAvRoC74JvkhabzOy2taIY48ninlKLfKKrH7OngNefTThsmwj_K3iwE0pK5SVydd4738nskDDrxLIBlZMv7prrOeJ-9lYrB8Z3PlNhll5niVD96zPwgb5xpmNCubmgVPbXSzLOwl0vvnkh80TVVt-Hqa2I1siibKJBT82X_NjBgGRAkvL--rwGoTjIp1uvJVug6k9msieXAIstuZepNHbbuM3pxDpcuN5t-8YlU8cg2F5V_vsSe0t1PLdGLr0-UGhDhQ_VOFlnVZ_I6QWTXl5-STcxQCnzNdh5iRPj8GGWTKy0P71XKX9gJVVBS3HpDGvyPfr-MzbjuU7xofF8qQUENgAAAAH0oQZcAA", #shasha
]

# Defaults
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

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PM_GUARD")

# ================= DATABASE ================= #

try:
    mongo = MongoClient(MONGO_DB_URI)
    db = mongo["VIPMUSIC_PM_GUARD"]
    config_col = db["config"]
    approved_col = db["approved"]
    users_col = db["users"]
    logger.info("✅ MongoDB Connected Successfully")
except Exception as e:
    logger.error(f"❌ MongoDB Connection Failed: {e}")
    exit()

# ================= RUNTIME CACHE (FLOOD) ================= #

FLOOD_CACHE = {} 

# ================= HELPERS ================= #

def get_config(key, default):
    doc = config_col.find_one({"_id": "main"})
    return doc.get(key, default) if doc else default

def set_config(key, value):
    config_col.update_one({"_id": "main"}, {"$set": {key: value}}, upsert=True)

def is_approved(uid):
    # Owners and Admins are always approved
    if uid in OWNERS or uid in ADMINS:
        return True
    return approved_col.find_one({"user_id": uid}) is not None

def approve_user(uid):
    approved_col.update_one({"user_id": uid}, {"$set": {"user_id": uid}}, upsert=True)
    users_col.delete_one({"user_id": uid}) # Reset warns

def disapprove_user(uid):
    approved_col.delete_one({"user_id": uid})

def check_flood(uid):
    """
    Checks if user is spamming (5 messages in 15 seconds).
    Returns True if flooding.
    """
    now = time.time()
    FLOOD_CACHE.setdefault(uid, [])
    # Keep only timestamps within the last 15 seconds
    FLOOD_CACHE[uid] = [t for t in FLOOD_CACHE[uid] if now - t < 15]
    FLOOD_CACHE[uid].append(now)
    
    return len(FLOOD_CACHE[uid]) >= 5

def increment_warn(uid):
    # Using ReturnDocument.AFTER to ensure we get the updated count
    res = users_col.find_one_and_update(
        {"user_id": uid},
        {"$inc": {"warns": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return res.get("warns", 1)

def reset_warns(uid):
    users_col.delete_one({"user_id": uid})

async def clean_previous_warnings(client, chat_id):
    """Deletes previous bot messages to keep chat clean"""
    try:
        async for msg in client.search_messages(chat_id, from_user="me", limit=5):
            # Look for keywords in text or caption
            text = msg.text or msg.caption or ""
            if "𝐏𝐦𝐒𝐞𝐜𝐮𝐫𝐞" in text or "Warns:" in text:
                await msg.delete()
    except:
        pass

# ================= HANDLERS ================= #

# --- Admin Commands ---
# Filter: Only allow if sender is Me (Owner) or in ADMINS list
admin_filter = filters.command(["pmhelp", "a", "da", "setlimit", "setpmmsg", "setblockmsg", "setpmimg", "pmimg", "block"], prefixes=[".", "/"]) & (filters.me | filters.user(ADMINS))

async def help_cmd(_, m):
    txt = (
        "<b>🛡️ PM Guard Commands</b>\n\n"
        "`.a` - Approve User (Reply)\n"
        "`.da` - Disapprove User (Reply)\n"
        "`.setlimit <n>` - Set Max Warns\n"
        "`.setpmmsg <text>` - Set Warning Text\n"
        "`.setblockmsg <text>` - Set Block Text\n"
        "`.setpmimg` (Reply) - Set Image\n"
        "`.pmimg` - Toggle Image On/Off\n"
        "`.block` (Reply) - Force Block"
    )
    await m.reply(txt)

async def approve_cmd(_, m):
    if m.reply_to_message:
        uid = m.reply_to_message.from_user.id
        approve_user(uid)
        await m.reply(f"✅ User {uid} approved to PM.")
    else:
        await m.reply("⚠️ Reply to a user.")

async def disapprove_cmd(_, m):
    if m.reply_to_message:
        uid = m.reply_to_message.from_user.id
        disapprove_user(uid)
        await m.reply(f"❌ User {uid} disapproved.")
    else:
        await m.reply("⚠️ Reply to a user.")

async def set_limit_cmd(_, m):
    try:
        val = int(m.command[1])
        set_config("limit", val)
        await m.reply(f"✅ Limit set to {val}")
    except:
        await m.reply("⚠️ Usage: .setlimit 5")

async def set_pm_msg_cmd(_, m):
    if len(m.command) > 1:
        txt = m.text.split(None, 1)[1]
        set_config("pm_msg", txt)
        await m.reply("✅ PM Message updated.")

async def set_block_msg_cmd(_, m):
    if len(m.command) > 1:
        txt = m.text.split(None, 1)[1]
        set_config("block_msg", txt)
        await m.reply("✅ Block Message updated.")

async def set_img_cmd(_, m):
    if m.reply_to_message and m.reply_to_message.photo:
        fid = m.reply_to_message.photo.file_id
        set_config("pm_img", fid)
        set_config("img_on", True)
        await m.reply("✅ PM Image set and enabled.")
    else:
        await m.reply("⚠️ Reply to an image.")

async def toggle_img_cmd(_, m):
    curr = get_config("img_on", False)
    set_config("img_on", not curr)
    await m.reply(f"✅ Image is now {'ON' if not curr else 'OFF'}")

async def block_cmd(c, m):
    if m.reply_to_message:
        await c.block_user(m.reply_to_message.from_user.id)
        await m.reply("🚫 User blocked.")

# --- Auto Approve Logic ---

async def auto_approve_outgoing(_, m: Message):
    """Automatically approve anyone the owner messages."""
    if m.chat.type == enums.ChatType.PRIVATE:
        user_id = m.chat.id
        if not is_approved(user_id):
            approve_user(user_id)
            # Optional: Notify log
            # logger.info(f"Auto-approved {user_id} because owner messaged them.")

# --- Main Guard Logic ---

async def pm_guard(client: Client, m: Message):
    # 1. Validation: Must be incoming private msg, not from me, not from bot/service
    if not m.from_user: return
    
    uid = m.from_user.id
    
    # Check Allow List (Database or Admin List)
    if is_approved(uid):
        return

    # 2. Settings Load
    limit = get_config("limit", DEFAULT_LIMIT)
    pm_text = get_config("pm_msg", DEFAULT_PM_MSG)
    block_text = get_config("block_msg", DEFAULT_BLOCK_MSG)
    img_on = get_config("img_on", False)
    img_id = get_config("pm_img", None)

    # 3. Flood Check (Immediate Block if spamming fast)
    if check_flood(uid):
        await m.reply(block_text)
        await client.block_user(uid)
        reset_warns(uid)
        return

    # 4. Processing Delay (Human-like behavior)
    await asyncio.sleep(random.uniform(0.5, 1.0))

    # 5. Warn Logic
    warns = increment_warn(uid)

    if warns > limit:
        await m.reply(block_text)
        await client.block_user(uid)
        reset_warns(uid)
        return

    # 6. Send Warning
    try:
        final_text = pm_text.format(limit=limit)
    except:
        final_text = pm_text
    
    final_text += f"\n\n⚠️ <b>Warns: {warns}/{limit}</b>"

    # Delete old warning to keep chat clean
    await clean_previous_warnings(client, m.chat.id)

    # Send new warning
    if img_on and img_id:
        try:
            await m.reply_photo(img_id, caption=final_text)
        except Exception as e:
            await m.reply(final_text)
    else:
        await m.reply(final_text)

# ================= CLIENT SETUP ================= #

async def start_client(session, idx):
    if not session: return
    try:
        app = Client(
            name=f"VIP_PM_{idx}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session,
            in_memory=True,
            parse_mode=enums.ParseMode.HTML  # Important for blockquotes
        )
        await app.start()
        
        # 1. Register Admin Commands
        # Using filters.me ensures the owner can use commands even in Saved Messages (Outgoing)
        app.add_handler(MessageHandler(help_cmd, filters.command("pmhelp", prefixes=".") & (filters.me | filters.user(ADMINS))))
        app.add_handler(MessageHandler(approve_cmd, filters.command(["a", "approve"], prefixes=".") & (filters.me | filters.user(ADMINS))))
        app.add_handler(MessageHandler(disapprove_cmd, filters.command(["da", "deny"], prefixes=".") & (filters.me | filters.user(ADMINS))))
        app.add_handler(MessageHandler(set_limit_cmd, filters.command("setlimit", prefixes=".") & (filters.me | filters.user(ADMINS))))
        app.add_handler(MessageHandler(set_pm_msg_cmd, filters.command("setpmmsg", prefixes=".") & (filters.me | filters.user(ADMINS))))
        app.add_handler(MessageHandler(set_block_msg_cmd, filters.command("setblockmsg", prefixes=".") & (filters.me | filters.user(ADMINS))))
        app.add_handler(MessageHandler(set_img_cmd, filters.command("setpmimg", prefixes=".") & (filters.me | filters.user(ADMINS))))
        app.add_handler(MessageHandler(toggle_img_cmd, filters.command("pmimg", prefixes=".") & (filters.me | filters.user(ADMINS))))
        app.add_handler(MessageHandler(block_cmd, filters.command("block", prefixes=".") & (filters.me | filters.user(ADMINS))))

        # 2. Register Auto-Approve (Outgoing Messages)
        # If YOU send a message, that user is automatically approved
        app.add_handler(MessageHandler(
            auto_approve_outgoing, 
            filters.private & filters.outgoing & ~filters.bot & ~filters.service
        ))

        # 3. Register PM Guard (Incoming Private Messages)
        # Added ~filters.command to ensure commands don't trigger the warning
        guard_filter = (
            filters.private & 
            filters.incoming & 
            ~filters.me & 
            ~filters.bot & 
            ~filters.service & 
            ~filters.command(["pmhelp", "a", "da"], prefixes=".")
        )
        app.add_handler(MessageHandler(pm_guard, guard_filter))

        me = await app.get_me()
        logger.info(f"🛡️ PM Guard Active: {me.first_name} | ID: {me.id}")
        
        return app
        
    except Exception as e:
        logger.error(f"Failed to start client {idx}: {e}")

async def main():
    logger.info("Initializing PM Guard Clients...")
    await asyncio.gather(*[start_client(s, i) for i, s in enumerate(STRING_SESSIONS) if s])
    await asyncio.Event().wait() # Keep alive

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
