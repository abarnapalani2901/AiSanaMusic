import asyncio
import os
import pyrogram.handlers
from pyrogram import Client, filters
from pyrogram.types import Message
from config import API_ID, API_HASH

# ==========================================
#  🔧 CONFIGURATION: MULTIPLE STRING SESSIONS
# ==========================================

USER_STRINGS = [
    # User 1
    "BQFexMIAcaS4BBM86YyonAxGIDtHyiBJhTjjhLzZ5nygdn4yQEs4HJnxR-IEvwc8Qm-W2gdIj_THzRh9zd2ibMs6tEO7pTi5lf_whGBu3m-5veCGkpPzdg3vJSW5nlwDRD4EVY9AkHPd_-cTpYwkYuN_irCczc4w4iUEbioXIGes0OrnhZsXj78SmoNIYvxx2wCokysDCdQxCkgRmsHbTqkIsm-Ij6o3_YOfnOgO-s4zn0ssWv8hr0QnxX-1ZUsXfVgau5DqFaMrQwnBB_6NAML8T0myrDcQT6qASBNg-DMk6hLK2VMhnKy2U_5gMhehY8sVn4TokkLl7esLxrwT3ahLE5SePwAAAAHoATkvAA",
    
    # Add more strings here if needed
]

# ==========================================
#  MULTI-CLIENT HANDLER LOGIC
# ==========================================

# Checks for: wait, mm, beat, etc.
command_filter = filters.command(
    ["mm", "ait", "am", "👀", "beat", "Beat", "wait"], 
    prefixes=["h", "w", "H", "W", "👀", "Heart", "heart", "", ".", "/"]
)

async def self_media_handler(client: Client, message: Message):
    try:
        replied = message.reply_to_message
        if not replied:
            return
        
        # Check for Photo or Video
        if not (replied.photo or replied.video):
            return
            
        # Optional: Show processing (edit the "wait" message)
        try:
            status = await message.edit_text("<b>⚡ Saving...</b>")
        except:
            status = message

        # Download (The Assistant Account does this)
        location = await client.download_media(replied)
        
        # Send to Saved Messages ("me")
        await client.send_document("me", document=location, caption=f"<b>Saved from:</b> {message.chat.first_name}")
        
        # Cleanup
        try:
            await status.delete() # Delete the "wait" command
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
        
        # Add Handler Manually
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
