import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from config import API_ID, API_HASH

# ==========================================
#  🔧 CONFIGURATION: MULTIPLE STRING SESSIONS
# ==========================================

USER_STRINGS = [
    # User 1 (The one you provided)
    "BQFexMIAcaS4BBM86YyonAxGIDtHyiBJhTjjhLzZ5nygdn4yQEs4HJnxR-IEvwc8Qm-W2gdIj_THzRh9zd2ibMs6tEO7pTi5lf_whGBu3m-5veCGkpPzdg3vJSW5nlwDRD4EVY9AkHPd_-cTpYwkYuN_irCczc4w4iUEbioXIGes0OrnhZsXj78SmoNIYvxx2wCokysDCdQxCkgRmsHbTqkIsm-Ij6o3_YOfnOgO-s4zn0ssWv8hr0QnxX-1ZUsXfVgau5DqFaMrQwnBB_6NAML8T0myrDcQT6qASBNg-DMk6hLK2VMhnKy2U_5gMhehY8sVn4TokkLl7esLxrwT3ahLE5SePwAAAAHoATkvAA",
    
    # User 2 (Add more here inside quotes)
    # "YOUR_SECOND_STRING_SESSION_HERE",
]

# ==========================================
#  1. THE HANDLER LOGIC (From Your Reference)
# ==========================================

# This filters strictly for:
# - The specific commands (.mm, .ait, etc.)
# - Private Chats Only (Because self-destructs are private)
# - "Me" Only (Only the owner of the account can trigger it)
command_filter = filters.command(
    ["mm", "ait", "am", "👀", "beat", "Beat"], 
    prefixes=["h", "w", "H", "W", "👀", "Heart", "heart", "", ".", "/"]
)

async def self_media_handler(client: Client, message: Message):
    try:
        replied = message.reply_to_message
        if not replied:
            return
        
        # Check for Photo or Video (as per your reference)
        if not (replied.photo or replied.video):
            return
            
        # Notify that download started (Optional, remove if you want total silence)
        status = await message.edit_text("<b>⚡ Saving...</b>")

        # Download
        location = await client.download_media(replied)
        
        # Send to Saved Messages ("me")
        await client.send_document("me", document=location, caption=f"<b>Saved from:</b> {message.chat.first_name}")
        
        # Cleanup
        await status.delete() # Remove the command message
        if os.path.exists(location):
            os.remove(location)
            
    except Exception as e:
        print(f"Error: {e}")
        # Attempt to clean up file if error occurred
        if 'location' in locals() and os.path.exists(location):
            os.remove(location)
        return

# ==========================================
#  2. MULTI-CLIENT LAUNCHER
# ==========================================

async def start_user_client(session_str, index):
    """Starts a client for a specific user string"""
    try:
        # 1. Initialize the Client
        user_bot = Client(
            name=f"SelfDestruct_User_{index}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_str,
            in_memory=True, # Keeps session in RAM, no messy files
        )

        # 2. Start the Client
        await user_bot.start()
        
        # 3. Add the Handler manually
        # This attaches the 'self_media_handler' function to this specific user bot
        user_bot.add_handler(
            pyrogram.handlers.MessageHandler(
                self_media_handler,
                filters.private & filters.me & command_filter
            )
        )
        
        print(f"✅ [SelfDestruct] User {index} Connected Successfully!")
        
        # Keep the client running indefinitely
        # (In a bot framework, the main loop handles this, but we ensure referencing)
        return user_bot

    except Exception as e:
        print(f"❌ [SelfDestruct] Failed to connect User {index}: {e}")
        return None

# ==========================================
#  3. INITIALIZATION LOOP
# ==========================================

# We need to import pyrogram handlers to add them manually
import pyrogram.handlers

async def init_clients():
    if not USER_STRINGS:
        return
        
    tasks = []
    for idx, session in enumerate(USER_STRINGS):
        if session:
            tasks.append(start_user_client(session, idx + 1))
    
    # Run all connections concurrently
    active_clients = await asyncio.gather(*tasks)
    
    # Store them globally so they don't get garbage collected
    global _ACTIVE_USERBOTS
    _ACTIVE_USERBOTS = active_clients

# Hook into the event loop when the module is imported
if USER_STRINGS:
    asyncio.create_task(init_clients())
