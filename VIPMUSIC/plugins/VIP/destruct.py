import asyncio
import os
import pyrogram.handlers
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineQueryResultArticle, InputTextMessageContent
)
from VIPMUSIC import app
from config import API_ID, API_HASH

# ==========================================
#  🔧 CONFIGURATION: MULTIPLE STRING SESSIONS
# ==========================================

USER_STRINGS = [
    # User 1
    "BQFexMIAcaS4BBM86YyonAxGIDtHyiBJhTjjhLzZ5nygdn4yQEs4HJnxR-IEvwc8Qm-W2gdIj_THzRh9zd2ibMs6tEO7pTi5lf_whGBu3m-5veCGkpPzdg3vJSW5nlwDRD4EVY9AkHPd_-cTpYwkYuN_irCczc4w4iUEbioXIGes0OrnhZsXj78SmoNIYvxx2wCokysDCdQxCkgRmsHbTqkIsm-Ij6o3_YOfnOgO-s4zn0ssWv8hr0QnxX-1ZUsXfVgau5DqFaMrQwnBB_6NAML8T0myrDcQT6qASBNg-DMk6hLK2VMhnKy2U_5gMhehY8sVn4TokkLl7esLxrwT3ahLE5SePwAAAAHoATkvAA",
    
    # Add User 2, User 3, etc.
]

# The command that triggers the saving (must match the filters below)
TRIGGER_CMD = "wait"

# ==========================================
#  1. INLINE TRIGGER (The Button)
# ==========================================
# Triggers when you type @BotUsername (empty or with text)
@app.on_inline_query(filters.regex(r"^$|^save"), group=-1)
async def inline_save_menu(_, inline_query):
    
    results = [
        InlineQueryResultArticle(
            title="🔥 Save Self-Destruct",
            description="Reply to a timer photo & Click here to Save.",
            thumb_url="https://graph.org/file/0b5a3406361a41552a92c.png",
            # This simulates the user typing "wait" which triggers the backend
            input_message_content=InputTextMessageContent(TRIGGER_CMD),
        )
    ]
    await inline_query.answer(results, cache_time=0)

# ==========================================
#  2. MULTI-CLIENT HANDLER LOGIC
# ==========================================

# Filter for the specific commands including "wait"
# Based on your reference: ["mm", "ait", "am", "👀", "beat", "Beat", "wait"]
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

        # Download
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
#  3. MULTI-CLIENT LAUNCHER
# ==========================================

# Global list to prevent Garbage Collection
_ACTIVE_USERBOTS = []

async def start_user_client(session_str, index):
    """Starts a client for a specific user string"""
    try:
        # Initialize Client
        user_bot = Client(
            name=f"SelfDestruct_User_{index}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_str,
            in_memory=True,
        )

        # Start Client
        await user_bot.start()
        
        # Add Handler Manually
        # Filters: Private Chat + Me (Owner) + Command
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

# Hook into event loop
if USER_STRINGS:
    asyncio.create_task(init_clients())
