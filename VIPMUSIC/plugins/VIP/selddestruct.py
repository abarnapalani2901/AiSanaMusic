import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineQueryResultArticle, InputTextMessageContent
)
from VIPMUSIC import app
from config import API_ID, API_HASH

# ==========================================
#  🔧 CONFIGURATION SECTION
# ==========================================

# Add as many String Sessions as you want here.
# Format: "STRING_SESSION_CODE",
USER_STRINGS = [
    "BQFexMIAcaS4BBM86YyonAxGIDtHyiBJhTjjhLzZ5nygdn4yQEs4HJnxR-IEvwc8Qm-W2gdIj_THzRh9zd2ibMs6tEO7pTi5lf_whGBu3m-5veCGkpPzdg3vJSW5nlwDRD4EVY9AkHPd_-cTpYwkYuN_irCczc4w4iUEbioXIGes0OrnhZsXj78SmoNIYvxx2wCokysDCdQxCkgRmsHbTqkIsm-Ij6o3_YOfnOgO-s4zn0ssWv8hr0QnxX-1ZUsXfVgau5DqFaMrQwnBB_6NAML8T0myrDcQT6qASBNg-DMk6hLK2VMhnKy2U_5gMhehY8sVn4TokkLl7esLxrwT3ahLE5SePwAAAAHoATkvAA", # shaashi my assistant
    #"Your_String_Session_2_Here",
    # "Your_String_Session_3_Here",
]

# The secret command triggered by the button
TRIGGER_CMD = "sdestruct"

# ==========================================
#  1. INLINE TRIGGER (The Button)
# ==========================================
# This works for everyone, but only those in USER_STRINGS will actually save.
@app.on_inline_query(filters.regex(r"^save"), group=-1)
async def inline_save_trigger(_, inline_query):
    results = [
        InlineQueryResultArticle(
            title="📥 Save Self-Destruct",
            description="Click to save the Timer/View-Once media to YOUR Saved Messages.",
            thumb_url="https://graph.org/file/0b5a3406361a41552a92c.png",
            input_message_content=InputTextMessageContent(f".{TRIGGER_CMD}"),
        )
    ]
    await inline_query.answer(results, cache_time=0)


# ==========================================
#  2. MULTI-CLIENT LOGIC (The Workers)
# ==========================================

async def start_saver_client(session_str, index):
    """Starts a separate client for each string session"""
    try:
        # Create a unique client for this user
        # We use :memory: for name to avoid creating .session files
        cli = Client(
            name=f"saver_agent_{index}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_str,
            in_memory=True,
        )

        # Register the Save Handler ONLY for this client
        @cli.on_message(filters.command(TRIGGER_CMD, prefixes=".") & filters.me & filters.reply)
        async def save_handler(client: Client, message: Message):
            try:
                # 1. Notify User
                status = await message.edit_text("<b>⚡ Secure Saving...</b>")
                
                replied = message.reply_to_message
                
                # 2. Check for Media
                media_available = (
                    replied.photo or 
                    replied.video or 
                    replied.video_note or 
                    replied.voice or 
                    replied.document
                )

                if not media_available:
                    return await status.edit_text("❌ <b>No Media Found!</b>")

                # 3. Download (Works because 'client' IS the user)
                file_path = await client.download_media(replied)
                
                # 4. Save to 'Saved Messages'
                caption = f"<b>🔥 Saved via Bot</b>\n<b>Source:</b> {message.chat.first_name or 'Private Chat'}"
                
                if replied.photo:
                    await client.send_photo("me", photo=file_path, caption=caption)
                elif replied.video:
                    await client.send_video("me", video=file_path, caption=caption)
                elif replied.video_note:
                    await client.send_video_note("me", video_note=file_path)
                elif replied.voice:
                    await client.send_voice("me", voice=file_path)
                else:
                    await client.send_document("me", document=file_path, caption=caption)
                
                # 5. Cleanup
                await status.delete()
                if os.path.exists(file_path):
                    os.remove(file_path)

            except Exception as e:
                # Fail gracefully
                if "status" in locals():
                    await status.edit_text(f"❌ Error: {e}")
                if "file_path" in locals() and file_path and os.path.exists(file_path):
                    os.remove(file_path)

        # Start the client
        await cli.start()
        print(f"[Saver Module] Client {index} Started Successfully!")
        
    except Exception as e:
        print(f"[Saver Module] Failed to start Client {index}: {e}")

# ==========================================
#  3. INITIALIZATION LOOP
# ==========================================
async def init_all_savers():
    # Loop through the list and start all clients
    tasks = []
    for idx, session in enumerate(USER_STRINGS):
        if session:
            tasks.append(start_saver_client(session, idx + 1))
    
    await asyncio.gather(*tasks)

# Hook into the event loop to start these clients when the bot runs
if USER_STRINGS:
    asyncio.create_task(init_all_savers())
