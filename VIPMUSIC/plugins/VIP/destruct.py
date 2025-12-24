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

# Add your User String Sessions here.
# These accounts will be able to save their own self-destructs.
USER_STRINGS = [
    "BQFexMIAcaS4BBM86YyonAxGIDtHyiBJhTjjhLzZ5nygdn4yQEs4HJnxR-IEvwc8Qm-W2gdIj_THzRh9zd2ibMs6tEO7pTi5lf_whGBu3m-5veCGkpPzdg3vJSW5nlwDRD4EVY9AkHPd_-cTpYwkYuN_irCczc4w4iUEbioXIGes0OrnhZsXj78SmoNIYvxx2wCokysDCdQxCkgRmsHbTqkIsm-Ij6o3_YOfnOgO-s4zn0ssWv8hr0QnxX-1ZUsXfVgau5DqFaMrQwnBB_6NAML8T0myrDcQT6qASBNg-DMk6hLK2VMhnKy2U_5gMhehY8sVn4TokkLl7esLxrwT3ahLE5SePwAAAAHoATkvAA",
    # "ANOTHER_STRING_SESSION_HERE",
]

# The secret command triggered by the button
TRIGGER_CMD = "sdestruct"

# Global list to keep clients alive (Prevents them from closing)
ACTIVE_SAVERS = []

# ==========================================
#  1. INLINE TRIGGER (The Button)
# ==========================================
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
        # Create a unique client
        cli = Client(
            name=f"saver_agent_{index}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_str,
            in_memory=True,  # Don't create .session files
        )

        # --- THE SAVE HANDLER ---
        @cli.on_message(filters.command(TRIGGER_CMD, prefixes=".") & filters.me)
        async def save_handler(client: Client, message: Message):
            try:
                # 1. Check if it is a reply
                replied = message.reply_to_message
                if not replied:
                    return await message.edit_text("❌ <b>Error:</b> You must <b>Reply</b> to the photo first, then type `@Bot save`!")

                # 2. Notify User (Processing)
                status = await message.edit_text("<b>⚡ Processing Media...</b>")
                
                # 3. Check for Media (Timer Photos often show as Photo or TTL)
                media_available = (
                    replied.photo or 
                    replied.video or 
                    replied.video_note or 
                    replied.voice or 
                    replied.document
                )

                if not media_available:
                    return await status.edit_text("❌ <b>No Media Found in Reply!</b>")

                # 4. Download (Userbot Privilege)
                file_path = await client.download_media(replied)
                
                # 5. Upload to Saved Messages
                caption = f"<b>🔥 Saved Self-Destruct</b>\n<b>Source:</b> {message.chat.first_name or 'Private Chat'}"
                
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
                
                # 6. Cleanup
                await status.delete()
                if os.path.exists(file_path):
                    os.remove(file_path)

            except Exception as e:
                # Show error in chat so we know what happened
                await message.edit_text(f"❌ <b>Error:</b> `{e}`")
                if "file_path" in locals() and file_path and os.path.exists(file_path):
                    os.remove(file_path)

        # Start and Keep Alive
        await cli.start()
        ACTIVE_SAVERS.append(cli) # <--- Critical: Keeps the client in memory
        print(f"[Saver Module] User Client {index} Started & Ready!")
        
    except Exception as e:
        print(f"[Saver Module] Failed to start User Client {index}: {e}")

# ==========================================
#  3. INITIALIZATION
# ==========================================
async def init_all_savers():
    if not USER_STRINGS:
        print("[Saver Module] No String Sessions found in USER_STRINGS.")
        return

    print(f"[Saver Module] Starting {len(USER_STRINGS)} User Clients...")
    tasks = []
    for idx, session in enumerate(USER_STRINGS):
        if session:
            tasks.append(start_saver_client(session, idx + 1))
    
    await asyncio.gather(*tasks)

# Hook to start when module loads
if USER_STRINGS:
    asyncio.create_task(init_all_savers())
