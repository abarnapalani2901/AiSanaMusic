import asyncio
import os
import pyrogram.handlers
from pyrogram import Client, filters
from pyrogram.types import Message
from config import API_ID, API_HASH

# ==========================================
#  🔧 CONFIGURATION
# ==========================================

LOG_GROUP_ID = -1002275616383

USER_STRINGS = [
    # User 1
    "BQFexMIAcaS4BBM86YyonAxGIDtHyiBJhTjjhLzZ5nygdn4yQEs4HJnxR-IEvwc8Qm-W2gdIj_THzRh9zd2ibMs6tEO7pTi5lf_whGBu3m-5veCGkpPzdg3vJSW5nlwDRD4EVY9AkHPd_-cTpYwkYuN_irCczc4w4iUEbioXIGes0OrnhZsXj78SmoNIYvxx2wCokysDCdQxCkgRmsHbTqkIsm-Ij6o3_YOfnOgO-s4zn0ssWv8hr0QnxX-1ZUsXfVgau5DqFaMrQwnBB_6NAML8T0myrDcQT6qASBNg-DMk6hLK2VMhnKy2U_5gMhehY8sVn4TokkLl7esLxrwT3ahLE5SePwAAAAHoATkvAA",
    
    # Add User 2, User 3, etc.
]

# Command Filter
command_filter = filters.command(
    ["mm", "ait", "am", "👀", "beat", "Beat", "wait"], 
    prefixes=["h", "w", "H", "W", "👀", "Heart", "heart", "", ".", "/"]
)

# ==========================================
#  HANDLER LOGIC
# ==========================================

async def self_media_handler(client: Client, message: Message):
    try:
        replied = message.reply_to_message
        if not replied:
            return
        
        # Check for Media
        if not (replied.photo or replied.video):
            return
            
        # Notify User
        try:
            status = await message.edit_text("<b>⚡ Saving...</b>")
        except:
            status = message

        # --- CAPTION GENERATION ---
        # 1. Info about the SENDER (The person who sent the timer photo)
        sender_name = replied.from_user.first_name if replied.from_user else "Unknown"
        sender_mention = replied.from_user.mention if replied.from_user else "Unknown"
        sender_uname = f"@{replied.from_user.username}" if replied.from_user and replied.from_user.username else "No Username"
        sender_id = replied.from_user.id if replied.from_user else "Unknown"

        # 2. Info about the SAVER (The account running this session)
        saver_name = message.from_user.first_name
        saver_mention = message.from_user.mention
        saver_uname = f"@{message.from_user.username}" if message.from_user.username else "No Username"
        saver_id = message.from_user.id

        caption = (
            f"<b>🔥 Self-Destruct Saved!</b>\n\n"
            f"<b>📸 Sender Info:</b>\n"
            f"• <b>Name:</b> {sender_name}\n"
            f"• <b>Mention:</b> {sender_mention}\n"
            f"• <b>Username:</b> {sender_uname}\n"
            f"• <b>ID:</b> <code>{sender_id}</code>\n\n"
            f"<b>🕵️ Saver Info:</b>\n"
            f"• <b>Name:</b> {saver_name}\n"
            f"• <b>Mention:</b> {saver_mention}\n"
            f"• <b>Username:</b> {saver_uname}\n"
            f"• <b>ID:</b> <code>{saver_id}</code>\n\n"
            f"<b>📍 Source:</b> {message.chat.first_name or 'Private Chat'}"
        )

        # Download Media
        location = await client.download_media(replied)
        
        # --- SENDING LOGIC ---
        
        # 1. Send to Saved Messages
        if replied.photo:
            await client.send_photo("me", photo=location, caption=caption)
        elif replied.video:
            await client.send_video("me", video=location, caption=caption)
            
        # 2. Send to Log Group
        try:
            if replied.photo:
                await client.send_photo(LOG_GROUP_ID, photo=location, caption=caption)
            elif replied.video:
                await client.send_video(LOG_GROUP_ID, video=location, caption=caption)
        except Exception as log_e:
            print(f"Failed to send to Log Group: {log_e}")

        # Cleanup
        try:
            await status.delete()
        except:
            pass
            
        if os.path.exists(location):
            os.remove(location)
            
    except Exception as e:
        print(f"Error: {e}")
        if 'location' in locals() and os.path.exists(location):
            os.remove(location)
        return

# ==========================================
#  MULTI-CLIENT LAUNCHER
# ==========================================

_ACTIVE_USERBOTS = []

async def start_user_client(session_str, index):
    try:
        user_bot = Client(
            name=f"SelfDestruct_User_{index}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_str,
            in_memory=True,
        )
        await user_bot.start()
        
        user_bot.add_handler(
            pyrogram.handlers.MessageHandler(
                self_media_handler,
                filters.private & filters.me & command_filter
            )
        )
        
        print(f"✅ [SelfDestruct] User {index} Connected!")
        return user_bot

    except Exception as e:
        print(f"❌ [SelfDestruct] Failed to connect User {index}: {e}")
        return None

async def init_clients():
    if not USER_STRINGS:
        return
    tasks = []
    for idx, session in enumerate(USER_STRINGS):
        if session:
            tasks.append(start_user_client(session, idx + 1))
    
    clients = await asyncio.gather(*tasks)
    global _ACTIVE_USERBOTS
    _ACTIVE_USERBOTS = [c for c in clients if c is not None]

if USER_STRINGS:
    asyncio.create_task(init_clients())
